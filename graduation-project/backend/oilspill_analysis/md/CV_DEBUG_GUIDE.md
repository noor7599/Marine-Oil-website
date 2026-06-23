# CV Detection Debugging Guide

## Problem Summary

The CV model is producing masks where **100% of pixels are marked as oil**, instead of the expected 1-20%. This breaks downstream classifiers and distorts the final ensemble decision.

**Expected behavior:**
- Oil pixels: 50,000-500,000 (1-20% of image)
- Oil class in prediction map: Class 6 among 15 classes
- Confidence: 0.3-0.8 (reasonable range)

**Current behavior:**
- Oil pixels: 4,392,500 (100% of image)
- Confidence: 1.0 or 0.99+ (suspiciously high)
- All pixels marked as oil spill

---

## Debugging Output Levels

### Level 1: Quick Inference (src/cv/quick_inference.py)

Traces the MariNeXt model inference pipeline with detailed logging at 4 key points:

#### 1. **Model Loading**
```
[QUICKINF] Model checkpoint info:
  File: /path/to/trained_models/marinext_2.pth
  File size: 12.5 MB
  Checkpoint keys: ['model_state_dict', 'class_labels', ...]
  Total parameters: 2,847,502
```
**What to check:** File exists, file size > 0, checkpoint contains state_dict

#### 2. **Image Loading & Preprocessing**
```
[QUICKINF] Input image preprocessing:
  SAR image shape: (1540, 2560, 11)
  Input value range - Min: -26.5, Max: 5.2, Mean: -18.3
  After median filter - Min: -26.3, Max: 5.1
  After gaussian filter - Min: -26.2, Max: 5.0
  After normalization - Min: -2.1, Max: 3.4, Mean: 0.01
```
**What to check:** 
- Values should change from dB range (-25 to 5) to normalized range (-2 to 3)
- No NaN or extreme values
- Gaussian filter shouldn't remove all signal

#### 3. **First Patch Inference**
```
[QUICKINF] First patch inference (patch 0,0):
  Logits min/max/mean: 2.1 / 8.5 / 4.2
  Softmax confidence range: 0.02 - 0.98
  Class distribution:
    Class 0: 45,234 pixels (17%)
    Class 1: 32,123 pixels (12%)
    Class 6 (Oil): 87,923 pixels (34%)
    ...
```
**What to check:**
- Logits should vary widely (not all same value)
- Softmax should include classes 0-14
- Class 6 should be ONE OF several top classes, not all 100%

#### 4. **Output Aggregation & Mask**
```
[QUICKINF] Output aggregation:
  Total pixels predicted: 3,937,600
  Class distribution (full image):
    Class 0: 256,234 pixels (6.5%)
    Class 1: 189,234 pixels (4.8%)
    Class 6 (Oil): 3,850,234 pixels (97.8%) ← SUSPICIOUS!
  
  Raw mask unique values: {0, 1}
  Oil pixels in binary mask: 3,850,234 (97.8%)
  ⚠️  WARNING: Suspiciously high oil percentage!
```
**What to check:**
- Oil percentage should be 1-20%, not 95-100%
- All classes should appear in predictions

---

### Level 2: CV Model Wrapper (src/cv_model.py)

Converts multi-class predictions to binary mask and performs sanity checks:

```
[CV_MODEL] DEBUG - Multi-class mask analysis:
  Shape: (1540, 2560)
  Unique values: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
  Value range - Min: 0, Max: 14, Mean: 6.2
  Oil class pixels (class 6): 3,850,234

[CV_MODEL] DEBUG - Binary mask analysis:
  Shape: (1540, 2560)
  Unique values: [0, 1]
  Binary sum (oil pixels): 3,850,234
  Binary mean (oil percentage): 97.8%

[CV_MODEL] WARNING: All-or-most oil detection (97.8%) suggests possible model failure
```

**What to check:**
- Multi-class mask should contain ALL 15 classes (0-14)
- If only class 6 appears → Model output is wrong
- If binary has values other than 0,1 → Mask processing error

---

### Level 3: Run CV (src/cv/run_cv.py)

