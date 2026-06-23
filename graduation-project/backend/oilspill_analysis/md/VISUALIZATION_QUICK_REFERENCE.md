# Quick Reference - New Visualization & Reporting Functions

## Function 1: 4-Panel CV Visualization
**Location**: `src/cv_utils.py`
**Function**: `create_cv_4panel_visualization()`

### Usage
```python
from src.cv_utils import create_cv_4panel_visualization

create_cv_4panel_visualization(
    sar_image_path="data/raw/sar_image.tiff",
    multiclass_mask_path="data/processed/multiclass_mask.tiff",
    binary_mask_path="data/processed/oil_mask.npy",
    output_path="data/processed/visualizations/cv_4panel.png",
    confidence=0.85,
    oil_area_km2=125.5,
    title="Oil Spill Detection Analysis - 2023-03-18"
)
```

### Parameters
- **sar_image_path** (str): Original SAR TIFF file
- **multiclass_mask_path** (str): Multi-class TIFF from MariNeXt (15 classes)
- **binary_mask_path** (str): Binary oil mask NPY file
- **output_path** (str): Where to save PNG (creates directories if needed)
- **confidence** (float): CV confidence score 0-1 (for annotation)
- **oil_area_km2** (float): Estimated oil area (for annotation)
- **title** (str, optional): Custom title for visualization

### Returns
- **str**: Path to saved PNG file
- **None**: If visualization failed (logged to logger)

### Output
Creates 2x2 panel PNG (150 DPI):
- **Top-left**: Original SAR (grayscale normalization)
- **Top-right**: Detected classes (15-class color map)
- **Bottom-left**: SAR + class overlay
- **Bottom-right**: Oil binary mask (white=oil, black=water)

---

## Function 2: Trajectory Animation GIF
**Location**: `src/cv_utils.py`
**Function**: `create_simulation_gif()`

### Usage
```python
from src.cv_utils import create_simulation_gif

create_simulation_gif(
    trajectory_files=["data/processed/trajectory_20230318.nc"],
    output_path="data/processed/visualizations/drift_animation.gif",
    coastline_data=None,
    title="Oil Drift Trajectory - 2023-03-18",
    fps=2
)
```

### Parameters
- **trajectory_files** (list): List of NetCDF trajectory files (time-sequence)
- **output_path** (str): Where to save GIF
- **coastline_data** (dict, optional): Dict with 'lon' and 'lat' arrays for coastline
- **title** (str, optional): Title for animation frames
- **fps** (int): Frames per second (default: 2)

### Returns
- **str**: Path to saved GIF file
- **None**: If GIF creation failed (logged to logger)

### Features
- Time-indexed frame progression
- Particle color variation by time
- Coastline overlay support (optional)
- Customizable playback speed
- Automatic coastline/directory creation

---

## Function 3: Professional HTML Report
**Location**: `src/report_generator.py`
**Function**: `generate_professional_html_report()`

### Usage
```python
from src.report_generator import generate_professional_html_report

report_path = generate_professional_html_report(
    results=pipeline_results_dict,
    output_path="data/processed/reports/professional_report_20230318.html"
)
```

### Parameters
- **results** (dict): Complete pipeline results dictionary from main_pipeline.py
- **output_path** (str, optional): Custom output path (auto-generates if None)

### Returns
- **str**: Path to generated HTML file

### Included Sections
1. **Header**: Bold announcement with report type
2. **Quick Metrics**: 4-card grid (Decision, Confidence, Date, Status)
3. **Confidence Bar**: Visual 0-100% indicator with gradient
4. **Classifier Analysis**: 3-column grid showing:
   - Computer Vision (pixels, area, confidence, model)
   - Physics-Guided (oceanographic features)
   - NLP (maritime incident analysis, risk level)
5. **Environmental Conditions**: Wind, current, temperature table
6. **Ensemble Logic**: Explanation of 40/30/30 weights
7. **Recommendations**: Action items based on result
8. **Footer**: Disclaimer and metadata

### Styling Features
- Responsive grid layouts
- Gradient header (purple theme)
- Card hover effects
- Color-coded results
- Professional typography
- Mobile-friendly

---

## Function 4: Enhanced Report Generator (Existing)
**Location**: `src/report_generator.py`
**Function**: `generate_pdf_report()`

### Updated Behavior
- **Primary**: Uses fpdf2 (lightweight PDF generation)
- **Fallback 1**: reportlab (if fpdf2 unavailable)
- **Fallback 2**: HTML (if both PDF libraries fail)

### Method
```python
from src.report_generator import generate_pdf_report

pdf_path = generate_pdf_report(
    results=pipeline_results_dict,
    output_path="data/processed/reports/report.pdf"
)
```

