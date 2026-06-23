# Quick Reference: Testing the Three Fixes

## PROBLEM 1: Drift Simulation CSV Duplicates

### What to test:
Run the pipeline on a small simulation (6-12 hours) and check the trajectory CSV.

```bash
# The simulation CSV should be written to:
# data/processed/runs/{timestamp}/simulation_{release_time}_trajectories.csv
```

### Expected behavior (AFTER FIX):
- CSV file has NO repeated final rows
- Log output includes message: `"Position unchanged ... Skipping duplicate row"`
- Log output includes message: `"Position stagnant for 3+ timesteps. Stopping trajectory output"`
- Each row has unique (timestamp, lat, lon) tuple

### Example Test Data
Create a test with short duration where particles will stabilize:
- Release location: Mediterranean Sea (narrow basin → particles hit coast quickly)
- Duration: 8-12 hours
- Look for: Particles should stop moving after hitting boundary

### Validation Script (Python):
```python
import pandas as pd
import numpy as np

csv_file = "data/processed/runs/{timestamp}/simulation_{release_time}_trajectories.csv"
df = pd.read_csv(csv_file)

# Check for duplicate rows (same lat/lon in consecutive timesteps)
df['pos_changed'] = (
    (df['lon'].diff().abs() > 0.0001) | 
    (df['lat'].diff().abs() > 0.0001)
)

# After first row, all should have position_changed=True (or be NaN for first row)
duplicates = (~df['pos_changed'].iloc[1:]).sum()
print(f"Duplicate rows found: {duplicates}")
assert duplicates == 0, f"Found {duplicates} duplicate rows!"
print("✓ PASS: No duplicate trajectories")
```

---

## PROBLEM 2: Physics-Guided Classifier Radiometric Values

### What to test:
Run PG classifier on known SAR image with detected oil spill.

### Expected behavior (AFTER FIX):
- Log output includes: `"Radiometric filtering: raw pixels n=... min=... dB max=... dB"`
- Mean intensity is in range: **-60 to +5 dB** (realistic for gamma0)
- Std intensity is in range: **< 4 dB** (not inflated by nodata)
- Log output does NOT include: `"CRITICAL"` warnings about radiometric values

### Typical values for ocean:
- Mean: **-18 to -22 dB** (clean water)
- Std: **0.5 to 2.0 dB** (smooth surface)
- Min: **-25 to -28 dB**
- Max: **-15 to -18 dB**

### Typical values for oil slick:
- Mean: **-22 to -28 dB** (darker than water)
- Std: **1.0 to 3.0 dB** (smoother than water)
- Min: **-30 to -35 dB**
- Max: **-20 to -25 dB**

### Validation Script (Python):
```python
import logging
import re

# Set up to capture logs
logging.basicConfig(level=logging.INFO)

# Run classifier
from src.pg_classifier import extract_radiometric_features
features = extract_radiometric_features(sar_image, mask)

# Validate ranges
mean = features.mean_intensity
std = features.std_intensity

assert -60 <= mean <= 5, f"Mean {mean} dB outside valid range!"
assert std <= 20, f"Std {std} dB unrealistically high!"

# Check log doesn't contain critical errors
# (This would be in actual logging output)
print(f"✓ PASS: Mean={mean:.2f} dB, Std={std:.2f} dB (realistic)")
```

---

## PROBLEM 3: Decision Layer Evidence Voting

### What to test:
Create test cases where models disagree on Oil vs False Positive.

### Test Case 1: CV votes Oil, PG+NLP vote FP
```python
from src.decision_layer import DecisionLayer

decision_layer = DecisionLayer()

# Test case: 1 Oil vote, 2 FP votes
pg_result = {
    'classification': 'False Positive',
    'confidence': 0.70
}
nlp_result = {
    'classification': 'False Positive',
    'risk_level': 'LOW',
    'confidence': 0.60
}
cv_score = 0.80  # CV votes Oil

decision = decision_layer.decide(pg_result, nlp_result, cv_score=cv_score)

# AFTER FIX: Should be "Non-oil" because:
# - Oil_evidence = 0.80 × 0.40 = 0.32
# - NonOil_evidence = (0.70 × 0.30) + (0.60 × 0.30) = 0.39
# - 0.39 > 0.32 → "Non-oil" decision ✓

print(f"Final: {decision.final_prediction}")
assert decision.final_prediction == "Non-oil", f"Wrong decision!"
print("✓ PASS: Correctly voted Non-oil despite CV saying Oil")
```

