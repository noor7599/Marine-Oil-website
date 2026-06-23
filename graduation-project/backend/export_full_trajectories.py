"""
export_full_trajectories.py
───────────────────────────
Run this to convert your OpenDrift NetCDF file into a proper per-particle
trajectory CSV that the TrajectoryMap component can animate correctly.

Usage:
    python export_full_trajectories.py \
        --nc  path/to/your_simulation.nc \
        --out path/to/trajectories_full.csv

The output CSV will have one row per particle per timestep:
    trajectory, time, lon, lat, mass_oil, status
    0,  2023-03-18 12:00:00, 121.540, 13.334, 0.68, 0
    1,  2023-03-18 12:00:00, 121.541, 13.335, 0.68, 0
    ...
    999, 2023-03-18 12:30:00, 121.542, 13.330, 0.67, 0
    ...

This is the format the TrajectoryMap parser expects:
  - N particles × T timesteps = N×T rows total
  - Each timestep has exactly N rows (one per particle)
  - The animation will show real per-particle drift + spread
"""

import argparse
import numpy as np
import pandas as pd
import xarray as xr
from pathlib import Path


def export_trajectories(nc_path: str, out_path: str):
    print(f"Loading: {nc_path}")
    ds = xr.open_dataset(nc_path)

    print("Variables found:", list(ds.data_vars))
    print("Dimensions:", dict(ds.dims))

    # OpenDrift NetCDF layout:
    #   dimensions: trajectory (= n_particles), time (= n_timesteps)
    #   variables:  lon[trajectory, time], lat[trajectory, time], ...

    lons = ds["lon"].values          # shape: (n_particles, n_timesteps)
    lats = ds["lat"].values
    times = ds["time"].values        # datetime64 array, length n_timesteps

    n_particles, n_timesteps = lons.shape
    print(f"Particles: {n_particles}  |  Timesteps: {n_timesteps}")

    # Optional variables (present in some OpenDrift runs)
    mass_oil   = ds["mass_oil"].values   if "mass_oil"   in ds else np.ones((n_particles, n_timesteps))
    status     = ds["status"].values     if "status"     in ds else np.zeros((n_particles, n_timesteps))

    rows = []
    for t_idx in range(n_timesteps):
        t_str = pd.Timestamp(times[t_idx]).isoformat(sep=" ", timespec="seconds")
        for p_idx in range(n_particles):
            lon = float(lons[p_idx, t_idx])
            lat = float(lats[p_idx, t_idx])
            if np.isnan(lon) or np.isnan(lat):
                continue          # skip stranded / deactivated particles
            rows.append({
                "trajectory": p_idx,
                "time":       t_str,
                "lon":        round(lon, 6),
                "lat":        round(lat, 6),
                "mass_oil":   round(float(mass_oil[p_idx, t_idx]), 6),
                "status":     int(status[p_idx, t_idx]),
            })

    df = pd.DataFrame(rows)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)

    print(f"\nExported {len(df):,} rows  ({n_particles} particles × {n_timesteps} timesteps)")
    print(f"Saved to: {out_path}")
    print("\nSample (first 5 rows):")
    print(df.head().to_string())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export OpenDrift NetCDF → full trajectory CSV")
    parser.add_argument("--nc",  required=True, help="Path to OpenDrift .nc file")
    parser.add_argument("--out", required=True, help="Output CSV path")
    args = parser.parse_args()
    export_trajectories(args.nc, args.out)