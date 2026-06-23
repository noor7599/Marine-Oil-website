# Integration Pipeline (Oil Spill Analysis) — Team Run Guide

This guide describes how to **set up environments**, **configure paths**, **add Copernicus credentials (ERA5 + CMEMS)**, and **run the end‑to‑end integration pipeline**.

The pipeline orchestrator is:

- `src/main/main_pipeline.py` (class `HybridPipeline`)

It runs:

- **CV (MariNeXt)** via a **separate conda env** (`mados`) using a subprocess runner
- **Coordinate extraction + environmental downloads**
- **OpenDrift simulation**
- **PG rules**
- **NLP incident validation (optional, via CSV)**
- **Ensemble decision**
- **Reports + saved run folder**

---

## 1) Prerequisites

- **Windows 10/11**
- **Miniconda/Anaconda installed** (`conda` available in terminal)
- **Git LFS not required** (unless your team stores large models that way)
- Optional but recommended: **CUDA-capable GPU** for faster CV inference

Repository root in this guide:

- `oilspill_analysis/`

---

## 2) Create the conda environments

You need **two** environments:

- **`oilspill3`**: runs the main integration pipeline + downloads + simulation + PG + NLP
- **`mados`**: runs MariNeXt (mmcv/mmseg/torch stack) invoked by subprocess

### 2.1 Create `oilspill3` (Python 3.9)

From `oilspill_analysis/`:

```bash
conda create -n oilspill3 python=3.9 -y
conda activate oilspill3
python -m pip install --upgrade pip
pip install -r requirements_oilspill3.txt
```

### 2.2 Create `mados` (Python 3.10+)

From `oilspill_analysis/`:

```bash
conda create -n mados python=3.10 -y
conda activate mados
python -m pip install --upgrade pip
pip install -r requirements_mados.txt
```

Notes:

- `requirements_mados.txt` pins `torch==1.13.1` + `mmcv==1.7.0` etc. If your GPU/CUDA differs, align torch wheels accordingly.
- The integration pipeline calls CV through `CVSubprocessRunner(conda_env="mados")`, so the env **name must match** (or change `--cv-env` at runtime).

---

## 3) Define project paths (config + CV quick inference path)

Pipeline config lives at:

- `oilspill_analysis/config.json`

Key path fields:

- `data.raw_dir`, `data.processed_dir` (relative paths are relative to repo root)
- `cv_model.quick_inference_path` (absolute path to MariNeXt wrapper workspace)

Open `config.json` and set:

- `cv_model.quick_inference_path` to the path that contains your MariNeXt “quick inference” entrypoint expected by your `cv_subprocess.py` implementation.

Example (Windows):

```json
"cv_model": {
  "quick_inference_path": "D:\\path\\to\\cv\\mados",
  "model_type": "marinext",
  "fallback_enabled": true,
  "darkness_threshold": -18.0
}


---

## 4) Copernicus credentials (ERA5 + CMEMS)

Environmental downloads happen in `src/data_downloader.py` (called by `src/main/main_pipeline.py`).

### 4.1 ERA5 (Copernicus Climate Data Store / CDS)

You need a CDS account + API key.

- Create an account at: CDS portal (Climate Data Store)
- Generate your API key (CDS profile page)

#### Create the `.cdsapirc` file (Windows)

Create this file:

- `%USERPROFILE%\.cdsapirc`

Contents:

```text
url: https://cds.climate.copernicus.eu/api/v2
key: <uid>:<api-key>
```

Validation (inside `oilspill3` env):

```bash
conda activate oilspill3
python -c "import cdsapi; print('cdsapi ok')"
```

### 4.2 CMEMS (Copernicus Marine / CopernicusMarine client)

This repo uses `copernicusmarine` (see `requirements*.txt`).

#### Option A (recommended): interactive init

In `oilspill3`:

```bash
conda activate oilspill3
copernicusmarine login
```

Follow prompts for username/password.

#### Option B: store credentials in `config.json`

In `config.json`:

```json
"download": {
  "cmems_username": "YOUR_USERNAME",
  "cmems_password": "YOUR_PASSWORD",
  "cmems_dataset_id": "cmems_mod_glo_phy_my_0.083deg_P1D-m"
}
```

Security note:

- Prefer **environment variables** or `copernicusmarine login` over committing passwords into git.

---

## 5) Input data requirements

### 5.1 SAR image

You need a SAR GeoTIFF (or TIFF) compatible with:

- `rasterio.open(image_path)`
- `process_sar_image(...)` metadata extraction

The pipeline reads:

- raster pixel array (band 1)
- bounds/transform/metadata for coordinates and timestamps (best effort)

### 5.2 NLP incident database (optional but recommended)

Provide a CSV path to enable NLP validation:

- Use `--csv path\to\incidents.csv`

If `--csv` is not provided, the pipeline prints:

- `NLP skipped (no CSV provided)`

---

## 6) Run the integration pipeline (end-to-end)

Always run the main orchestrator in **`oilspill3`** (it will call CV in `mados` as a subprocess).

```bash
conda activate oilspill3
python "src/main/main_pipeline.py" --image "D:\path\to\sar_image.tif" --csv "D:\path\to\incidents.csv"
```

Optional flags:

- `--cv-env mados`: name of the CV conda env (default: `mados`)
- `--no-cv`: skip MariNeXt and use the threshold detector

Examples:

```bash
# Run without NLP
python "src/main/main_pipeline.py" --image "D:\data\sar.tif"

# Force no CV (threshold detector)
python "src/main/main_pipeline.py" --image "D:\data\sar.tif" --no-cv

# Custom CV env name
python "src/main/main_pipeline.py" --image "D:\data\sar.tif" --cv-env mados
```

---

## 7) Outputs (where to find results)

Each run creates a timestamped folder:

- `data/processed/runs/<timestamp>/`

Inside you’ll typically find:

- `pipeline_results.json`
- `cv_results.json` (if CV subprocess produced it and copy succeeded)
- `visualizations/` (CV panels, PG visuals, trajectory map/GIF exports)
- `reports/` (HTML/PDF reports; NLP PDF if generated)
- Simulation artifacts (`.nc`) in the run folder

---

## 8) Common issues and fixes

### 8.1 CV subprocess can’t find conda / env

Symptoms:

- CV stage fails immediately and pipeline falls back (or errors)

Fixes:

- Ensure `conda` is available in the shell that launches the pipeline
- Ensure the env exists: `conda env list`
- Ensure env name matches `--cv-env` (default `mados`)

### 8.2 ERA5 download fails (CDS)

Symptoms:

- Authentication errors from `cdsapi`

Fixes:

- Verify `%USERPROFILE%\.cdsapirc` exists and has correct `url` + `key`
- Confirm the API key is active and correct

### 8.3 CMEMS download fails

Fixes:

- Run `copernicusmarine login` in `oilspill3`
- Confirm dataset id in `config.json` (`download.cmems_dataset_id`)

### 8.4 Rasterio import issues

Fix:

```bash
conda activate oilspill3
pip install --upgrade rasterio
```

### 8.5 OpenDrift / netCDF errors

Fix:

```bash
conda activate oilspill3
pip install --upgrade opendrift netCDF4 xarray
```

---

## 9) Team conventions (recommended)

- **Do not commit secrets**
  - No CDS keys, CMEMS passwords, or `.cdsapirc` into git
- Keep a `.env` or internal password manager entry for credentials distribution
- Standardize env names across machines:
  - `oilspill3` (main)
  - `mados` (CV)

