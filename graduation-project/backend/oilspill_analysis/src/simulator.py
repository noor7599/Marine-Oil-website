"""
Module for running oil spill simulations using OpenDrift
Notebook 3: Run Simulation
"""

import os
import json
import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional

try:
    import xarray as xr
    from opendrift.readers import reader_netCDF_CF_generic, reader_constant  # type: ignore
    from opendrift.models.openoil import OpenOil  # type: ignore
    OPENDRIFT_AVAILABLE = True
except ImportError:
    OPENDRIFT_AVAILABLE = False

logger = logging.getLogger(__name__)


def run_simulation(
    era5_file: str,
    cmems_file: str,
    release_lat: float,
    release_lon: float,
    release_time: datetime,
    output_dir: str = None,
    num_particles: int = 1000,
    duration_hours: int = 24,
    time_step_minutes: int = 30,
    oil_type: str = 'GENERIC MEDIUM CRUDE'
) -> Dict:
    """
    Run oil spill simulation using OpenDrift
    
    Parameters:
    -----------
    era5_file : str
        Path to ERA5 wind data (NetCDF)
    cmems_file : str
        Path to CMEMS ocean current data (NetCDF)
    release_lat, release_lon : float
        Release location coordinates
    release_time : datetime
        Release time for simulation
    output_dir : str, optional
        Output directory for simulation results
    num_particles : int
        Number of oil particles to simulate
    duration_hours : int
        Simulation duration in hours
    time_step_minutes : int
        Model time step in minutes
    oil_type : str
        Type of oil to simulate
    
    Returns:
    --------
    dict
        Simulation results with metadata
    """
    if not OPENDRIFT_AVAILABLE:
        raise ImportError("OpenDrift not installed. Run: pip install opendrift")
    
    if output_dir is None:
        # Try to use current working directory + outputs, or fallback
        output_dir = os.path.abspath('outputs')
    else:
        output_dir = os.path.abspath(output_dir)
    
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info(f"Initializing OpenOil model...")
    
    # Initialize model
    o = OpenOil(loglevel=20)
    
    # Create readers
    logger.info("Creating data readers...")
    
    # Wave reader (constant, zero values)
    wave_reader = reader_constant.Reader({
        'sea_surface_wave_significant_height': 0.0,
        'sea_surface_wave_stokes_drift_x_velocity': 0.0,
        'sea_surface_wave_stokes_drift_y_velocity': 0.0,
    })
    
    # ERA5 wind reader with mapping
    era5_reader = reader_netCDF_CF_generic.Reader(
        filename=era5_file,
        standard_name_mapping={
            'u10': 'x_wind',
            'v10': 'y_wind'
        }
    )
    
    # CMEMS current reader with mapping
    cmems_reader = reader_netCDF_CF_generic.Reader(
        filename=cmems_file,
        standard_name_mapping={
            'uo': 'eastward_sea_water_velocity',
            'vo': 'northward_sea_water_velocity'
        }
    )
    
    logger.info(f"ERA5 coverage: {era5_reader.start_time} to {era5_reader.end_time}")
    logger.info(f"CMEMS coverage: {cmems_reader.start_time} to {cmems_reader.end_time}")
    
    # Validate release time
    if not (era5_reader.start_time <= release_time <= era5_reader.end_time):
        raise ValueError(f"Release time {release_time} outside ERA5 coverage")
    if not (cmems_reader.start_time <= release_time <= cmems_reader.end_time):
        raise ValueError(f"Release time {release_time} outside CMEMS coverage")
    
    # Add readers to model
    o.add_reader(cmems_reader)
    o.add_reader(era5_reader)
    o.add_reader(wave_reader)
    
    logger.info("Readers added successfully")
    
    # Configure model
    logger.info("Configuring model parameters...")
    o.set_config('seed:oil_type', oil_type)
    o.set_config('general:coastline_action', 'previous')
    o.set_config('drift:horizontal_diffusivity', 1.0)
    o.set_config('drift:wind_uncertainty', 0.2)
    o.set_config('drift:current_uncertainty', 0.1)
    o.set_config('processes:evaporation', True)
    o.set_config('processes:dispersion', True)
    o.set_config('processes:emulsification', True)
    
    # Seed elements
    logger.info(f"Seeding {num_particles} particles...")
    np.random.seed(42)
    o.seed_elements(
        lon=release_lon,
        lat=release_lat,
        radius=100,  # 100m release radius
        number=num_particles,
        time=release_time
    )
    
    # Determine simulation end time
    end_time = min(era5_reader.end_time, cmems_reader.end_time)
    actual_duration = min(duration_hours, int((end_time - release_time).total_seconds() / 3600))
    
    if actual_duration < 1:
        raise ValueError(f"Not enough data coverage for simulation")
    
    logger.info(f"Running simulation for {actual_duration} hours...")
    
    # Generate output filename
    unique_tag = datetime.now().strftime("%H%M%S")
    outfile = os.path.join(
        output_dir,
        f'simulation_{release_time.strftime("%Y%m%dT%H%MZ")}_{unique_tag}.nc'
    )
    
    # Run simulation
    o.run(
        duration=timedelta(hours=actual_duration),
        time_step=timedelta(minutes=time_step_minutes),
        time_step_output=timedelta(minutes=30),  # Output at 12:00 and 12:30 (2 steps per hour)
        outfile=outfile,
        export_variables=[
            'mass_oil', 'water_fraction', 'density',
            'area', 'evaporated_mass', 'viscosity', 'age_seconds'
        ]
    )
    
    logger.info(f"Simulation complete!")
    logger.info(f"Active elements: {o.num_elements_active()}")
    logger.info(f"Deactivated elements: {o.num_elements_deactivated()}")
    
    # Get oil budget (may fail in some OpenDrift versions due to missing 'z' variable)
    budget = {}
    try:
        budget = o.get_oil_budget()
    except KeyError as e:
        if "'z'" in str(e) or "z" in str(e):
            logger.warning(f"Could not compute oil budget (OpenDrift version issue): {e}")
            budget = {
                'status': 'skipped',
                'reason': 'z variable not in output'
            }
        else:
            raise
    
    # Prepare result
    result = {
        'setup': {
            'date': release_time.strftime('%Y-%m-%d'),
            'release_time': release_time.isoformat(),
            'release_location': {
                'latitude': float(release_lat),
                'longitude': float(release_lon)
            },
            'num_particles': num_particles,
            'duration_hours': actual_duration,
            'time_step_minutes': time_step_minutes
        },
        'results': {
            'final_active_elements': int(o.num_elements_active()),
            'deactivated_elements': int(o.num_elements_deactivated()),
            'oil_budget': budget,
            'outfile': outfile
        }
    }
    
    # Save results
    results_file = os.path.join(
        output_dir,
        f'simulation_results_{release_time.strftime("%Y%m%dT%H%MZ")}.json'
    )
    with open(results_file, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    
    logger.info(f"Results saved to {results_file}")
    
    # Release memory (may not be available in all OpenDrift versions)
    try:
        o.release_mem()
    except AttributeError:
        pass
    
    return result


def extract_simulation_trajectories(simulation_nc_file: str) -> np.ndarray:
    """
    Extract particle trajectories from simulation NetCDF file
    
    Parameters:
    -----------
    simulation_nc_file : str
        Path to simulation NetCDF output file
    
    Returns:
    --------
    np.ndarray
        Array of shape (time_steps, 2) with [lon, lat] or (trajectories, time_steps, 2)
    """
    try:
        ds = xr.open_dataset(simulation_nc_file)
        
        if 'lon' not in ds or 'lat' not in ds:
            raise ValueError(f"Required variables 'lon' and 'lat' not found in {simulation_nc_file}")
        
        lon = ds['lon'].values
        lat = ds['lat'].values
        
        # Handle different dimensions: could be (time, traj), (traj, time), or just (time,)
        # Stack into appropriate shape
        if lon.ndim == 1 and lat.ndim == 1:
            # 1D arrays (single trajectory)
            trajectories = np.stack([lon, lat], axis=1)  # Shape: (time_steps, 2)
        elif lon.ndim == 2 and lat.ndim == 2:
            # 2D arrays (multiple trajectories)
            if lon.shape[0] < lon.shape[1]:
                # Likely (time, trajectories) - need to transpose
                lon = lon.T
                lat = lat.T
            trajectories = np.stack([lon, lat], axis=2)  # Shape: (trajectories, time_steps, 2)
        else:
            raise ValueError(f"Unexpected array dimensions: lon={lon.shape}, lat={lat.shape}")
        
        ds.close()
        
        logger.info(f"Extracted trajectories with shape: {trajectories.shape}")
        
        return trajectories
        
    except Exception as e:
        logger.error(f"Error extracting trajectories: {str(e)}")
        raise
