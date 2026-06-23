#!/usr/bin/env python3
"""
Debug script to analyze the latest CV mask outputs and compare
mados vs oilspill3 results
"""

import json
import subprocess
from pathlib import Path
import sys
import numpy as np

def analyze_mask(mask_path):
    """Analyze a TIFF mask file."""
    try:
        import rasterio
    except ImportError:
        print("ERROR: rasterio not installed")
        return None
    
    try:
        with rasterio.open(mask_path) as src:
            mask_data = src.read(1).astype(np.uint8)
        
        unique_vals = np.unique(mask_data)
        oil_pixels = np.sum(mask_data == 6)  # Oil class
        total_pixels = mask_data.size
        oil_pct = 100.0 * oil_pixels / total_pixels
        
        return {
            "shape": mask_data.shape,
            "unique_classes": list(unique_vals),
            "oil_pixels": int(oil_pixels),
            "oil_percentage": round(oil_pct, 2),
            "total_pixels": total_pixels,
            "dtype": str(mask_data.dtype)
        }
    except Exception as e:
        return {"error": str(e)}

def main():
    workspace_root = Path("d:\\L4 S1\\Graduation Project in AI (I)\\Integration layer\\oilspill_analysis")
    
    # Check CV results from subprocess
    cv_results_path = workspace_root / "temp" / "output" / "cv_results.json"
    
    print("=" * 80)
    print("CV OUTPUT ANALYSIS - OILSPILL3 ENVIRONMENT")
    print("=" * 80)
    
    if cv_results_path.exists():
        with open(cv_results_path) as f:
            cv_data = json.load(f)
        
        print("\n[CV Results JSON]")
        print(f"  Status: {cv_data.get('status')}")
        print(f"  Detected: {cv_data.get('detected')}")
        print(f"  Oil Pixels: {cv_data.get('oil_pixels')}")
        print(f"  Total Pixels: {cv_data.get('total_pixels')}")
        print(f"  Oil Percentage: {100 * cv_data.get('oil_pixels', 0) / cv_data.get('total_pixels', 1):.2f}%")
        print(f"  Confidence: {cv_data.get('confidence')}")
        print(f"  Model: {cv_data.get('model')}")
        
        # Analyze the actual mask file
        mask_path = cv_data.get('mask_path')
        if mask_path and Path(mask_path).exists():
            print(f"\n[Analyzing Mask: {Path(mask_path).name}]")
            analysis = analyze_mask(mask_path)
            if "error" in analysis:
                print(f"  ERROR: {analysis['error']}")
            else:
                print(f"  Unique Classes: {analysis['unique_classes']}")
                print(f"  Oil Class (6) Pixels: {analysis['oil_pixels']}")
                print(f"  Oil Percentage: {analysis['oil_percentage']}%")
                print(f"  Shape: {analysis['shape']}")
                print(f"  dtype: {analysis['dtype']}")
        else:
            print(f"  ERROR: Mask file not found at {mask_path}")
    else:
        print(f"  ERROR: cv_results.json not found at {cv_results_path}")
    
    # Now test running the CV in the mados environment directly for comparison
    print("\n" + "=" * 80)
    print("TESTING DIRECT RUN IN MADOS ENVIRONMENT")
    print("=" * 80)
    
    test_image = workspace_root / "data" / "raw" / "2023-03-18-00_00_2023-03-18-23_59_Sentinel-1_IW_VV+VH_VV_-_decibel_gamma0(zoomed).tiff"
    test_output = workspace_root / "temp" / "test_output"
    test_output.mkdir(parents=True, exist_ok=True)
    
    if test_image.exists():
        print(f"\nTest image exists: {test_image}")
        print(f"Running CV in mados environment...")
        
        # Run in mados environment
        cmd = f'conda run -n mados python "{workspace_root}/src/cv/run_cv.py" --input "{test_image}" --output "{test_output}" 2>&1'
        
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
            
            print(f"\nReturn code: {result.returncode}")
            
            # Check if results were created
            test_results = test_output / "cv_results.json"
            if test_results.exists():
                with open(test_results) as f:
                    test_cv_data = json.load(f)
                
                print("\n[Mados Direct Run Results]")
                print(f"  Status: {test_cv_data.get('status')}")
                print(f"  Oil Pixels: {test_cv_data.get('oil_pixels')}")
                print(f"  Confidence: {test_cv_data.get('confidence')}")
                
                # Analyze mask
                mask_path = test_cv_data.get('mask_path')
                if mask_path and Path(mask_path).exists():
                    print(f"\n[Analyzing Direct Run Mask]")
                    analysis = analyze_mask(mask_path)
                    if "error" not in analysis:
                        print(f"  Unique Classes: {analysis['unique_classes']}")
                        print(f"  Oil Class (6) Pixels: {analysis['oil_pixels']}")
                        print(f"  Oil Percentage: {analysis['oil_percentage']}%")
            else:
                print(f"\nERROR: No cv_results.json in {test_output}")
                print(f"stdout:\n{result.stdout}")
                print(f"stderr:\n{result.stderr}")
        
        except subprocess.TimeoutExpired:
            print("ERROR: Command timed out")
        except Exception as e:
            print(f"ERROR: {e}")
    else:
        print(f"ERROR: Test image not found at {test_image}")

if __name__ == "__main__":
    main()
