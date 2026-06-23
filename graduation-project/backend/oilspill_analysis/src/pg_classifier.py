"""
Physics-Guided Oil Spill Classifier (Rule-Based)
Notebook 4: PG Classifier
"""

import os
import json
import math
import logging
import numpy as np
from dataclasses import dataclass, asdict
from typing import Tuple, Dict, Optional
from datetime import datetime

import cv2
from scipy import ndimage
from netCDF4 import Dataset
import rasterio

logger = logging.getLogger(__name__)


def _ensure_binary_mask(mask: np.ndarray) -> np.ndarray:
    """
    Ensure mask is a 2D binary uint8 array with values {0,1}.
    Accepts probability/uint8/boolean masks and converts safely.
    """
    if mask is None:
        raise ValueError("Mask is None")
    m = np.asarray(mask)
    if m.ndim != 2:
        # Some pipelines may pass (H, W, 1) or similar
        m = np.squeeze(m)
    if m.ndim != 2:
        raise ValueError(f"Expected 2D mask, got shape {m.shape}")
    # Robust binarization: any positive value is treated as foreground
    m_bin = (m > 0).astype(np.uint8)
    return m_bin


def _sar_to_db_if_needed(sar_image: np.ndarray) -> np.ndarray:
    """
    Convert SAR to dB *only if* it appears to be in linear (or normalized linear) scale.
    Heuristic: if values are mostly non-negative and max is small (<= ~5), treat as linear.
    If it already contains typical dB negatives, leave as-is.
    """
    if sar_image is None:
        raise ValueError("SAR image is None")
    sar = np.asarray(sar_image).astype(np.float32, copy=False)

    finite = np.isfinite(sar)
    if not np.any(finite):
        raise ValueError("SAR image contains no finite values")

    vmin = float(np.nanmin(sar))
    vmax = float(np.nanmax(sar))

    # Already dB-like: contains negatives with a reasonable dynamic range
    if vmin < -1.0:
        return sar

    # Likely linear/normalized (e.g. 0..1 or 0..3)
    if vmin >= 0.0 and vmax <= 5.0:
        return 10.0 * np.log10(np.maximum(sar, 0.0) + 1e-8)

    # Ambiguous: leave unchanged, but caller can inspect debug logs
    return sar


@dataclass
class GeometricFeatures:
    """Geometric properties of detected spot in SAR image"""
    area: float  # pixels
    perimeter: float  # pixels
    orientation: float  # degrees (0-180)
    elongation_ratio: float  # major_axis / minor_axis
    compactness: float  # (4π * area) / (perimeter²)


@dataclass
class RadiometricFeatures:
    """Radiometric (intensity) properties from SAR image"""
    mean_intensity: float  # dB
    std_intensity: float  # dB
    min_intensity: float  # dB
    max_intensity: float  # dB


@dataclass
class RuleResults:
    """Results of physics-based rule checks"""
    darkness_pass: bool
    smoothness_pass: bool
    shape_pass: bool
    alignment_pass: bool
    all_pass: bool


class ClassifierConfig:
    """Configuration for physics-guided classifier"""
    
    def __init__(self):
        # Thresholds adjusted for gamma0 data (typically -30 to +5 dB)
        # Previous: -15.0 dB (too strict for gamma0)
        self.DARKNESS_THRESHOLD = -10.0  # dB - relaxed for gamma0
        
        # Oil on water can have 2-5 dB variation - increased from 2.0 for real oil
        self.SMOOTHNESS_THRESHOLD = 4.5  # dB - accommodate real oil texture
        
        # Relaxed shape thresholds for real slick boundaries
        self.ELONGATION_THRESHOLD = 1.5  # was 1.8
        self.COMPACTNESS_THRESHOLD = 0.3  # was 2.0 - accept jagged slicks
        self.ALIGNMENT_TOLERANCE = 90.0  # degrees - drift prediction uncertainty
        self.POSITION_MATCH_TOLERANCE_KM = 10.0
        self.DRIFT_TIME_WINDOW = (1, 2)  # hours
        
        # Rule weights: alignment is most reliable (physics-based)
        self.rule_weights = {
            'darkness': 0.25,      # Least reliable (varies with processing)
            'smoothness': 0.20,    # Moderate reliability
            'shape': 0.20,         # Least reliable (many look-alikes)
            'alignment': 0.35      # Physics-based drift direction match (binary pass/fail)
        }

        # Default scoring mode: "sigmoid" (existing soft scoring)
        # Options: "binary", "sigmoid", "fuzzy"
        self.scoring_mode = "fuzzy"

        # Fuzzy rule configuration for trapezoidal membership functions.
        # Bounds are intentionally generous; they can be tuned without
        # changing the scoring logic.
        self.RULE_CONFIG = {
            "darkness": {
                # SAR intensity in dB (lower = darker = better)
                "low": -5.0,       # too bright → score 0
                "high": -25.0,     # extremely dark
                "ideal_low": -12.0,
                "ideal_high": -18.0,
                "inverted": True,  # lower values are better
            },
            "smoothness": {
                # Std-dev of intensity in dB (lower = smoother = better)
                # Real oil can have 2-5 dB variation - updated bounds
                "low": 6.0,        # very rough
                "high": 0.5,       # very smooth
                "ideal_low": 4.0,  # optimal oil texture
                "ideal_high": 1.5,
                "inverted": True,  # lower values are better
            },
            "shape_elongation": {
                # Elongation ratio (higher = more elongated)
                # Realistic bounds for real oil slick morphology
                "low": 1.0,        # circular / compact
                "high": 7.0,       # very elongated
                "ideal_low": 1.5,  # moderately elongated
                "ideal_high": 4.5,
                "inverted": False,  # higher is better
            },
            "shape_compactness": {
                # Compactness: (4πA)/P² – moderate values preferred
                # Real oil slicks are very jagged with complex boundaries
                "low": 0.05,       # very jagged (realistic oil slicks)
                "high": 0.8,       # smooth shape
                "ideal_low": 0.15, # typical oil texture
                "ideal_high": 0.5,
                "inverted": False,
            },
            "alignment": {
                # Angular difference in degrees (0° = perfectly aligned, 90° = tolerance)
                # Inverted: lower difference = better score
                # For inverted fuzzy: high < ideal_high < ideal_low < low
                "low": 100.0,      # fully false at 100°+ (at/beyond tolerance)
                "high": 0.0,       # perfectly aligned at 0° (fully true)
                "ideal_low": 60.0, # acceptable alignment up to 60° (good confidence)
                "ideal_high": 15.0, # excellent alignment below 15° (high confidence)
                "inverted": True,  # lower angular difference is better
            },
        }


