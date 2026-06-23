"""
Module for extracting coordinates and metadata from SAR TIFF images
Notebook 1: Extract Coordinates
"""

import os
import json
import glob
import logging
from typing import Dict, Tuple, Optional
from datetime import datetime

import rasterio
from PIL import Image
from PIL.ExifTags import TAGS

logger = logging.getLogger(__name__)


def get_image_metadata(image_path: str) -> Dict:
    """
    Extract all metadata from image file (TIFF format)
    
    Parameters:
    -----------
    image_path : str
        Path to the TIFF image file
    
    Returns:
    --------
    dict
        Dictionary containing image metadata (bounds, CRS, transform, EXIF data)
    """
    metadata = {}
    
    # Get TIFF metadata using rasterio
    try:
        with rasterio.open(image_path) as src:
            metadata['bounds'] = src.bounds._asdict()
            metadata['crs'] = str(src.crs)
            metadata['transform'] = list(src.transform)
            metadata['shape'] = src.shape
            logger.info(f"Extracted rasterio metadata from {image_path}")
    except Exception as e:
        logger.error(f"Failed to extract rasterio metadata: {e}")
        raise
    
    # Get EXIF metadata using PIL
    try:
        with Image.open(image_path) as img:
            exif = img._getexif()
            if exif:
                for tag_id in exif:
                    tag = TAGS.get(tag_id, tag_id)
                    data = exif.get(tag_id)
                    # Decode bytes if needed
                    if isinstance(data, bytes):
                        try:
                            data = data.decode()
                        except:
                            data = str(data)
                    metadata[tag] = data
                logger.info("Extracted EXIF metadata")
            else:
                logger.warning("No EXIF metadata found")
    except Exception as e:
        logger.warning(f"No EXIF metadata found: {e}")
    
    return metadata


def extract_coordinates(image_path: str) -> Tuple[float, float, float, float, dict]:
    """
    Extract latitude/longitude coordinates from TIFF image
    
    Parameters:
    -----------
    image_path : str
        Path to the TIFF image file
    
    Returns:
    --------
    tuple
        (lat_min, lat_max, lon_min, lon_max, metadata)
    """
    metadata = get_image_metadata(image_path)
    bounds = metadata['bounds']
    
    lat_min = bounds['bottom']
    lat_max = bounds['top']
    lon_min = bounds['left']
    lon_max = bounds['right']
    
    logger.info(f"Extracted coordinates: {lat_min:.2f}°N to {lat_max:.2f}°N, "
                f"{lon_min:.2f}°E to {lon_max:.2f}°E")
    
    return lat_min, lat_max, lon_min, lon_max, metadata


def find_tiff_files(directory: str, patterns: list = None) -> list:
    """
    Find TIFF files in directory
    
    Parameters:
    -----------
    directory : str
        Directory to search
    patterns : list, optional
        TIFF file patterns (default: ['*.tif', '*.tiff'])
    
    Returns:
    --------
    list
        List of found TIFF file paths
    """
    if patterns is None:
        patterns = ['*.tif', '*.tiff']
    
    files = []
    for p in patterns:
        files.extend(glob.glob(os.path.join(directory, p)))
    
    logger.info(f"Found {len(files)} TIFF file(s) in {directory}")
    return files


def auto_detect_image(raw_dir: str = None) -> Optional[str]:
    """
    Auto-detect TIFF image in raw data directory
    
    Parameters:
    -----------
    raw_dir : str, optional
        Raw data directory (default: ../data/raw)
    
    Returns:
    --------
    str or None
        Path to the first TIFF file found, or None if not found
    """
    if raw_dir is None:
        # Try multiple possible paths
        possible_paths = [
            os.path.join('data', 'raw'),
            os.path.join('..', 'data', 'raw'),
            os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'raw'))
        ]
        
        raw_dir = None
        for path in possible_paths:
            if os.path.exists(path):
                raw_dir = path
                break
        
        if raw_dir is None:
            raw_dir = os.path.join('data', 'raw')
    
    files = find_tiff_files(raw_dir)
    if files:
        logger.info(f"Auto-detected image: {files[0]}")
        return files[0]
    
    logger.warning(f"No TIFF files found in {raw_dir}")
    return None


def process_sar_image(image_path: str = None, output_dir: str = None) -> Dict:
    """
    Main processing function: Extract metadata from SAR image and save to JSON
    
    Parameters:
    -----------
    image_path : str, optional
        Path to the TIFF image file (auto-detect if not provided)
    output_dir : str, optional
        Output directory for metadata JSON
    
    Returns:
    --------
    dict
        Dictionary containing extracted metadata and coordinates
    """
    # Auto-detect if not provided
    if image_path is None:
        image_path = auto_detect_image()
        if image_path is None:
            raise FileNotFoundError("No TIFF files found in data directories")
    
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")
    
    # Set default output directory
    if output_dir is None:
        possible_paths = [
            os.path.join('data', 'processed'),
            os.path.join('..', 'data', 'processed'),
            os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'processed'))
        ]
        output_dir = None
        for path in possible_paths:
            if os.path.exists(path):
                output_dir = path
                break
        if output_dir is None:
            output_dir = os.path.join('data', 'processed')
    
    # Create output directory if needed
    os.makedirs(output_dir, exist_ok=True)
    
    # Extract metadata and coordinates
    lat_min, lat_max, lon_min, lon_max, metadata = extract_coordinates(image_path)
    
    # Prepare output dictionary
    result = {
        'image_path': image_path,
        'coordinates': {
            'lat_min': lat_min,
            'lat_max': lat_max,
            'lon_min': lon_min,
            'lon_max': lon_max
        },
        'metadata': metadata
    }
    
    # Save metadata to JSON
    out_json = os.path.join(output_dir, os.path.basename(image_path) + '.metadata.json')
    with open(out_json, 'w') as f:
        json.dump(metadata, f, default=str, indent=2)
    
    logger.info(f"Saved metadata to {out_json}")
    
    return result