Post-processing sanity checks and confidence calculation:

```
[CV] DEBUG - Mask loading:
  Mask file: data/processed/mask_011235.npy
  Mask shape: (1540, 2560)
  Mask dtype: uint8
  Mask unique values: [0, 1]
  Mask value range - Min: 0, Max: 1

[CV] DEBUG - Mask statistics:
  Total pixels: 3,937,600
  Oil pixels: 3,850,234
  Oil percentage: 97.8%

[CV] WARNING: All pixels marked as oil! This suggests a model issue.
[CV]          Setting confidence to 0.3 (suspicious detection)
```

**What to check:**
- If oil percentage > 95%: Confidence capped at 0.3
- If oil percentage = 0%: Confidence = 0.0
- Otherwise: Confidence based on detection size

---

### Level 4: Decision Layer (src/decision_layer.py)

Ensemble decision-making with warnings for suspicious inputs:

```
[DECISION] Ensemble inputs: CV=0.3, PG=0.7, RF=0.78, NLP=0.75
[DECISION] Decision weights - CV: 0.35, PG: 0.30, RF: 0.15, NLP: 0.20

[DECISION] WARNING: CV confidence is 0.3 (suspiciously low!)
[DECISION] This may indicate the CV model produced an all-oil or all-non-oil mask

[DECISION] Weighted calculation: (0.3×0.35) + (0.7×0.30) + (0.78×0.15) + (0.75×0.20) = 0.633
[DECISION] Final Decision: Oil-like
[DECISION] Confidence: 63.3%
```

**What to check:**
- If CV confidence = 1.0: Critical failure
- If CV confidence = 0.0: No detection
- If CV confidence = 0.3: Suspicious input (all-oil mask)

---

## How to Run Debugging

### Option 1: Run CV Pipeline Only

```bash
cd d:\L4 S1\Graduation Project in AI (I)\Integration layer\oilspill_analysis

python src/cv/run_cv.py --input data/raw/2023-03-18-*.tiff --output data/processed/ 2>&1 | tee cv_debug.log
```

This will produce a detailed log file showing all 4 levels of debugging above.

### Option 2: Run Full Pipeline with Debug Output

```bash
python src/main/main_pipeline.py --config config.json 2>&1 | tee pipeline_debug.log
```

This will capture all logging from CV, RF, NLP, and the ensemble decision layer.

### Option 3: Check Specific Mask File

```python
import numpy as np
from PIL import Image

mask_path = "data/processed/mask_file.npy"
mask = np.load(mask_path)

print(f"Shape: {mask.shape}")
print(f"Unique values: {np.unique(mask)}")
print(f"Oil pixels: {np.sum(mask)} / {mask.size}")
print(f"Oil percentage: {100 * np.sum(mask) / mask.size:.2f}%")
```

---

## Root Cause Diagnostic Tree

### Symptom: 100% of pixels are oil

**Check 1: Is the multi-class prediction correct?**
```python
# In cv_model DEBUG output, look for:
# "Unique values: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]"

If only [6] appears:
  → CAUSE: Model predicts ONLY class 6 (Oil Spill)
  → FIX: Check model weights, input preprocessing
  
If [0-14] appear:
  → Continue to Check 2
```

**Check 2: Is class 6 abnormally dominant?**
```python
# In cv_model DEBUG output:
# "Oil class pixels (class 6): 3,850,234 (97.8%)"

If >95% of pixels are class 6:
  → CAUSE: Model logits favor class 6
  → FIX: Check sigmoid/softmax temperature, or retrain model
  
If class 6 is <50% of predictions:
  → Continue to Check 3
```

**Check 3: Is the binary threshold wrong?**
```python
# Check line: (preds == _OIL_CLASS_INDEX)
# _OIL_CLASS_INDEX = 6

If you see "Oil class pixels: 0":
  → CAUSE: Oil class is not 6 in this model
  → FIX: Check labels_0based.index('Oil Spill') in quick_inference.py
  
Otherwise:
  → Continue to Check 4
```

