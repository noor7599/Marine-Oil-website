# Modularization Summary - Oil Spill Analysis Pipeline

## Conversion Complete ✓

All 5 notebooks have been successfully converted into modular Python modules with automated orchestration.

---

## What Was Done

### 1. Created `src/` Module Structure

#### Core Modules:
- **`config.py`** - Configuration management (centralized settings)
- **`coordinate_extractor.py`** - Extract SAR image metadata (Notebook 1)
- **`data_downloader.py`** - Download ERA5 & CMEMS data (Notebook 2)
- **`simulator.py`** - Run OpenDrift simulations (Notebook 3)
- **`pg_classifier.py`** - Physics-Guided rule-based classifier (Notebook 4)
- **`rf_classifier.py`** - Random Forest ML classifier (Notebook 5)
- **`decision_layer.py`** - Weighted ensemble voting
- **`pipeline.py`** - Main orchestrator (runs all steps automatically)

#### Supporting Files:
- **`main.py`** - Command-line entry point
- **`requirements.txt`** - All dependencies listed
- **`config.json`** - Configuration template (fully customizable)
- **`README.md`** - Complete documentation
- **`QUICKSTART.md`** - 5-minute setup guide

---

## Key Features

### ✓ Fully Automated
Each step's **output automatically becomes the next step's input**. No manual file transfers needed.

### ✓ Modular Design
**Use parts independently:**
```python
from src.coordinate_extractor import process_sar_image
from src.simulator import run_simulation
from src.rf_classifier import RFClassifier
```

### ✓ Configurable
Edit `config.json` to adjust:
- Model weights (how much each model influences final decision)
- Physical thresholds (darkness, smoothness, alignment)
- Simulation parameters (particles, duration, oil type)
- Data directories and API credentials

### ✓ Production-Ready
- Error handling throughout
- Comprehensive logging to file
- JSON-serializable results
- Input validation

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────┐
│ USER UPLOADS SAR IMAGE (via upload interface)   │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
    ┌──────────────────────────────────┐
    │ STEP 1: Extract Coordinates      │
    │ (coordinate_extractor.py)        │
    │ Input: SAR TIFF Image            │
    │ Output: Location & Date          │
    └────────────┬─────────────────────┘
                 │
                 ▼
    ┌──────────────────────────────────┐
    │ STEP 2: Download Data            │
    │ (data_downloader.py)             │
    │ Input: Coordinates & Date        │
    │ Output: ERA5 & CMEMS NetCDF      │
    └────────────┬─────────────────────┘
                 │
                 ▼
    ┌──────────────────────────────────┐
    │ STEP 3: Run Simulation           │
    │ (simulator.py)                   │
    │ Input: ERA5, CMEMS, Location     │
    │ Output: Particle Trajectories    │
    └────────────┬─────────────────────┘
                 │
        ┌────────┴────────┐
        │                 │
        ▼                 ▼
    ┌─────────────┐  ┌──────────────┐
    │ STEP 4:     │  │ STEP 5:      │
    │ PG Rules    │  │ Random Forest│
    │ Classifier  │  │ Classifier   │
    └─────────────┘  └──────────────┘
        │                 │
        └────────┬────────┘
                 │
                 ▼
    ┌──────────────────────────────────┐
    │ STEP 6: Ensemble Decision        │
    │ (decision_layer.py)              │
    │ Input: PG + RF + NLP scores      │
    │ Output: Final Decision           │
    └────────────┬─────────────────────┘
                 │
                 ▼
    ┌──────────────────────────────────┐
    │ FINAL RESULT                     │
    │ Prediction: Oil/Non-Oil          │
    │ Confidence: 0-1 score            │
    │ Reasoning: Weight breakdown      │
    └──────────────────────────────────┘
```

---

## How To Use

### Option 1: Command Line (Easiest)

```bash
# Run complete pipeline automatically
python main.py

# Or specify image
python main.py --image data/raw/my_image.tiff

# Or run single step
python main.py --step 1 --image data/raw/my_image.tiff
```

### Option 2: Python Code

```python
from src.pipeline import OilSpillPipeline

# Initialize
pipeline = OilSpillPipeline('config.json')

# Run everything automatically
results = pipeline.run_complete_pipeline(
    image_path='data/raw/image.tiff'
)

# Check results
print(results['step_6_final_decision'])
```

### Option 3: Individual Steps

```python
from src.coordinate_extractor import process_sar_image
from src.data_downloader import download_environmental_data
from src.simulator import run_simulation

# Step 1
coords = process_sar_image('image.tiff', 'data/processed')

