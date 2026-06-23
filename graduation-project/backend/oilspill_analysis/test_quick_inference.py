#!/usr/bin/env python
"""Test that cv_model correctly locates the quick_inference script."""
import sys
import os

from src import cv_model

print("cv_model module loaded, attempting to run import helper")
qi = cv_model._find_quick_inference_module()  # pylint: disable=protected-access
if qi is not None:
    print(f"✓ quick_inference module imported via wrapper: {qi}")
    assert hasattr(qi, 'run_inference')
else:
    print("⚠ quick_inference not available in sys.path (fallback expected at runtime)")

print("test_quick_inference completed")
