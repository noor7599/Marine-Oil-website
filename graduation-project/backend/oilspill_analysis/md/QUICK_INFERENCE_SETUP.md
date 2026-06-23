# Quick Inference Setup Guide

## Overview
The Oil Spill Analysis Pipeline supports two CV models:
1. **MariNeXt** (Primary) - Deep learning model via `quick_inference.py`
2. **Fallback** (Automatic) - Intensity-based detection using SAR statistics

> ⚠ Make sure you are running inside the `mados` conda environment when you
> attempt to import or run the MariNeXt model – the required packages are
> installed in that environment and the helper script will warn you otherwise.

## Current Status
✅ **System Status**: Pipeline is operational with fallback CV model
- Primary MariNeXt model: ❌ Dependencies not installed
- Fallback model: ✅ Active and working

## Quick Inference Setup

### Path Configuration
The `quick_inference.py` location is configured in `config.json`:
```json
{
  "cv_model": {
    "quick_inference_path": "D:\\L4 S1\\Graduation Project in AI (I)\\cv\\mados",
    "model_type": "marinext",
    "fallback_enabled": true,
    "darkness_threshold": -18.0
  }
}
```

### Required Dependencies for MariNeXt
To use the full MariNeXt model, install these packages:

```bash
pip install mmcv mmseg-custom marinext torch torchvision
```

**Dependency Details:**
- `mmcv` - OpenMMLab Computer Vision Foundation  
- `mmseg-custom` - Image Segmentation models  
- `marinext` - Oil spill detection model  
- `torch`, `torchvision` - Deep learning framework  

### Current Fallback Behavior
**When quick_inference is not available:**
- Uses intensity-based detection  
- Threshold: -18.0 dB (configurable)  
- Output: Binary mask of detected oil pixels  
- Performance: Fast, lightweight, no GPU required  

### How It Works

1. **On Pipeline Start (Step 0)**
   - `cv_model.py` attempts to load quick_inference from configured path
   - If successful → Uses MariNeXt deep learning model
   - If failed → Falls back to intensity-based detection

2. **Oil Detection Check**
   - Analyzes CV model output
   - If oil detected (>0% pixels) → Continues to full analysis
   - If no oil detected (0% pixels) → Skips to final decision

3. **Result**
   - Binary mask saved as `.npy` file
   - Visualization PNG created
   - Detection percentage included in results

## Installation Steps

### Option 1: Using AutoInstall Script
```bash
cd src
python install_cv_dependencies.py
```

### Option 2: Manual Installation
```bash
# Create virtual environment (optional but recommended)
python -m venv cv_env
cv_env\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install mmcv mmseg-custom
pip install marinext torch torchvision -f https://download.pytorch.org/whl/torch_stable.html
```

### Option 3: Using conda
```bash
conda create -n cv_env python=3.10
conda activate cv_env
conda install pytorch torchvision torchaudio pytorch-cuda=11.8 -c pytorch -c nvidia
pip install mmcv mmseg-custom marinext
```

## Verification

### Test Import
```python
python test_quick_inference.py
```

Expected output if successful:
```
✓ Added to sys.path
✓ SUCCESS: quick_inference imported!
✓ run_inference function found!
```

### Test Pipeline
```bash
python main.py --step 0
```

Expected logged messages:
```
Loading quick_inference from: D:\L4 S1\Graduation Project in AI (I)\cv\mados
✓ Successfully imported quick_inference module (MariNeXt available)
```

## Troubleshooting

### Issue: "No module named 'mmcv'"
**Solution**: Install mmcv
```bash
pip install mmcv-full
```

### Issue: CUDA/GPU compatibility
**Solution**: Install CPU-only version
```bash
pip install torch torchvision -f https://download.pytorch.org/whl/cpu/torch_stable.html
```

### Issue: marinext module not found
**Solution**: Install from source
```bash
git clone https://github.com/yourusername/marinext.git
cd marinext
pip install -e .
```

## Configuration Options

### Modify Detection Threshold
Edit `config.json`:
```json
"cv_model": {
  "darkness_threshold": -18.0
}
```

Lower values = more sensitive, higher = more conservative

### Disable Fallback
```json
"cv_model": {
  "fallback_enabled": false
}
```

Note: If quick_inference unavailable and fallback disabled, CV step will fail.

## Pipeline Flow with CV Models

```
SAR Image Input
      ↓
[STEP 0] CV Inference
      ├→ Try MariNeXt
      │   └→ Success? Use ML model
      │   └→ Failed? Try fallback
      └→ Use Intensity-based fallback
      ↓
Oil Detected? (>0% pixels)
      ├→ YES: Continue to Steps 1-6 (full analysis)
      └→ NO: Skip to final decision (NO OIL DETECTED)
```

## Performance Notes

| Model | Speed | Accuracy | GPU Required | Notes |
|-------|-------|----------|--------------|-------|
| MariNeXt | ~5-10s/image | High | Optional | Deep learning model |
| Fallback | ~2-3s/image | Medium | No | Fine for quick assessment |

## Support

For issues or questions about quick_inference integration:
1. Check `config.json` path configuration
2. Run `test_quick_inference.py` diagnostic script
3. Review pipeline logs in `logs/` directory
4. Check CUDA/PyTorch compatibility if GPU errors occur

---
**Last Updated**: 2026-02-24
**Pipeline Version**: 1.0 with CV Integration