# Step 2
environ_data = download_environmental_data('metadata.json')

# Step 3
sim_result = run_simulation(
    environ_data['files']['era5'],
    environ_data['files']['cmems'],
    ...
)
```

---

## File Flow

```
input/
  └─ image.tiff (user uploads)
       │
       └─→ Step 1: Extract
            Output: metadata.json
            
       └─→ Step 2: Download
            Output: era5_wind*.nc
                    cmems_current*.nc
            
       └─→ Step 3: Simulate
            Output: simulation_*.nc
            
       └─→ Step 4: PG Classify
            Output: pg_result.json
            
       └─→ Step 5: RF Classify
            Output: rf_result.json
            
       └─→ Step 6: Ensemble
            Output: final_decision.json
```

---

## Configuration Example

**before:** Each notebook had hardcoded paths and parameters
**after:** Single `config.json` file

```json
{
  "decision_layer": {
    "pg_weight": 0.4,      // Increase for stricter physics
    "rf_weight": 0.4,      // Increase for ML reliability
    "nlp_weight": 0.2      // Optional NLP component
  },
  "pg_classifier": {
    "darkness_threshold": -15.0,     // Adjust sensitivity
    "alignment_tolerance": 40.0      // Oil drift angle matching
  },
  "simulation": {
    "num_particles": 1000,           // More = more accurate but slower
    "duration_hours": 24             // Simulation length
  }
}
```

---

## Running the Integration Layer

Your integration layer setup with **3 external models** + decision layer:

```python
from src.decision_layer import make_ensemble_decision

# Step 1: Run your 3 external model APIs
cv_output = call_cv_model(image)              # Your CV model
pg_output = run_pg_classifier(features)       # Physics-Guided
rf_output = run_rf_classifier(features)       # Random Forest
nlp_output = call_nlp_model(report)           # Your NLP model

# Step 2: Get final decision
final_decision = make_ensemble_decision(
    pg_result=pg_output,
    rf_result=rf_output,
    nlp_result=nlp_output,
    weights={'pg': 0.4, 'rf': 0.4, 'nlp': 0.2}
)

# Step 3: Return to user
return {
    'prediction': final_decision['final_prediction'],
    'confidence': final_decision['final_confidence'],
    'model_votes': final_decision['individual_decisions']
}
```

---

## Benefits of Modularization

| Before (Notebooks) | After (Modules) |
|-------------------|-----------------|
| Manual run each notebook | Fully automated pipeline |
| Copy/paste results between notebooks | Automatic data flow |
| Parameters hardcoded in cells | Centralized config.json |
| Difficult to version control | Clean git-compatible structure |
| Can't reuse code easily | Import and use directly |
| No logging | Comprehensive logs |
| Manual error handling | Automatic error checking |
| Import Jupyter → export Python | Direct Python usage |

---

## Next Phase: Integration Layer

To build a **web interface** for your integration layer:

### Flask/FastAPI Setup:
```python
from flask import Flask, request, jsonify
from src.pipeline import OilSpillPipeline

app = Flask(__name__)
pipeline = OilSpillPipeline()

@app.route('/upload', methods=['POST'])
def upload_image():
    image_file = request.files['image']
    image_file.save('temp.tiff')
    
    # Run pipeline automatically
    results = pipeline.run_complete_pipeline(image_path='temp.tiff')
    
    return jsonify(results['step_6_final_decision'])

@app.route('/configure', methods=['POST'])
def configure_weights():
    weights = request.json  # {'pg': 0.4, 'rf': 0.4, 'nlp': 0.2}
    pipeline.config.set('decision_layer.pg_weight', weights['pg'])
    # ... etc
    return jsonify({'status': 'success'})
```

---

## Testing the Pipeline

```bash
# Test complete pipeline
python -m pytest tests/test_pipeline.py

# Test individual modules
python -m pytest tests/test_coordinate_extractor.py
python -m pytest tests/test_simulator.py
python -m pytest tests/test_classifiers.py
```

---

## Summary

✅ **Notebooks converted to Python modules**  
✅ **Automatic orchestration between steps**  
✅ **Configurable parameters**  
✅ **Production-ready error handling**  
✅ **Ready for integration layer**  
✅ **Comprehensive documentation**  

**Next Step:** Build the web interface (Flask/FastAPI) for user uploads!

---

## Questions?

See:
- `README.md` - Full documentation
- `QUICKSTART.md` - 5-minute setup
- `config.json` - All parameters with explanations
- Source code docstrings - Every function documented
