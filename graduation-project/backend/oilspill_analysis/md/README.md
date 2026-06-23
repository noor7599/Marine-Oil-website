# Oil Spill Analysis Pipeline - Modular Architecture

## Overview

This is a complete automated pipeline for oil spill detection combining:
- **Computer Vision**: SAR image analysis and coordinate extraction
- **Physics Simulation**: OpenDrift oil spill modeling
- **Machine Learning**: Random Forest classifier
- **Physics-Guided Rules**: Expert-based verification rules
- **Ensemble Decision**: Weighted voting from multiple models

## Project Structure

```
src/
├── __init__.py              # Package initialization
├── config.py                # Configuration management (including CV & NLP sections)
├── cv_model.py              # Wrapper around mados/quick_inference.py (MariNeXt CV)
├── coordinate_extractor.py  # Extract metadata from SAR TIFF (Notebook 1)
├── data_downloader.py       # Download ERA5 & CMEMS data (Notebook 2)
├── simulator.py             # OpenDrift simulation (Notebook 3)
├── pg_classifier.py         # Physics-Guided classifier (Notebook 4)
├── rf_classifier.py         # Random Forest classifier (Notebook 5)
├── decision_layer.py        # Weighted ensemble decision
├── model.py                 # NLP validation/incident matching module
└── pipeline.py              # Main orchestrator

main.py                       # Entry point script
requirements.txt              # Python dependencies (for NLP + core pipeline)
config.json                   # Configuration (create from default)
```

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Setup API Credentials

#### Copernicus Climate Data Store (ERA5):
```bash
# Create ~/.cdsapirc file with:
url: https://cds.climate.copernicus.eu/api/v2
key: <your-api-key>
```

#### Copernicus Marine Service (CMEMS):
```bash
copernicus_marine init
# Follow prompts to enter username and password
```

## Usage

### Complete Pipeline (Automated)

Before running the pipeline make sure you activate the **mados** conda
environment where the MariNeXt CV stack is installed:

```bash
conda activate mados
```

Dependencies for the NLP module are satisfied by the standard
`requirements.txt` file; no additional environment is required.

```bash
# Run complete workflow (CV -> extraction -> simulation -> PG -> RF -> NLP -> ensemble)
python main.py

# Run with specific SAR image
python main.py --image /path/to/image.tiff

# Run with custom configuration
python main.py --config config.json
```

### Individual Steps

The pipeline is now organized into seven numbered steps; the new **step 7** runs
an NLP validation module against a historical incident database.  The
`--csv` argument can be used to override the default incident file location.

```bash
# Step 1: Extract coordinates
python main.py --step 1 --image /path/to/image.tiff

# Step 2: Download environmental data
python main.py --step 2

# Step 3: Run simulation
python main.py --step 3

# Step 4: Physics-Guided classification
python main.py --step 4 --sar-image path.tiff --mask mask.npy

# Step 5: Random Forest classification
python main.py --step 5

# Step 6: NLP validation/classification
python main.py --step 7 --csv data/raw/incidents_balanced_cleaned.csv

# Step 7: Final decision (ensemble of PG, RF and optional NLP)
python main.py --step 6
```

### Programmatic Usage

```python
from src.pipeline import OilSpillPipeline

# Initialize pipeline
pipeline = OilSpillPipeline('config.json')

# Run complete workflow
results = pipeline.run_complete_pipeline(
    image_path='/path/to/image.tiff',
    sar_image_path='/path/to/sar.tiff',
    binary_mask_path='/path/to/mask.npy'
)

# Access individual results
final_decision = results['step_6_final_decision']
print(f"Final prediction: {final_decision['final_prediction']}")
print(f"Confidence: {final_decision['final_confidence']}")
```

### Individual Module Usage

```python
from src.coordinate_extractor import process_sar_image
from src.data_downloader import download_environmental_data
from src.simulator import run_simulation
from src.pg_classifier import classify_with_physical_guidance
from src.rf_classifier import RFClassifier
from src.decision_layer import make_ensemble_decision

# Step 1: Extract coordinates
coords = process_sar_image('image.tiff', 'data/processed')

# Step 2: Download data
environ_data = download_environmental_data('metadata.json', 'data/processed')

# Step 3: Run simulation
sim_result = run_simulation(
    era5_file='era5.nc',
    cmems_file='cmems.nc',
    release_lat=10.5,
    release_lon=120.5,
    release_time=datetime(2023, 4, 23, 12, 0),
    output_dir='outputs'
)

# Step 4: Physics-Guided classification
pg_result = classify_with_physical_guidance(
    sar_image=sar_data,
    binary_mask=mask_data,
    simulation_file='simulation.nc',
    spot_centroid=(10.5, 120.5)
)

# Step 5: Random Forest classification
rf = RFClassifier()
rf.train(X_train, y_train)
rf_result = rf.predict_single({'mean_intensity': -15, 'std_intensity': 1.2, ...})

# Step 6: Ensemble decision
final_decision = make_ensemble_decision(pg_result, rf_result)
```