def extract_geometric_features(binary_mask: np.ndarray) -> GeometricFeatures:
    """
    Extract geometric features from binary mask
    
    Parameters:
    -----------
    binary_mask : np.ndarray
        Binary image with detected spot
    
    Returns:
    --------
    GeometricFeatures
        Geometric properties of the spot
    """
    # Ensure binary {0,1} mask, then convert to {0,255} for OpenCV stability
    m = _ensure_binary_mask(binary_mask)
    mask_cv = (m * 255).astype(np.uint8, copy=False)

    # Light cleanup to reduce jagged/noisy boundaries that explode perimeter.
    # Keep it minimal (3x3) to avoid changing geometry significantly.
    kernel = np.ones((3, 3), dtype=np.uint8)
    mask_clean = cv2.morphologyEx(mask_cv, cv2.MORPH_CLOSE, kernel, iterations=1)
    mask_clean = cv2.morphologyEx(mask_clean, cv2.MORPH_OPEN, kernel, iterations=1)

    if logger.isEnabledFor(logging.DEBUG):
        uniques = np.unique(m)
        logger.debug(
            "Mask stats: shape=%s dtype=%s unique=%s area_px=%d",
            m.shape, m.dtype, uniques.tolist(), int(m.sum())
        )
        logger.debug(
            "Mask cleanup: area_px_before=%d area_px_after=%d",
            int(np.count_nonzero(mask_cv)), int(np.count_nonzero(mask_clean))
        )

    # Find contours (external only)
    contours, _ = cv2.findContours(mask_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        raise ValueError("No contours found in binary mask")
    
    # Get largest contour (the spot)
    contour = max(contours, key=cv2.contourArea)
    
    # Calculate basic properties (pixel units)
    area = float(cv2.contourArea(contour))
    perimeter_raw = float(cv2.arcLength(contour, True))

    # Smooth/simplify contour slightly to reduce pixel staircasing, which can
    # inflate perimeter and collapse compactness.
    eps = max(1.0, 0.01 * perimeter_raw)
    contour_smooth = cv2.approxPolyDP(contour, epsilon=eps, closed=True)
    perimeter_smooth = float(cv2.arcLength(contour_smooth, True))

    hull = cv2.convexHull(contour)
    hull_perimeter = float(cv2.arcLength(hull, True))
    
    # Fit ellipse
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "Contour stats: points=%d area=%.2f perim_raw=%.2f perim_smooth=%.2f hull_perim=%.2f eps=%.2f",
            int(len(contour)), area, perimeter_raw, perimeter_smooth, hull_perimeter, float(eps)
        )

    if len(contour) >= 5 and area > 0.0:
        (cx, cy), (axis1, axis2), orientation = cv2.fitEllipse(contour)

        # OpenCV does NOT guarantee axis order; ensure major >= minor
        major_axis = float(max(axis1, axis2))
        minor_axis = float(min(axis1, axis2))

        elongation_ratio = major_axis / (minor_axis + 1e-6)
        # Compactness: use smoothed perimeter by default; hull as a robustness fallback.
        compactness_smooth = (4.0 * np.pi * area) / (perimeter_smooth ** 2 + 1e-6)
        compactness_hull = (4.0 * np.pi * area) / (hull_perimeter ** 2 + 1e-6)

        # If the boundary is extremely jagged, raw perimeter can be pathological.
        # Prefer the less pathologic estimate in that case.
        compactness = compactness_smooth
        if compactness_smooth < 0.10 and compactness_hull > compactness_smooth:
            compactness = compactness_hull

        # Safety guards
        if not np.isfinite(elongation_ratio) or elongation_ratio < 1.0:
            elongation_ratio = 1.0
        if not np.isfinite(compactness) or compactness <= 0.0:
            compactness = 0.0

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Ellipse fit: center=(%.2f,%.2f) axis1=%.2f axis2=%.2f major=%.2f minor=%.2f orient=%.2f elong=%.3f compact_smooth=%.3f compact_hull=%.3f compact_used=%.3f",
                float(cx), float(cy), float(axis1), float(axis2),
                major_axis, minor_axis, float(orientation),
                float(elongation_ratio),
                float(compactness_smooth), float(compactness_hull), float(compactness)
            )
    else:
        orientation = 0
        elongation_ratio = 1.0
        compactness = 0.0
    
    logger.info(
        "Geometric features: area=%.0fpx, perim=%.1fpx, hull_perim=%.1fpx, orient=%.1f°, elong=%.2f, compact=%.2f",
        area, perimeter_smooth, hull_perimeter, float(orientation), float(elongation_ratio), float(compactness)
    )
    
    return GeometricFeatures(
        area=float(area),
        perimeter=float(perimeter_smooth),
        orientation=float(orientation),
        elongation_ratio=float(elongation_ratio),
        compactness=float(compactness)
    )


