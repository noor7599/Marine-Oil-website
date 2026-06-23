"""
Module for downloading ERA5 wind data and CMEMS ocean current data
Notebook 2: Download Data
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional

try:
    import cdsapi
    import xarray as xr
    from copernicusmarine import subset
    DOWNLOAD_AVAILABLE = True
except ImportError:
    DOWNLOAD_AVAILABLE = False

logger = logging.getLogger(__name__)


def download_era5_data(
    date: datetime,
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    output_dir: str = None,
    api_key: str = None,
    grid_resolution: float = 0.25,
    padding: float = 0.25
) -> str:
    """
    Download ERA5 reanalysis wind data
    """
    if not DOWNLOAD_AVAILABLE:
        raise ImportError("cdsapi not installed. Run: pip install cdsapi xarray netCDF4")
    if output_dir is None:
        output_dir = os.path.join('..', 'data', 'processed')
    
    os.makedirs(output_dir, exist_ok=True)
    
    lat_max_padded = lat_max + padding
    lat_min_padded = lat_min - padding
    lon_max_padded = lon_max + padding
    lon_min_padded = lon_min - padding
    
    logger.info(f"Downloading ERA5 data for area: {lat_max_padded:.2f}N to {lat_min_padded:.2f}N")
    
    c = cdsapi.Client()
    
    era5_request = {
        'product_type': 'reanalysis',
        'format': 'netcdf',
        'variable': ['10m_u_component_of_wind', '10m_v_component_of_wind'],
        'year': date.strftime('%Y'),
        'month': date.strftime('%m'),
        'day': date.strftime('%d'),
        'time': [f"{h:02d}:00" for h in range(24)],
        'area': [lat_max_padded, lon_min_padded, lat_min_padded, lon_max_padded],
        'grid': [grid_resolution, grid_resolution],
    }
    
    era5_output = os.path.join(output_dir, f'era5_wind_{date.strftime("%Y%m%d")}.nc')
    
    try:
        logger.info(f"Downloading ERA5 data to: {era5_output}")
        c.retrieve('reanalysis-era5-single-levels', era5_request, era5_output)
        logger.info("ERA5 download complete!")
        return era5_output
    except Exception as e:
        logger.error(f"Error downloading ERA5 data: {e}")
        raise


def download_cmems_data(
    date: datetime,
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
    output_dir: str = None,
    padding: float = 0.25,
    dataset_id: str = 'cmems_mod_glo_phy_my_0.083deg_P1D-m'
) -> str:
    """
    Download CMEMS ocean current data with hardcoded credentials for automation
    """
    if not DOWNLOAD_AVAILABLE:
        raise ImportError("copernicusmarine not installed.")
    if output_dir is None:
        output_dir = os.path.join('..', 'data', 'processed')
    
    os.makedirs(output_dir, exist_ok=True)
    
    lat_max_padded = lat_max + padding
    lat_min_padded = lat_min - padding
    lon_max_padded = lon_max + padding
    lon_min_padded = lon_min - padding
    
    start_date = f"{date.strftime('%Y-%m-%d')}T00:00:00"
    end_date = f"{(date + timedelta(days=1)).strftime('%Y-%m-%d')}T00:00:00"
    
    cmems_output = os.path.join(output_dir, f'cmems_current_{date.strftime("%Y%m%d")}.nc')
    
    try:
        logger.info(f"Downloading CMEMS data to: {cmems_output} (Using Automated Auth)")
        # THE AUTH IS HANDLED HERE AUTOMATICALLY
        subset(
            dataset_id=dataset_id,
            variables=["uo", "vo"],
            start_datetime=start_date,
            end_datetime=end_date,
            minimum_latitude=lat_min_padded,
            maximum_latitude=lat_max_padded,
            minimum_longitude=lon_min_padded,
            maximum_longitude=lon_max_padded,
            output_filename=cmems_output,
            username="nbarakat",
            password="Noorsacc2026!",
            force_download=True
        )
        logger.info("CMEMS download complete!")
        
        # Verify
        cmems_ds = xr.open_dataset(cmems_output)
        cmems_ds.close()
        
        return cmems_output
    except Exception as e:
        logger.error(f"Error downloading CMEMS data: {e}")
        raise


def verify_downloaded_data(era5_file: str, cmems_file: str, output_dir: str = None) -> Dict:
    """
    Verify downloaded ERA5 and CMEMS data
    """
    if output_dir is None:
        output_dir = os.path.join('..', 'data', 'processed')
    
    logger.info("Verifying downloaded data...")
    era5_ds = xr.open_dataset(era5_file)
    cmems_ds = xr.open_dataset(cmems_file)
    
    verification = {
        'era5': {'file': era5_file, 'dimensions': {dim: int(size) for dim, size in era5_ds.dims.items()}},
        'cmems': {'file': cmems_file, 'dimensions': {dim: int(size) for dim, size in cmems_ds.dims.items()}}
    }
    
    era5_ds.close()
    cmems_ds.close()
    return verification


def download_environmental_data(
    image_metadata_file: str,
    output_dir: str = None,
    api_key: str = None,
    skip_if_exists: bool = True
) -> Dict:
    """
    Main processing function: Download all environmental data
    """
    if output_dir is None:
        output_dir = os.path.join('..', 'data', 'processed')
    
    with open(image_metadata_file, 'r') as f:
        metadata = json.load(f)
    
    bounds = metadata['bounds']
    lat_min, lat_max = bounds['bottom'], bounds['top']
    lon_min, lon_max = bounds['left'], bounds['right']
    
    filename = os.path.basename(image_metadata_file).split('.metadata.json')[0]
    # Handle different date formats in filenames
    date_str = filename.split('-00_00')[0]
    date = datetime.strptime(date_str, '%Y-%m-%d')
    
    era5_expected = os.path.join(output_dir, f'era5_wind_{date.strftime("%Y%m%d")}.nc')
    cmems_expected = os.path.join(output_dir, f'cmems_current_{date.strftime("%Y%m%d")}.nc')
    
    # Process ERA5
    if skip_if_exists and os.path.exists(era5_expected):
        era5_file = era5_expected
    else:
        era5_file = download_era5_data(date, lat_min, lat_max, lon_min, lon_max, output_dir, api_key)
    
    # Process CMEMS
    if skip_if_exists and os.path.exists(cmems_expected):
        cmems_file = cmems_expected
    else:
        cmems_file = download_cmems_data(date, lat_min, lat_max, lon_min, lon_max, output_dir)
    
    verification = verify_downloaded_data(era5_file, cmems_file, output_dir)
    
    return {
        'date': date.isoformat(),
        'files': {'era5': era5_file, 'cmems': cmems_file},
        'verification': verification
    }