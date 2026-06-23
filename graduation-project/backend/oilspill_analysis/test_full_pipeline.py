#!/usr/bin/env python3
"""
Comprehensive test: Run full pipeline and verify CV results
"""

import subprocess
import json
from pathlib import Path

def run_pipeline_test():
    workspace_root = Path("d:\\L4 S1\\Graduation Project in AI (I)\\Integration layer\\oilspill_analysis")
    image = workspace_root / "data" / "raw" / "2023-03-18-00_00_2023-03-18-23_59_Sentinel-1_IW_VV+VH_VV_-_decibel_gamma0(zoomed).tiff"
    csv = workspace_root / "data" / "raw" / "incidents_balanced_cleaned.csv"
    
    print("=" * 80)
    print("RUNNING FULL PIPELINE TEST")
    print("=" * 80)
    print(f"Image: {image.name}")
    print(f"CSV: {csv.name}\n")
    
    # Run the pipeline
    cmd = f'conda run -n oilspill3 python "{workspace_root}/src/main/main_pipeline.py" --image "{image}" --csv "{csv}"'
    
    print(f"Command: {cmd}\n")
    print("Running... (this may take a few minutes)\n")
    
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=600  # 10 minutes
        )
        
        print("PIPELINE OUTPUT:")
        print("-" * 80)
        if result.stdout:
            print(result.stdout)
        print("-" * 80)
        
        if result.returncode != 0 and result.stderr:
            print("\nPIPELINE ERRORS:")
            print("-" * 80)
            print(result.stderr)
            print("-" * 80)
        
        print(f"\nReturn code: {result.returncode}")
        
        # Check results
        cv_results = workspace_root / "temp" / "output" / "cv_results.json"
        if cv_results.exists():
            with open(cv_results) as f:
                cv_data = json.load(f)
            
            print("\n" + "=" * 80)
            print("CV RESULTS VERIFICATION")
            print("=" * 80)
            print(f"Status: {cv_data.get('status')}")
            print(f"Oil pixels: {cv_data.get('oil_pixels')}")
            print(f"Total pixels: {cv_data.get('total_pixels')}")
            print(f"Oil percentage: {100 * cv_data.get('oil_pixels', 0) / cv_data.get('total_pixels', 1):.2f}%")
            print(f"Confidence: {cv_data.get('confidence')}")
            
            mask_path = Path(cv_data.get('mask_path', ''))
            print(f"\nMask file: {mask_path.name}")
            print(f"  Exists: {mask_path.exists()}")
            print(f"  Is NPY: {mask_path.suffix == '.npy'}")
            
            if mask_path.exists() and mask_path.suffix == '.npy':
                try:
                    import numpy as np
                    mask = np.load(mask_path)
                    print(f"  Shape: {mask.shape}")
                    print(f"  Dtype: {mask.dtype}")
                    print(f"  Unique values: {np.unique(mask).tolist()}")
                    print(f"  ✓ Successfully loaded as NPY")
                except Exception as e:
                    print(f"  ✗ Error loading NPY: {e}")
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("ERROR: Pipeline timed out (>10 minutes)")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == "__main__":
    success = run_pipeline_test()
    exit(0 if success else 1)
