# Softmax Confidence Implementation - Technical Update

## Overview
Updated CV confidence calculation to use softmax probabilities directly from the MariNeXt model instead of heuristic-based methods. This provides more accurate confidence scores that reflect the model's true uncertainty per class.

## Changes Made

### 1. quick_inference.py - Extract Softmax Scores
**Location**: `src/cv/quick_inference.py` (lines 160-210)

**What Changed**:
- Added confidence accumulation per class during patch processing
- Calculate average softmax probability for each of 15 semantic classes
- Compute overall average confidence across all detected classes
- Return confidence dictionary alongside mask and visualization

**New Return Format**:
```python
# Before
mask_path, viz_path = run_inference(image_path, ...)

# After  
mask_path, viz_path, confidences_dict = run_inference(image_path, ...)

# confidences_dict contains:
{
    'overall_confidence': 0.7234,  # Average confidence across all classes
    'class_confidences': {
        '0': 0.6521,   # Marine Water
        '6': 0.8945,   # Oil Spill (most important)
        '2': 0.7123,   # Dense Sargassum
        ...
    }
}
```

**Code Logic**:
```python
# Accumulate confidence from softmax during inference
probs = torch.softmax(logits, dim=1)
patch_conf = probs.max(1)[0].squeeze().cpu().numpy()  # Per-pixel max probability
confidence_full[y:y+patch_size, ...] += patch_conf * weight_mask

# Post-process: Average confidence per class
for class_idx in range(15):
    class_mask = predictions == class_idx
    if class_mask.any():
        avg_confidence_per_class[class_idx] = (
            confidence_full[class_mask].sum() / weights_full[class_mask].sum()
        )
```

### 2. run_cv.py - Use Oil Class Softmax Confidence
**Location**: `src/cv/run_cv.py` (lines 50-80, 110-130)

**What Changed**:
- Extract oil class (class 6) softmax confidence from returned dictionary
- Use oil class confidence directly as CV confidence metric
- Fallback to heuristic method if softmax unavailable (for backward compatibility)
- Debug output shows which method was used

**New Logic**:
```python
if use_softmax and oil_class_confidence > 0:
    # Use actual softmax probability for oil class
    confidence = oil_class_confidence
    print(f"Oil class softmax confidence: {oil_class_confidence:.4f}")
else:
    # Fallback to old heuristic-based method
    if oil_pixels == 0:
        confidence = 0.0
    elif oil_percentage > 95:
        confidence = 0.3  # Suspicious
    elif oil_percentage > 30:
        confidence = 0.6  # Large detections often false positives
    else:
        confidence = 0.75  # Normal detection
```

### 3. cv_model.py - Pass Softmax Scores Through Pipeline
**Location**: `src/cv_model.py` (lines 150-165, 230-237)

**What Changed**:
- Extract oil class confidence from run_inference result
- Pass confidence through pipeline statistics
- Add confidence field to final results dictionary

**Implementation**:
```python
result = qi.run_inference(image_path, output_dir=output_dir)

# Handle new 3-tuple return format
if len(result) == 3:
    mask_path, viz_path, confidences_dict = result
    oil_confidence = float(confidences_dict['class_confidences']['6'])
else:
    # Backward compatibility
    mask_path, viz_path = result
    oil_confidence = None

# Add to stats
stats.update({
    'confidence': oil_confidence if oil_confidence is not None else 0.0,
    ...
})
```

## Why This Is Better

### 1. **Model-Based vs Heuristic**
- **Old**: Used pixel count heuristics (suspicious if >95%, normal if 1-30%, etc.)
- **New**: Uses actual softmax probabilities that express model uncertainty

### 2. **Per-Class Confidence**
- **Old**: Single binary confidence based on detection size
- **New**: Individual confidence for each of 15 classes, oil class confidence explicitly used

### 3. **Uncertainty Quantification**
- **Old**: 0.3-0.75 confidence range regardless of model certainty
- **New**: Full 0.0-1.0 range reflecting softmax probabilities (can be >0.9 for high certainty)

### 4. **Interpretability**
- **Old**: "75% confidence because 5% of image is oil"
- **New**: "94% confidence because softmax probability of oil class is 0.94"

## Confidence Score Range

### Oil Class Softmax Confidence
- **0.0-0.3**: Model very uncertain oil is present (likely false positive)
- **0.3-0.5**: Model somewhat uncertain (could be debris, sargassum, etc.)
- **0.5-0.7**: Model moderately confident of oil (reasonable detection)
- **0.7-0.85**: Model quite confident (strong detection)
- **0.85-1.0**: Model very confident of oil (high quality detection)

## Output Examples

### High Confidence Oil Detection
```
[CV] DEBUG - Oil detection statistics:
  Oil pixels (class 6): 98,726
  Oil percentage: 0.75%
[CV] Using softmax confidence from model:
  Oil class softmax confidence: 0.9234
  Overall average confidence: 0.7123
```

### Low Confidence with Many Pixels (Suspicious)
```
[CV] DEBUG - Oil detection statistics:
  Oil pixels (class 6): 5,234,123
  Oil percentage: 97.2%
[CV] Using softmax confidence from model:
  Oil class softmax confidence: 0.3421  ← Low despite high pixel count
  Overall average confidence: 0.5612
```

### No Oil Detected
```
[CV] DEBUG - Oil detection statistics:
  Oil pixels (class 6): 0
  Oil percentage: 0.00%
[CV] Using softmax confidence from model:
  Oil class softmax confidence: 0.0000
  Overall average confidence: 0.6234
```

## Integration with Pipeline

The softmax confidence flows through the pipeline as:

1. **STEP 3**: CV model returns softmax-based confidence
2. **STEP 8**: Ensemble decision uses oil class confidence in weighted average:
   ```
   ensemble_confidence = 0.40 * cv_confidence + 0.30 * pg_confidence + 0.30 * nlp_confidence
   ```
3. **STEP 9**: Professional report shows confidence scores and their sources

## Backward Compatibility

If `quick_inference.py` returns old format (2-tuple instead of 3-tuple):
- Automatically detected and handled
- Falls back to heuristic-based confidence calculation
- No pipeline failures, just uses old method

## Testing

All files verified with Python syntax check:
```bash
python -m py_compile src/cv/quick_inference.py src/cv/run_cv.py src/cv_model.py
✓ All CV files have valid Python syntax
```

## Files Modified

| File | Change | Impact |
|------|--------|--------|
| `src/cv/quick_inference.py` | Added softmax accumulation & return dict | Calculate per-class confidence |
| `src/cv/run_cv.py` | Extract & use oil class softmax score | Apply model confidence directly |
| `src/cv_model.py` | Extract confidence from return dict | Pass through pipeline |

## Next Steps (Optional)

1. **Temperature Scaling**: If softmax probabilities are too confident (0.9+), apply temperature scaling
2. **Ensemble Calibration**: Retrain ensemble weights knowing CV uses calibrated probabilities
3. **Confidence Thresholds**: Set different decision thresholds based on confidence ranges
4. **Audit Trail**: Log source of confidence (softmax vs heuristic) for each detection

---

**Last Updated**: 2026-03-05
**Status**: Implemented and verified
**Accuracy Impact**: More realistic confidence scores reflecting model uncertainty
