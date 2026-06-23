#!/usr/bin/env python3
"""Extract frames from trajectory GIF."""
import sys, os, json
from pathlib import Path
from PIL import Image

def find_run_directory(run_id: str) -> str:
    """Find run directory with detailed logging."""
    backend_root = Path(__file__).parent.absolute()
    print(f"🔍 Searching for run '{run_id}'", file=sys.stderr)
    print(f"   Backend root: {backend_root}", file=sys.stderr)
    
    candidates = [
        backend_root / "oilspill_analysis" / "data" / "processed" / "runs" / run_id,
        backend_root / "oilspill_analysis" / "runs" / run_id,
        backend_root / "results" / run_id,
        Path(run_id),  # Try as absolute path
    ]
    
    for candidate in candidates:
        print(f"   Checking: {candidate}", file=sys.stderr)
        if candidate.exists():
            if (candidate / "visualizations").exists():
                print(f"   ✅ Found: {candidate}", file=sys.stderr)
                return str(candidate.resolve())
            else:
                print(f"   ⚠️ Exists but no visualizations folder", file=sys.stderr)
    
    raise FileNotFoundError(f"Run directory not found for: {run_id}")

def extract_frames(run_id: str):
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"🎬 Extracting frames for run: {run_id}", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)
    
    try:
        run_dir = Path(find_run_directory(run_id))
    except FileNotFoundError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
    
    viz_dir = run_dir / "visualizations"
    if not viz_dir.exists():
        print(f"❌ Visualizations directory not found: {viz_dir}", file=sys.stderr)
        sys.exit(1)
    
    # Find GIF file
    gif_files = list(viz_dir.glob("*trajectory*.gif")) + list(viz_dir.glob("*.gif"))
    if not gif_files:
        print(f"❌ No GIF files found in {viz_dir}", file=sys.stderr)
        print(f"   Files in visualizations: {list(viz_dir.iterdir())}", file=sys.stderr)
        sys.exit(1)
    
    gif_path = sorted(gif_files, key=lambda p: p.stat().st_mtime, reverse=True)[0]
    print(f"📁 Using GIF: {gif_path.name}", file=sys.stderr)
    print(f"   Size: {gif_path.stat().st_size} bytes", file=sys.stderr)
    
    # Create frames directory
    frames_dir = run_dir / "gif_frames"
    try:
        frames_dir.mkdir(exist_ok=True)
        print(f"📁 Created frames directory: {frames_dir}", file=sys.stderr)
    except PermissionError as e:
        print(f"❌ Cannot create frames directory: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Extract frames
    frame_count = 0
    try:
        with Image.open(gif_path) as im:
            print(f"🎞️  Extracting frames...", file=sys.stderr)
            while True:
                output_path = frames_dir / f"frame_{frame_count:02d}.png"
                
                # Convert and save
                if im.mode in ("RGBA", "P"):
                    im.convert("RGBA").save(output_path, "PNG")
                else:
                    im.convert("RGB").save(output_path, "PNG")
                
                frame_count += 1
                
                try:
                    im.seek(im.tell() + 1)
                except EOFError:
                    break
        
        print(f"✅ Extracted {frame_count} frames", file=sys.stderr)
        
        # Write metadata
        metadata = {
            "frame_count": frame_count,
            "bounds": {},
            "source_gif": gif_path.name,
            "extracted_at": __import__("datetime").datetime.utcnow().isoformat() + "Z"
        }
        
        bounds_file = frames_dir / "bounds.json"
        with open(bounds_file, "w") as f:
            json.dump(metadata, f, indent=2)
        
        print(f"📄 Metadata: {bounds_file}", file=sys.stderr)
        print(f"{'='*60}\n", file=sys.stderr)
        
    except Exception as e:
        print(f"❌ Error extracting frames: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python process_gif_frames.py <run_id>", file=sys.stderr)
        sys.exit(1)
    
    extract_frames(sys.argv[1])