def extract_radiometric_features(sar_image: np.ndarray, binary_mask: np.ndarray) -> RadiometricFeatures:
    """
    Extract radiometric features (SAR intensity) from masked region
    
    Parameters:
    -----------
    sar_image : np.ndarray
        SAR image in dB
    binary_mask : np.ndarray
        Binary mask indicating region of interest
    
    Returns:
    --------
    RadiometricFeatures
        Radiometric properties
    """
    m = _ensure_binary_mask(binary_mask)
    # Use the same minimal cleanup as geometry to avoid including tiny spurs/noise
    mask_cv = (m * 255).astype(np.uint8, copy=False)
    kernel = np.ones((3, 3), dtype=np.uint8)
    mask_clean = cv2.morphologyEx(mask_cv, cv2.MORPH_CLOSE, kernel, iterations=1)
    mask_clean = cv2.morphologyEx(mask_clean, cv2.MORPH_OPEN, kernel, iterations=1)
    m_use = (mask_clean > 0)
    sar_db = _sar_to_db_if_needed(sar_image)

    if logger.isEnabledFor(logging.DEBUG):
        finite = np.isfinite(sar_db)
        logger.debug(
            "SAR stats (used): shape=%s dtype=%s min=%.3f max=%.3f mean=%.3f",
            sar_db.shape, sar_db.dtype,
            float(np.nanmin(sar_db)), float(np.nanmax(sar_db)), float(np.nanmean(sar_db))
        )
        if np.any(finite):
            # Also report raw input range for debugging scale issues
            sraw = np.asarray(sar_image)
            logger.debug(
                "SAR stats (raw): dtype=%s min=%.6f max=%.6f mean=%.6f",
                sraw.dtype,
                float(np.nanmin(sraw.astype(np.float64, copy=False))),
                float(np.nanmax(sraw.astype(np.float64, copy=False))),
                float(np.nanmean(sraw.astype(np.float64, copy=False)))
            )

    sar_masked = sar_db[m_use]
    sar_masked = sar_masked[np.isfinite(sar_masked)]
    
    if len(sar_masked) == 0:
        raise ValueError("No pixels selected by mask")

    logger.info(f"Radiometric: mask pixel count = {len(sar_masked)}")

    # Filter obvious nodata / floor-clipped values and extreme outliers
    # Step 1: Remove extreme bounds (nodata floor and brightness ceiling)
    floor_threshold = -80.0  # dB - nodata floor for SAR processing
    ceiling_threshold = 5.0  # dB - unrealistic brightness for ocean
    sar_bounded = sar_masked[(sar_masked > floor_threshold) & (sar_masked < ceiling_threshold)]
    
    if len(sar_bounded) < len(sar_masked):
        dropped = len(sar_masked) - len(sar_bounded)
        logger.info(
            f"Dropped {dropped} extreme outlier pixels (outside [{floor_threshold}, {ceiling_threshold}] dB). Remaining: {len(sar_bounded)} pixels."
        )
    
    # Failsafe: if removing extremes removed everything, use original
    if len(sar_bounded) == 0:
        logger.warning("Extreme filtering removed all pixels! Using original masked SAR values.")
        sar_bounded = sar_masked
    
    # Step 2: Apply percentile clipping to remove statistical outliers
    p5 = float(np.percentile(sar_bounded, 5))
    p95 = float(np.percentile(sar_bounded, 95))
    sar_valid = sar_bounded[(sar_bounded >= p5) & (sar_bounded <= p95)]
    
    logger.info(
        f"Percentile clipping: 5th={p5:.2f} dB, 95th={p95:.2f} dB. "
        f"Clipped {len(sar_bounded) - len(sar_valid)} outlier pixels. Valid pixels: {len(sar_valid)}."
    )
    
    # Failsafe: if percentile clipping removed too much, use bounded version
    if len(sar_valid) == 0:
        logger.warning("Percentile clipping removed all pixels! Using bounded SAR values.")
        sar_valid = sar_bounded

    mean_intensity = float(np.mean(sar_valid))
    std_intensity = float(np.std(sar_valid))
    min_intensity = float(np.min(sar_valid))
    max_intensity = float(np.max(sar_valid))

    # Useful always-on sanity log (helps catch scale/nodata issues without DEBUG)
    logger.info(
        "Radiometric features: mean=%.2f dB std=%.2f dB min=%.2f dB max=%.2f dB (n=%d/%d after filtering)",
        mean_intensity, std_intensity, min_intensity, max_intensity,
        int(sar_valid.size), int(sar_masked.size)
    )

    if mean_intensity < -80.0 or mean_intensity > 20.0 or std_intensity > 15.0:
        logger.warning(
            "Radiometric values look unusual for gamma0 dB (mean=%.2f, std=%.2f). "
            "This may indicate wrong SAR scaling or nodata in the masked region.",
            mean_intensity, std_intensity
        )
    
    return RadiometricFeatures(
        mean_intensity=mean_intensity,
        std_intensity=std_intensity,
        min_intensity=min_intensity,
        max_intensity=max_intensity
    )


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two points in kilometers
    
    Parameters:
    -----------
    lat1, lon1 : float
        First point coordinates
    lat2, lon2 : float
        Second point coordinates
    
    Returns:
    --------
    float
        Distance in kilometers
    """
    R = 6371.0  # Earth radius in km
    
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate bearing (direction) from point 1 to point 2
    
    Parameters:
    -----------
    lat1, lon1 : float
        Starting point
    lat2, lon2 : float
        Ending point
    
    Returns:
    --------
    float
        Bearing in degrees (0-360)
    """
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    dlon = lon2_rad - lon1_rad
    
    y = math.sin(dlon) * math.cos(lat2_rad)
    x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon)
    
    bearing_rad = math.atan2(y, x)
    bearing_deg = (math.degrees(bearing_rad) + 360) % 360
    
    return bearing_deg


