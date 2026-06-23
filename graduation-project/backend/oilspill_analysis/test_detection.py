#!/usr/bin/env python
"""Simple smoke test for the CV wrapper module"""
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

from src.cv_model import run_cv_inference, extract_oil_pixels

# try running with a fake path to ensure graceful failure
path = 'nonexistent_image.tiff'
result = run_cv_inference(path, output_dir='outputs')

print("\n=== RESULTS ===")
print(result)

# make sure we always get a dictionary and expected keys even if file missing
assert isinstance(result, dict)
assert 'status' in result

# if mask path is returned and exists, try extraction
if result.get('mask_path') and os.path.exists(result['mask_path']):
    metrics = extract_oil_pixels(result['mask_path'])
    assert 'oil_pixels' in metrics
    print("extract_oil_pixels succeeded:", metrics)

print("test_detection completed")
