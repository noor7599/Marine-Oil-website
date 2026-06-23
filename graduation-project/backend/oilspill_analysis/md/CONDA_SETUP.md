# Conda Environment Setup Guide

This project requires **ONE conda environment** (Python 3.9) with both core pipeline and CV model dependencies.

---

## Quick Setup (Recommended)

```bash
# 1. Create environment with Python 3.9
conda create -n oilspill python=3.9 -y

# 2. Activate it
conda activate oilspill

# 3. Navigate to project
cd "d:\L4 S1\Graduation Project in AI (I)\Integration layer\oilspill_analysis"

# 4. Install all dependencies (core + CV + NLP)
pip install -r requirements.txt

# 5. Verify
python -c "import src.pipeline; import torch; import mmcv; print('✓ All OK')"

# 6. Run the pipeline
python main.py
```

That's it! No need for multiple environments.

---

## Run the Pipeline

```bash
# Activate environment
conda activate oilspill

# Run complete end-to-end workflow
python main.py

# Run specific steps
python main.py --step 0  # CV inference (MariNeXt)
python main.py --step 7  # NLP validation
python main.py --step 6  # Final decision

# With custom image
python main.py --image data/raw/your_image.tiff
```

---

## Troubleshooting

### Installation Fails
**Error**: Dependency conflicts during `pip install -r requirements.txt`

**Solution**:
```bash
# Clean Python cache
pip cache purge

# Reinstall with force
pip install --force-reinstall --no-cache-dir -r requirements.txt
```

### NumPy/OpenCV Conflict
**Error**: `opencv-python requires numpy>=2; but you have numpy 1.26.4`

**Solution**: Already fixed in requirements.txt. If you still see this:
```bash
pip install numpy==1.26.4 --force-reinstall
pip install -r requirements.txt
```

### Slow Installation (PyTorch)
PyTorch can take several minutes to download (~1GB). Be patient or use:
```bash
pip install -r requirements.txt --quiet
```

### Memory Issues
If installation fails due to memory:
```bash
# Install separately to avoid holding everything in memory
pip install numpy==1.26.4
pip install pandas scipy scikit-learn
pip install rasterio Pillow
pip install opendrift netCDF4 xarray
pip install torch torchvision  # Large, installs separately
pip install mmcv mmsegmentation opencv-python
```

---

## Environment Variables (Optional for Data Download)

```bash
# Set ERA5 Climate Data Store API key
set CDS_API_KEY=your_key_here

# Set CMEMS ocean data credentials
set CMEMS_USERNAME=your_username
set CMEMS_PASSWORD=your_password

# Test with:
python main.py --step 2
```

---

## What's Included?

✅ **Core Pipeline**
- opendrift (ocean simulation)
- rasterio (SAR image processing)
- cdsapi/copernicusmarine (data download)
- scikit-learn (RF classifier)

✅ **Computer Vision (MariNeXt)**
- torch, torchvision (neural networks)
- mmcv, mmsegmentation (image segmentation)
- opencv-python (image processing)

✅ **NLP Validation**
- geopy (geographic distance)
- reportlab (PDF generation)

---

## Single Command to Get Started

```bash
conda create -n oilspill python=3.9 -y && \
conda activate oilspill && \
cd "d:\L4 S1\Graduation Project in AI (I)\Integration layer\oilspill_analysis" && \
pip install -r requirements.txt && \
python main.py
```