def extract_drift_direction(nc_file_path: str, spot_centroid: Tuple[float, float], 
                           config: ClassifierConfig = None) -> float:
    """
    Extract drift direction from simulation over first hour
    
    Parameters:
    -----------
    nc_file_path : str
        Path to NetCDF simulation file
    spot_centroid : Tuple[float, float]
        Spot centroid (lat, lon)
    config : ClassifierConfig, optional
        Classifier configuration
    
    Returns:
    --------
    float
        Drift direction in degrees (0-360)
    """
    if config is None:
        config = ClassifierConfig()
    
    spot_lat, spot_lon = spot_centroid
    
    try:
        import xarray as xr
        ds = xr.open_dataset(nc_file_path)
    except:
        from netCDF4 import Dataset
        ds = Dataset(nc_file_path, 'r')
        is_netcdf4 = True
    else:
        is_netcdf4 = False
    
    try:
        if is_netcdf4:
            lons = ds.variables.get('lon', None)
            lats = ds.variables.get('lat', None)
            times = ds.variables.get('time', None)
            
            if not all([lons, lats, times]):
                raise ValueError("Required NetCDF variables (lon, lat, time) not found")
            
            lon_vals = lons[:]
            lat_vals = lats[:]
            time_vals = times[:]
        else:
            # xarray
            if 'lon' not in ds or 'lat' not in ds or 'time' not in ds:
                raise ValueError("Required xarray variables (lon, lat, time) not found")
            
            lon_vals = ds['lon'].values
            lat_vals = ds['lat'].values
            time_vals = ds['time'].values
        
        if len(time_vals) < 2:
            raise ValueError("NetCDF file has less than 2 time steps")
        
        # Handle different array dimensions
        if lon_vals.ndim == 1:
            # Single trajectory (1D arrays)
            start_lon = float(lon_vals[0])
            start_lat = float(lat_vals[0])
            end_lon = float(lon_vals[1])
            end_lat = float(lat_vals[1])
        elif lon_vals.ndim == 2:
            # Multiple trajectories (2D arrays)
            # Find closest trajectory to spot
            min_distance = float('inf')
            best_trajectory_idx = 0
            
            # Handle both (time, traj) and (traj, time) shapes
            if lon_vals.shape[0] == len(time_vals):
                # Shape is (time, trajectories)
                for i in range(lon_vals.shape[1]):
                    dist = haversine_distance(lat_vals[0, i], lon_vals[0, i], spot_lat, spot_lon)
                    if dist < min_distance:
                        min_distance = dist
                        best_trajectory_idx = i
                
                start_lon = float(lon_vals[0, best_trajectory_idx])
                start_lat = float(lat_vals[0, best_trajectory_idx])
                end_lon = float(lon_vals[1, best_trajectory_idx])
                end_lat = float(lat_vals[1, best_trajectory_idx])
            else:
                # Shape is (trajectories, time)
                for i in range(lon_vals.shape[0]):
                    dist = haversine_distance(lat_vals[i, 0], lon_vals[i, 0], spot_lat, spot_lon)
                    if dist < min_distance:
                        min_distance = dist
                        best_trajectory_idx = i
                
                start_lon = float(lon_vals[best_trajectory_idx, 0])
                start_lat = float(lat_vals[best_trajectory_idx, 0])
                end_lon = float(lon_vals[best_trajectory_idx, 1])
                end_lat = float(lat_vals[best_trajectory_idx, 1])
            
            if min_distance > config.POSITION_MATCH_TOLERANCE_KM:
                logger.warning(f"No trajectory within {config.POSITION_MATCH_TOLERANCE_KM} km (closest: {min_distance:.1f} km)")
        else:
            raise ValueError(f"Unexpected lon/lat array dimensions: {lon_vals.ndim}D")
        
        drift_direction = calculate_bearing(start_lat, start_lon, end_lat, end_lon)
        
        logger.info(f"Drift direction: {drift_direction:.1f}° (start: {start_lat:.3f}, {start_lon:.3f} -> end: {end_lat:.3f}, {end_lon:.3f})")
        
        return drift_direction
        
    finally:
        ds.close()


def normalize_angle_difference(angle1: float, angle2: float) -> float:
    """Calculate minimum angular difference between two angles"""
    angle1 = angle1 % 360
    angle2 = angle2 % 360
    
    diff = abs(angle1 - angle2)
    if diff > 180:
        diff = 360 - diff
    
    return diff


def calculate_soft_score(value: float, threshold: float, margin: float, inverted: bool = False) -> float:
    """
    Calculate soft (continuous) score using logistic sigmoid function.
    Instead of binary pass/fail, this provides a gradient.
    
    Parameters:
    -----------
    value : float
        Actual feature value (e.g., mean_intensity, std_intensity)
    threshold : float
        Target threshold
    margin : float
        Margin for soft transition (score goes 0→1 over this range)
    inverted : bool
        If True, lower values are better (e.g., darkness). If False, higher values are better.
    
    Returns:
    --------
    float
        Score 0-1, where 0.5 = threshold value
    """
    if inverted:
        # For inverted metrics (lower is better): score = sigmoid(-(value - threshold) / margin)
        score = 1.0 / (1.0 + np.exp((value - threshold) / margin))
    else:
        # For normal metrics (higher is better): score = sigmoid((value - threshold) / margin)
        score = 1.0 / (1.0 + np.exp(-(value - threshold) / margin))
    
    return float(np.clip(score, 0.0, 1.0))


def fuzzy_score(
    value: float,
    low: float,
    high: float,
    ideal_low: float,
    ideal_high: float,
    inverted: bool = False
) -> float:
    """
    Trapezoidal membership function in [0, 1].

    - Outside [low, high]  → score = 0
    - Between [ideal_low, ideal_high] → score = 1
    - Linear ramps between low→ideal_low and ideal_high→high.

    The parameters may be given in either increasing or decreasing order
    (e.g. for inverted metrics such as "lower is better"); ordering is
    normalised internally.
    """
    # Map to an axis where "higher is better"
    if inverted:
        v = -float(value)
        a_candidates = [-high, -low, -ideal_low, -ideal_high]
    else:
        v = float(value)
        a_candidates = [low, high, ideal_low, ideal_high]

    # Sort bounds: a <= b <= c <= d
    a, b, c, d = sorted(a_candidates)

    if d == a:  # degenerate
        return 0.0

    if v <= a or v >= d:
        return 0.0
    if b <= v <= c:
        return 1.0
    if a < v < b:
        return (v - a) / (b - a)
    # c < v < d
    return (d - v) / (d - c)


