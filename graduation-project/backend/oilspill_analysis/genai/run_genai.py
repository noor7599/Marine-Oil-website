#!/usr/bin/env python3
"""
🌍 Oil Spill GenAI Map Visualization (FIXED VERSION)

Now renders:
✔ Real map background (Cartopy)
✔ Lat/Lon correct positioning
✔ Oil spread animation over geography
"""

import os
import sys
import glob
import numpy as np
import pandas as pd
import imageio
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from pathlib import Path


# =========================================================
# FIND LATEST FILE
# =========================================================
def find_latest_trajectory():
    base_path = os.path.join(
        os.path.dirname(__file__),
        "backend",
        "oilspill_analysis",
        "data",
        "processed",
        "runs"
    )

    pattern = os.path.join(base_path, "*", "visualizations", "*trajectories.csv")
    files = glob.glob(pattern)

    if not files:
        raise FileNotFoundError("No trajectory files found")

    return max(files, key=os.path.getmtime)


# =========================================================
# LOAD TRAJECTORIES
# =========================================================
def load_trajectories(csv_path):
    df = pd.read_csv(csv_path, comment="#")

    time_col = None
    for c in ["time", "timestamp", "timestep", "time_step"]:
        if c in df.columns:
            time_col = c
            break

    if time_col is None:
        return {"0": df}

    groups = {}
    for t in sorted(df[time_col].unique()):
        groups[str(t)] = df[df[time_col] == t]

    return groups


# =========================================================
# DRAW ONE FRAME ON REAL MAP
# =========================================================
def draw_frame(df):
    fig = plt.figure(figsize=(8, 6))
    ax = plt.axes(projection=ccrs.PlateCarree())

    ax.add_feature(cfeature.COASTLINE)
    ax.add_feature(cfeature.LAND, color="lightgray")
    ax.add_feature(cfeature.OCEAN, color="lightblue")

    lats = df["lat"].values
    lons = df["lon"].values

    ax.scatter(
        lons,
        lats,
        color="black",
        s=5,
        alpha=0.6,
        transform=ccrs.PlateCarree()
    )

    ax.set_title("Oil Spill Spread Simulation")

    fig.canvas.draw()

    image = np.frombuffer(fig.canvas.tostring_rgb(), dtype="uint8")
    image = image.reshape(fig.canvas.get_width_height()[::-1] + (3,))

    plt.close(fig)
    return image


# =========================================================
# MAIN
# =========================================================
def main():
    print("🌍 Oil Spill MAP GenAI Visualization")
    print("=" * 50)

    traj_path = find_latest_trajectory()
    print("📂 Using:", traj_path)

    data = load_trajectories(traj_path)

    frames = []

    for t, df in sorted(data.items()):
        if len(df) < 2:
            continue

        frame = draw_frame(df)
        frames.append(frame)

    if not frames:
        print("❌ No frames generated")
        return

    output = "spill_map.gif"
    imageio.mimsave(output, frames, fps=2)

    print(f"✅ Saved: {output}")


if __name__ == "__main__":
    main()