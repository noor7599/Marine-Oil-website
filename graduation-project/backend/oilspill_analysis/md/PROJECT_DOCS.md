# Oil Spill Detection Pipeline - Documentation

**Graduation Project in AI (I) - Integration Layer**  
*March 2026*

---

## 📁 Project Structure

```
oilspill_analysis/
├── src/                           # Source code
│   ├── main/
│   │   ├── main_pipeline.py       # Orchestrator (oilspill3 environment)
│   │   ├── cv_subprocess.py       # CV subprocess handler
│   │   └── decision_layer.py      # Ensemble logic (CV + PG + NLP)
│   ├── cv/
│   │   ├── run_cv.py              # CV entry point (called from oilspill3)
│   │   └── quick_inference.py     # MariNeXt inference (mados environment)
│   ├── cv_utils.py                # CV visualization utilities
│   ├── cv_model.py                # Legacy CV wrapper
│   ├── coordinate_extractor.py    # SAR image coordinate extraction
│   ├── data_downloader.py         # Environmental data download
│   ├── simulator.py               # OpenDrift trajectory simulation
│   ├── pg_classifier.py           # Physics-Guided classification rules
│   ├── rf_classifier.py           # Random Forest (DEPRECATED - no longer used)
│   ├── model.py                   # Validation utilities
│   ├── visualizer.py              # Visualization helpers
│   ├── report_generator.py        # HTML/PDF/Text report generation
│   └── __init__.py
├── data/
│   ├── raw/                       # Input SAR images and incident CSVs
│   ├── processed/                 # Processed masks, coordinates, results
│   └── reports/                   # Generated reports (CSV, JSON)
├── notebooks/                     # Jupyter notebooks for model training
├── outputs/                       # Legacy output directory
├── temp/
│   ├── input/                     # Temporary input files
│   └── output/                    # CV subprocess outputs
├── logs/                          # Pipeline logs
├── config.json                    # Pipeline configuration
├── main.py                        # Legacy entry point
├── test_*.py                      # Test scripts
├── requirements.txt               # oilspill3 dependencies
├── requirements_mados.txt         # mados dependencies
└── PROJECT_DOCS.md               # This file
```

---

## ✅ Active Files (Used in Pipeline)

| File | Purpose | Environment | Status |
|------|---------|-------------|--------|
| `src/main/main_pipeline.py` | Orchestrates the full pipeline (Steps 1-9) | oilspill3 | ✓ Active |
| `src/main/cv_subprocess.py` | Calls CV in mados environment via subprocess | oilspill3 | ✓ Active |
| `src/main/decision_layer.py` | Weighted ensemble (CV 0.4, PG 0.3, NLP 0.3) | oilspill3 | ✓ Active |
| `src/cv/run_cv.py` | CV entry point, saves NPY binary mask | mados | ✓ Active |
| `src/cv/quick_inference.py` | MariNeXt model inference & multi-class mask | mados | ✓ Active |
| `src/cv_utils.py` | Side-by-side SAR + oil mask visualization | oilspill3 | ✓ New |
| `src/coordinate_extractor.py` | Extracts lat/lon bounds from SAR metadata | oilspill3 | ✓ Active |
| `src/data_downloader.py` | Downloads CMEMS/ERA5 environmental data | oilspill3 | ✓ Active |
| `src/simulator.py` | OpenDrift trajectory simulation | oilspill3 | ✓ Active |
| `src/pg_classifier.py` | Physics-Guided classification (drift alignment) | oilspill3 | ✓ Active |
| `src/model.py` | Detection validation utilities | oilspill3 | ✓ Active |
| `src/visualizer.py` | Visualization helper functions | oilspill3 | ✓ Active |
| `src/report_generator.py` | HTML/PDF/Text report generation | oilspill3 | ✓ Updated |

---

## ❌ Unused/Deprecated Files

| File | Reason | Status |
|------|--------|--------|
| `src/rf_classifier.py` | Removed from ensemble (RF weight=0) | Archived |
| `src/cv_model.py` | Replaced by `cv_subprocess.py` | Legacy |
| `main.py` | Replaced by `src/main/main_pipeline.py` | Legacy |
| `test_quick_inference.py` | Development/debugging only | Legacy |
| `notebooks/*.ipynb` | Model training (offline) | Historical |

