#!/usr/bin/env python3
"""
Test the CV pipeline with the fixed NPY output
"""

import subprocess
import json
from pathlib import Path

workspace_root = Path("d:\\L4 S1\\Graduation Project in AI (I)\\Integration layer\\oilspill_analysis")
test_image = workspace_root / "data" / "raw" / "2023-03-18-00_00_2023-03-18-23_59_Sentinel-1_IW_VV+VH_VV_-_decibel_gamma0(zoomed).tiff"
test_output = workspace_root / "temp" / "test_npy_output"
test_output.mkdir(parents=True, exist_ok=True)

print("Testing CV pipeline with NPY output fix...")
print(f"Input: {test_image}")
print(f"Output dir: {test_output}\n")

# Run CV in mados
cmd = f'conda run -n mados python "{workspace_root}/src/cv/run_cv.py" --input "{test_image}" --output "{test_output}"'

try:
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
    
    print(f"Return code: {result.returncode}")
    if result.stdout:
        print(f"\nStdout (last 30 lines):")
        lines = result.stdout.strip().split('\n')
        for line in lines[-30:]:
            print(f"  {line}")
    
    if result.stderr:
        print(f"\nStderr (last 10 lines):")
        lines = result.stderr.strip().split('\n')
        for line in lines[-10:]:
            print(f"  {line}")
    
    # Check if NPY file was created
    cv_results = test_output / "cv_results.json"
    if cv_results.exists():
        with open(cv_results) as f:
            data = json.load(f)
        
        print(f"\n[CV Results JSON]")
        print(f"  Status: {data.get('status')}")
        print(f"  Oil pixels: {data.get('oil_pixels')}")
        print(f"  Confidence: {data.get('confidence')}")
        
        mask_path = Path(data.get('mask_path', ''))
        if mask_path.exists():
            print(f"  ✓ Mask file exists: {mask_path.name}")
            print(f"  ✓ Mask is NPY file: {mask_path.suffix == '.npy'}")
        else:
            print(f"  ✗ Mask file NOT found: {mask_path}")
        
        multiclass_path = Path(data.get('multiclass_mask_path', ''))
        if multiclass_path.exists():
            print(f"  ✓ Multi-class mask exists: {multiclass_path.name}")
        else:
            print(f"  ✗ Multi-class mask NOT found: {multiclass_path}")
    else:
        print(f"\n✗ No cv_results.json produced!")
        print(f"Files in {test_output}:")
        for f in test_output.glob("*"):
            print(f"  - {f.name}")

except subprocess.TimeoutExpired:
    print("ERROR: Command timed out")
except Exception as e:
    print(f"ERROR: {e}")