def verify_physics_rules(
    geometric_features: GeometricFeatures,
    radiometric_features: RadiometricFeatures,
    drift_direction: float,
    config: ClassifierConfig = None,
    scoring_mode: str = "fuzzy"
) -> Tuple[RuleResults, Dict[str, float]]:
    """
    Verify physics-based classification rules with weighted scoring.
    
    Now supports SOFT CONTINUOUS SCORING (recommended) in addition to binary.
    Soft scoring provides gradient confidence instead of all-or-nothing.
    
    Parameters:
    -----------
    geometric_features : GeometricFeatures
        Geometric properties of spot
    radiometric_features : RadiometricFeatures
        Radiometric properties of spot
    drift_direction : float
        Expected drift direction (0-360°)
    config : ClassifierConfig, optional
        Classifier configuration
    use_soft_scoring : bool
        If True (recommended), use continuous sigmoid scoring.
        If False, use legacy binary scoring.
    
    Returns:
    --------
    tuple
        (RuleResults, Dict of rule_scores)
    """
    if config is None:
        config = ClassifierConfig()

    scoring_mode = (scoring_mode or "").lower()

    if scoring_mode == "binary":
        # ===== LEGACY BINARY SCORING =====
        darkness_pass = radiometric_features.mean_intensity < config.DARKNESS_THRESHOLD
        darkness_score = 1.0 if darkness_pass else 0.0
        logger.info(f"  ▸ Darkness rule: {radiometric_features.mean_intensity:.2f} dB < {config.DARKNESS_THRESHOLD} dB: {darkness_pass} (score={darkness_score})")
        
        smoothness_pass = radiometric_features.std_intensity < config.SMOOTHNESS_THRESHOLD
        smoothness_score = 1.0 if smoothness_pass else 0.0
        logger.info(f"  ▸ Smoothness rule: {radiometric_features.std_intensity:.2f} dB < {config.SMOOTHNESS_THRESHOLD} dB: {smoothness_pass} (score={smoothness_score})")
        
        shape_pass = (geometric_features.elongation_ratio > config.ELONGATION_THRESHOLD and
                      geometric_features.compactness > config.COMPACTNESS_THRESHOLD)
        shape_score = 1.0 if shape_pass else 0.0
        logger.info(f"  ▸ Shape rule: elongation={geometric_features.elongation_ratio:.2f}, compactness={geometric_features.compactness:.2f}: {shape_pass} (score={shape_score})")
        
        diff1 = normalize_angle_difference(geometric_features.orientation, drift_direction)
        diff2 = normalize_angle_difference(geometric_features.orientation + 180, drift_direction)
        min_diff = min(diff1, diff2)
        alignment_pass = min_diff <= config.ALIGNMENT_TOLERANCE
        alignment_score = 1.0 if alignment_pass else 0.0
        logger.info(f"  ▸ Alignment rule: {min_diff:.1f}° <= {config.ALIGNMENT_TOLERANCE}°: {alignment_pass} (score={alignment_score})")
    elif scoring_mode == "fuzzy":
        # ===== FUZZY TRAPEZOIDAL SCORING =====
        rc = config.RULE_CONFIG

        # Rule 1: Darkness
        d_cfg = rc.get("darkness", {})
        darkness_score = fuzzy_score(
            radiometric_features.mean_intensity,
            low=d_cfg.get("low", -5.0),
            high=d_cfg.get("high", -25.0),
            ideal_low=d_cfg.get("ideal_low", -12.0),
            ideal_high=d_cfg.get("ideal_high", -18.0),
            inverted=d_cfg.get("inverted", True),
        )
        darkness_pass = darkness_score > 0.5
        logger.info(
            f"  ▸ Darkness rule (fuzzy): value={radiometric_features.mean_intensity:.2f} dB → score={darkness_score:.3f}, pass={darkness_pass}"
        )

        # Rule 2: Smoothness
        s_cfg = rc.get("smoothness", {})
        smoothness_score = fuzzy_score(
            radiometric_features.std_intensity,
            low=s_cfg.get("low", 4.0),
            high=s_cfg.get("high", 0.0),
            ideal_low=s_cfg.get("ideal_low", 2.0),
            ideal_high=s_cfg.get("ideal_high", 0.5),
            inverted=s_cfg.get("inverted", True),
        )
        smoothness_pass = smoothness_score > 0.5
        logger.info(
            f"  ▸ Smoothness rule (fuzzy): std={radiometric_features.std_intensity:.2f} dB → score={smoothness_score:.3f}, pass={smoothness_pass}"
        )

        # Rule 3: Shape (combine elongation + compactness)
        se_cfg = rc.get("shape_elongation", {})
        sc_cfg = rc.get("shape_compactness", {})
        elongation_score = fuzzy_score(
            geometric_features.elongation_ratio,
            low=se_cfg.get("low", 1.0),
            high=se_cfg.get("high", 7.0),
            ideal_low=se_cfg.get("ideal_low", 1.5),
            ideal_high=se_cfg.get("ideal_high", 4.5),
            inverted=se_cfg.get("inverted", False),
        )
        compactness_score = fuzzy_score(
            geometric_features.compactness,
            low=sc_cfg.get("low", 0.05),
            high=sc_cfg.get("high", 0.8),
            ideal_low=sc_cfg.get("ideal_low", 0.15),
            ideal_high=sc_cfg.get("ideal_high", 0.5),
            inverted=sc_cfg.get("inverted", False),
        )
        shape_score = (elongation_score + compactness_score) / 2.0
        shape_pass = shape_score > 0.5
        logger.info(
            f"  ▸ Shape rule (fuzzy): elong={geometric_features.elongation_ratio:.3f}, "
            f"compact={geometric_features.compactness:.3f} → elong_score={elongation_score:.3f}, "
            f"compact_score={compactness_score:.3f}, combined={shape_score:.3f}, pass={shape_pass}"
        )

        # Rule 4: Alignment - Linear physics-based scoring (not fuzzy)
        # Alignment measures how well spill orientation matches drift direction
        diff1 = normalize_angle_difference(geometric_features.orientation, drift_direction)
        diff2 = normalize_angle_difference(geometric_features.orientation + 180, drift_direction)
        min_diff = min(diff1, diff2)
        
        # Linear scoring: alignment_score = max(0, 1 - diff/90)
        # This means: 0° → 1.0, 45° → 0.5, 90° → 0.0 (physics-based)
        alignment_score = max(0.0, 1.0 - (min_diff / 90.0))
        alignment_pass = min_diff <= 90.0
        
        logger.info(
            f"  ▸ Alignment rule (linear): orient={geometric_features.orientation:.1f}°, "
            f"drift={drift_direction:.1f}°, diff={min_diff:.1f}° → score={alignment_score:.3f}, pass={alignment_pass}"
        )
    else:
        # ===== SIGMOID SOFT SCORING (DEFAULT) =====
        # Rule 1: Darkness (lower intensity = higher score)
        darkness_score = calculate_soft_score(
            radiometric_features.mean_intensity,
            config.DARKNESS_THRESHOLD,
            margin=3.0,  # ±3dB transition zone
            inverted=True,
        )
        darkness_pass = darkness_score > 0.5
        logger.info(
            f"  ▸ Darkness rule: {radiometric_features.mean_intensity:.2f} dB < "
            f"{config.DARKNESS_THRESHOLD} dB: {darkness_pass} (soft_score={darkness_score:.3f})"
        )

        # Rule 2: Smoothness (lower std = higher score)
        smoothness_score = calculate_soft_score(
            radiometric_features.std_intensity,
            config.SMOOTHNESS_THRESHOLD,
            margin=1.0,  # ±1dB transition zone
            inverted=True,
        )
        smoothness_pass = smoothness_score > 0.5
        logger.info(
            f"  ▸ Smoothness rule: {radiometric_features.std_intensity:.2f} dB < "
            f"{config.SMOOTHNESS_THRESHOLD} dB: {smoothness_pass} (soft_score={smoothness_score:.3f})"
        )

        # Rule 3: Shape (higher elongation and compactness = higher score)
        elongation_score = calculate_soft_score(
            geometric_features.elongation_ratio,
            config.ELONGATION_THRESHOLD,
            margin=0.5,
            inverted=False,
        )
        compactness_score = calculate_soft_score(
            geometric_features.compactness,
            config.COMPACTNESS_THRESHOLD,
            margin=1.0,
            inverted=False,
        )
        shape_score = (elongation_score + compactness_score) / 2.0
        shape_pass = shape_score > 0.5
        logger.info(
            f"  ▸ Shape rule: elongation={geometric_features.elongation_ratio:.2f}, "
            f"compactness={geometric_features.compactness:.2f}: {shape_pass} (soft_score={shape_score:.3f})"
        )

        # Rule 4: Alignment (smaller angle difference = higher score)
        diff1 = normalize_angle_difference(geometric_features.orientation, drift_direction)
        diff2 = normalize_angle_difference(geometric_features.orientation + 180, drift_direction)
        min_diff = min(diff1, diff2)

        alignment_score = calculate_soft_score(
            min_diff,
            config.ALIGNMENT_TOLERANCE,
            margin=20.0,  # ±20° transition zone
            inverted=True,
        )
        alignment_pass = alignment_score > 0.5
        logger.info(
            f"  ▸ Alignment rule: {min_diff:.1f}° <= {config.ALIGNMENT_TOLERANCE}°: "
            f"{alignment_pass} (soft_score={alignment_score:.3f})"
        )

    all_pass = darkness_pass and smoothness_pass and shape_pass and alignment_pass
    
    # Create rule scores dict
    rule_scores = {
        'darkness': darkness_score,
        'smoothness': smoothness_score,
        'shape': shape_score,
        'alignment': alignment_score
    }
    
    return RuleResults(
        darkness_pass=darkness_pass,
        smoothness_pass=smoothness_pass,
        shape_pass=shape_pass,
        alignment_pass=alignment_pass,
        all_pass=all_pass
    ), rule_scores