---

## ⚙️ Environments

### oilspill3 (PRIMARY - Main Pipeline)
**Python:** 3.10+  
**Purpose:** Orchestrates the full detection pipeline
**Key Dependencies:**
- `opendrift` - Trajectory simulation
- `scikit-learn` 1.6.1 - PG & decision logic
- `pandas` - Data handling
- `numpy` - Numerical operations
- `matplotlib` - Visualization
- `rasterio` - SAR TIFF I/O
- `fpdf2` or `reportlab` - PDF reports

**Installation:**
```bash
conda create -n oilspill3 python=3.10
conda activate oilspill3
pip install -r requirements.txt
```

### mados (CV ONLY - MariNeXt Inference)
**Python:** 3.8+  
**Purpose:** Computer Vision detection using MariNeXt  
**Key Dependencies:**
- `torch` 1.11.0 - Neural network backend
- `torchvision` 0.12.0 - Image utilities
- `mmcv` - Computer vision framework
- `mmsegmentation` - Semantic segmentation
- `rasterio` - TIFF I/O

**Installation:**
```bash
conda create -n mados python=3.8
conda activate mados
pip install -r requirements_mados.txt
```

**Note:** CV runs in mados via subprocess from oilspill3

---

## 🚀 Quick Start

### Setup (One-time)
```bash
# Clone/prepare workspace
cd "d:\L4 S1\Graduation Project in AI (I)\Integration layer\oilspill_analysis"

# Create and activate oilspill3 environment
conda create -n oilspill3 python=3.10
conda activate oilspill3
pip install -r requirements.txt

# Ensure mados environment exists (CV dependency)
conda create -n mados python=3.8
conda activate mados
pip install -r requirements_mados.txt

# Switch back to oilspill3
conda activate oilspill3
```

### Run Pipeline
```bash
# Navigate to workspace
cd "d:\L4 S1\Graduation Project in AI (I)\Integration layer\oilspill_analysis"

# Activate oilspill3
conda activate oilspill3

# Run with test image
python src/main/main_pipeline.py \
  --image "data/raw/2023-03-18-00_00_2023-03-18-23_59_Sentinel-1_IW_VV+VH_VV_-_decibel_gamma0(zoomed).tiff" \
  --csv "data/raw/incidents_balanced_cleaned.csv"

# Check outputs
ls -la data/processed/                    # Masks & results
ls -la data/reports/                     # Generated reports
# PDF/HTML reports: oil_spill_report_YYYYMMDDTHHMMZ.{pdf,html,txt}
# CV visualization: cv_viz_YYYYMMDDTHHMMZ.png
```

---

## 📊 Pipeline Steps Overview

| Step | Module | Input | Output | Env |
|------|--------|-------|--------|-----|
| **1** | CV Detection | SAR image (TIFF) | Binary oil mask (NPY) | mados → oilspill3 |
| **2** | Coordinates | SAR metadata | Lat/lon bounds | oilspill3 |
| **3** | Oil Analysis | Binary mask | Oil pixel count, area | oilspill3 |
| **4** | Simulation | Environmental data | Trajectory file (NetCDF) | oilspill3 |
| **5** | PG Classification | SAR + mask + trajectory | Classification + confidence | oilspill3 |
| **6** | NLP Validation | Incidents CSV + coordinates | Risk level + confidence | oilspill3 |
| **7** | Ensemble Decision | CV + PG + NLP scores | Final prediction + confidence | oilspill3 |
| **8** | Report Generation | All results | HTML/PDF/Text reports | oilspill3 |

---

## 📂 Output Files

### Generated During Pipeline Run

| File Type | Location | Purpose |
|-----------|----------|---------|
| **Binary Mask (NPY)** | `data/processed/*_oil_binary.npy` | Binary 0/1 mask for oil / generated by CV |
| **Multi-class Mask (TIFF)** | `data/processed/*_mask.tiff` | 15-class predictions from MariNeXt |
| **CV Visualization (PNG)** | `data/processed/visualizations/cv_viz_*.png` | Side-by-side SAR + oil overlay |
| **Trajectory (NetCDF)** | `data/processed/simulation_*.nc` | OpenDrift predicted oil drift |
| **Results JSON** | `data/processed/cv_results.json`, `pipeline_results.json` | Structured results |
| **HTML Report** | `data/reports/oil_spill_report_*.html` | Web-viewable report |
| **PDF Report** | `data/reports/oil_spill_report_*.pdf` | Professional PDF (requires fpdf2/reportlab) |
| **Text Report** | `data/reports/oil_spill_report_*.txt` | Plain text summary |

