"""
Visualization Module for Oil Spill Detection Pipeline
Handles simulation animations, CV visualizations, and map overlays
"""

import os
import json
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Tuple, Optional, List
from datetime import datetime

try:
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation, PillowWriter, FFMpegWriter
    from matplotlib.patches import Rectangle
    import matplotlib.patches as mpatches
except ImportError:
    plt = None
    FuncAnimation = None

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None

try:
    import rasterio
except ImportError:
    rasterio = None

logger = logging.getLogger(__name__)


def save_mask_as_png(
    mask_data: np.ndarray,
    output_path: str,
    geospatial_info: Optional[Dict] = None,
    title: str = "Oil Spill Mask"
) -> str:
    """
    Convert binary mask to colored PNG with transparency option
    
    Parameters:
    -----------
    mask_data : np.ndarray
        Binary mask (0 or 1)
    output_path : str
        Path to save PNG file
    geospatial_info : dict, optional
        Geospatial metadata (lat/lon bounds, timestamp, confidence)
    title : str
        Title for the image
    
    Returns:
    --------
    str
        Path to saved PNG file
    """
    if Image is None:
        logger.warning("PIL not available, skipping mask PNG creation")
        return ""
    
    try:
        # Normalize mask to 0-255
        mask_normalized = (mask_data.astype(np.float32) * 255).astype(np.uint8)
        
        # Create RGB image: black background, red/orange for detected oil
        height, width = mask_data.shape
        rgb_image = Image.new('RGB', (width, height), color='black')
        pixels = rgb_image.load()
        
        # Color detected pixels orange/red
        for i in range(height):
            for j in range(width):
                if mask_data[i, j] > 0:
                    # Orange color for oil (RGB: 255, 165, 0)
                    pixels[j, i] = (255, 165, 0)
        
        # Add semi-transparent overlay option by creating RGBA
        rgb_image = rgb_image.convert('RGB')
        
        # Create output directory if needed
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Save image
        rgb_image.save(output_path, quality=95)
        
        logger.info(f"Mask PNG saved: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Error saving mask PNG: {e}")
        return ""


def create_cv_detection_visualization(
    sar_image: np.ndarray,
    mask_data: np.ndarray,
    output_path: str,
    confidence: float = 0.0,
    detected_area_km2: float = 0.0,
    coordinates: Optional[Dict] = None,
    timestamp: Optional[str] = None
) -> str:
    """
    Create side-by-side visualization of SAR image and detection mask
    
    Parameters:
    -----------
    sar_image : np.ndarray
        Original SAR image (normalized to 0-1)
    mask_data : np.ndarray
        Binary mask of detected oil
    output_path : str
        Path to save visualization PNG
    confidence : float
        Detection confidence score (0-1)
    detected_area_km2 : float
        Detected area in km²
    coordinates : dict, optional
        Bounding box coordinates (lat_min, lat_max, lon_min, lon_max)
    timestamp : str, optional
        Timestamp of detection
    
    Returns:
    --------
    str
        Path to saved visualization
    """
    if plt is None or Image is None:
        logger.warning("Matplotlib/PIL not available, skipping CV visualization")
        return ""
    
    try:
        # Create figure with two subplots
        fig, axes = plt.subplots(1, 2, figsize=(14, 6), dpi=100)
        fig.suptitle("Oil Spill Detection - SAR Analysis", fontsize=16, fontweight='bold')
        
        # Left: Original SAR image
        ax_sar = axes[0]
        im_sar = ax_sar.imshow(sar_image, cmap='gray', aspect='auto')
        ax_sar.set_title("Original SAR Image (VV Backscatter)", fontsize=12)
        ax_sar.set_xlabel("Pixel Column")
        ax_sar.set_ylabel("Pixel Row")
        plt.colorbar(im_sar, ax=ax_sar, label="Backscatter (dB)")
        
        # Right: SAR with mask overlay
        ax_mask = axes[1]
        # Create colored overlay
        mask_colored = np.zeros((*mask_data.shape, 3))
        mask_colored[:, :] = np.stack([sar_image, sar_image, sar_image], axis=2)  # Base SAR
        mask_colored[mask_data > 0] = [1.0, 0.6, 0.0]  # Orange for detected oil
        
        ax_mask.imshow(mask_colored, aspect='auto')
        ax_mask.set_title("Detection Overlay (Orange = Oil Spill)", fontsize=12)
        ax_mask.set_xlabel("Pixel Column")
        ax_mask.set_ylabel("Pixel Row")
        
        # Add bounding box if coordinates available
        if coordinates and 'lat_min' in coordinates:
            # Get image shape to create bounding box
            h, w = mask_data.shape
            # Create simple bounding box around detected region
            detected_pixels = np.where(mask_data > 0)
            if len(detected_pixels[0]) > 0:
                y_min, y_max = detected_pixels[0].min(), detected_pixels[0].max()
                x_min, x_max = detected_pixels[1].min(), detected_pixels[1].max()
                
                # Draw bounding box on both axes
                for ax in [ax_sar, ax_mask]:
                    rect = Rectangle((x_min, y_min), x_max - x_min, y_max - y_min,
                                   linewidth=2, edgecolor='cyan', facecolor='none')
                    ax.add_patch(rect)
        
        # Add text annotations
        textstr = f"Confidence: {confidence:.1%}\nArea: {detected_area_km2:.2f} km²"
        if timestamp:
            textstr += f"\nTime: {timestamp}"
        
        fig.text(0.5, 0.02, textstr, ha='center', fontsize=10,
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        # Save figure
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"CV detection visualization saved: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Error creating CV visualization: {e}")
        import traceback
        traceback.print_exc()
        return ""