def classify_with_physical_guidance(
    sar_image: np.ndarray,
    binary_mask: np.ndarray,
    simulation_file: str,
    spot_centroid: Tuple[float, float],
    config: ClassifierConfig = None
) -> Dict:
    """
    Classify oil spill using physics-guided weighted rules
    
    Parameters:
    -----------
    sar_image : np.ndarray
        SAR image in dB
    binary_mask : np.ndarray
        Binary mask of detected region
    simulation_file : str
        Path to simulation NetCDF file
    spot_centroid : Tuple[float, float]
        Spot centroid (lat, lon)
    config : ClassifierConfig, optional
        Classifier configuration
    
    Returns:
    --------
    dict
        Classification results with confidence
    """
    if config is None:
        config = ClassifierConfig()
    
    logger.info("=== Physics-Guided Classification ===")
    
    # Preprocess inputs robustly (do not change rule logic; only ensure correct units/formats)
    mask_bin = _ensure_binary_mask(binary_mask)
    sar_pre = np.asarray(sar_image)

    # Extract features
    geometric = extract_geometric_features(mask_bin)
    radiometric = extract_radiometric_features(sar_pre, mask_bin)
    
    # Get drift direction
    drift_direction = extract_drift_direction(simulation_file, spot_centroid, config)
    
    # Verify rules using configured scoring mode ("binary", "sigmoid", "fuzzy")
    rules, rule_scores = verify_physics_rules(
        geometric,
        radiometric,
        drift_direction,
        config,
        scoring_mode=getattr(config, "scoring_mode", "fuzzy"),
    )
    
    # Calculate weighted confidence score using soft scores
    # This gives a smooth 0-1 confidence instead of all-or-nothing
    weights = config.rule_weights
    weighted_score = (
        rule_scores['darkness'] * weights['darkness'] +
        rule_scores['smoothness'] * weights['smoothness'] +
        rule_scores['shape'] * weights['shape'] +
        rule_scores['alignment'] * weights['alignment']
    )

    # Complementary Non-Oil score: how strongly rules support "False Positive"
    non_oil_score = (
        (1.0 - rule_scores['darkness']) * weights['darkness'] +
        (1.0 - rule_scores['smoothness']) * weights['smoothness'] +
        (1.0 - rule_scores['shape']) * weights['shape'] +
        (1.0 - rule_scores['alignment']) * weights['alignment']
    )
    
    # Log rule scores with soft scoring
    logger.info(
        f"Soft rule scores: darkness={rule_scores['darkness']:.3f}, "
        f"smoothness={rule_scores['smoothness']:.3f}, "
        f"shape={rule_scores['shape']:.3f}, alignment={rule_scores['alignment']:.3f}"
    )
    logger.info(f"Weighted confidence: {weighted_score:.3f} (threshold: 0.55)")
    logger.info(f"Rule weights: {weights}")
    
    # IMPROVED CLASSIFICATION: Use continuous confidence with updated threshold
    OIL_THRESHOLD = 0.55
    classification = "Oil-like" if weighted_score >= OIL_THRESHOLD else "False Positive"

    # Directional confidence: oil_score when Oil-like, non_oil_score when False Positive
    confidence = weighted_score if classification == "Oil-like" else non_oil_score
    
    result = {
        'classification': classification,
        'confidence': float(confidence),
        'weighted_score': float(weighted_score),
        'oil_score': float(weighted_score),
        'non_oil_score': float(non_oil_score),
        'rules_passed': int(sum([1 for v in [rule_scores['darkness'], rule_scores['smoothness'], rule_scores['shape'], rule_scores['alignment']] if v > 0.5])),
        'geometric_features': asdict(geometric),
        'radiometric_features': asdict(radiometric),
        'drift_direction': float(drift_direction),
        'rule_results': asdict(rules),
        'rule_scores': rule_scores
    }
    
    return result