## Configuration

### Create Custom Configuration

```bash
python main.py --save-config config.json
```

### Configuration File (config.json)

```json
{
  "data": {
    "raw_dir": "../data/raw",
    "processed_dir": "../data/processed",
    "outputs_dir": "../outputs"
  },
  "simulation": {
    "oil_type": "GENERIC MEDIUM CRUDE",
    "num_particles": 1000,
    "duration_hours": 24
  },
  "pg_classifier": {
    "darkness_threshold": -15.0,
    "smoothness_threshold": 1.5,
    "alignment_tolerance": 40.0
  },
  "decision_layer": {
    "cv_weight": 0.3,   # weight assigned to computer vision output
    "pg_weight": 0.3,
    "rf_weight": 0.1,
    "nlp_weight": 0.3
  }
}
```

## Pipeline Steps

### Step 1: CV Detection
Run segmentation model (or simple threshold) on SAR image to locate oil-like pixels.
- Input: SAR image
- Output: Mask and confidence score

### Step 2: Extract Coordinates & Environmental Data
Extracts geolocation data from SAR TIFF image metadata and kicks off ERA5/CMEMS downloads.
- Input: SAR image metadata (includes date & bounds)
- Output: Coordinates, ERA5 wind & CMEMS current files (if available)

### Step 3: Oil Pixel Analysis
Calculate pixel counts and area from the CV mask
- Input: Binary mask
- Output: Oil pixel statistics

### Step 4: Trajectory Simulation
... (unchanged)


### Step 3: Run Simulation
Runs OpenDrift oil spill simulation with downloaded environmental data
- Input: ERA5, CMEMS data, release location and time
- Output: Particle trajectories NetCDF file

### Step 4: Physics-Guided Classification
Rule-based verification using SAR features and simulation drift direction
- Rules: Darkness, Smoothness, Shape, Alignment
- Output: Oil-like or False Positive classification

### Step 5: Random Forest Classification
Machine learning classifier trained on synthetic and real SAR data
- Output: Oil-like or Non-oil classification with confidence

### Step 6: Ensemble Decision
Weighted voting from multiple classifiers
- Combines: Physics-Guided, Random Forest, (optional) NLP
- Output: Final decision with confidence score

## Output Files

All results are saved to `outputs/` directory:

```
outputs/
├── simulation_YYYYMMDDTHHMMZ_HHMMSS.nc     # Simulation trajectories
├── simulation_results_YYYYMMDDTHHMMZ.json   # Simulation metadata
├── pipeline_results_YYYYMMDD_HHMMSS.json   # Complete pipeline results
├── train_test_split_results.csv             # ML training metrics
└── animations/
    └── oil_movement_YYYYMMDDTHHMMZ.mp4      # Animation of drift
```

## Decision Weights

Adjust model weights in configuration:

```json
"decision_layer": {
  "pg_weight": 0.4,        # Physics-Guided: 40%
  "rf_weight": 0.4,        # Random Forest: 40%
  "nlp_weight": 0.2        # NLP (optional): 20%
}
```

The weights are automatically normalized to sum to 1.0.

## Key Features

✓ **Fully Automated**: No manual intervention between steps  
✓ **Modular Design**: Use individual components independently  
✓ **Configurable**: All thresholds and weights adjustable  
✓ **Well-Documented**: Comprehensive docstrings and comments  
✓ **Ensemble Approach**: Multiple models reduce false positives  
✓ **Production-Ready**: Error handling and logging throughout

## Troubleshooting

### API Credentials Not Found
```bash
# ERA5: Create ~/.cdsapirc
# CMEMS: Run copernicus_marine init
```

### NetCDF4 Import Errors
```bash
pip install --upgrade netCDF4
```

### OpenDrift Installation Issues
```bash
pip install --upgrade opendrift
```

## Contributing

To add new classifiers:
1. Create module in `src/`
2. Implement prediction method returning dict with 'classification' and 'confidence'
3. Integrate in `decision_layer.py`
4. Update pipeline.py if needed

## References

- [OpenDrift](https://opendrift.github.io/)
- [Copernicus Climate Data Store](https://cds.climate.copernicus.eu/)
- [Copernicus Marine Service](https://marine.copernicus.eu/)
- [scikit-learn](https://scikit-learn.org/)

## License

Graduation Project - Oil Spill Detection System