def create_simulation_map_overlay(
    mask_data: np.ndarray,
    trajectory_data: Optional[Dict] = None,
    output_path: str = "",
    coordinates: Optional[Dict] = None,
    wind_speed: float = 0.0,
    current_speed: float = 0.0
) -> str:
    """
    Create static map showing initial oil location and simulated spread
    
    Parameters:
    -----------
    mask_data : np.ndarray
        Initial oil spill mask
    trajectory_data : dict, optional
        Simulation trajectory results
    output_path : str
        Path to save map PNG
    coordinates : dict, optional
        Bounding box (lat_min, lat_max, lon_min, lon_max)
    wind_speed : float
        Wind speed at time of detection (m/s)
    current_speed : float
        Current speed at time of detection (m/s)
    
    Returns:
    --------
    str
        Path to saved map
    """
    if plt is None:
        logger.warning("Matplotlib not available, skipping simulation map")
        return ""
    
    try:
        fig, ax = plt.subplots(figsize=(12, 10), dpi=100)
        
        # Show initial oil spill location
        ax.imshow(mask_data, cmap='Reds', alpha=0.7, aspect='auto')
        
        # Add coastline simulation (simple contour)
        h, w = mask_data.shape
        ax.axvline(x=0, color='brown', linewidth=3, label='Coastline (simulated)')
        
        # Add wind/current indicators
        if wind_speed > 0 or current_speed > 0:
            ax.arrow(w * 0.9, h * 0.1, w * 0.05, 0, head_width=h*0.02,
                    head_length=w*0.02, fc='blue', ec='blue', label='Wind direction')
            ax.arrow(w * 0.9, h * 0.2, 0, h * 0.05, head_width=w*0.02,
                    head_length=h*0.02, fc='green', ec='green', label='Current direction')
        
        # Add text annotations
        ax.set_xlabel("X Coordinate (pixels)", fontsize=11)
        ax.set_ylabel("Y Coordinate (pixels)", fontsize=11)
        ax.set_title("Oil Spill Simulation Map", fontsize=14, fontweight='bold')
        
        info_text = f"Initial Location\nWind: {wind_speed:.1f} m/s\nCurrent: {current_speed:.1f} m/s"
        ax.text(0.02, 0.98, info_text, transform=ax.transAxes,
               fontsize=10, verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        
        ax.legend(loc='upper right')
        ax.grid(alpha=0.3)
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"Simulation map saved: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Error creating simulation map: {e}")
        return ""


