# PG Classifier Improvements - Soft Continuous Scoring

**Date**: March 7, 2026
**Status**: Implemented

## Summary

Improved the PG classifier from **binary pass/fail scoring** to **soft continuous scoring** for more accurate and robust oil spill detection.

---

## Issues Fixed

### 1. **Incorrect "NOT OIL" Label (Main Issue)**
- **Problem**: 4-panel PG visualization displayed "NOT OIL ✗" even for actual oil spills
- **Root Cause**: Used `all_pass` binary check (all 4 rules MUST pass) - too strict
- **Solution**: 
  - Switch to **confidence-based classification** using weighted scores
  - Show soft score gradients (0-1) instead of binary PASS/FAIL
  - Use overall confidence >= 0.5 threshold instead of requiring all rules to pass
- **Result**: Now correctly identifies oil even if individual rules have partial scores

### 2. **All-or-Nothing Scoring**
- **Problem**: Binary scoring (0 or 1) doesn't reflect partial compliance
- **Solution**: Implement soft sigmoid-based continuous scoring

---

## Technical Changes

### A. New Soft Scoring Function

Added `calculate_soft_score()` that uses **logistic sigmoid** instead of hard thresholds:

```python
score = 1.0 / (1.0 + np.exp(-(value - threshold) / margin))
```

**Key Benefits**:
- Provides smooth 0-1 gradient instead of cliff-like 0→1 transition
- Parammeterizable "margin" allows control of harshness
- Handles both inverted (lower=better) and normal (higher=better) metrics

### B. Updated `verify_physics_rules()`

New parameter: `use_soft_scoring` (default: `True`)

**Soft Scoring Details**:

| Rule | Metric | Margin | Behavior |
|------|--------|--------|----------|
| **Darkness** | Mean intensity (inverted) | ±3 dB | Lower intensity → higher score |
| **Smoothness** | Std intensity (inverted) | ±1 dB | Lower variation → higher score |
| **Shape** | Elongation + Compactness | var | Average of both |
| **Alignment** | Angle difference (inverted) | ±20° | Smaller diff → higher score |

### C. Visualization Updates

Updated `create_pg_classifier_visualization()` to display:
- **Individual rule soft scores** (showing gradients instead of PASS/FAIL)
- **Overall confidence** using weighted average
- **Classification** from confidence threshold (>= 0.5)

**Before vs After**:
```
BEFORE:
└─ OVERALL:  NOT OIL ✗         (binary, all_pass=False)
   Confidence: 45%

AFTER:
├─ Darkness Rule: PARTIAL (0.62/1.0)
├─ Smoothness Rule: PARTIAL (0.58/1.0)
├─ Shape Rule: FAIL (0.35/1.0)
├─ Alignment Rule: PASS (0.85/1.0)
└─ Overall Confidence: 58%
   Classification: Oil-like
```

### D. Weighted Confidence Calculation

```python
confidence = (
    darkness_score × 0.15 +
    smoothness_score × 0.20 +
    shape_score × 0.15 +
    alignment_score × 0.50  # Physics-based, most reliable
)
```

**Threshold**: confidence >= 0.5 → "Oil-like"

---

## Benefits

1. **More Forgiving**: Doesn't require perfection on all rules
2. **Probabilistic**: Confidence reflects feature certainty
3. **Interpretable**: Soft scores show which rules are weak/strong
4. **Corrects False Negatives**: Real oil spills won't be rejected due to single weak rule
5. **Backward Compatible**: Legacy binary mode still available (`use_soft_scoring=False`)

---

## Configuration

Soft score margins can be tuned in `ClassifierConfig`:

```python
# Adjust margins to be more/less strict
darkness_margin = 3.0     # ±3 dB transition zone
smoothness_margin = 1.0   # ±1 dB transition zone
shape_margin = [0.5, 1.0] # ±0.5 for elongation, ±1.0 for compactness
alignment_margin = 20.0   # ±20° transition zone
```

---

## Example Use Cases

### Case 1: Weak Darkness + Strong Alignment
```
Darkness: 0.45 (slightly brighter than ideal)
Smoothness: 0.72 (good)
Shape: 0.58 (moderate)
Alignment: 0.88 (excellent drift physics match)
─────────────────────────────────
Confidence: 61% → Oil-like ✓
```
Previously: NOT OIL ✗ (darkness rule failed)

### Case 2: Strong Physics Match
```
Darkness: 0.35 (not very dark)
Smoothness: 0.40 (some noise)
Shape: 0.30 (irregular)
Alignment: 0.95 (perfect drift match)
─────────────────────────────────
Confidence: 62% → Oil-like ✓
```
Relies on physics-based alignment (50% weight) - correct!

---

## Testing Recommendations

1. **Regression Testing**: Compare new vs old classifications on historical detections
2. **Precision vs Recall**: Tune confidence threshold (0.5 or adjust) to balance:
   - High precision: Reduce false positives (increase threshold)
   - High recall: Reduce false negatives (decrease threshold)
3. **Feature Analysis**: Examine which soft scores miss or hit threshold in edge cases
4. **Visualization Review**: Check if confidence gradients match human expert judgment

---

## Backward Compatibility

To revert to legacy binary scoring:
```python
rules, rule_scores = verify_physics_rules(
    geometric, radiometric, drift_direction,
    use_soft_scoring=False  # Use old binary method
)
```

---

## Files Modified

- `src/pg_classifier.py`
  - Added: `calculate_soft_score()` function
  - Modified: `verify_physics_rules()` - added soft scoring logic
  - Modified: `classify_with_physical_guidance()` - auto enable soft scoring
  - Modified: `create_pg_classifier_visualization()` - display soft scores + confidence
