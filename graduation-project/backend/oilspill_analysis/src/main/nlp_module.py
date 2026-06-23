"""
NLP Module - Modified to accept file-based inputs from CV
"""

import json
from pathlib import Path
import numpy as np
from PIL import Image


def run_nlp_analysis(mask_image_path: str, confidence: float, cv_metadata: dict) -> dict:
    """
    Run NLP analysis on mask results
    
    Args:
        mask_image_path: Path to mask PNG/NPY from CV
        confidence: Confidence score from CV
        cv_metadata: Full CV metadata
    
    Returns:
        dict with NLP results
    """
    # Load mask image
    mask_path = Path(mask_image_path)
    
    if mask_path.suffix == '.npy':
        mask = np.load(mask_path)
    else:
        mask = np.array(Image.open(mask_path))
    
    # Example NLP logic: analyze detected region
    region_size = np.sum(mask)
    region_percentage = (region_size / mask.size) * 100 if mask.size > 0 else 0
    
    # Simple classification
    if region_percentage > 5:
        classification = "LARGE_SPILL"
    elif region_percentage > 1:
        classification = "MEDIUM_SPILL"
    elif region_percentage > 0.1:
        classification = "SMALL_SPILL"
    else:
        classification = "TRACE_SPILL"
    
    results = {
        "status": "success",
        "classification": classification,
        "region_percentage": round(region_percentage, 2),
        "cv_confidence": confidence,
        "risk_level": "HIGH" if region_percentage > 5 else "MEDIUM" if region_percentage > 1 else "LOW"
    }
    
    return results