**Check 4: Is preprocessing destroying the image?**
```python
# In quick_inference DEBUG output:
# "After normalization - Min: -2.1, Max: 3.4"

If Min and Max are too close (range < 0.1):
  → CAUSE: Preprocessing made all values uniform
  → FIX: Check normalization: Normalize(bands_mean, bands_std)
         Check if bands_mean/std are correct
  
If range is reasonable (-2 to 3):
  → Continue to Check 5
```

**Check 5: Is the model checkpoint corrupted?**
```python
# In quick_inference DEBUG output:
# "Checkpoint keys: ['model_state_dict', 'class_labels', ...]"

If 'model_state_dict' is missing:
  → CAUSE: Wrong checkpoint format
  → FIX: Check trained_models/marinext_2.pth file
  
If file size is very small (<100KB):
  → CAUSE: Corrupted or empty checkpoint
  → FIX: Retrain or restore from backup
```

---

## What Each Section Should Show

### Healthy Preprocessing
```
Input value range - Min: -26.5, Max: 5.2         ← dB values
After normalization - Min: -2.1, Max: 3.4       ← normalized
```
✓ Values changed from dB range to normalized range

### Healthy First Patch
```
Class distribution:
    Class 0: 45,234 pixels (17%)
    Class 1: 32,123 pixels (12%)
    Class 6 (Oil): 18,923 pixels (7%)            ← One of many
    Class 7: 25,345 pixels (9%)
    ...
```
✓ Multiple classes present, no single class dominates

### Healthy Final Mask
```
Oil pixels: 450,000 (11.4%)                      ← In expected range
Oil percentage: 11.4%                             ← Reasonable
```
✓ Percentage between 1-20%

### Unhealthy Symptoms
```
⚠️  "All pixels marked as oil!" → Model failure
⚠️  "Oil percentage: 100%" → Something very wrong
⚠️  "Unique values: [6]" only → All predictions same
⚠️  "Confidence: 1.0" → Not realistic
```

---

## Next Steps

1. **Run the CV pipeline** with debugging enabled: `python src/cv/run_cv.py ...`
2. **Capture the debug output** to a log file: `... 2>&1 | tee cv_debug.log`
3. **Check each level** against the diagnostic tree above
4. **Report the output** for the exact section where things go wrong
5. **Apply the corresponding fix** based on the root cause

---

## Key Files Modified for Debugging

| File | Changes | Purpose |
|------|---------|---------|
| `src/cv/quick_inference.py` | Added 4 logging sections | Trace model inference |
| `src/cv_model.py` | Added multi-class & binary debug | Verify mask conversion |
| `src/cv/run_cv.py` | Added statistics logging | Check final mask quality |
| `src/decision_layer.py` | Added suspicion warnings | Catch model failures early |

---

## Confidence Scoring Rules (Updated)

The ensemble now uses defensive confidence calculation:

```python
# In run_cv.py:
if oil_pixels == 0:
    confidence = 0.0                 # No detection
elif oil_pixels == total_pixels:
    confidence = 0.3                 # All oil (suspicious!)
elif oil_percentage > 30:
    confidence = 0.6                 # Large detection (likely FP)
elif oil_percentage < 0.1:
    confidence = 0.5                 # Tiny detection
else:
    confidence = 0.75                # Normal detection (1-30%)
```

This prevents unrealistic 1.0 confidences from suspicious all-oil masks.

---

## Expected Output After Fix

Once the CV model is working correctly, you should see:

```
✓ Oil pixels: 250,000-350,000 (6-9%)
✓ Confidence: 0.65-0.75 (reasonable)
✓ Class distribution: Multiple classes present (Class 0, 1, 2, 6, 7, etc.)
✓ Preprocessing: Normalized values in -2 to 3 range
✓ Final report: "Oil area: 12.5 km²" (realistic)
```

And the ensemble decision will use proper CV input:
```
[DECISION] Ensemble inputs: CV=0.72, PG=0.70, RF=0.78, NLP=0.75
[DECISION] Weighted calculation: (0.72×0.35) + (0.70×0.30) + (0.78×0.15) + (0.75×0.20) = 0.728
[DECISION] Final Confidence: 72.8% ✓
```
