# CV Confidence Calculation Documentation

## Updated cv_results.json Format

The `cv_results.json` now includes detailed documentation of how the confidence value is calculated.

### Example Output

```json
{
  "status": "success",
  "detected": true,
  "oil_pixels": 98726,
  "total_pixels": 4392500,
  "oil_percentage": 2.25,
  "confidence": 0.75,
  "confidence_calculation": {
    "method": "softmax_per_class_average",
    "source": "MariNeXt model softmax probabilities",
    "formula": "Weighted average of P(oil_class_6 | pixel) for pixels predicted as oil",
    "interpretation": "Model's average certainty (0-1) that detected oil pixels are actually oil spill: 75.0%"
  },
  "mask_path": "data/processed/sentinel_a1b2c3d4_oil_binary.npy",
  "multiclass_mask_path": "data/processed/sentinel_marinext_predictions.tiff",
  "visualization_path": "data/processed/sentinel_cv_visualization.png",
  "model": "marinext"
}
```

## Field Descriptions

### Core Detection Fields
- **detected** (boolean): Whether oil was detected in the image
- **oil_pixels** (integer): Number of pixels predicted as oil class (class 6)
- **total_pixels** (integer): Total number of pixels in image
- **oil_percentage** (number): Percentage of image marked as oil (oil_pixels / total_pixels)

### Confidence Value
- **confidence** (number 0-1): Model's certainty that detected pixels are truly oil spill

### Confidence Calculation Documentation
The `confidence_calculation` object explains how the confidence value was derived:

#### When Using Softmax Probabilities (Recommended)
```
method: "softmax_per_class_average"
source: "MariNeXt model softmax probabilities"
formula: "Weighted average of P(oil_class_6 | pixel) for pixels predicted as oil"
interpretation: "Model's average certainty (0-1) that detected oil pixels are actually oil spill: 75.0%"
```

**How it works:**
1. MariNeXt model outputs softmax probabilities for 15 classes per pixel
2. For each pixel predicted as oil (class 6), extract the softmax probability P(oil|pixel)
3. Calculate weighted average of these probabilities (weights based on spatial proximity)
4. Result: 0.75 = average softmax confidence for oil class among detected pixels

**Interpretation:**
- 0.75 means the model was 75% confident that detected pixels are oil
- Higher = more certain about detection
- Lower = higher uncertainty, might be false positives

#### When Using Heuristic Fallback
```
method: "heuristic_based"
source: "Heuristic based on detection statistics"
formula: "Fixed rules based on oil_percentage detection"
interpretation: "Assigned confidence based on detection characteristics: 75.0%"
```

**How it works (if softmax unavailable):**
- oil_percentage > 95% → confidence = 0.3 (suspicious, likely false positive)
- oil_percentage < 0.1% → confidence = 0.5 (very sparse detection)
- oil_percentage > 30% → confidence = 0.6 (large detections risky)
- 1-30% (normal) → confidence = 0.75 (typical valid detection)
- 0 pixels → confidence = 0.0 (no detection)

### Output Paths
- **mask_path**: Binary NPY file (0/1 for non-oil/oil pixels)
- **multiclass_mask_path**: Full TIFF with all 15 class predictions
- **visualization_path**: 4-panel visualization PNG

## Key Changes from Previous Version

| Field | Old | New | Purpose |
|-------|-----|-----|---------|
| `confidence` | `0.75` | `0.75` | Same value, now with documentation |
| NEW | — | `oil_percentage` | Shows % of image marked as oil |
| NEW | — | `confidence_calculation` | Explains how 0.75 was calculated |
| — | — | `method` | "softmax_per_class_average" or "heuristic_based" |
| — | — | `source` | Where confidence came from (model or fallback) |
| — | — | `formula` | Mathematical/algorithmic formula used |
| — | — | `interpretation` | Human-readable explanation |

## Accessing Confidence Details in Code

### In Python:
```python
import json

with open("data/processed/cv_results.json") as f:
    results = json.load(f)

confidence = results["confidence"]  # 0.75
method = results["confidence_calculation"]["method"]  # "softmax_per_class_average"
interpretation = results["confidence_calculation"]["interpretation"]  # "Model's average certainty..."
```

### In Decision Layer:
The decision layer reads this JSON and uses:
- `confidence` value for classifier inputs
- `confidence_calculation.method` to track quality of predictions
- `oil_percentage` to detect suspicious detections

## Quality Indicators

When reviewing cv_results.json, look for:
1. **method**: Prefer "softmax_per_class_average" over "heuristic_based"
2. **confidence**: Values above 0.7 indicate higher confidence
3. **oil_percentage**: 1-30% is typical valid range, extremes suggest false positives
4. **interpretation**: Explicitly shows the % confidence for clarity
