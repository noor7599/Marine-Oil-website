"""
CV Visualization Utilities
Creates visual outputs from computer vision detection results
"""

import numpy as np
import logging
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


def create_cv_visualization(
    sar_image_path: str,
    binary_mask_path: str,
    output_path: str,
    confidence: float = 0.0,
    oil_area_km2: float = 0.0,
    title: Optional[str] = None
) -> Optional[str]:
    """
    Create side-by-side visualization of original SAR image and oil detection mask.
    This is the fallback 2-panel version used when multiclass TIFF is not available.
    
    Parameters:
    -----------
    sar_image_path : str
        Path to original SAR TIFF image
    binary_mask_path : str
        Path to binary oil mask (NPY file)
    output_path : str
        Path where PNG visualization will be saved
    confidence : float
        CV confidence score (0-1) for annotation
    oil_area_km2 : float
        Estimated oil area in km² for annotation
    title : str, optional
        Custom title; defaults to timestamp
    
    Returns:
    --------
    str or None
        Path to saved visualization PNG, or None if creation failed
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        from matplotlib.colors import ListedColormap
        import rasterio
    except ImportError as e:
        logger.error(f"Failed to import required visualization libraries: {e}")
        return None
    
    try:
        # Load SAR image
        with rasterio.open(sar_image_path) as src:
            if src.count >= 3:
                # Multi-band: use first 3 as RGB
                sar_data = src.read([1, 2, 3]).astype(np.float32)
                sar_data = np.transpose(sar_data, (1, 2, 0))
            else:
                # Single or dual band: use first band
                sar_data = src.read(1).astype(np.float32)
        
        # Normalize SAR data to 0-1 range
        if sar_data.ndim == 3:
            sar_normalized = np.zeros_like(sar_data)
            for i in range(sar_data.shape[2]):
                band = sar_data[:, :, i]
                vmin, vmax = np.percentile(band[np.isfinite(band)], [2, 98])
                sar_normalized[:, :, i] = np.clip((band - vmin) / (vmax - vmin + 1e-8), 0, 1)
        else:
            vmin, vmax = np.percentile(sar_data[np.isfinite(sar_data)], [2, 98])
            sar_normalized = np.clip((sar_data - vmin) / (vmax - vmin + 1e-8), 0, 1)
            # Convert to RGB (grayscale)
            sar_normalized = np.stack([sar_normalized] * 3, axis=2)
        
        # Load binary mask
        if str(binary_mask_path).endswith('.npy'):
            binary_mask = np.load(binary_mask_path).astype(np.uint8)
        else:
            # Try to load as image
            from PIL import Image
            img = Image.open(binary_mask_path).convert('L')
            binary_mask = (np.array(img) > 127).astype(np.uint8)
        
        # Create figure with side-by-side subplots
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        
        # Plot 1: Original SAR image
        if sar_normalized.ndim == 3 and sar_normalized.shape[2] == 3:
            axes[0].imshow(sar_normalized)
        else:
            axes[0].imshow(sar_normalized[:, :, 0], cmap='gray')
        axes[0].set_title('Original SAR Image', fontsize=12, fontweight='bold')
        axes[0].axis('off')
        
        # Plot 2: SAR with oil mask overlay
        if sar_normalized.ndim == 3 and sar_normalized.shape[2] == 3:
            axes[1].imshow(sar_normalized)
        else:
            axes[1].imshow(sar_normalized[:, :, 0], cmap='gray')
        
        # Overlay oil mask in red
        oil_overlay = np.zeros((*binary_mask.shape, 4))
        oil_overlay[binary_mask == 1, :] = [1, 0, 0, 0.6]  # Red with 60% transparency
        axes[1].imshow(oil_overlay)
        axes[1].set_title('Oil Detection Mask', fontsize=12, fontweight='bold')
        axes[1].axis('off')
        
        # Add annotations
        if title is None:
            title = f"CV Detection - {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}"
        
        fig.suptitle(title, fontsize=14, fontweight='bold', y=0.98)
        
        # Add text annotations at bottom
        anno_text = f"Confidence: {confidence*100:.1f}% | Oil Area: {oil_area_km2:.2f} km²"
        fig.text(0.5, 0.02, anno_text, ha='center', fontsize=10, style='italic')
        
        # Add colorbar legend
        red_patch = mpatches.Patch(color=[1, 0, 0, 0.6], label='Oil Detection')
        fig.legend(handles=[red_patch], loc='lower center', ncol=1, bbox_to_anchor=(0.5, -0.02))
        
        # Tight layout
        plt.tight_layout(rect=[0, 0.05, 1, 0.96])
        
        # Save figure
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(str(output_path_obj), dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        logger.info(f"CV visualization saved: {output_path_obj}")
        return str(output_path_obj)
        
    except Exception as e:
        logger.error(f"Failed to create CV visualization: {e}")
        import traceback
        traceback.print_exc()
        return None


def create_cv_4panel_visualization(
    sar_image_path: str,
    multiclass_mask_path: str,
    binary_mask_path: str,
    output_path: str,
    confidence: float = 0.0,
    oil_area_km2: float = 0.0,
    title: Optional[str] = None
) -> Optional[str]:
    """
    Create professional 4-panel visualization showing CV detection pipeline.
    
    Layout:
    - Top-left: Original SAR image (grayscale)
    - Top-right: Detected classes (multi-class TIFF with colormap)
    - Bottom-left: Overlay (SAR + class colors)
    - Bottom-right: Oil binary mask (white=oil, black=non-oil)
    
    Parameters:
    -----------
    sar_image_path : str
        Path to original SAR TIFF image
    multiclass_mask_path : str
        Path to multi-class TIFF from MariNeXt (15 classes)
    binary_mask_path : str
        Path to binary oil mask (NPY file)
    output_path : str
        Path where PNG will be saved
    confidence : float
        CV confidence score (0-1) for annotation
    oil_area_km2 : float
        Estimated oil area in km² for annotation
    title : str, optional
        Custom title
    
    Returns:
    --------
    str or None
        Path to saved visualization PNG
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        from matplotlib.colors import ListedColormap
        import rasterio
    except ImportError as e:
        logger.error(f"Failed to import visualization libraries: {e}")
        return None
    
    try:
        # Load SAR image (original)
        with rasterio.open(sar_image_path) as src:
            if src.count >= 3:
                sar_data = src.read([1, 2, 3]).astype(np.float32)
                sar_data = np.transpose(sar_data, (1, 2, 0))
            else:
                sar_data = src.read(1).astype(np.float32)
        
        # Normalize SAR to 0-1
        if sar_data.ndim == 3:
            sar_normalized = np.zeros_like(sar_data)
            for i in range(sar_data.shape[2]):
                band = sar_data[:, :, i]
                valid = np.isfinite(band)
                if valid.any():
                    vmin, vmax = np.percentile(band[valid], [2, 98])
                    sar_normalized[:, :, i] = np.clip((band - vmin) / (vmax - vmin + 1e-8), 0, 1)
        else:
            valid = np.isfinite(sar_data)
            if valid.any():
                vmin, vmax = np.percentile(sar_data[valid], [2, 98])
                sar_normalized = np.clip((sar_data - vmin) / (vmax - vmin + 1e-8), 0, 1)
            else:
                sar_normalized = np.zeros_like(sar_data)
        
        # Convert to grayscale if RGB
        if sar_normalized.ndim == 3:
            sar_gray = np.mean(sar_normalized, axis=2)
        else:
            sar_gray = sar_normalized
        
        # Load multi-class mask
        with rasterio.open(multiclass_mask_path) as src:
            multiclass_data = src.read(1).astype(np.uint8)
        
        # Load binary mask
        if str(binary_mask_path).endswith('.npy'):
            binary_mask = np.load(binary_mask_path).astype(np.uint8)
        else:
            from PIL import Image
            img = Image.open(binary_mask_path).convert('L')
            binary_mask = (np.array(img) > 127).astype(np.uint8)
        
        # Create colormap for 15 classes (MariNeXt classes)
        colors = [
            [0, 0, 0],         # 0: Background (black)
            [0.2, 0.2, 0.8],   # 1: Marine Debris (blue)
            [0.5, 0.2, 0.5],   # 2: Dense Sargassum (purple)
            [0.2, 0.8, 0.8],   # 3: Natural Organic Material (cyan)
            [1, 0.5, 0],       # 4: Ship (orange)
            [0, 0.8, 0.2],     # 5: Marine Water (green)
            [1, 0, 0],         # 6: Oil Spill (RED)
            [0.8, 0, 0.8],     # 7: Sediment-Laden Water (magenta)
            [1, 1, 0],         # 8: Foam (yellow)
            [0, 0.5, 0.8],     # 9: Turbid Water (blue-green)
            [0.8, 0.8, 0],     # 10: Shallow Water (olive)
            [0.8, 0.4, 0.2],   # 11: Waves & Wakes (brown)
            [0.6, 0.6, 1],     # 12: Oil Platform (light blue)
            [0.4, 0.8, 0.6],   # 13: Kelp (teal)
            [0.8, 0.6, 0.8]    # 14: Sex foam (light purple)
        ]
        cmap_classes = ListedColormap(colors)
        
        # Create overlay: multiclass data with transparency
        overlay = np.zeros((*multiclass_data.shape, 3))
        for class_id in np.unique(multiclass_data):
            mask = multiclass_data == class_id
            overlay[mask] = colors[int(class_id)]
        
        # Create 2x2 figure
        fig, axes = plt.subplots(2, 2, figsize=(14, 12))
        
        # Panel 1: Original SAR
        axes[0, 0].imshow(sar_gray, cmap='gray')
        axes[0, 0].set_title('Original SAR Image', fontsize=12, fontweight='bold')
        axes[0, 0].axis('off')
        
        # Panel 2: Detected Classes
        im = axes[0, 1].imshow(multiclass_data, cmap=cmap_classes, vmin=0, vmax=14)
        axes[0, 1].set_title('Detected Classes (MariNeXt)', fontsize=12, fontweight='bold')
        axes[0, 1].axis('off')
        
        # Panel 3: Overlay
        axes[1, 0].imshow(sar_gray, cmap='gray', alpha=0.6)
        axes[1, 0].imshow(overlay, alpha=0.6)
        axes[1, 0].set_title('SAR + Class Overlay', fontsize=12, fontweight='bold')
        axes[1, 0].axis('off')
        
        # Panel 4: Oil Binary
        axes[1, 1].imshow(binary_mask, cmap='gray')
        axes[1, 1].set_title('Oil Binary (White=Oil)', fontsize=12, fontweight='bold')
        axes[1, 1].axis('off')
        
        # Add overall title
        if title is None:
            title = f"Computer Vision Detection - {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}"
        fig.suptitle(title, fontsize=14, fontweight='bold', y=0.98)
        
        # Add annotation panel
        info_text = f"Confidence: {confidence*100:.1f}% | Oil Area: {oil_area_km2:.2f} km² | Oil Pixels: {binary_mask.sum():,}"
        fig.text(0.5, 0.02, info_text, ha='center', fontsize=10, style='italic', 
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
        
        plt.tight_layout(rect=[0, 0.05, 1, 0.96])
        
        # Save
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(str(output_path_obj), dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        logger.info(f"4-panel CV visualization saved: {output_path_obj}")
        return str(output_path_obj)
        
    except Exception as e:
        logger.error(f"Failed to create 4-panel visualization: {e}")
        import traceback
        traceback.print_exc()
        return None


def create_simulation_gif(
    trajectory_files: list,
    output_path: str,
    coastline_data: Optional[dict] = None,
    title: Optional[str] = None,
    fps: int = 2
) -> Optional[str]:
    """
    Create animated GIF of oil drift simulation using particle trajectories.
    
    Parameters:
    -----------
    trajectory_files : list
        List of trajectory NetCDF files (time-sequence) or single simulation file
    output_path : str
        Path to save GIF
    coastline_data : dict, optional
        Dict with 'lon' and 'lat' arrays for coastline overlay
    title : str, optional
        Title for animation (default: "Oil Spill Movement Over Time")
    fps : int
        Frames per second (default: 2)
    
    Returns:
    --------
    str or None
        Path to saved GIF
    """
    try:
        import matplotlib.pyplot as plt
        import xarray as xr
        import numpy as np
        import pandas as pd
        from PIL import Image
        import io
    except ImportError as e:
        logger.error(f"Failed to import required libraries for GIF: {e}")
        return None
    
    try:
        # Handle both single file and list of files
        if isinstance(trajectory_files, str):
            trajectory_files = [trajectory_files]
        
        # Find the simulation NetCDF file
        sim_file = None
        for f in trajectory_files:
            if isinstance(f, str) and f.endswith('.nc'):
                sim_file = f
                break
        
        if not sim_file:
            # Try to find it in the directory
            import glob
            traj_dir = Path(trajectory_files[0]).parent if trajectory_files else Path('.')
            nc_files = list(glob.glob(str(traj_dir / '*simulation*.nc')))
            if nc_files:
                sim_file = nc_files[-1]  # Get most recent
        
        if not sim_file:
            logger.error("No simulation NetCDF file found in trajectory_files")
            return None
        
        # Load simulation data
        logger.info(f"Loading simulation data from: {sim_file}")
        ds = xr.open_dataset(sim_file)
        
        # Extract data
        lon_data = ds['lon'].values  # Shape: (trajectory, time)
        lat_data = ds['lat'].values   # Shape: (trajectory, time)
        time_data = ds['time'].values  # Shape: (time,)
        
        # Handle mass_oil data if available
        if 'mass_oil' in ds:
            mass_oil_data = ds['mass_oil'].values  # Shape: (trajectory, time)
            has_mass = True
        else:
            has_mass = False
            logger.warning("No mass_oil data in simulation file, using trajectory index for coloring")
        
        # Handle status if available
        if 'status' in ds:
            status_data = ds['status'].values
            has_status = True
        else:
            has_status = False
        
        num_particles = lon_data.shape[0]
        num_timesteps = lon_data.shape[1]

        # OpenDrift time can be 2D (trajectory, time); use one timestamp per step for labels
        if time_data.ndim == 2:
            if time_data.shape[0] == num_particles and time_data.shape[1] == num_timesteps:
                time_per_step = time_data[0, :]
            else:
                time_per_step = time_data[:, 0] if time_data.shape[1] == num_particles else time_data[0, :]
        else:
            time_per_step = time_data

        logger.info(f"Simulation has {num_particles} particles and {num_timesteps} time steps")
        
        # Calculate map bounds
        mask = ~(np.isnan(lon_data) | np.isnan(lat_data))
        if np.any(mask):
            lon_min, lon_max = np.nanmin(lon_data), np.nanmax(lon_data)
            lat_min, lat_max = np.nanmin(lat_data), np.nanmax(lat_data)
            # Add 5% buffer
            lon_buffer = (lon_max - lon_min) * 0.05
            lat_buffer = (lat_max - lat_min) * 0.05
            lon_min -= lon_buffer
            lon_max += lon_buffer
            lat_min -= lat_buffer
            lat_max += lat_buffer
        else:
            logger.error("No valid particle data found")
            return None
        
        # Prepare frames
        frames = []
        
        logger.info("Generating GIF frames...")
        
        for time_idx in range(num_timesteps):
            try:
                # Create figure
                fig, ax = plt.subplots(figsize=(12, 10))
                
                # Get current positions
                lons = lon_data[:, time_idx]
                lats = lat_data[:, time_idx]
                
                # Filter valid particles
                if has_status:
                    status = status_data[:, time_idx]
                    valid = (status == 0) & (~np.isnan(lons)) & (~np.isnan(lats))
                else:
                    valid = (~np.isnan(lons)) & (~np.isnan(lats))
                
                num_valid = np.sum(valid)
                
                # Get data for valid particles
                valid_lons = lons[valid]
                valid_lats = lats[valid]
                
                # Color by oil mass if available
                if has_mass:
                    mass = mass_oil_data[:, time_idx]
                    valid_mass = mass[valid]
                    
                    # Only color if there's variation in mass
                    if np.max(valid_mass) > np.min(valid_mass):
                        scatter = ax.scatter(valid_lons, valid_lats, 
                                           c=valid_mass, s=50, cmap='YlOrRd',
                                           alpha=0.7, edgecolors='darkred', linewidth=0.5)
                        cbar = plt.colorbar(scatter, ax=ax)
                        cbar.set_label('Oil Mass (kg)', fontsize=11)
                    else:
                        scatter = ax.scatter(valid_lons, valid_lats, 
                                           c='red', s=50, alpha=0.7, 
                                           edgecolors='darkred', linewidth=0.5)
                else:
                    scatter = ax.scatter(valid_lons, valid_lats, 
                                       c='red', s=50, alpha=0.7, 
                                       edgecolors='darkred', linewidth=0.5)
                
                # Plot coastline if provided
                if coastline_data and 'lon' in coastline_data and 'lat' in coastline_data:
                    ax.plot(coastline_data['lon'], coastline_data['lat'], 
                           'k-', linewidth=2, label='Coastline', zorder=1)
                
                # Formatting
                ax.set_xlim(lon_min, lon_max)
                ax.set_ylim(lat_min, lat_max)
                ax.set_xlabel('Longitude (°E)', fontsize=12)
                ax.set_ylabel('Latitude (°N)', fontsize=12)
                ax.set_title(title or 'Oil Spill Movement Over Time', 
                           fontsize=14, fontweight='bold')
                ax.grid(True, alpha=0.3, linestyle='--')
                
                # Add time info box
                time_str = pd.Timestamp(time_per_step[time_idx]).strftime('%Y-%m-%d %H:%M:%S UTC')
                info_text = f'Time: {time_str}\nParticles: {num_valid}'
                ax.text(0.02, 0.98, info_text, transform=ax.transAxes,
                       fontsize=11, verticalalignment='top',
                       bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.9, pad=0.8))
                
                # Save to PIL Image
                buf = io.BytesIO()
                plt.savefig(buf, dpi=100, bbox_inches='tight')
                buf.seek(0)
                
                # Load image carefully
                img = Image.open(buf)
                img.load()  # Force load while file is open
                img_copy = img.copy()  # Make a copy
                frames.append(img_copy)
                buf.close()
                
                plt.close(fig)
                
                logger.debug(f"Frame {time_idx + 1}/{num_timesteps} created ({num_valid} particles)")
                
            except Exception as e:
                logger.warning(f"Could not create frame {time_idx}: {e}")
                continue
        
        ds.close()
        
        if not frames:
            logger.error("No frames generated for GIF")
            return None
        
        # Save as GIF
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            frames[0].save(
                str(output_path_obj),
                save_all=True,
                append_images=frames[1:],
                duration=int(1000 / fps),  # milliseconds per frame
                loop=0,
                optimize=False
            )
            logger.info(f"Simulation GIF saved: {output_path_obj} ({len(frames)} frames at {fps} fps)")
            return str(output_path_obj)
        except Exception as e:
            logger.error(f"Failed to save GIF: {e}")
            return None
        
    except Exception as e:
        logger.error(f"Failed to create simulation GIF: {e}")
        import traceback
        traceback.print_exc()
        return None


def export_simulation_for_viewing(
    nc_path: str,
    output_dir: str,
    map_title: Optional[str] = None,
    csv_max_rows: Optional[int] = 100000,
) -> Optional[dict]:
    """
    Save the simulation .nc in easy-to-view forms while keeping the original .nc.
    Produces: (1) static trajectory map PNG, (2) CSV of trajectory data.
    """
    try:
        import xarray as xr
        import pandas as pd
        import matplotlib.pyplot as plt
    except ImportError as e:
        logger.error(f"Required libraries for simulation export not found: {e}")
        return None

    nc_path = Path(nc_path)
    if not nc_path.exists() or nc_path.suffix.lower() != '.nc':
        logger.warning(f"Simulation file not found or not .nc: {nc_path}")
        return None

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    base_name = nc_path.stem
    map_png_path = out / f"{base_name}_trajectories_map.png"
    csv_path = out / f"{base_name}_trajectories.csv"

    try:
        ds = xr.open_dataset(str(nc_path))

        if 'lon' not in ds or 'lat' not in ds:
            logger.warning("Simulation .nc missing lon/lat variables")
            ds.close()
            return None

        lon_data = np.asarray(ds['lon'].values)
        lat_data = np.asarray(ds['lat'].values)
        time_var = ds.get('time', None)
        time_vals = np.asarray(time_var.values) if time_var is not None else np.arange(lat_data.shape[1])
        time_vals = np.atleast_1d(time_vals)

        if lon_data.shape[0] < lon_data.shape[1]:
            n_traj, n_time = lon_data.shape[0], lon_data.shape[1]
        else:
            n_time, n_traj = lon_data.shape[0], lon_data.shape[1]
            lon_data = lon_data.T
            lat_data = lat_data.T

        # OpenDrift stores time as 2D (trajectory, time) - same shape as lon/lat. Index by time step, not trajectory.
        if time_vals.ndim == 2:
            if time_vals.shape[0] == n_traj and time_vals.shape[1] == n_time:
                # (trajectory, time): timestamp for step t_idx is time_vals[0, t_idx]
                time_per_step = [time_vals[0, t] for t in range(n_time)]
            elif time_vals.shape[0] == n_time and time_vals.shape[1] == n_traj:
                # (time, trajectory): timestamp for step t_idx is time_vals[t_idx, 0]
                time_per_step = [time_vals[t, 0] for t in range(n_time)]
            else:
                time_per_step = [time_vals[min(t, len(time_vals) - 1)] for t in range(n_time)]
        else:
            # 1D time: one value per output step
            n_time_vals = len(time_vals)
            time_per_step = [time_vals[min(t, n_time_vals - 1)] if n_time_vals > 0 else t for t in range(n_time)]

        # Time variable may have fewer elements than lon/lat time dimension; cap index
        n_time_vals = len(time_per_step)
        
        # Optional physical variables from OpenDrift output
        has_status = 'status' in ds
        has_mass = 'mass_oil' in ds
        has_age = 'age_seconds' in ds
        has_visc = 'viscosity' in ds
        has_dens = 'density' in ds
        has_water = 'water_fraction' in ds

        def _align_shape(var_name: str) -> Optional[np.ndarray]:
            """Load variable and align its shape with lon/lat if possible."""
            if var_name not in ds:
                return None
            arr = np.asarray(ds[var_name].values)
            if arr.shape == lon_data.shape:
                return arr
            if arr.T.shape == lon_data.shape:
                return arr.T
            # Fallback: cannot align reliably
            logger.warning(f"Variable '{var_name}' has unexpected shape {arr.shape}; expected {lon_data.shape}")
            return None

        status_data = _align_shape('status') if has_status else None
        mass_data = _align_shape('mass_oil') if has_mass else None
        age_data = _align_shape('age_seconds') if has_age else None
        visc_data = _align_shape('viscosity') if has_visc else None
        dens_data = _align_shape('density') if has_dens else None
        water_data = _align_shape('water_fraction') if has_water else None

        # Static map: all trajectories as lines
        fig, ax = plt.subplots(figsize=(12, 10))
        step = max(1, n_traj // 500)
        for i in range(0, n_traj, step):
            lons = lon_data[i, :]
            lats = lat_data[i, :]
            valid = np.isfinite(lons) & np.isfinite(lats)
            if np.sum(valid) < 2:
                continue
            ax.plot(lons[valid], lats[valid], color='#c0392b', alpha=0.4, linewidth=0.8)
        ax.plot(lon_data[0, 0], lat_data[0, 0], 'ko', markersize=10, label='Release point', zorder=5)
        ax.set_xlabel('Longitude (°E)', fontsize=12)
        ax.set_ylabel('Latitude (°N)', fontsize=12)
        ax.set_title(map_title or f'Simulation trajectories – {base_name}', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.legend(loc='upper right')
        ax.set_aspect('equal', adjustable='box')
        plt.tight_layout()
        plt.savefig(str(map_png_path), dpi=150, bbox_inches='tight')
        plt.close(fig)
        logger.info(f"Simulation map saved: {map_png_path}")
        
        # CSV: aggregated trajectory per time step
        # One row per output time, representing the mean position and mean oil properties
        rows = []
        prev_lon = None
        prev_lat = None
        consecutive_stagnant = 0
        max_stagnant_steps = 3  # Stop if position unchanged for 3+ consecutive timesteps
        position_change_threshold = 0.0001  # degrees (~11 m at equator)
        
        for t_idx in range(n_time):
            # Use correct timestamp for this time step (handles 2D time from OpenDrift)
            time_val = time_per_step[t_idx] if t_idx < n_time_vals else time_per_step[-1]
            try:
                ts = pd.Timestamp(time_val)
                time_str = ts.strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                time_str = str(time_val)

            lons_t = lon_data[:, t_idx]
            lats_t = lat_data[:, t_idx]
            valid = np.isfinite(lons_t) & np.isfinite(lats_t)
            num_valid_particles = int(np.sum(valid))
            
            if not np.any(valid):
                logger.debug(f"No valid particles at timestep {t_idx}")
                consecutive_stagnant += 1
                if consecutive_stagnant >= max_stagnant_steps:
                    logger.warning(f"No valid particles for {consecutive_stagnant} consecutive steps. Stopping trajectory.")
                    break
                continue
            else:
                # Reset stagnation if we have particles again
                if num_valid_particles > 10:
                    consecutive_stagnant = 0

            # Aggregate over all valid particles at this time step
            mean_lon = float(np.nanmean(lons_t[valid]))
            mean_lat = float(np.nanmean(lats_t[valid]))
            
            # Check if position has changed AND we still have meaningful particle count
            if prev_lon is not None and prev_lat is not None:
                lon_delta = abs(mean_lon - prev_lon)
                lat_delta = abs(mean_lat - prev_lat)
                position_changed = (lon_delta > position_change_threshold) or (lat_delta > position_change_threshold)
                
                if not position_changed:
                    consecutive_stagnant += 1
                    logger.warning(
                        f"Timestep {t_idx}: Position unchanged (Δlon={lon_delta:.6f}, Δlat={lat_delta:.6f}). "
                        f"Valid particles: {num_valid_particles}. Stagnant for {consecutive_stagnant} steps. Skipping."
                    )
                    
                    # Stop simulation if stuck for too long
                    if consecutive_stagnant >= max_stagnant_steps:
                        logger.warning(
                            f"Position stagnant for {max_stagnant_steps}+ timesteps. "
                            f"Stopping trajectory output to prevent duplicate rows."
                        )
                        break
                    continue
                else:
                    consecutive_stagnant = 0  # Reset stagnation counter
            else:
                consecutive_stagnant = 0

            row = {
                'trajectory': 0,          # single aggregated trajectory
                'time': time_str,
                'status': 0.0,            # default if status not available
                'age_seconds': np.nan,
                'lon': mean_lon,
                'lat': mean_lat,
                'mass_oil': np.nan,
                'viscosity': np.nan,
                'density': np.nan,
                'water_fraction': np.nan,
            }

            if status_data is not None:
                status_t = status_data[:, t_idx][valid]
                # Use the most common status among valid particles
                if status_t.size > 0:
                    values, counts = np.unique(status_t, return_counts=True)
                    row['status'] = float(values[np.argmax(counts)])

            if age_data is not None:
                age_t = age_data[:, t_idx][valid]
                if age_t.size > 0:
                    row['age_seconds'] = float(np.nanmean(age_t))

            if mass_data is not None:
                mass_t = mass_data[:, t_idx][valid]
                if mass_t.size > 0:
                    row['mass_oil'] = float(np.nanmean(mass_t))

            if visc_data is not None:
                visc_t = visc_data[:, t_idx][valid]
                if visc_t.size > 0:
                    row['viscosity'] = float(np.nanmean(visc_t))

            if dens_data is not None:
                dens_t = dens_data[:, t_idx][valid]
                if dens_t.size > 0:
                    row['density'] = float(np.nanmean(dens_t))

            if water_data is not None:
                water_t = water_data[:, t_idx][valid]
                if water_t.size > 0:
                    row['water_fraction'] = float(np.nanmean(water_t))

            rows.append(row)
            
            # Update tracking for next iteration
            prev_lon = mean_lon
            prev_lat = mean_lat

            if csv_max_rows and len(rows) >= csv_max_rows:
                break

        if rows:
            df = pd.DataFrame(rows)
            with open(str(csv_path), 'w', encoding='utf-8') as f:
                f.write("# Aggregated trajectory per output time step (mean over all particles).\n")
            df.to_csv(str(csv_path), index=False, mode='a')
            logger.info(f"Simulation CSV saved: {csv_path} ({len(df)} rows)")
        else:
            csv_path = None

        ds.close()

        return {
            'nc_path': str(nc_path),
            'map_png': str(map_png_path),
            'csv': str(csv_path) if csv_path else None,
        }
    except Exception as e:
        logger.error(f"Failed to export simulation for viewing: {e}")
        import traceback
        traceback.print_exc()
        return None
