# CV Debug & Fix Report

## Problem Identified

The CV pipeline was producing results with the **wrong format**, causing downstream processing in oilspill3 to fail.

### Root Cause

**Issue 1: File Format Mismatch**
- `run_cv.py` (mados environment) was returning the **multi-class TIFF mask path** in cv_results.json
- `extract_oil_pixels()` function in cv_model.py expects a **binary NPY mask file**
- When the pipeline tried to load the mask, it attempted: `np.load(tiff_path)` → **FAILURE**

```
BEFORE (Broken):
- run_cv.py outputs: mask_path = "...zoomed_mask.tiff" (multi-class)
- extract_oil_pixels() tries: np.load("...mask.tiff") → ERROR
- Pipeline fails or produces wrong results

AFTER (Fixed):  
- run_cv.py outputs: mask_path = "...oil_binary.npy" (binary)
- extract_oil_pixels() calls: np.load("...oil_binary.npy") → SUCCESS
- Pipeline works correctly
```

### Issue 2: Windows Path Handling in Subprocess

The `cv_subprocess.py` was using shell=True with a list, which could cause issues with spaces in paths on Windows.

## Fixes Applied

### Fix 1: [src/cv/run_cv.py](src/cv/run_cv.py)

**Changed:** Modified run_cv.py to save the binary oil mask as NPY and return that path

```python
# OLD CODE:
result_data = {
    "mask_path": str(mask_path),  # This was the multi-class TIFF
    ...
}

# NEW CODE:
# Save binary oil mask as NPY (required by extract_oil_pixels in cv_model.py)
unique_id = str(uuid.uuid4())[:8]
binary_mask_path = output_path / f"{Path(input_image_path).stem}_{unique_id}_oil_binary.npy"
np.save(str(binary_mask_path), oil_binary)

result_data = {
    "mask_path": str(binary_mask_path),  # Now returns the binary NPY path
    "multiclass_mask_path": str(mask_path),  # Store TIFF path for reference
    ...
}
```

**Result:** The JSON result now contains:
- `mask_path`: Binary oil mask as NPY file (for extract_oil_pixels)
- `multiclass_mask_path`: Full multi-class TIFF (for reference/debugging)

### Fix 2: [src/main/cv_subprocess.py](src/main/cv_subprocess.py)

**Changed:** Improved Windows path handling when calling conda subprocess

```python
# OLD CODE:
cmd = ["conda", "run", "-n", self.conda_env, "python", ...]
subprocess.run(cmd, shell=True)  # Mixing list with shell=True is problematic

# NEW CODE:
# Properly construct command string on Windows to handle spaces in paths
if sys.platform == "win32":
    cmd = f'conda run -n {self.conda_env} python "{cv_script_abs}" --input "{image_path_abs}" --output "{output_dir_abs}"'
else:
    cmd = ["conda", "run", "-n", self.conda_env, ...]

subprocess.run(cmd, shell=isinstance(cmd, str))  # shell=True only when cmd is string
```

**Result:** More robust subprocess calls on Windows with proper path quoting

## Verification

To verify the fixes work:

1. **Quick Test - CV Only:**
```bash
cd "d:\L4 S1\Graduation Project in AI (I)\Integration layer\oilspill_analysis"
python test_cv_npy.py
```
Expected output:
```
✓ Mask file exists: 2023-03-18-..._oil_binary.npy
✓ Mask is NPY file: True
```

2. **Full Test - Complete Pipeline:**
```bash
python test_full_pipeline.py
```
This will run the complete pipeline and verify:
- CV produces NPY mask
- extract_oil_pixels can load the mask
- All downstream processing works

## Expected Behavior After Fix

When running main_pipeline.py in oilspill3:
- CV subprocess calls mados environment correctly
- Produces binary NPY mask with ~98,726 oil pixels (2.25%)
- extract_oil_pixels loads it successfully
- Pipeline processes all steps without errors
- Final results are consistent between mados and oilspill3

## Files Modified

1. [src/cv/run_cv.py](src/cv/run_cv.py)
   - Added UUID import
   - Modified to save binary oil mask as NPY
   - Updated JSON result format

2. [src/main/cv_subprocess.py](src/main/cv_subprocess.py)
   - Improved Windows path handling
   - Better command construction for subprocess calls

## Testing the Fix

Run the exact same image through both environments:
```bash
# In oilspill3:
python src/main/main_pipeline.py --image data/raw/2023-03-18-*.tiff --csv data/raw/incidents_balanced_cleaned.csv

# Compare results in temp/output/cv_results.json
# Should show: oil_pixels: 98726, confidence: 0.75
```

If both produce identical results (same oil_pixels count and confidence), the fix is working!
