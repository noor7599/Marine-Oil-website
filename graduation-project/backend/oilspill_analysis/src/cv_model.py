"""
Wrapper module for the MariNeXt computer vision model (quick_inference.py)
Provides a simple API that the pipeline can consume without knowing about the
heavy dependencies or the original script location.

The functions in this module will attempt to import and call
`mados/quick_inference.py` from the conda environment named **mados**.  If the
script cannot be found or the import fails the code will fall back to a very
simple intensity threshold detector so that the overall pipeline can still run
in environments where the full CV stack is not installed.

All paths are handled relative to the workspace / configuration so the
pipeline remains portable.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np

from config import get_config

logger = logging.getLogger(__name__)

# oil spill index used by the Marinext model (0-based as defined in quick_inference)
_OIL_CLASS_INDEX = 6


def _find_quick_inference_module() -> Optional[object]:
    """Locate and import the quick_inference module.

    The configuration key ``cv_model.quick_inference_path`` may be set to the
    directory containing ``quick_inference.py`` (normally the "mados" folder).
    If not provided the function will look for a sibling directory named
    ``mados`` relative to this file.  The path is added to ``sys.path`` so that
    a normal ``import quick_inference`` works.
    """
    cfg = get_config()
    qi_path = cfg.get('cv_model.quick_inference_path')
    if qi_path and os.path.exists(qi_path):
        path = qi_path
    else:
        # try local mados directory
        base = Path(__file__).parent.parent
        candidate = base / 'mados'
        if candidate.exists():
            path = str(candidate)
        else:
            return None
    if path not in sys.path:
        sys.path.insert(0, path)
    try:
        import quick_inference
        return quick_inference
    except ImportError as e:
        logger.warning(f"Failed to import quick_inference from {path}: {e}")
        return None


def _check_conda_env():
    env = os.environ.get('CONDA_DEFAULT_ENV')
    if env and env != 'mados':
        logger.warning(f"Current conda environment '{env}' does not match 'mados'. "
                       "Make sure you activate the correct environment before running.")


def extract_oil_pixels(binary_mask_path: str) -> Dict:
    """Load a binary mask and report basic metrics.

    Parameters
    ----------
    binary_mask_path : str
        Filepath to a numpy ``.npy`` file containing a {0,1} mask where 1 = oil.

    Returns
    -------
    dict
        Keys: ``oil_pixels``, ``total_pixels``, ``oil_percentage``.
    """
    arr = np.load(binary_mask_path)
    total = arr.size
    oil = int(arr.sum())
    pct = 100.0 * oil / total if total > 0 else 0.0
    return {
        'oil_pixels': oil,
        'oil_pixel_count': oil,  # alias for pipeline/reports
        'total_pixels': total,
        'oil_percentage': pct
    }


def _simple_threshold_detector(image_path: str, output_dir: str) -> Tuple[str, Dict]:
    """Fallback detector that thresholds the first band of the image.

    This is used when the full MariNeXt inference script is not importable.
    It writes a binary mask (.npy) to ``output_dir`` and returns the path plus
    statistics.
    """
    import rasterio

    logger.warning("Using simple intensity threshold detector (cv_model.fallback enabled)")
    thresh = get_config().get('cv_model.darkness_threshold', -18.0)

    with rasterio.open(image_path) as src:
        img = src.read(1).astype(np.float32)

    binary = (img < thresh).astype(np.uint8)
    base = Path(image_path).stem
    binary_path = os.path.join(output_dir, f"{base}_threshold_mask.npy")
    np.save(binary_path, binary)

    stats = extract_oil_pixels(binary_path)
    stats.update({'mask_path': binary_path, 'model_type': 'threshold'})
    return binary_path, stats


def run_cv_inference(image_path: str, output_dir: str = None) -> Dict:
    """Run the CV model on a single SAR TIFF and return results suitable for
    the pipeline.

    Parameters
    ----------
    image_path : str
        Path to the input SAR image (TIFF)
    output_dir : str, optional
        Directory where masks/visualizations are saved.  Defaults to the
        configured ``data.outputs_dir``.

    Returns
    -------
    dict
        ``status`` = "success" or "error";
        ``mask_path`` = path to binary ``.npy`` mask;
        ``oil_pixels`` / ``oil_percentage`` / ``detected`` / ``model_type`` etc.
    """
    if output_dir is None:
        output_dir = get_config().get('data.outputs_dir')
    os.makedirs(output_dir, exist_ok=True)

    _check_conda_env()

    qi = _find_quick_inference_module()
    if qi is None:
        # fall back immediately if script not available
        if get_config().get('cv_model.fallback_enabled', True):
            return _simple_threshold_detector(image_path, output_dir)
        else:
            return {'status': 'error', 'message': 'quick_inference module not found'}

    try:
        before = set(os.listdir(output_dir))
        result = qi.run_inference(image_path, output_dir=output_dir)
        # quick_inference now returns (mask_path, viz_path, confidences_dict) or (mask_path, viz_path) for backward compatibility
        if isinstance(result, tuple):
            if len(result) == 3:
                mask_path, _, confidences_dict = result
                oil_confidence = float(confidences_dict.get('class_confidences', {}).get('6', 0.0))
            else:
                mask_path = result[0] if result else None
                oil_confidence = None
        else:
            mask_path = result
            oil_confidence = None
    except Exception as exc:
        logger.warning(f"quick_inference.run_inference failed: {exc}")
        if get_config().get('cv_model.fallback_enabled', True):
            return _simple_threshold_detector(image_path, output_dir)
        else:
            return {'status': 'error', 'message': str(exc)}

    if mask_path is None or not os.path.exists(mask_path):
        # attempt to locate new mask file in directory
        after = set(os.listdir(output_dir))
        newfiles = after - before
        for f in newfiles:
            if f.endswith('_mask.tiff'):
                mask_path = os.path.join(output_dir, f)
                break

    if mask_path is None or not os.path.exists(mask_path):
        return {'status': 'error', 'message': 'mask file not produced'}

    # convert multi-class mask to binary and save as numpy
    import rasterio
    with rasterio.open(mask_path) as src:
        preds = src.read(1)
    
    print(f"[CV_MODEL] DEBUG - Multi-class mask analysis:")
    print(f"  Shape: {preds.shape}")
    print(f"  Unique values: {np.unique(preds)}")
    print(f"  Value range - Min: {np.min(preds)}, Max: {np.max(preds)}, Mean: {np.mean(preds):.2f}")
    print(f"  Oil class pixels (class {_OIL_CLASS_INDEX}): {int(np.sum(preds == _OIL_CLASS_INDEX))}")

    binary = (preds == _OIL_CLASS_INDEX).astype(np.uint8)
    
    print(f"[CV_MODEL] DEBUG - Binary mask analysis:")
    print(f"  Shape: {binary.shape}")
    print(f"  Unique values: {np.unique(binary)}")
    print(f"  Binary sum (oil pixels): {int(np.sum(binary))}")
    print(f"  Binary mean (oil percentage): {100.0 * np.mean(binary):.2f}%")
    bin_path = os.path.join(output_dir, Path(mask_path).stem + '_binary.npy')
    np.save(bin_path, binary)

    stats = extract_oil_pixels(bin_path)
    
    # DEBUGGING: Add detailed logging for mask sanity checks
    oil_pixels = stats['oil_pixels']
    total_pixels = stats['total_pixels']
    oil_pct = stats['oil_percentage']
    
    print(f"[CV_MODEL] DEBUG - Final mask statistics from cv_model.py:")
    print(f"  Oil pixels: {oil_pixels:,} / {total_pixels:,} = {oil_pct:.2f}%")
    print(f"  Unique values in binary mask: {np.unique(binary)}")
    
    if oil_pct > 95:
        logger.warning(f"[CV_MODEL] SUSPICIOUS: {oil_pct:.1f}% of image marked as oil! "
                      f"This may indicate a model issue. Check mask_path={bin_path}")
        print(f"[CV_MODEL] WARNING: All-or-most oil detection ({oil_pct:.1f}%) suggests possible model failure")
    elif oil_pct < 0.01 and oil_pixels > 0:
        print(f"[CV_MODEL] Note: Very small oil detection ({oil_pct:.4f}% = {oil_pixels} pixels)")
    elif oil_pixels == 0:
        print(f"[CV_MODEL] Note: No oil detected (0 pixels)")
    else:
        print(f"[CV_MODEL] Normal detection: {oil_pct:.2f}% of image")
    
    stats.update({'mask_path': bin_path,
                  'detected': stats['oil_pixels'] > 0,
                  'is_classification': True,
                  'model_type': 'marinext',
                  'confidence': oil_confidence if oil_confidence is not None else 0.0,
                  'status': 'success'})
    
    if oil_confidence is not None:
        print(f"[CV_MODEL] Using softmax oil class confidence: {oil_confidence:.4f}")
    
    return stats