---

## 🔧 Troubleshooting

### Issue: CV subprocess fails
**Symptoms:** "Conda run: command not found" or "mados environment not found"

**Solutions:**
1. Verify mados environment exists: `conda env list | grep mados`
2. Reinstall mados: `conda create -n mados python=3.8 && conda activate mados && pip install -r requirements_mados.txt`
3. Check Windows PATH includes conda: `where conda`

### Issue: PDF generation fails
**Symptoms:** "PDF report saved as HTML" - PDF tools not installed

**Solution:**
```bash
conda activate oilspill3
pip install fpdf2
# or
pip install reportlab
```

### Issue: Oil mask is all 1s or all 0s
**Symptoms:** 100% or 0% detection, high/low confidence

**Debugging:**
```python
import numpy as np
mask = np.load("data/processed/*_oil_binary.npy")
print(f"Unique values: {np.unique(mask)}")
print(f"Oil percentage: {100 * mask.sum() / mask.size:.2f}%")
```

If issue persists, check [CV_DEBUG_GUIDE.md](CV_DEBUG_GUIDE.md)

### Issue: Environmental data download fails
**Symptoms:** "Environmental download failed" in logs

**Solutions:**
1. Check internet connection
2. Verify CMEMS/ERA5 services are up
3. Check coordinates are valid lat/lon
4. Try with CSV date range instead of auto-detected date

### Issue: NLP validation has no matches
**Symptoms:** "NLP validation: 0 database matches"

**Causes:**
- Incident CSV may be empty or wrong format
- Detected location/time not in database
- CSV requires columns: `latitude`, `longitude`, `date`

---

## 🔐 Configuration

**File:** `config.json`

Key settings:
```json
{
  "cv_model": {
    "fallback_enabled": false,
    "darkness_threshold": -18.0
  },
  "data": {
    "outputs_dir": "data/processed/",
    "downloads_dir": "data/processed/"
  },
  "ensemble": {
    "cv_weight": 0.4,
    "pg_weight": 0.3,
    "nlp_weight": 0.3
  }
}
```

---

## 📋 Ensemble Weights (Updated)

**Current (Active):**
- **CV Detection:** 0.40 (43% of decision)
- **Physics-Guided:** 0.30 (33% of decision)
- **NLP Validation:** 0.30 (33% of decision)
- **Random Forest:** 0.00 (REMOVED)

**Rationale:**
- CV favored (highest confidence from model)
- PG provides physics constraints
- NLP provides historical context
- RF removed (low individual performance)

---

## 📚 References

- **CV Model:** [MariNeXt](https://github.com/geo-smart/marinext-oss) - Oil spill detection
- **Simulation:** [OpenDrift](https://github.com/OpenDrift/opendrift) - Trajectory modeling
- **Environmental Data:** CMEMS, ERA5
- **Original Dataset:** Sentinel-1 SAR imagery

---

## ✨ Recent Changes

- **2026-03-05:** 
  - ✓ Removed RF classifier (weight=0)
  - ✓ Updated ensemble to CV/PG/NLP only
  - ✓ Added CV side-by-side visualization (cv_utils.py)
  - ✓ Enhanced PDF report generation (reportlab/fpdf2 support)
  - ✓ Created this comprehensive documentation

---

## 📞 Support

For issues or questions, check:
1. [CV_DEBUG_GUIDE.md](CV_DEBUG_GUIDE.md) - CV detection debugging
2. [TESTING_RESULTS.md](TESTING_RESULTS.md) - Test result documentation
3. [QUICK_INFERENCE_SETUP.md](QUICK_INFERENCE_SETUP.md) - CV setup
4. Pipeline logs: `logs/` directory

---

**End of Documentation**  
*For development or modifications, maintain backward compatibility with existing APIs*