---

## Integration in Pipeline

### STEP 3: CV Detection
```python
# Automatically called in main_pipeline.py STEP 3
create_cv_4panel_visualization(
    sar_image_path=str(image_path),
    multiclass_mask_path=multiclass_tiff,
    binary_mask_path=str(mask_path),
    output_path=cv_viz_path,
    confidence=cv_confidence,
    oil_area_km2=cv_area
)
```

### STEP 4: Simulation
```python
# Automatically called in main_pipeline.py STEP 4
create_simulation_gif(
    trajectory_files=[trajectory_file],
    output_path=gif_path,
    title=f"Oil Drift Trajectory - {timestamp}",
    fps=2
)
```

### STEP 9: Report Generation
```python
# Automatically called in main_pipeline.py STEP 9
generate_professional_html_report(results, professional_html_path)
```

---

## Error Handling

All functions include graceful error handling:

```python
try:
    create_cv_4panel_visualization(...)
except Exception as e:
    logger.error(f"Visualization failed: {e}")
    # Pipeline continues, no fatal error
```

**Logging**: All functions use Python's `logging` module
- Enable debug: `logging.getLogger().setLevel(logging.DEBUG)`
- Messages logged to `logs/` directory

---

## Requirements

### Required Packages
```
matplotlib>=3.3.0       # Visualization
rasterio>=1.1.0         # SAR raster I/O
numpy>=1.19.0           # Array operations
xarray>=0.16.0          # NetCDF handling
Pillow>=7.0.0           # Image formats
```

### Optional Packages
```
fpdf2>=2.4.0            # PDF generation (preferred)
reportlab>=3.5.0        # PDF fallback
cartopy>=0.17.0         # Map backgrounds (future)
folium>=0.12.0          # Interactive maps (future)
```

---

## Examples

### Example 1: Full Pipeline Run (Auto-generates all outputs)
```bash
cd d:\L4\ S1\Graduation\ Project\ in\ AI\ \(I\)\Integration\ layer\oilspill_analysis
python src/main/main_pipeline.py --image data/raw/sentinel_image.tiff --csv data/raw/incidents.csv
```

**Output**:
- ✓ 4-panel CV visualization (`cv_4panel_*.png`)
- ✓ Trajectory animation (`trajectory_animation_*.gif`)
- ✓ Professional report (`oil_spill_professional_report_*.html`)
- ✓ Standard reports (HTML, PDF, text)

### Example 2: Generate Visualizations Only
```python
import sys
from pathlib import Path
sys.path.insert(0, 'src')
from cv_utils import create_cv_4panel_visualization

create_cv_4panel_visualization(
    sar_image_path="data/raw/20230318_VV.tiff",
    multiclass_mask_path="data/processed/multiclass_seg.tiff",
    binary_mask_path="data/processed/oil_mask_binary.npy",
    output_path="data/processed/visualizations/my_analysis.png",
    confidence=0.92,
    oil_area_km2=45.3
)
```

### Example 3: Generate Report from Results
```python
import json
from report_generator import generate_professional_html_report

with open("data/processed/pipeline_results.json") as f:
    results = json.load(f)

report = generate_professional_html_report(
    results=results,
    output_path="custom_report.html"
)
print(f"Report: {report}")
```

---

## Troubleshooting

### Issue: "create_cv_4panel_visualization not found"
**Solution**: Ensure import is correct:
```python
from src.cv_utils import create_cv_4panel_visualization
# NOT: from cv_utils import ...
```

### Issue: GIF not generating
**Possible causes**:
- Trajectory file missing or invalid
- xarray not installed
- NetCDF file format issue

**Solution**: Check trajectory file exists:
```bash
ls -la data/processed/simulation*.nc
```

### Issue: Professional report looks plain
**Likely cause**: Browser not rendering CSS properly
**Solution**: Open in modern browser (Chrome, Firefox, Edge)

### Issue: PDF generation fails
**Expected behavior**: Automatically falls back to HTML
**Check output**: Look for `.html` file instead of `.pdf`

---

## Performance Notes

- **4-panel visualization**: 1-3 seconds (depends on image size)
- **GIF animation**: 5-15 seconds (depends on number of frames)
- **HTML report**: <0.5 seconds
- **PDF report**: 1-5 seconds (if library available)

## File Size Notes

- **4-panel PNG**: 2-8 MB (150 DPI)
- **Trajectory GIF**: 5-50 MB (depends on particles/frames)
- **HTML reports**: 100-500 KB
- **PDF reports**: If available, typically 300-800 KB

---

**Last Updated**: 2024
**Compatibility**: Python 3.7+, Windows/Linux/macOS
