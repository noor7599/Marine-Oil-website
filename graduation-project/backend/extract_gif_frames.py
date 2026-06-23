#!/usr/bin/env python3
"""
extract_gif_frames.py
─────────────────────
Extracts all frames from a trajectory GIF, removes the background
(palette index 0 = the grey/white map background), and saves each
frame as a transparent PNG into:
  <run_dir>/gif_frames/frame_00.png
  <run_dir>/gif_frames/frame_01.png
  ...

Also writes gif_frames/meta.json with frame count and the
geographic bounds read from the trajectory CSV in the same folder.

Usage:
  python3 extract_gif_frames.py <run_id>

Example:
  python3 extract_gif_frames.py 20260430T0042Z
"""

import sys
import os
import json
import csv
from pathlib import Path
from typing import Optional
from PIL import Image

# ─── Locate the run directory ─────────────────────────────────────────────────
def find_run_dir(run_id: str) -> Path:
    script_dir = Path(__file__).parent
    candidates = [
        script_dir / "oilspill_analysis" / "data" / "processed" / "runs" / run_id,
        script_dir / "oilspill_analysis" / "runs" / run_id,
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(
        f"Run directory not found for '{run_id}'.\nChecked:\n" +
        "\n".join(str(c) for c in candidates)
    )

# ─── Find the GIF in visualizations/ ─────────────────────────────────────────
def find_gif(run_dir: Path) -> Path:
    vis_dir = run_dir / "visualizations"
    if not vis_dir.exists():
        raise FileNotFoundError(f"visualizations/ not found in {run_dir}")
    gifs = sorted(vis_dir.glob("*.gif"))
    if not gifs:
        raise FileNotFoundError(f"No .gif files found in {vis_dir}")
    # Prefer trajectory_animation_*.gif
    for g in gifs:
        if g.name.startswith("trajectory_animation_"):
            return g
    return gifs[0]

# ─── Find the trajectory CSV ──────────────────────────────────────────────────
def find_csv(run_dir: Path) -> Optional[Path]:
    vis_dir = run_dir / "visualizations"
    for directory in [vis_dir, run_dir]:
        if not directory.exists():
            continue
        for f in sorted(directory.glob("*.csv")):
            return f   # take the first CSV found
    return None

# ─── Read CSV bounds ──────────────────────────────────────────────────────────
def read_csv_bounds(csv_path: Path) -> dict:
    min_lat, max_lat =  float("inf"), float("-inf")
    min_lon, max_lon =  float("inf"), float("-inf")

    with open(csv_path, newline="") as f:
        # Skip comment lines starting with '#'
        for line in f:
            if not line.startswith('#'):
                # Found the header line; read from here
                reader = csv.DictReader([line] + f.readlines())
                break
        else:
            # No non-comment lines found
            return {}
        
        for row in reader:
            try:
                lat = float(row["lat"])
                lon = float(row["lon"])
            except (KeyError, ValueError, TypeError):
                continue
            if lat < min_lat: min_lat = lat
            if lat > max_lat: max_lat = lat
            if lon < min_lon: min_lon = lon
            if lon > max_lon: max_lon = lon

    if min_lat == float("inf"):
        return {}

    pad_lat = (max_lat - min_lat) * 0.08
    pad_lon = (max_lon - min_lon) * 0.08

    return {
        "minLat": min_lat - pad_lat,
        "maxLat": max_lat + pad_lat,
        "minLon": min_lon - pad_lon,
        "maxLon": max_lon + pad_lon,
    }

# ─── Extract frames with palette-index transparency ───────────────────────────
def extract_frames(gif_path: Path, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    gif = Image.open(gif_path)
    
    # Ensure palette mode for index-based transparency
    if gif.mode != "P":
        gif = gif.convert("P")
    
    n_frames = gif.n_frames
    print(f"  GIF: {gif_path.name}  size={gif.size}  frames={n_frames}  mode={gif.mode}")
    
    # Get palette data [R,G,B,R,G,B,...]
    palette = gif.getpalette()
    if not palette:
        raise ValueError(f"GIF {gif_path.name} has no palette data")
    
    # Build a list of palette indices that are "background" (white or black)
    # These should be made transparent to show the map beneath
    background_indices = set()
    colored_indices = set()
    
    for idx in range(256):
        r = palette[idx * 3]
        g = palette[idx * 3 + 1]
        b = palette[idx * 3 + 2]
        
        # White background or pure black (ocean/water) → transparent
        is_white = (r > 240 and g > 240 and b > 240)
        is_black = (r == 0 and g == 0 and b == 0)
        
        if is_white or is_black:
            background_indices.add(idx)
        else:
            colored_indices.add(idx)
    
    print(f"  ℹ Background indices (transparent): {len(background_indices)} indices")
    print(f"  ℹ Oil/colored indices (opaque): {len(colored_indices)} indices")
    if colored_indices:
        sample_idx = next(iter(colored_indices))
        r = palette[sample_idx * 3]
        g = palette[sample_idx * 3 + 1]
        b = palette[sample_idx * 3 + 2]
        print(f"       Example: index {sample_idx} → RGB({r}, {g}, {b})")
    
    for i in range(n_frames):
        gif.seek(i)
        
        # Get raw palette indices for this frame
        try:
            palette_indices = gif.tobytes()
        except AttributeError:
            palette_indices = gif.tostring()  # PIL < 9.0 compatibility
        
        width, height = gif.size
        
        # Create RGBA image manually
        rgba = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        pixels = rgba.load()
        
        for y in range(height):
            for x in range(width):
                idx = palette_indices[y * width + x]
                if idx in background_indices:
                    # Background: fully transparent
                    pixels[x, y] = (0, 0, 0, 0)
                else:
                    # Foreground (oil): get RGB from palette, full opacity
                    r = palette[idx * 3]
                    g = palette[idx * 3 + 1]
                    b = palette[idx * 3 + 2]
                    pixels[x, y] = (r, g, b, 255)
        
        # Optional realism enhancement: subtle blur for anti-aliasing
        # Uncomment the next 2 lines if frames look too pixelated
        # from PIL import ImageFilter
        # rgba = rgba.filter(ImageFilter.GaussianBlur(radius=0.3))
        
        out_path = out_dir / f"frame_{i:02d}.png"
        rgba.save(out_path, "PNG")
        print(f"  Saved frame {i:02d} → {out_path.name}")
    
    return n_frames

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print("Usage: python3 extract_gif_frames.py <run_id>")
        sys.exit(1)

    run_id  = sys.argv[1]
    print(f"\n=== Extracting GIF frames for run: {run_id} ===\n")

    run_dir  = find_run_dir(run_id)
    gif_path = find_gif(run_dir)
    out_dir  = run_dir / "gif_frames"

    print(f"Run dir : {run_dir}")
    print(f"GIF     : {gif_path}")
    print(f"Output  : {out_dir}\n")

    n_frames = extract_frames(gif_path, out_dir)

    # Read geographic bounds from CSV
    bounds = {}
    csv_path = find_csv(run_dir)
    if csv_path:
        print(f"\n  Reading bounds from: {csv_path.name}")
        bounds = read_csv_bounds(csv_path)
        print(f"  Bounds: {bounds}")
    else:
        print("  ⚠ No CSV found — bounds will be empty")

    # Write meta.json
    meta = {
        "frame_count": n_frames,
        "bounds":      bounds,
        "gif_name":    gif_path.name,
    }
    meta_path = out_dir / "meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"\n  Written: {meta_path}")
    print(f"\n✅ Done — {n_frames} frames extracted to {out_dir}\n")

if __name__ == "__main__":
    main()