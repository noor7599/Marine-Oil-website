#!/usr/bin/env python
"""
Automated setup script for oil spill analysis pipeline
Creates ONE conda environment with all dependencies (core + CV + NLP)
"""

import subprocess
import sys
from pathlib import Path

def run_cmd(cmd, desc=""):
    """Execute shell command"""
    print(f"\n{'='*70}")
    print(f"Running: {desc}")
    print(f"Command: {cmd}")
    print('='*70)
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"❌ Failed: {desc}")
        return False
    print(f"✓ Completed: {desc}")
    return True


def setup_environment():
    """Create unified oilspill environment with all dependencies"""
    print("\n" + "="*70)
    print("SETTING UP UNIFIED OIL SPILL ANALYSIS ENVIRONMENT")
    print("="*70)
    
    print("\n📦 Creating conda environment: oilspill (Python 3.9)")
    if not run_cmd("conda create -n oilspill python=3.9 -y", "Create oilspill environment"):
        return False
    
    project_dir = Path(__file__).parent
    req_file = project_dir / "requirements.txt"
    
    print("\n📥 Installing all dependencies (this may take several minutes)...")
    print("   - Core: opendrift, rasterio, cdsapi")
    print("   - ML: scikit-learn, joblib")
    print("   - CV: torch, mmcv, mmsegmentation, opencv-python")
    print("   - NLP: geopy, reportlab")
    
    cmd = f'conda run -n oilspill pip install -r "{req_file}"'
    if not run_cmd(cmd, "Install all dependencies"):
        return False
    
    print("\n✓ Environment 'oilspill' created successfully!")
    return True


def verify_setup():
    """Verify all components installed correctly"""
    print("\n" + "="*70)
    print("VERIFYING INSTALLATION")
    print("="*70)
    
    checks = [
        ("Core Pipeline", "import src.pipeline; print('✓ Pipeline OK')"),
        ("PyTorch", "import torch; print('✓ PyTorch OK')"),
        ("MMCv", "import mmcv; print('✓ MMCv OK')"),
        ("OpenCV", "import cv2; print('✓ OpenCV OK')"),
        ("NLP (geopy)", "import geopy; print('✓ Geopy OK')"),
        ("Ocean Sim", "import opendrift; print('✓ OpenDrift OK')"),
    ]
    
    failed = []
    for name, cmd in checks:
        result = subprocess.run(
            f'conda run -n oilspill python -c "{cmd}"',
            shell=True, capture_output=True, text=True
        )
        if result.returncode == 0:
            print(result.stdout.strip())
        else:
            print(f"❌ {name} failed")
            failed.append(name)
    
    if failed:
        print(f"\n⚠ Some components failed: {', '.join(failed)}")
        return False
    
    return True


def main():
    """Main setup workflow"""
    print("""
╔════════════════════════════════════════════════════════════════════════╗
║   Oil Spill Analysis Pipeline - Unified Environment Setup             ║
╚════════════════════════════════════════════════════════════════════════╝

This script will create ONE conda environment (oilspill, Python 3.9) with:
  ✓ Core pipeline (opendrift, rasterio, etc.)
  ✓ Computer Vision (torch, mmcv, opencv)
  ✓ NLP Validation (geopy, reportlab)
  ✓ All dependencies to run: python main.py
    """)
    
    input("Press Enter to continue...")
    
    # Setup
    if not setup_environment():
        print("\n✗ Setup failed. Please check the error messages above.")
        return 1
    
    # Verify
    if not verify_setup():
        print("\n⚠ Verification found issues but environment may still work")
    
    # Print summary
    print("""
╔════════════════════════════════════════════════════════════════════════╗
║                    ✓ SETUP COMPLETE!                                  ║
╚════════════════════════════════════════════════════════════════════════╝

To get started:

    1. Activate the environment:
       conda activate oilspill

    2. Run the complete pipeline:
       python main.py

    3. Or run specific steps:
       python main.py --step 0  # CV inference
       python main.py --step 7  # NLP validation
       python main.py --step 6  # Final ensemble decision

    4. With custom image:
       python main.py --image data/raw/your_image.tiff

For troubleshooting, see: CONDA_SETUP.md
    """)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
