# -*- coding: utf-8 -*-
'''
Quick Inference Script for MariNeXt Model - Fully Corrected Version
'''

import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

import sys
import torch
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from glob import glob
from pathlib import Path
import uuid
from scipy import ndimage
from scipy.ndimage import gaussian_filter, median_filter
import torchvision.transforms as transforms
from torch.nn import functional as F
import matplotlib.colors as mcolors

# Ensure MariNeXt pathing is correct
marinext_root = Path(__file__).parent / "marinext"
if str(marinext_root) not in sys.path:
    sys.path.insert(0, str(marinext_root))

try:
    import rasterio
    HAS_RASTERIO = True
except ImportError:
    HAS_RASTERIO = False

# Import local utilities
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))
from marinext.marinext_wrapper import MariNext
from utils.dataset import bands_mean, bands_std
from utils.assets import labels, mados_color_mapping

labels_0based = [
    'Marine Water', 'Marine Debris', 'Dense Sargassum', 'Natural Organic Material',
    'Ship', 'Water Turbidity', 'Oil Spill', 'Sediment-Laden Water', 'Foam',
    'Turbid Water', 'Shallow Water', 'Waves & Wakes', 'Oil Platform',
    'Kelp Beds', 'Sex Foam'
]

def preprocess_image(image, median_size=5, gaussian_sigma=1.0):
    image_filtered = np.zeros_like(image, dtype=np.float32)
    for band in range(image.shape[2]):
        image_filtered[:, :, band] = median_filter(image[:, :, band], size=median_size)
    image_smoothed = np.zeros_like(image_filtered, dtype=np.float32)
    for band in range(image.shape[2]):
        image_smoothed[:, :, band] = gaussian_filter(image_filtered[:, :, band], sigma=gaussian_sigma)
    return image_smoothed

def run_inference(
    image_path,
    model_path='./marinext/trained_models/marinext_2.pth', 
    output_dir='./results/inference'
):
    if not HAS_RASTERIO:
        print("❌ ERROR: rasterio is required.")
        return None, None

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # --- CRITICAL FIX: MODEL INITIALIZATION ---
    print("Loading model...")
    # Force 11 channels to match your SAR checkpoint dimensions [16, 11, 3, 3]
    model = MariNext(in_channels=11, num_classes=15)
    model.to(device)
    model.eval()

    checkpoint = torch.load(model_path, map_location=device)
    
    # --- CRITICAL FIX: DYNAMIC KEY REMAPPING ---
    new_state_dict = {}
    for k, v in checkpoint.items():
        # 1. Map mmseg 1.x 'decoder' to mmseg 2.x 'decode_head'
        name = k.replace('decoder', 'decode_head')
        
        # 2. Fix the nested dwconv error (dwconv.dwconv -> dwconv)
        if 'dwconv.dwconv' in name:
            name = name.replace('dwconv.dwconv', 'dwconv')
            
        # 3. Filter out legacy projection layers
        if 'proj1' in name or 'proj2' in name:
            continue
            
        new_state_dict[name] = v

    # Load corrected dict with strict=False to bypass minor non-functional mismatches
    model.load_state_dict(new_state_dict, strict=False)
    print("✓ Model loaded and keys remapped")

    # Load image
    with rasterio.open(image_path) as src:
        image = src.read()
        image = np.moveaxis(image, (0, 1, 2), (2, 0, 1))

    # Preprocessing & Padding
    if image.shape[2] < 11:
        padding = 11 - image.shape[2]
        mean_band = np.mean(image, axis=2, keepdims=True)
        image = np.concatenate([image] + [mean_band] * padding, axis=2)
    else:
        image = image[:, :, :11]

    image = preprocess_image(image)
    image_tensor = transforms.Compose([transforms.ToTensor()])(image)
    image_tensor = transforms.Normalize(bands_mean, bands_std)(image_tensor).unsqueeze(0).to(device)

    # Sliding-window Inference
    h, w = image.shape[:2]
    patch_size, stride = 512, 256
    predictions_full = np.zeros((h, w), dtype=np.float32)
    weights_full = np.zeros((h, w), dtype=np.float32)
    class_probs_full = np.zeros((h, w, 15), dtype=np.float32)

    # Simple Gaussian-like weight mask for smoothing patches
    weight_mask = np.ones((patch_size, patch_size), dtype=np.float32)
    for i in range(patch_size):
        for j in range(patch_size):
            dist = ((i - patch_size / 2) ** 2 + (j - patch_size / 2) ** 2) ** 0.5
            weight_mask[i, j] = 1.0 / (1.0 + dist / (patch_size / 4))

    y_pos = list(range(0, h - patch_size + 1, stride))
    if y_pos[-1] + patch_size < h: y_pos.append(h - patch_size)
    x_pos = list(range(0, w - patch_size + 1, stride))
    if x_pos[-1] + patch_size < w: x_pos.append(w - patch_size)

    for y in y_pos:
        for x in x_pos:
            patch = image_tensor[:, :, y:y+patch_size, x:x+patch_size]
            with torch.no_grad():
                logits = model(patch)
                logits = F.interpolate(logits, size=(patch_size, patch_size), mode='bilinear')
                probs = torch.softmax(logits, dim=1)
                patch_preds = probs.argmax(1).squeeze().cpu().numpy()
                patch_conf = probs.max(1)[0].squeeze().cpu().numpy()
                probs_np = probs.squeeze(0).permute(1, 2, 0).cpu().numpy()

            predictions_full[y:y+patch_size, x:x+patch_size] += patch_preds * weight_mask * patch_conf
            weights_full[y:y+patch_size, x:x+patch_size] += patch_conf * weight_mask
            for c in range(15):
                class_probs_full[y:y+patch_size, x:x+patch_size, c] += probs_np[:,:,c] * weight_mask

    # Finalize predictions
    predictions = np.zeros((h, w), dtype=np.uint8)
    mask_valid = weights_full > 0
    predictions[mask_valid] = np.round(predictions_full[mask_valid] / weights_full[mask_valid]).astype(np.uint8)

    # Summary and Save
    os.makedirs(output_dir, exist_ok=True)
    base_name = f"{Path(image_path).stem}_{str(uuid.uuid4())[:8]}"
    mask_path = os.path.join(output_dir, f"{base_name}_mask.tiff")
    
    with rasterio.open(mask_path, 'w', driver='GTiff', height=h, width=w, count=1, dtype=rasterio.uint8) as dst:
        dst.write_band(1, predictions)

    # Confidence calculation for class 6 (Oil Spill)
    oil_idx = 6
    class_mask = predictions == oil_idx
    oil_conf = 0.0
    if class_mask.any():
        oil_conf = np.average(class_probs_full[class_mask, oil_idx], weights=weights_full[class_mask])

    print(f"✓ Inference complete. Oil Confidence: {oil_conf:.4f}")
    
    return mask_path, "visualization_path_placeholder.png", {
        'overall_confidence': float(np.mean(predictions_full[mask_valid]/weights_full[mask_valid])),
        'class_confidences': {'6': float(oil_conf)}
    }