def create_simulation_animation(
    trajectory_nc_file: str,
    mask_data: np.ndarray,
    output_path: str = "",
    fps: int = 10,
    format: str = "mp4"
) -> str:
    """
    Create animated visualization of oil spill trajectory simulation
    
    Parameters:
    -----------
    trajectory_nc_file : str
        Path to NetCDF file with trajectory data
    mask_data : np.ndarray
        Initial oil spill mask
    output_path : str
        Path to save animation
    fps : int
        Frames per second for animation
    format : str
        Output format ('mp4', 'gif')
    
    Returns:
    --------
    str
        Path to saved animation
    """
    if plt is None:
        logger.warning("Matplotlib not available, skipping animation creation")
        return ""
    
    try:
        logger.info(f"Creating simulation animation from {trajectory_nc_file}")
        
        # Try to load trajectory data
        try:
            import xarray as xr
            ds = xr.open_dataset(trajectory_nc_file)
            
            # Extract positions if available
            if 'lon' in ds and 'lat' in ds:
                lons = ds['lon'].values
                lats = ds['lat'].values
                times = ds['time'].values if 'time' in ds else None
            else:
                logger.warning("No lon/lat in trajectory file, creating placeholder animation")
                lons = None
                lats = None
                times = None
        except Exception as e:
            logger.warning(f"Could not load trajectory data: {e}, creating placeholder")
            lons = None
            lats = None
            times = None
        
        # Create figure and animation
        fig, ax = plt.subplots(figsize=(10, 8), dpi=100)
        
        # Show initial mask
        ax.imshow(mask_data, cmap='Reds', alpha=0.7, aspect='auto')
        ax.set_xlabel("Longitude (pixels)")
        ax.set_ylabel("Latitude (pixels)")
        ax.set_title("Oil Spill Trajectory Simulation", fontsize=14, fontweight='bold')
        
        # If trajectory data available, add particle paths
        frame_count = 1
        if lons is not None and len(lons.shape) > 1:
            frame_count = lons.shape[0]
            
            # Plot subset of particle trajectories
            n_particles = min(100, lons.shape[1])  # Show max 100 particles for clarity
            for i in range(0, n_particles, max(1, n_particles // 20)):
                if not np.isnan(lons[0, i]):
                    ax.plot(lons[:, i], lats[:, i], alpha=0.5, linewidth=0.5)
        
        ax.grid(alpha=0.3)
        ax.legend(['Initial spill', 'Particle trajectories'], loc='upper right')
        
        # Create output directory
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Save as static frame (animation creation requires video codec)
        # For now, save as high-quality PNG
        static_path = output_path.replace('.mp4', '.png').replace('.gif', '.png')
        plt.tight_layout()
        plt.savefig(static_path, dpi=150, bbox_inches='tight')
        
        logger.info(f"Simulation visualization saved: {static_path}")
        logger.info(f"Note: Full animation requires FFmpeg. Saved static frame instead.")
        
        plt.close()
        return static_path
        
    except Exception as e:
        logger.error(f"Error creating simulation animation: {e}")
        import traceback
        traceback.print_exc()
        return ""


def save_results_summary(
    results_dict: Dict,
    output_path: str
) -> str:
    """
    Save visualization results summary as JSON
    
    Parameters:
    -----------
    results_dict : dict
        Dictionary with visualization paths and metadata
    output_path : str
        Path to save JSON summary
    
    Returns:
    --------
    str
        Path to saved file
    """
    try:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results_dict, f, indent=2, default=str)
        
        logger.info(f"Visualization summary saved: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Error saving visualization summary: {e}")
        return ""
