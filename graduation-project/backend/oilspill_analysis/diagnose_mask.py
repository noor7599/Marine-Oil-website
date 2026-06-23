#!/usr/bin/env python
"""Diagnose the mask file content"""
import rasterio
import numpy as np

mask_path = r"data/raw/2023-03-18-00_00_2023-03-18-23_59_Sentinel-1_IW_VV+VH_VV_-_decibel_gamma0(zoomed)_c6490596_mask.tiff"

print(f"Analyzing: {mask_path}\n")

try:
    with rasterio.open(mask_path) as src:
        print(f"Profile: {src.profile}")
        print(f"Shape: {src.shape}")
        print(f"Data type: {src.dtypes}")
        print(f"Number of bands: {src.count}")
        
        for band_idx in range(1, src.count + 1):
            data = src.read(band_idx)
            print(f"\n--- Band {band_idx} ---")
            print(f"Shape: {data.shape}")
            print(f"Min value: {np.min(data)}")
            print(f"Max value: {np.max(data)}")
            print(f"Mean value: {np.mean(data):.4f}")
            print(f"Data type: {data.dtype}")
            
            # Count unique values
            unique_vals, counts = np.unique(data, return_counts=True)
            print(f"Unique values: {dict(zip(unique_vals[:10], counts[:10]))}")
            
            # Check if this is already a binary mask
            if set(unique_vals).issubset({0, 1, 255}):
                non_zero = np.sum(data > 0)
                print(f"Non-zero pixels: {non_zero} ({100*non_zero/data.size:.2f}%)")
                
            # Check pixel value ranges (for SAR data)
            percentiles = [0, 1, 5, 25, 50, 75, 95, 99, 100]
            print(f"Percentiles: {np.percentile(data, percentiles)}")
            
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
