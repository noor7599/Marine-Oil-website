"""
CV Module Runner - Direct wrapper around quick_inference.py
Runs in mados environment
"""

import sys
import os
import json
import subprocess
import uuid
from pathlib import Path


def run_cv_pipeline(input_image_path: str, output_dir: str):
    """
    Run quick_inference.py directly (assumes user is already in conda mados env)
    
    Args:
        input_image_path: Path to SAR TIFF image (absolute or relative)
        output_dir: Directory to save results
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    try:
        # Get the original mados directory location
        # Original location: D:\L4 S1\Graduation Project in AI (I)\cv\mados
        original_mados = Path("/Users/mac/Desktop/mados")
        
        if not original_mados.exists():
            raise RuntimeError(f"Original mados directory not found at: {original_mados}")
        
        quick_inf_script = original_mados / 'quick_inference.py'
        model_path = original_mados / 'marinext' / 'trained_models' / 'marinext_2.pth'
        
        if not quick_inf_script.exists():
            raise RuntimeError(f"quick_inference.py not found at: {quick_inf_script}")
        
        print(f"[CV] Loading image: {input_image_path}")
        print(f"[CV] Using model: {model_path}")
        print(f"[CV] Using mados from: {original_mados}")
        print(f"[CV] Assuming user is in conda mados environment")
        
        # Convert relative input path to absolute
        original_cwd = Path.cwd()
        if not Path(input_image_path).is_absolute():
            input_image_path = str(original_cwd / input_image_path)
        
        # Convert output to absolute
        output_path_abs = str(original_cwd / output_path)
        
        # Add mados to path and change to mados directory
        original_dir = os.getcwd()
        os.chdir(str(original_mados))
        sys.path.insert(0, str(original_mados))
        
        try:
            # Import and run quick_inference directly
            from quick_inference import run_inference
            
            print(f"[CV] Running quick_inference...")
            result = run_inference(
                image_path=input_image_path,
                model_path=str(model_path),
                output_dir=output_path_abs
            )
            
            # Restore original directory
            os.chdir(original_dir)
            
            # Handle new return format: (mask_path, viz_path, confidences_dict)
            if isinstance(result, tuple) and len(result) == 3:
                mask_path, viz_path, confidences_dict = result
                overall_confidence = confidences_dict.get('overall_confidence', 0.0)
                class_confidences = confidences_dict.get('class_confidences', {})
                oil_class_confidence = float(class_confidences.get('6', 0.0))  # Oil Spill is class 6
                use_softmax = True
            else:
                # Fallback for older version
                mask_path, viz_path = result
                overall_confidence = 0.0
                oil_class_confidence = 0.0
                use_softmax = False
            
        except Exception as e:
            os.chdir(original_dir)
            raise e
        
        if mask_path is None or viz_path is None:
            raise RuntimeError("Quick inference returned None. Check error messages above.")
        
        # quick_inference returns (mask_path, viz_path) where:
        # - mask_path: multi-class TIFF with class predictions (0-14)
        # - viz_path: visualization PNG
        # We need to read the multi-class mask and extract oil class (6)
        
        import numpy as np
        import rasterio
        
        # Read the multi-class mask from TIFF
        with rasterio.open(mask_path) as src:
            multi_class_predictions = src.read(1).astype(np.uint8)
        
        print(f"[CV] DEBUG - Multi-class mask analysis:")
        print(f"  File: {mask_path}")
        print(f"  Shape: {multi_class_predictions.shape}")
        print(f"  Unique classes: {np.unique(multi_class_predictions)}")
        
        # Extract oil class (class 6 in labels_0based)
        oil_idx = 6  # Oil Spill is at index 6 in labels_0based
        oil_binary = (multi_class_predictions == oil_idx).astype(np.uint8)
        
        total_pixels = oil_binary.size
        oil_pixels = int(np.sum(oil_binary))
        oil_percentage = 100.0 * oil_pixels / total_pixels
        
        print(f"[CV] DEBUG - Oil detection statistics:")
        print(f"  Total pixels: {total_pixels:,}")
        print(f"  Oil pixels (class {oil_idx}): {oil_pixels:,}")
        print(f"  Oil percentage: {oil_percentage:.2f}%")
        
        # Use softmax confidence from model if available, else use heuristics
        if use_softmax and oil_class_confidence > 0:
            # Use the actual softmax probability for oil class confidence
            confidence = oil_class_confidence
            print(f"[CV] Using softmax confidence from model:")
            print(f"  Oil class softmax confidence: {oil_class_confidence:.4f}")
            print(f"  Overall average confidence: {overall_confidence:.4f}")
        else:
            # Fallback to heuristic-based calculation if softmax not available
            print(f"[CV] Using heuristic-based confidence (softmax unavailable)")
            if oil_pixels == 0:
                confidence = 0.0
                print(f"  No oil detected")
            elif oil_percentage > 95:
                confidence = 0.3
                print(f"  {oil_percentage:.1f}% of image marked as oil (suspicious)")
            elif oil_percentage < 0.1:
                confidence = 0.5
            elif oil_percentage > 30:
                confidence = 0.6  # Large detections are more likely false positives
            else:
                confidence = 0.75  # Normal detection (1-30%)
        
        detected = bool(oil_pixels > 0)
        
        # Save binary oil mask as NPY (required by extract_oil_pixels in cv_model.py)
        unique_id = str(uuid.uuid4())[:8]
        binary_mask_path = output_path / f"{Path(input_image_path).stem}_{unique_id}_oil_binary.npy"
        np.save(str(binary_mask_path), oil_binary)
        
        # Preprocessed mask PNG for PG classifier: use quick_inference's denoised PNG if present
        oil_binary_png_path = Path(mask_path).parent / (Path(mask_path).stem.replace('_mask', '') + '_oil_binary.png')
        if not oil_binary_png_path.exists():
            oil_binary_png_path = output_path / f"{Path(input_image_path).stem}_{unique_id}_oil_binary.png"
            try:
                from PIL import Image
                Image.fromarray((oil_binary * 255).astype(np.uint8)).save(str(oil_binary_png_path))
            except Exception:
                oil_binary_png_path = None
        oil_binary_png_str = str(oil_binary_png_path) if (oil_binary_png_path and Path(oil_binary_png_path).exists()) else None
        
        # Create result JSON with confidence calculation documentation
        confidence_method = "softmax_per_class_average" if (use_softmax and oil_class_confidence > 0) else "heuristic_based"
        
        result_data = {
            "status": "success",
            "detected": detected,
            "oil_pixels": oil_pixels,
            "total_pixels": total_pixels,
            "oil_percentage": round(100.0 * oil_pixels / total_pixels, 2),
            "confidence": round(confidence, 4),
            "confidence_calculation": {
                "method": confidence_method,
                "source": "MariNeXt model softmax probabilities" if (use_softmax and oil_class_confidence > 0) else "Heuristic based on detection statistics",
                "formula": "Weighted average of P(oil_class_6 | pixel) for pixels predicted as oil" if (use_softmax and oil_class_confidence > 0) else "Fixed rules based on oil_percentage detection",
                "interpretation": f"Model's average certainty (0-1) that detected oil pixels are actually oil spill: {confidence:.1%}"
            },
            "mask_path": str(binary_mask_path),  # Return NPY path (binary mask), not TIFF
            "multiclass_mask_path": str(mask_path),  # Store TIFF path for reference
            "oil_binary_png_path": oil_binary_png_str,  # Preprocessed mask for PG (temp/output *oil_binary.png)
            "visualization_path": str(viz_path),
            "model": "marinext"
        }
        
        # Save JSON
        json_output = output_path / "cv_results.json"
        with open(json_output, 'w') as f:
            json.dump(result_data, f, indent=2)
        
        print(f"[CV] ✓ Success: {oil_pixels} oil pixels detected ({confidence*100:.2f}%)")
        print(f"[CV] ✓ Binary mask (NPY) saved: {binary_mask_path}")
        print(f"[CV] ✓ Multi-class mask (TIFF) saved: {mask_path}")
        print(f"[CV] ✓ Results saved: {json_output}")
        
        return 0
        
    except Exception as e:
        import traceback
        try:
            os.chdir(original_cwd)
        except:
            pass
        error_result = {
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        json_output = Path(output_dir) / "cv_results.json"
        json_output.parent.mkdir(parents=True, exist_ok=True)
        with open(json_output, 'w') as f:
            json.dump(error_result, f, indent=2)
        
        print(f"[CV] ✗ Error: {str(e)}", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="CV Module Runner")
    parser.add_argument("--input", required=True, help="Input SAR image path")
    parser.add_argument("--output", required=True, help="Output directory for results")
    
    args = parser.parse_args()
    
    exit_code = run_cv_pipeline(args.input, args.output)
    sys.exit(exit_code)