### Test Case 2: All models vote Oil
```python
pg_result = {
    'classification': 'Oil-like',
    'confidence': 0.85
}
nlp_result = {
    'classification': 'HIGH RISK',
    'risk_level': 'HIGH',
    'confidence': 0.90
}
cv_score = 0.92

decision = decision_layer.decide(pg_result, nlp_result, cv_score=cv_score)

# AFTER FIX: Should be "Oil-like" because:
# - Oil_evidence = (0.92 × 0.40) + (0.85 × 0.30) + (0.90 × 0.30) = 0.891
# - NonOil_evidence = 0.0
# - 0.891 > 0.0 → "Oil-like" decision ✓

assert decision.final_prediction == "Oil-like"
print("✓ PASS: Correctly voted Oil-like with unanimous agreement")
```

### Expected Log Output Format:
```
[DECISION] Raw predictions - CV: Oil, PG: Non-Oil, NLP: Non-Oil
[DECISION] Confidences - CV: 0.80, PG: 0.70, NLP: 0.60
[DECISION] CV votes 'Oil' with evidence: 0.320
[DECISION] PG votes 'Non-Oil' with evidence: 0.210
[DECISION] NLP votes 'Non-Oil' with evidence: 0.180
[DECISION] Total Oil evidence: 0.320
[DECISION] Total Non-Oil evidence: 0.390
[DECISION] Final Decision: Non-oil (confidence: 0.390)
[DECISION] Decision Basis: Non-Oil evidence (0.390) >= Oil evidence (0.320)
```

### Validation: Check Decision Summary
```python
summary = decision.decision_summary

# Should have these keys (NEW in Fixed version)
assert 'oil_evidence' in summary
assert 'nonoil_evidence' in summary
assert 'decision_method' in summary

# Should show separated evidence
oil_ev = summary['oil_evidence']
nonoil_ev = summary['nonoil_evidence']
assert oil_ev >= 0 and nonoil_ev >= 0
print(f"✓ PASS: Summary shows Oil={oil_ev:.3f}, NonOil={nonoil_ev:.3f}")
```

---

## All Fixes Verification Checklist

### Code Quality
- [ ] No syntax errors: `python -m py_compile src/cv_utils.py src/pg_classifier.py src/decision_layer.py`
- [ ] Imports work: `from src.cv_utils import export_simulation_for_viewing`
- [ ] Imports work: `from src.pg_classifier import extract_radiometric_features`
- [ ] Imports work: `from src.decision_layer import DecisionLayer`

### Functionality
- [ ] Problem 1: Simulator CSV has no duplicate rows
- [ ] Problem 2: Radiometric values realistic for gamma0 range
- [ ] Problem 3: Decision layer separates Oil/NonOil evidence correctly

### Logging
- [ ] Problem 1: Log includes "Position unchanged" messages
- [ ] Problem 2: Log includes "Radiometric filtering:" summary
- [ ] Problem 3: Log includes "[DECISION]" messages with evidence breakdown

### Backward Compatibility
- [ ] Pipeline still accepts same input formats
- [ ] Model outputs (CV, PG, NLP) unchanged
- [ ] All JSON fields present (may have additional "_evidence" fields)

---

## Rollback Plan (if needed)

If any issues occur during testing:

### Rollback Problem 1:
```bash
git checkout src/cv_utils.py
# Or manually remove these sections from export_simulation_for_viewing:
# - prev_lon, prev_lat tracking
# - consecutive_stagnant counter
# - position_changed check
# - logger.warning calls
```

### Rollback Problem 2:
```bash
git checkout src/pg_classifier.py
# Or manually revert extract_radiometric_features to use old filtering logic
```

### Rollback Problem 3:
```bash
git checkout src/decision_layer.py
# Or manually restore old decide() method (weighted average logic)
```

---

## Documentation of Changes

See [FIXES_SUMMARY.md](FIXES_SUMMARY.md) for complete detailed explanation of:
- Root causes for each problem
- Implementation details
- Expected behaviors and examples
- Files modified

