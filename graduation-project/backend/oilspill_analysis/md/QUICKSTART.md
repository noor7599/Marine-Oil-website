# Quick Start Guide - Oil Spill Analysis Pipeline

## 5-Minute Setup

### 1. Install Dependencies (2 min)
```bash
cd oilspill_analysis
pip install -r requirements.txt
```

### 2. Setup Credentials (1 min)

**ERA5 (Copernicus Climate):**
- Go to: https://cds.climate.copernicus.eu/
- Create account, accept terms
- Get API key from user profile
- Create `~/.cdsapirc` file:
```
url: https://cds.climate.copernicus.eu/api/v2
key: YOUR_API_KEY_HERE
```

**CMEMS (Copernicus Marine):**
- Go to: https://marine.copernicus.eu/
- Create account, accept terms
- Run in terminal:
```bash
copernicus_marine init
# Enter your username and password when prompted
```

### 3. Prepare Your Data (1 min)

Place your SAR TIFF image in:
```
data/raw/your_image.tiff
```

### 4. Run Pipeline (1 min)

```bash
# Auto-detects SAR image and runs complete workflow
python main.py
```

**That's it!** Results will be saved to `outputs/`

---

## Usage Examples

### Example 1: Complete Automated Workflow
```bash
python main.py
```

### Example 2: With Specific Image
```bash
python main.py --image data/raw/my_sar_image.tiff
```

### Example 3: Run Single Step
```bash
# Just extract coordinates
python main.py --step 1 --image data/raw/my_image.tiff

# Just download environmental data
python main.py --step 2

# Just run simulation  
python main.py --step 3
```

### Example 4: Programmatic Use
```python
from src.pipeline import OilSpillPipeline

pipeline = OilSpillPipeline()
results = pipeline.run_complete_pipeline()

print(results['step_6_final_decision']['final_prediction'])
print(results['step_6_final_decision']['final_confidence'])
```

---

## Understanding Results

### Final Output (in outputs/pipeline_results_*.json)

```json
{
  "step_6_final_decision": {
    "final_prediction": "Oil-like",
    "final_confidence": 0.87,
    "individual_decisions": [
      {
        "model_name": "Physics-Guided",
        "prediction": "Oil-like",
        "confidence": 0.75,
        "weight": 0.4
      },
      {
        "model_name": "Random Forest",
        "prediction": "Oil-like",
        "confidence": 0.95,
        "weight": 0.4
      }
    ]
  }
}
```

**Interpretation:**
- `final_prediction`: "Oil-like" = Oil spill detected, "Non-oil" = False alarm
- `final_confidence`: Confidence score (0-1, higher is more confident)
- `individual_decisions`: Each model's vote with weight

---

## Troubleshooting

### "No TIFF files found in data/raw"
✓ Solution: Place your SAR image in `data/raw/` directory

### "CDS API credentials not found"
✓ Solution: Create `~/.cdsapirc` file with API key (see Setup step 2)

### "CMEMS login failed"
✓ Solution: Run `copernicus_marine init` and enter credentials

### "NetCDF4 error"
✓ Solution: `pip install --upgrade netCDF4`

### "OpenDrift installation failed"
✓ Solution: Try `pip install --upgrade opendrift --no-cache-dir`

---

## Configuration Customization

Edit `config.json` to adjust model weights:

```json
"decision_layer": {
  "pg_weight": 0.4,        # Increase for stricter physics checks
  "rf_weight": 0.4,        # Increase for ML confidence
  "nlp_weight": 0.2        # Optional NLP component weight
}
```

Or physics thresholds:

```json
"pg_classifier": {
  "darkness_threshold": -15.0,      # Lower = requires darker spot
  "alignment_tolerance": 40.0       # Higher = more lenient orientation matching
}
```

---

## Output Files Overview

| File | Purpose |
|------|---------|
| `simulation_*.nc` | Particle trajectories from OpenDrift |
| `pipeline_results_*.json` | Complete pipeline results |
| `train_test_split_results.csv` | ML model evaluation metrics |
| `animations/oil_movement_*.mp4` | Animation of oil drift |
| `logs/pipeline_*.log` | Detailed execution logs |

---

## Next Steps

After your first run:

1. **Review Results**: Check `outputs/pipeline_results_*.json`
2. **Adjust Weights**: Edit `config.json` if needed
3. **Check Logs**: View `logs/pipeline_*.log` for details
4. **Run Again**: Re-run with adjusted parameters

---

## Quick Command Reference

```bash
# Extract coordinates only
python main.py --step 1 --image data/raw/image.tiff

# Download environmental data
python main.py --step 2

# Run simulation
python main.py --step 3

# Physics-guided classification
python main.py --step 4 --sar-image data/raw/sar.tiff --mask mask.npy

# Random Forest classification
python main.py --step 5

# Final decision
python main.py --step 6

# Save configuration template
python main.py --save-config my_config.json

# Run with custom config
python main.py --config my_config.json
```

---

## Support

For issues or questions:
1. Check logs in `logs/` directory
2. Review README.md for detailed documentation
3. Check configuration in `config.json`
4. Verify API credentials are setup correctly

**Happy oil spill detecting!** 🛢️➡️🚫
