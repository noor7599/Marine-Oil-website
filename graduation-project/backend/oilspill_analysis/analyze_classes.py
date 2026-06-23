#!/usr/bin/env python
"""Detailed mask analysis to identify oil class"""
import rasterio
import numpy as np
from pathlib import Path

mask_path = r"data/raw/2023-03-18-00_00_2023-03-18-23_59_Sentinel-1_IW_VV+VH_VV_-_decibel_gamma0(zoomed)_c6490596_mask.tiff"

print(f"Analyzing: {mask_path}\n")

try:
    with rasterio.open(mask_path) as src:
        data = src.read(1)
        
    print("=" * 60)
    print("CLASSIFICATION MASK ANALYSIS")
    print("=" * 60)
    print(f"Image shape: {data.shape}")
    print(f"Data type: {data.dtype}")
    print(f"Value range: {np.min(data)} to {np.max(data)}")
    print()
    
    # Count pixels per class
    unique_vals, counts = np.unique(data, return_counts=True)
    total_pixels = data.size
    
    print("Class Distribution:")
    print("-" * 60)
    for val, count in zip(unique_vals, counts):
        percentage = 100 * count / total_pixels
        print(f"Class {val:2d}: {count:10,d} pixels ({percentage:6.2f}%)")
    
    print("\n" + "=" * 60)
    print("HYPOTHESIS: Which class is OIL?")
    print("=" * 60)
    
    # Look for spatial patterns
    print(f"\nMost common class: {unique_vals[np.argmax(counts)]} ({np.max(counts)} pixels)")
    print(f"Least common class: {unique_vals[np.argmin(counts)]} ({np.min(counts)} pixels)")
    
    print("\nCommon classification schemes:")
    print("Option 1 (Binary): 0=No oil, 1=Oil")
    print("Option 2 (Multi): 1=Water, 2=Land, 3+=Oil types")
    print("Option 3 (Multi): 0=Background, 5=Water, 6=Oil, 7+=Other")
    
    print(f"\nBased on data, likely scenarios:")
    print(f"- Class 6 ({counts[np.where(unique_vals == 6)[0][0]]} pixels) could be OIL")
    print(f"- Class 5 ({counts[np.where(unique_vals == 5)[0][0]]} pixels) could be WATER (most common)")
    
    # Save a visualization
    print("\nTip: To identify which class is oil:")
    print("1. Check the original annotation/metadata for this file")
    print("2. Look at class 6 - it's much rarer than class 5 (typical for oil)")
    print("3. Test different class values to see which produces correct results")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