def create_pg_classifier_visualization(
    binary_mask_path: str,
    sar_image_path: str,
    classification_result: dict,
    output_dir: str
) -> dict:
    """
    Create comprehensive visualizations of PG classifier analysis.
    
    Parameters:
    -----------
    binary_mask_path : str
        Path to binary oil mask (NPY or TIFF)
    sar_image_path : str
        Path to original SAR image (TIFF)
    classification_result : dict
        Result from classify_spot() function
    output_dir : str
        Directory to save visualization images
    
    Returns:
    --------
    dict
        Paths to generated visualization files
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        from matplotlib.patches import FancyArrowPatch
    except ImportError:
        logger.error("matplotlib required for visualizations. Install with: pip install matplotlib")
        return {}
    
    try:
        import numpy as np
        from pathlib import Path
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load binary mask (support .npy, .png, or rasterio-readable)
        if binary_mask_path.endswith('.npy'):
            binary_mask = np.load(binary_mask_path, allow_pickle=True)
        elif binary_mask_path.lower().endswith('.png'):
            from PIL import Image
            img = Image.open(binary_mask_path).convert('L')
            arr = np.array(img)
            binary_mask = (arr > 127).astype(np.uint8)  # white = oil
        else:
            with rasterio.open(binary_mask_path) as src:
                binary_mask = src.read(1)
        
        if binary_mask.max() > 1:
            binary_mask = (binary_mask > 0).astype(np.uint8)
        
        # Load SAR image
        with rasterio.open(sar_image_path) as src:
            sar_image = src.read(1)
        
        # Normalize SAR for visualization (keep dB scale for colorbar where needed)
        sar_norm = (sar_image - np.nanmin(sar_image)) / (np.nanmax(sar_image) - np.nanmin(sar_image) + 1e-6)
        
        geom = classification_result['geometric_features']
        radio = classification_result['radiometric_features']
        rules = classification_result['rule_results']
        drift_direction = classification_result['drift_direction']
        conf = classification_result.get('confidence', 0)
        
        viz_files = {}
        
        # ===== Visualization 1: 2-Panel (notebook style) - SAR dB + Binary Mask with colorbars =====
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        
        im0 = axes[0].imshow(sar_image, cmap='gray')
        axes[0].set_title('SAR Image (dB)', fontsize=12, fontweight='bold')
        plt.colorbar(im0, ax=axes[0], label='Intensity (dB)')
        axes[0].set_xlabel('Pixels (X)')
        axes[0].set_ylabel('Pixels (Y)')
        
        im1 = axes[1].imshow(binary_mask, cmap='gray', vmin=0, vmax=1)
        axes[1].set_title('Binary Mask (white=oil)', fontsize=12, fontweight='bold')
        plt.colorbar(im1, ax=axes[1])
        axes[1].set_xlabel('Pixels (X)')
        axes[1].set_ylabel('Pixels (Y)')
        
        plt.tight_layout()
        mask_viz_path = output_dir / 'pg_mask_visualization.png'
        plt.savefig(mask_viz_path, dpi=150, bbox_inches='tight')
        plt.close()
        viz_files['mask_overlay'] = str(mask_viz_path)
        
        # ===== Visualization 1b: 2-Panel - Mask + SAR with overlay (original) =====
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        
        axes[0].imshow(binary_mask, cmap='gray')
        axes[0].set_title('Binary Oil Mask', fontsize=12, fontweight='bold')
        axes[0].set_xlabel('Pixels (X)')
        axes[0].set_ylabel('Pixels (Y)')
        axes[0].grid(True, alpha=0.3)
        
        axes[1].imshow(sar_norm, cmap='gray', alpha=0.8)
        mask_overlay = np.ma.masked_where(binary_mask == 0, binary_mask)
        axes[1].imshow(mask_overlay, cmap='Reds', alpha=0.5)
        axes[1].set_title('SAR Image with Mask Overlay', fontsize=12, fontweight='bold')
        axes[1].set_xlabel('Pixels (X)')
        axes[1].set_ylabel('Pixels (Y)')
        
        plt.tight_layout()
        overlay_viz_path = output_dir / 'pg_sar_mask_overlay.png'
        plt.savefig(overlay_viz_path, dpi=150, bbox_inches='tight')
        plt.close()
        viz_files['sar_mask_overlay'] = str(overlay_viz_path)
        
        # ===== Visualization 2: Feature Summary (notebook 2x2 style) =====
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        # Top-left: SAR image (dB) with mask contour
        ax = axes[0, 0]
        im = ax.imshow(sar_image, cmap='gray')
        ax.contour(binary_mask, colors='red', linewidths=2)
        ax.set_title('SAR Image (dB) with Mask Contour', fontsize=11, fontweight='bold')
        plt.colorbar(im, ax=ax, label='Intensity (dB)')
        ax.set_xlabel('Pixels (X)')
        ax.set_ylabel('Pixels (Y)')
        
        # Top-right: Binary mask
        ax = axes[0, 1]
        im = ax.imshow(binary_mask, cmap='gray', vmin=0, vmax=1)
        ax.set_title('Binary Mask (Oil Region)', fontsize=11, fontweight='bold')
        plt.colorbar(im, ax=ax)
        ax.set_xlabel('Pixels (X)')
        ax.set_ylabel('Pixels (Y)')
        
        # Bottom-left: SAR intensity histogram in oil region
        ax = axes[1, 0]
        mask_pixels = sar_image[binary_mask > 0]
        if len(mask_pixels) > 0:
            ax.hist(mask_pixels, bins=30, color='steelblue', alpha=0.7, edgecolor='black')
            ax.axvline(x=radio['mean_intensity'], color='red', linestyle='--', linewidth=2, label=f"Mean: {radio['mean_intensity']:.2f} dB")
            if radio['std_intensity'] > 0:
                ax.axvline(radio['mean_intensity'] - radio['std_intensity'], color='orange', linestyle=':', linewidth=2, label='±1σ')
                ax.axvline(radio['mean_intensity'] + radio['std_intensity'], color='orange', linestyle=':', linewidth=2)
            ax.set_xlabel('SAR Intensity (dB)', fontsize=10)
            ax.set_ylabel('Frequency', fontsize=10)
            ax.set_title('Distribution of SAR Values in Oil Region', fontsize=11, fontweight='bold')
            ax.legend()
            ax.grid(True, alpha=0.3, axis='y')
        else:
            ax.text(0.5, 0.5, 'No mask pixels', ha='center', va='center', transform=ax.transAxes)
            ax.set_title('SAR in Oil Region', fontsize=11, fontweight='bold')
        
        # Bottom-right: Rule results text
        ax = axes[1, 1]
        ax.axis('off')
        
        # Use confidence from weighted score (soft scoring) instead of all_pass binary check
        conf = classification_result['confidence']  # Weighted score 0-1
        classification = classification_result['classification']  # "Oil-like" or "False Positive"
        rule_scores = classification_result.get('rule_scores', {})
        
        rule_text = f"""
        RULE VERIFICATION RESULTS
        {'='*40}
        
        ✓ Darkness Rule:    {'PASS' if rules['darkness_pass'] else 'FAIL'}
          Score: {rule_scores.get('darkness', 0):.2f}/1.0
          Actual: {radio['mean_intensity']:.2f} dB
        
        ✓ Smoothness Rule:  {'PASS' if rules['smoothness_pass'] else 'FAIL'}
          Score: {rule_scores.get('smoothness', 0):.2f}/1.0
          Actual: {radio['std_intensity']:.2f} dB
        
        ✓ Shape Rule:       {'PASS' if rules['shape_pass'] else 'FAIL'}
          Score: {rule_scores.get('shape', 0):.2f}/1.0
          E={geom['elongation_ratio']:.2f}, C={geom['compactness']:.2f}
        
        ✓ Alignment Rule:   {'PASS' if rules['alignment_pass'] else 'FAIL'}
          Score: {rule_scores.get('alignment', 0):.2f}/1.0
          Orient: {geom['orientation']:.1f}°, Drift: {drift_direction:.1f}°
        
        {'='*40}
        Overall Confidence: {conf:.1%}
        Classification: {classification}
        """
        ax.text(0.05, 0.95, rule_text, transform=ax.transAxes,
               fontsize=9, verticalalignment='top', family='monospace',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        
        plt.tight_layout()
        feature_viz_path = output_dir / 'pg_features_summary.png'
        plt.savefig(feature_viz_path, dpi=150, bbox_inches='tight')
        plt.close()
        viz_files['features_summary'] = str(feature_viz_path)
        
        # ===== Visualization 3: Rule Score Gauge =====
        fig, ax = plt.subplots(figsize=(10, 6))
        
        rules_list = ['Darkness', 'Smoothness', 'Shape', 'Alignment']
        rules_pass = [
            rules['darkness_pass'],
            rules['smoothness_pass'],
            rules['shape_pass'],
            rules['alignment_pass']
        ]
        scores = classification_result['rule_scores']
        rule_scores = [scores['darkness'], scores['smoothness'], scores['shape'], scores['alignment']]
        
        colors = ['#2ca02c' if p else '#d62728' for p in rules_pass]
        bars = ax.barh(rules_list, rule_scores, color=colors, alpha=0.7, edgecolor='black', linewidth=2)
        
        # Add value labels
        for i, (bar, score) in enumerate(zip(bars, rule_scores)):
            ax.text(score + 0.02, i, f'{score:.2f}', va='center', fontsize=11, fontweight='bold')
        
        ax.set_xlim(0, 1.1)
        ax.set_xlabel('Rule Score', fontsize=12)
        ax.set_title('Physics-Based Rule Verification Scores', fontsize=13, fontweight='bold')
        ax.axvline(x=0.5, color='gray', linestyle='--', linewidth=1, alpha=0.5)
        ax.grid(True, alpha=0.3, axis='x')
        
        plt.tight_layout()
        rules_viz_path = output_dir / 'pg_rule_scores.png'
        plt.savefig(rules_viz_path, dpi=150, bbox_inches='tight')
        plt.close()
        viz_files['rule_scores'] = str(rules_viz_path)
        
        # ===== Visualization 4: Polar alignment (notebook style) - Mask orientation vs drift direction =====
        orientation = geom['orientation']
        tolerance = 90.0  # Updated alignment tolerance to match relaxed physics-based rule
        orientation_rad = np.radians(orientation)
        orientation_reversed_rad = np.radians((orientation + 180) % 360)
        drift_rad = np.radians(drift_direction)
        diff1 = normalize_angle_difference(orientation, drift_direction)
        diff2 = normalize_angle_difference(orientation + 180, drift_direction)
        min_diff = min(diff1, diff2)
        result_str = "PASS ✓" if min_diff <= tolerance else "FAIL ✗"
        
        fig, ax = plt.subplots(1, 1, figsize=(10, 10), subplot_kw=dict(projection='polar'))
        directions = [0, 90, 180, 270]
        labels = ['N (0°)', 'E (90°)', 'S (180°)', 'W (270°)']
        for direction, label in zip(directions, labels):
            ax.plot([np.radians(direction), np.radians(direction)], [0, 1], 'k-', alpha=0.3)
            ax.text(np.radians(direction), 1.15, label, ha='center', fontsize=10)
        ax.set_ylim(0, 1.3)
        ax.set_theta_zero_location('N')
        ax.set_theta_direction(-1)
        ax.arrow(0, 0, orientation_rad, 0.9, head_width=0.15, head_length=0.1,
                 fc='blue', ec='blue', linewidth=3, label='Mask Orientation', alpha=0.8)
        ax.arrow(0, 0, orientation_reversed_rad, 0.85, head_width=0.15, head_length=0.1,
                 fc='lightblue', ec='blue', linewidth=2, linestyle='--', label='Orientation (reversed)', alpha=0.6)
        ax.arrow(0, 0, drift_rad, 1.0, head_width=0.15, head_length=0.1,
                 fc='red', ec='red', linewidth=3, label='Drift Direction', alpha=0.8)
        title_text = (
            f"Alignment Check: Mask Orientation vs Drift Direction\n"
            f"Mask Orientation: {orientation:.1f}° (bidirectional)  |  "
            f"Drift Direction: {drift_direction:.1f}°\n"
            f"Min angular difference: {min_diff:.1f}°  |  Tolerance: {tolerance:.1f}°  →  {result_str}"
        )
        ax.set_title(title_text, fontsize=12, fontweight='bold', pad=20)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=10)
        plt.tight_layout()
        polar_viz_path = output_dir / 'pg_alignment_polar.png'
        plt.savefig(polar_viz_path, dpi=150, bbox_inches='tight')
        plt.close()
        viz_files['alignment_polar'] = str(polar_viz_path)
        
        logger.info(f"✓ Generated {len(viz_files)} PG classifier visualizations")
        return viz_files
        
    except Exception as e:
        logger.error(f"Failed to create PG classifier visualizations: {e}")
        import traceback
        traceback.print_exc()
        return {}

