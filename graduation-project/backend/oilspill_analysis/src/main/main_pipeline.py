#!/usr/bin/env python3
"""
Main Pipeline Orchestrator (oilspill3 environment)
Complete workflow: CV → Simulation → PG/RF Classification → NLP → Ensemble Decision
"""

import json
import os
import sys
import argparse
import re
from pathlib import Path
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
import time
from datetime import datetime


try:
    import rasterio
except ImportError:
    rasterio = None

# Local imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
from cv_model import run_cv_inference, extract_oil_pixels
from coordinate_extractor import process_sar_image
from data_downloader import download_environmental_data
from simulator import run_simulation
from pg_classifier import classify_with_physical_guidance, create_pg_classifier_visualization
from decision_layer import make_ensemble_decision
from model import validate_detection
from cv_subprocess import CVSubprocessRunner
from cv_utils import create_simulation_gif, export_simulation_for_viewing
from visualizer import (
    create_simulation_map_overlay,
    create_simulation_animation
)
from report_generator import (
    format_nlp_report_text,
    generate_html_report,
    generate_text_report,
    generate_pdf_report,
    generate_final_pdf_report
)


# --- Helper Functions ---
def extract_timestamp_from_filename(filename: str) -> Optional[datetime]:
    """
    Extract date from Sentinel-1 filename pattern.
    Example: 2023-03-18-00_00_2023-03-18-23_59_Sentinel-1_...
    Returns datetime at noon of the detected date, or None if not found.
    """
    # Match pattern like 2023-03-18-00_00 at the start of filename
    match = re.search(r'(\d{4})-(\d{2})-(\d{2})', filename)
    if match:
        try:
            year, month, day = match.groups()
            # Return datetime at noon UTC on the detected date
            return datetime(int(year), int(month), int(day), 12, 0, 0)
        except Exception:
            return None
    return None


# --- Detailed Report Generation ---
def clean_path_for_report(path: str) -> str:
    """
    Extract filename from full path for cleaner report display.
    
    Args:
        path: Full file path
        
    Returns:
        Just the filename, or original if extraction fails
    """
    if not path or not isinstance(path, str):
        return "N/A"
    try:
        return Path(path).name
    except Exception:
        return path


def generate_detailed_report(results: dict, output_dir: Path):
    """
    Generate a professional PDF report using ReportLab.
    
    Includes executive summary, module results, geospatial data, 
    environmental conditions, and recommendations.
    
    Args:
        results: Pipeline results dictionary
        output_dir: Directory to save PDF report
    """
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Table, TableStyle, 
            Spacer, PageBreak, Image
        )
    except ImportError:
        print("ReportLab not installed. Falling back to text report.")
        return generate_text_fallback_report(results, output_dir)
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "final_report.pdf"
    
    try:
        # Initialize PDF document
        doc = SimpleDocTemplate(
            str(report_path),
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch,
        )
        
        # Container for PDF elements
        story = []
        
        # Get styles
        styles = getSampleStyleSheet()
        
        # Define custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a3a52'),
            spaceAfter=6,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#2c5aa0'),
            spaceAfter=12,
            spaceBefore=12,
            fontName='Helvetica-Bold'
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            fontName='Helvetica'
        )

        def _format_year(value) -> str:
            if value is None:
                return "N/A"
            # pandas.Timestamp / datetime / date objects typically expose .year
            try:
                year = getattr(value, "year", None)
                if year is not None:
                    return str(int(year))
            except Exception:
                pass
            try:
                s = str(value)
                return s[:4] if len(s) >= 4 and s[:4].isdigit() else "N/A"
            except Exception:
                return "N/A"
        
        # Extract key data
        now = datetime.now()
        start_time = results.get('start_time', now)
        duration = results.get('duration', 0)
        if not duration and 'end_time' in results:
            try:
                duration = (results['end_time'] - start_time).total_seconds()
            except Exception:
                duration = 0
        
        input_image = results.get('input_image', 'N/A')
        input_filename = clean_path_for_report(input_image)
        
        cv = results.get('steps', {}).get('cv', {})
        pg = results.get('steps', {}).get('pg_classification', {})
        rf = results.get('steps', {}).get('rf_classification', {})
        nlp = results.get('steps', {}).get('nlp_validation', {})
        ensemble = results.get('steps', {}).get('ensemble_decision', {})
        env = results.get('steps', {}).get('environmental_data', {})
        coords = results.get('steps', {}).get('coordinate_extraction', {}).get('coordinates', {})
        
        # ===== 1. COVER HEADER =====
        story.append(Paragraph("Oil Spill Detection Analysis Report", title_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Metadata table
        metadata = [
            ['Run Timestamp:', now.strftime('%Y-%m-%d %H:%M:%S UTC')],
            ['Input Image:', input_filename],
            ['Processing Duration:', f'{duration:.1f} seconds'],
        ]
        
        metadata_table = Table(metadata, colWidths=[2*inch, 3.5*inch])
        metadata_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Helvetica', 9),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1a3a52')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f0f7ff')]),
        ]))
        story.append(metadata_table)
        story.append(Spacer(1, 0.3*inch))
        
        # ===== 2. EXECUTIVE SUMMARY =====
        final_pred = ensemble.get('final_prediction', 'Unknown')
        final_conf = ensemble.get('final_confidence', 0)
        is_oil = final_pred == 'Oil-like'
        
        alert_color = colors.HexColor('#c92a2a') if is_oil else colors.HexColor('#2b8a3e')
        alert_text = 'ALERT: OIL SPILL DETECTED' if is_oil else 'NO OIL SPILL DETECTED'
        
        # Alert box
        alert_para = Paragraph(
            f'<b>{alert_text}</b>',
            ParagraphStyle(
                'Alert',
                parent=styles['Normal'],
                fontSize=16,
                textColor=colors.white,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            )
        )
        
        alert_table = Table([[alert_para]], colWidths=[5.5*inch])
        alert_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), alert_color),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(alert_table)
        story.append(Spacer(1, 0.15*inch))
        
        # Confidence summary
        conf_text = f'Overall Confidence: <b>{final_conf*100:.1f}%</b>'
        story.append(Paragraph(conf_text, normal_style))
        story.append(Spacer(1, 0.25*inch))
        
        # ===== 3. CV DETECTION RESULTS =====
        story.append(Paragraph('1. Computer Vision Detection Results', heading_style))
        
        cv_data = [
            ['Metric', 'Value'],
            ['Model', 'MariNeXt'],
            ['Status', cv.get('status', 'N/A')],
            ['Oil Detected', 'YES' if cv.get('detected') else 'NO'],
            ['Confidence', f"{cv.get('confidence', 0)*100:.1f}%"],
            ['Oil Pixels', f"{cv.get('oil_pixels', 0):,}"],
            ['Total Pixels', f"{cv.get('total_pixels', 0):,}"],
            ['Oil Coverage', f"{cv.get('oil_percentage', 0):.2f}%"],
        ]
        
        cv_table = Table(cv_data, colWidths=[2.5*inch, 3*inch])
        cv_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ]))
        story.append(cv_table)
        story.append(Spacer(1, 0.25*inch))
        
        # ===== 4. GEOSPATIAL INFORMATION =====
        story.append(Paragraph('2. Geospatial Information', heading_style))
        
        geo_data = [
            ['Parameter', 'Value'],
            ['Latitude Min', f"{coords.get('lat_min', 'N/A'):.4f}"],
            ['Latitude Max', f"{coords.get('lat_max', 'N/A'):.4f}"],
            ['Longitude Min', f"{coords.get('lon_min', 'N/A'):.4f}"],
            ['Longitude Max', f"{coords.get('lon_max', 'N/A'):.4f}"],
        ]
        
        geo_table = Table(geo_data, colWidths=[2.5*inch, 3*inch])
        geo_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ]))
        story.append(geo_table)
        story.append(Spacer(1, 0.25*inch))
        
        # ===== 5. ENVIRONMENTAL DATA =====
        story.append(Paragraph('3. Environmental Data', heading_style))
        
        env_data = [['Dataset', 'File']]
        if 'files' in env:
            for k, v in env['files'].items():
                env_data.append([k.upper(), clean_path_for_report(v)])
        
        env_table = Table(env_data, colWidths=[2*inch, 3.5*inch])
        env_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ]))
        story.append(env_table)
        story.append(Spacer(1, 0.25*inch))
        
        # ===== 6. NLP VALIDATION SUMMARY =====
        story.append(Paragraph('4. NLP Validation & Historical Correlation', heading_style))
        
        nlp_data = [
            ['Metric', 'Value'],
            ['Risk Level', nlp.get('risk_level', 'N/A')],
            ['Confidence', f"{nlp.get('confidence', 0)*100:.1f}%"],
            ['Distance Matches', str(nlp.get('distance_matches', 0))],
            ['Time Matches', str(nlp.get('time_matches', 0))],
            ['Joint Matches', str(nlp.get('joint_matches', 0))],
        ]
        
        nlp_table = Table(nlp_data, colWidths=[2.5*inch, 3*inch])
        nlp_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightyellow),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ]))
        story.append(nlp_table)
        
        # Closest historical incident
        if nlp.get('reports') and isinstance(nlp['reports'], dict):
            by_distance = nlp['reports'].get('by_distance', [])
            if by_distance and len(by_distance) > 0:
                incident = by_distance[0]
                story.append(Spacer(1, 0.15*inch))
                distance_km = incident.get('distance_km', None)
                distance_str = f"{float(distance_km):.1f} km" if isinstance(distance_km, (int, float)) else "N/A"
                closest_text = (
                    f"<b>Closest Historical Incident:</b> {incident.get('name', 'N/A')}<br/>"
                    f"Location: {incident.get('location', 'N/A')}<br/>"
                    f"Distance: {distance_str}<br/>"
                    f"Year: {_format_year(incident.get('date', None))}"
                )
                story.append(Paragraph(closest_text, normal_style))
        
        story.append(Spacer(1, 0.25*inch))
        
        # ===== 7. MODULE BREAKDOWN TABLE =====
        story.append(Paragraph('5. Module Breakdown & Ensemble Decision', heading_style))
        
        module_data = [['Module', 'Prediction', 'Confidence', 'Weight']]
        
        if 'individual_decisions' in ensemble:
            for d in ensemble['individual_decisions']:
                module_data.append([
                    d.get('model_name', 'Unknown'),
                    d.get('prediction', 'N/A'),
                    f"{d.get('confidence', 0)*100:.1f}%",
                    f"{d.get('weight', 0)*100:.0f}%"
                ])
        
        if not module_data or len(module_data) == 1:
            # Fallback: manually construct from available classifiers
            module_data.append([
                'CV Detection',
                'Oil' if cv.get('detected') else 'Non-Oil',
                f"{cv.get('confidence', 0)*100:.1f}%",
                '40%'
            ])
            module_data.append([
                'Physics-Guided',
                pg.get('classification', 'N/A'),
                f"{pg.get('confidence', 0)*100:.1f}%",
                '30%'
            ])
            module_data.append([
                'NLP Validation',
                'Oil' if nlp.get('confidence', 0) > 0.5 else 'Non-Oil',
                f"{nlp.get('confidence', 0)*100:.1f}%",
                '30%'
            ])
        
        module_table = Table(module_data, colWidths=[1.8*inch, 1.5*inch, 1.3*inch, 0.9*inch])
        module_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a3a52')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#e6f2ff')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ]))
        story.append(module_table)
        story.append(Spacer(1, 0.25*inch))
        
        # ===== 8. RECOMMENDATIONS =====
        story.append(Paragraph('6. Recommendations & Actions', heading_style))
        
        if is_oil:
            rec_text = """
            <b>OIL SPILL DETECTED - IMMEDIATE ACTION REQUIRED:</b><br/>
            <br/>
            &#8226; Contact maritime authorities and coast guard immediately<br/>
            &#8226; Deploy response teams and containment equipment<br/>
            &#8224; Monitor drift simulation for trajectory prediction<br/>
            &#8224; Cross-check with satellite imagery and aerial surveys<br/>
            &#8224; Activate environmental assessment protocols<br/>
            &#8224; Document all findings and prepare response briefings<br/>
            """
        else:
            rec_text = """
            <b>NO OIL SPILL DETECTED - MAINTAIN STANDARD PROTOCOLS:</b><br/>
            <br/>
            &#8226; Continue regular satellite monitoring of the region<br/>
            &#8224; Maintain surveillance systems on alert<br/>
            &#8224; Re-analyze if new adverse signals are detected<br/>
            &#8224; Share images with monitoring networks for cross-validation<br/>
            &#8224; Schedule regular follow-up checks as per protocol<br/>
            """
        
        story.append(Paragraph(rec_text, normal_style))
        story.append(Spacer(1, 0.25*inch))
        
        # ===== 9. WARNINGS/ERRORS =====
        warnings = results.get('warnings', [])
        errors = results.get('errors', [])
        
        if warnings or errors:
            story.append(Paragraph('7. Warnings & Errors', heading_style))
            
            if warnings:
                story.append(Paragraph('<b>Warnings:</b>', normal_style))
                for w in warnings:
                    story.append(Paragraph(f'&#8226; {str(w)[:100]}', normal_style))
                story.append(Spacer(1, 0.1*inch))
            
            if errors:
                story.append(Paragraph('<b>Errors:</b>', normal_style))
                for e in errors:
                    story.append(Paragraph(f'&#8226; {str(e)[:100]}', normal_style))
                story.append(Spacer(1, 0.1*inch))
        
        # ===== FOOTER =====
        story.append(Spacer(1, 0.4*inch))
        footer_text = """
        <i>This report was automatically generated by the Oil Spill Detection Pipeline.<br/>
        Final deployment decisions must be made by qualified maritime authorities based on multiple data sources.<br/>
        For technical details, refer to the complete pipeline results JSON file.</i>
        """
        story.append(Paragraph(footer_text, ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER
        )))
        
        # Build PDF
        doc.build(story)
        print(f"✓ Professional PDF report saved: {report_path}")
        return str(report_path)
        
    except Exception as e:
        print(f"Error generating PDF report: {e}")
        import traceback
        traceback.print_exc()
        return generate_text_fallback_report(results, output_dir)


def generate_text_fallback_report(results: dict, output_dir: Path):
    """
    Fallback text report generator if PDF creation fails.
    """
    report_lines = []
    now = datetime.now()
    
    report_lines.append("=" * 70)
    report_lines.append("OIL SPILL DETECTION ANALYSIS REPORT")
    report_lines.append("=" * 70)
    report_lines.append(f"Run Timestamp: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"Input Image: {results.get('input_image', 'N/A')}")
    report_lines.append("")
    
    ensemble = results.get('steps', {}).get('ensemble_decision', {})
    is_oil = ensemble.get('final_prediction') == 'Oil-like'
    alert = "OIL SPILL DETECTED" if is_oil else "NO OIL SPILL DETECTED"
    report_lines.append(f"STATUS: {alert}")
    report_lines.append(f"Confidence: {ensemble.get('final_confidence', 0):.1%}")
    report_lines.append("=" * 70)
    report_lines.append("")
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "final_report.txt"
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))
    
    print(f"Text report saved as fallback: {report_path}")
    return str(report_path)


class HybridPipeline:
    """Full orchestrator: CV subprocess + trajectory + classifiers + NLP + ensemble."""
    
    def __init__(self, config_path: str = None, conda_env: str = "mados"):
        """
        Initialize pipeline.
        
        Args:
            config_path: Path to config.json (auto-detected if None)
            conda_env: Name of mados environment for CV
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config.json"
        
        self.config_path = Path(config_path)
        self.workspace_root = self.config_path.parent
        self.data_dir = self.workspace_root / "data"
        self.processed_dir = self.data_dir / "processed"
        self.visualizations_dir = self.processed_dir / "visualizations"
        self.reports_dir = self.workspace_root / "data" / "reports"
        self.masks_dir = self.processed_dir / "masks"
        
        # Create output directories
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.visualizations_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.masks_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize CV subprocess runner
        self.cv_runner = CVSubprocessRunner(
            conda_env=conda_env,
            workspace_root=str(self.workspace_root)
        )
    
    def run_full_pipeline(self, image_path: str, run_cv: bool = True,
                          csv_path: str = None) -> Dict[str, Any]:
        """
        Run complete pipeline with all stages.
        
        Args:
            image_path: Path to SAR image
            run_cv: Whether to run CV subprocess (True) or use threshold detector (False)
            csv_path: Path to incidents CSV for NLP validation
        
        Returns:
            Dict with all pipeline results
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        # Create a dedicated folder for this run (all results in one place)
        run_timestamp = datetime.now().strftime("%Y%m%dT%H%MZ")  # Safe for filenames (no colons)
        self.run_dir = self.processed_dir / "runs" / run_timestamp
        self.run_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / "visualizations").mkdir(exist_ok=True)
        (self.run_dir / "reports").mkdir(exist_ok=True)
        self.visualizations_dir = self.run_dir / "visualizations"
        self.reports_dir = self.run_dir / "reports"
        print(f"  Run output folder: {self.run_dir}")
        
        print(f"\n{'='*70}")
        print(f"COMPREHENSIVE OIL SPILL PIPELINE")
        print(f"{'='*70}\n")
        
        results = {
            "input_image": str(image_path),
            "steps": {}
        }
        
        # STEP 1: CV Detection
        print("[STEP 1] Computer Vision Detection...")
        if run_cv:
            success, cv_result = self.cv_runner.run_inference(str(image_path))
            if success:
                print(f"  ✓ MariNeXt Success: {cv_result['mask_path']}")
                print(f"  ✓ Confidence: {cv_result.get('confidence', 'N/A')}")
                results["steps"]["cv"] = cv_result
                mask_path = cv_result['mask_path']
                # Copy CV outputs from temp/output into run folder so they appear with other results
                import shutil
                for key, dest_name in [
                    ('mask_path', 'cv_binary_mask'),
                    ('oil_binary_png_path', 'cv_oil_binary.png'),
                    ('visualization_path', 'cv_detection_panel.png'),
                ]:
                    src = cv_result.get(key)
                    if not src or not Path(src).exists():
                        continue
                    src_path = Path(src)
                    if key == 'mask_path':
                        dest_name = 'cv_binary_mask' + src_path.suffix
                    dest_path = self.visualizations_dir / dest_name
                    try:
                        shutil.copy2(src_path, dest_path)
                        print(f"  ✓ CV output copied: {dest_name}")
                    except Exception as e:
                        print(f"  ⚠ Copy failed for {dest_name}: {e}")
                # Copy cv_results.json from temp/output into run folder
                cv_results_src = self.cv_runner.temp_dir / "output" / "cv_results.json"
                if cv_results_src.exists():
                    import shutil
                    try:
                        shutil.copy2(cv_results_src, self.run_dir / "cv_results.json")
                        print(f"  ✓ cv_results.json copied to run folder")
                    except Exception as e:
                        print(f"  ⚠ Copy cv_results.json failed: {e}")
            else:
                print(f"  ✗ CV Failed, using threshold detector: {cv_result.get('error', 'Unknown')}")
                run_cv = False
        
        if not run_cv:
            output_dir = self.processed_dir
            cv_tuple = run_cv_inference(str(image_path), str(output_dir))
            
            # Handle tuple or dict return from run_cv_inference
            if isinstance(cv_tuple, tuple):
                mask_path_temp, stats = cv_tuple
                cv_result = {
                    "mask_path": str(mask_path_temp),
                    "status": "success",
                    "confidence": stats.get("confidence", 0.0) if isinstance(stats, dict) else 0.0,
                }
                if isinstance(stats, dict):
                    cv_result.update(stats)
            else:
                cv_result = cv_tuple
            
            print(f"  ✓ Threshold Detector: {cv_result.get('mask_path', 'Unknown')}")
            results["steps"]["cv"] = cv_result
            mask_path = cv_result.get('mask_path', '')
            # Copy mask into run folder when using threshold detector (no temp/output)
            if mask_path and Path(mask_path).exists():
                import shutil
                dest = self.visualizations_dir / ("cv_binary_mask" + Path(mask_path).suffix)
                try:
                    shutil.copy2(mask_path, dest)
                    print(f"  ✓ CV mask copied to run folder: {dest.name}")
                except Exception as e:
                    print(f"  ⚠ Copy mask failed: {e}")
        
        # Set visualization_path for reports when we have a panel in run folder
        cv_step = results.get("steps", {}).get("cv", {})
        panel_path = self.visualizations_dir / "cv_detection_panel.png"
        if panel_path.exists() and cv_step:
            cv_step["visualization_path"] = str(panel_path)
        
        # STEP 2: Coordinate Extraction and Environmental Data
        print("\n[STEP 2] Coordinate Extraction & Environmental Data...")
        try:
            coord_info = process_sar_image(str(image_path), str(self.processed_dir))
            print(f"  ✓ Coordinates: {coord_info['coordinates']}")
            results["steps"]["coordinate_extraction"] = coord_info

            # metadata JSON produced by process_sar_image
            metadata_file = str(self.processed_dir / (image_path.name + '.metadata.json'))
            try:
                env_res = download_environmental_data(metadata_file, output_dir=str(self.processed_dir))
                print("  ✓ Environmental data downloaded")
                results["steps"]["environmental_data"] = env_res
            except Exception as e:
                print(f"  ✗ Environmental download failed: {e}")
                results["steps"]["environmental_data"] = {"error": str(e)}
        except Exception as e:
            print(f"  ✗ Coordinate extraction failed: {e}")
            results["steps"]["coordinate_extraction"] = {"error": str(e)}
            # proceed without coordinates
            coord_info = None
        
        # STEP 3: Extract oil pixel statistics (from CV mask)
        print("\n[STEP 3] Oil Pixel Analysis...")
        try:
            oil_stats = extract_oil_pixels(mask_path)
            oil_px = oil_stats.get('oil_pixels', oil_stats.get('oil_pixel_count', 0))
            total_px = oil_stats.get('total_pixels', 1)
            print(f"  ✓ Oil pixels: {oil_px:,}")
            # Estimate area from coordinates if available
            oil_area_km2 = 0.0
            coord_meta = results.get('steps', {}).get('coordinate_extraction', {}).get('metadata', {})
            if coord_meta.get('transform') and total_px > 0 and oil_px > 0:
                try:
                    import math
                    t = coord_meta['transform']
                    px_w_deg = abs(float(t[0])) if len(t) >= 2 else 1e-4
                    px_h_deg = abs(float(t[4])) if len(t) >= 6 else 1e-4
                    b = coord_meta.get('bounds', {})
                    lat_mid = (float(b.get('bottom', 0)) + float(b.get('top', 0))) / 2
                    km_per_deg_lon = 111.32 * max(0.01, abs(math.cos(math.radians(lat_mid))))
                    km_per_deg_lat = 111.32
                    area_km2_per_px = (px_w_deg * km_per_deg_lon) * (px_h_deg * km_per_deg_lat)
                    oil_area_km2 = oil_px * area_km2_per_px
                except Exception:
                    pass
            oil_stats['oil_area_km2'] = oil_area_km2
            print(f"  ✓ Oil area: {oil_area_km2:.2f} km²")
            results["steps"]["oil_analysis"] = oil_stats
        except Exception as e:
            print(f"  ✗ Oil analysis failed: {str(e)}")
            print(f"    (This is OK - continuing with other steps)")
            oil_stats = {"oil_pixels": 0, "oil_pixel_count": 0, "oil_area_km2": 0.0}
        
        # STEP 4: Trajectory Simulation
        print("\n[STEP 4] Trajectory Simulation...")
        # --- Environmental file verification ---
        def verify_env_files(results):
            env = results.get('steps', {}).get('environmental_data', {})
            files = env.get('files', {})
            missing = []
            for k, v in files.items():
                p = Path(v)
                if not p.exists() or p.stat().st_size == 0:
                    missing.append((k, str(p)))
            return missing, files

        missing, env_files = verify_env_files(results)
        if missing:
            print("WARNING: Environmental data files missing or empty:")
            for k, path in missing:
                print(f"  {k}: {path}")
            simulation_result = {
                "status": "skipped",
                "reason": f"Environmental data not found: {[p for _, p in missing]}"
            }
            results["steps"]["simulation"] = simulation_result
            trajectory_file = None
        else:
            print("All environmental data files verified.")
            try:
                # Actually run the simulation with verified environmental data
                print(f"  ▸ Running simulation with ERA5: {env_files.get('era5')}")
                print(f"  ▸ Running simulation with CMEMS: {env_files.get('cmems')}")
                
                # Extract coordinates for simulation center point
                coords = results["steps"].get("coordinate_extraction", {}).get("coordinates", {})
                release_lat = (coords.get('lat_min', 0) + coords.get('lat_max', 0)) / 2
                release_lon = (coords.get('lon_min', 0) + coords.get('lon_max', 0)) / 2
                
                # Extract release time: Priority 1. Metadata, 2. Filename, 3. Current Time (Warning)
                metadata = results["steps"].get("coordinate_extraction", {}).get("metadata", {})
                timestamp_str = metadata.get("DateTime") or metadata.get("TIFFTAG_DATETIME")
                release_time = None
                release_time_source = None
                
                # Priority 1: Try to parse metadata timestamp
                if timestamp_str:
                    try:
                        release_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        release_time_source = "Metadata"
                    except Exception:
                        pass
                
                # Priority 2: Try to extract from input image filename
                if release_time is None:
                    input_image = results["steps"].get("coordinate_extraction", {}).get("image_path", "")
                    if input_image:
                        filename = Path(input_image).name
                        release_time = extract_timestamp_from_filename(filename)
                        if release_time:
                            release_time_source = "Filename"
                
                # Priority 3: Fall back to current time with warning
                if release_time is None:
                    release_time = datetime.now()
                    release_time_source = "System Time (WARNING)"
                    print(f"  ⚠️  Warning: Could not extract timestamp from metadata or filename.")
                    print(f"      Using current time: {release_time.isoformat()}")
                    print(f"      This may cause simulation errors if data is not from today.")
                
                print(f"  ▸ Release time source: {release_time_source}")
                print(f"  ▸ Release time: {release_time.isoformat()}")
                
                # Call run_simulation with correct parameters (returns dict, not file path)
                # duration_hours=24 so trajectory has many output steps (e.g. 12:00 … 23:00)
                sim_result = run_simulation(
                    era5_file=env_files.get('era5'),
                    cmems_file=env_files.get('cmems'),
                    release_lat=release_lat,
                    release_lon=release_lon,
                    release_time=release_time,
                    output_dir=str(self.run_dir),
                    duration_hours=24
                )
                
                # Extract trajectory file from simulation result
                trajectory_file = sim_result.get('results', {}).get('outfile', None)
                
                # Generate trajectory GIF animation
                try:
                    if trajectory_file and Path(trajectory_file).exists():
                        gif_path = str(self.visualizations_dir / f"trajectory_animation_{run_timestamp}.gif")
                        create_simulation_gif(
                            trajectory_files=[trajectory_file],
                            output_path=gif_path,
                            title=f"Oil Drift Trajectory - {run_timestamp}",
                            fps=2
                        )
                        print(f"  ✓ Trajectory animation saved: {gif_path}")
                        sim_result['gif_path'] = gif_path
                        # Easy-to-view export: static map PNG + CSV (keeps .nc)
                        view_export = export_simulation_for_viewing(
                            nc_path=trajectory_file,
                            output_dir=str(self.visualizations_dir),
                            map_title=f"Simulation trajectories – {Path(trajectory_file).stem}",
                        )
                        if view_export:
                            sim_result['viewable_export'] = view_export
                            print(f"  ✓ Simulation map: {view_export.get('map_png', '')}")
                            if view_export.get('csv'):
                                print(f"  ✓ Simulation CSV: {view_export.get('csv')}")
                except Exception as e:
                    print(f"  ⚠ Trajectory GIF generation failed: {e}")
                
                simulation_result = {
                    "status": "success",
                    "era5_file": env_files.get('era5'),
                    "cmems_file": env_files.get('cmems'),
                    "trajectory_file": trajectory_file,
                    "setup": sim_result.get('setup', {}),
                    "results_summary": {
                        "active_elements": sim_result.get('results', {}).get('final_active_elements'),
                        "deactivated_elements": sim_result.get('results', {}).get('deactivated_elements')
                    },
                    "gif_path": sim_result.get('gif_path'),
                    "viewable_export": sim_result.get('viewable_export'),
                }
                print(f"  ✓ Simulation completed: {trajectory_file}")
                results["steps"]["simulation"] = simulation_result
            except Exception as e:
                print(f"  ✗ Simulation failed: {str(e)}")
                import traceback
                traceback.print_exc()
                simulation_result = {
                    "status": "failed",
                    "error": str(e),
                    "era5_file": env_files.get('era5'),
                    "cmems_file": env_files.get('cmems')
                }
                results["steps"]["simulation"] = simulation_result
                trajectory_file = None
        
        # STEP 5: Physical-Guided Classification
        print("\n[STEP 5] Physics-Guided Classification...")
        try:
            # Check if trajectory simulation succeeded
            sim_step = results["steps"].get("simulation", {})
            if trajectory_file is None or sim_step.get("status") != "success":
                print(f"  ⊘  PG Classification skipped (simulation unavailable)")
                pg_result = {
                    "classification": "Not performed",
                    "confidence": 0.0,
                    "status": "skipped",
                    "reason": "Trajectory simulation failed"
                }
                results["steps"]["pg_classification"] = pg_result
            else:
                # Load SAR image and extract mask
                from PIL import Image
                
                # Load SAR image - try rasterio first, then PIL
                sar_data = None
                if rasterio:
                    try:
                        with rasterio.open(str(image_path)) as src:
                            sar_data = src.read(1).astype(np.float32)
                        print(f"  ▸ Loaded SAR image (rasterio): shape {sar_data.shape}")
                    except Exception as e:
                        print(f"  ▸ Rasterio failed, trying PIL: {str(e)}")
                
                if sar_data is None:
                    # Fallback to PIL
                    sar_image = Image.open(str(image_path)).convert('L')
                    sar_data = np.array(sar_image, dtype=np.float32)
                    print(f"  ▸ Loaded SAR image (PIL): shape {sar_data.shape}")
                
                # Load mask
                mask_data = None
                if mask_path and Path(mask_path).exists():
                    if str(mask_path).endswith('.npy'):
                        mask_data = np.load(mask_path, allow_pickle=True).astype(np.uint8)
                    else:
                        img = Image.open(mask_path).convert('L')
                        mask_data = (np.array(img) > 0).astype(np.uint8)
                    print(f"  ▸ Loaded mask: shape {mask_data.shape}")
                
                if mask_data is None or mask_data.sum() == 0:
                    print(f"  ⊘  PG Classification skipped (no valid mask)")
                    pg_result = {
                        "classification": "Not performed",
                        "confidence": 0.0,
                        "status": "skipped",
                        "reason": "No valid mask"
                    }
                    results["steps"]["pg_classification"] = pg_result
                else:
                    # Extract spot centroid from mask
                    from scipy import ndimage
                    labeled, num_features = ndimage.label(mask_data)
                    if num_features == 0:
                        raise ValueError("No connected components in mask")
                    
                    # Get centroid of largest connected component
                    sizes = ndimage.sum(mask_data, labeled, range(num_features + 1))
                    largest_label = np.argmax(sizes)
                    centroid_coords = ndimage.center_of_mass(mask_data, labeled, largest_label)

                    # Convert pixel-space centroid to lat/lon using raster transform when available,
                    # with proportional interpolation fallback.
                    coords = results["steps"].get("coordinate_extraction", {}).get("coordinates", {}) or {}
                    centroid_row, centroid_col = float(centroid_coords[0]), float(centroid_coords[1])
                    spot_centroid = None

                    # Primary: use rasterio transform
                    if rasterio is not None:
                        try:
                            with rasterio.open(str(image_path)) as src:
                                x, y = src.xy(centroid_row, centroid_col)
                                # rasterio returns (x=lon, y=lat)
                                spot_centroid = (float(y), float(x))
                        except Exception as e:
                            print(f"  ⚠ Spot centroid geo-conversion via rasterio failed: {e}")
                            spot_centroid = None

                    # Fallback: proportional interpolation within coordinate bounds
                    if spot_centroid is None and coords:
                        try:
                            lat_min = float(coords.get('lat_min', 0.0))
                            lat_max = float(coords.get('lat_max', 0.0))
                            lon_min = float(coords.get('lon_min', 0.0))
                            lon_max = float(coords.get('lon_max', 0.0))
                            h, w = mask_data.shape
                            # Normalize row/col to [0,1]
                            row_norm = centroid_row / max(h - 1, 1)
                            col_norm = centroid_col / max(w - 1, 1)
                            lat_center = lat_min + (lat_max - lat_min) * row_norm
                            lon_center = lon_min + (lon_max - lon_min) * col_norm
                            spot_centroid = (lat_center, lon_center)
                        except Exception as e:
                            print(f"  ⚠ Spot centroid fallback interpolation failed: {e}")
                            spot_centroid = None

                    # Absolute fallback: use bbox center if everything else failed
                    if spot_centroid is None:
                        lat_center = (coords.get('lat_min', 0.0) + coords.get('lat_max', 0.0)) / 2
                        lon_center = (coords.get('lon_min', 0.0) + coords.get('lon_max', 0.0)) / 2
                        spot_centroid = (lat_center, lon_center)

                    print(f"  ▸ Spot centroid: lat={spot_centroid[0]:.6f}, lon={spot_centroid[1]:.6f}")
                    
                    # Call PG classifier with correct parameters
                    pg_result = classify_with_physical_guidance(
                        sar_image=sar_data,
                        binary_mask=mask_data,
                        simulation_file=trajectory_file,
                        spot_centroid=spot_centroid
                    )
                    print(f"  ✓ PG Classification completed: {pg_result.get('classification')} (conf={pg_result.get('confidence', 0):.2f})")
                    
                    # Generate PG visualization (use preprocessed oil_binary.png from temp/output when available)
                    try:
                        binary_mask_path_for_pg = cv_result.get('oil_binary_png_path') or mask_path
                        pg_viz_result = create_pg_classifier_visualization(
                            binary_mask_path=str(binary_mask_path_for_pg),
                            sar_image_path=str(image_path),
                            classification_result=pg_result,
                            output_dir=str(self.visualizations_dir)
                        )
                        if pg_viz_result:
                            print(f"  ✓ PG Visualizations generated: {len(pg_viz_result)} outputs")
                            # Add visualization paths to result
                            pg_result['visualization_paths'] = pg_viz_result
                    except Exception as e:
                        print(f"  ⚠ PG visualization failed: {e}")
                    
                    results["steps"]["pg_classification"] = pg_result
        except Exception as e:
            print(f"  ✗ PG Classification failed: {str(e)}")
            import traceback
            traceback.print_exc()
            results["steps"]["pg_classification"] = {"error": str(e), "status": "failed"}
            pg_result = {"classification": "Not performed", "confidence": 0.0}
        
        # STEP 6: Random Forest Classification
        # STEP 6: NLP Validation (RF removed - ensemble now uses CV, PG, NLP only)
        print("\n[STEP 6] NLP Validation...")
        nlp_result = None
        if csv_path and Path(csv_path).exists():
            try:
                # Extract REAL coordinates from Step 2
                coords = results["steps"].get("coordinate_extraction", {}).get("coordinates", {})
                lat_center = (coords.get('lat_min', 0.0) + coords.get('lat_max', 0.0)) / 2
                lon_center = (coords.get('lon_min', 0.0) + coords.get('lon_max', 0.0)) / 2
                
                # Extract timestamp: Priority 1. Metadata, 2. Filename, 3. Current Time (Warning)
                metadata = results["steps"].get("coordinate_extraction", {}).get("metadata", {})
                timestamp_str = metadata.get("DateTime") or metadata.get("TIFFTAG_DATETIME")
                release_time_nlp = None
                nlp_time_source = None
                
                # Priority 1: Try metadata
                if timestamp_str:
                    try:
                        release_time_nlp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        nlp_time_source = "Metadata"
                    except Exception:
                        pass
                
                # Priority 2: Try filename
                if release_time_nlp is None:
                    input_image = results["steps"].get("coordinate_extraction", {}).get("image_path", "")
                    if input_image:
                        filename = Path(input_image).name
                        release_time_nlp = extract_timestamp_from_filename(filename)
                        if release_time_nlp:
                            nlp_time_source = "Filename"
                
                # Priority 3: Fall back with warning
                if release_time_nlp is None:
                    release_time_nlp = datetime.now()
                    nlp_time_source = "System Time (WARNING)"
                    print(f"  ⚠️  Warning: NLP timestamp extracted from system time (not ideal)")
                
                release_time_iso = release_time_nlp.isoformat()
                
                # Get CV prediction for is_oil_prediction
                cv_step = results["steps"].get("cv", {})
                oil_stats_for_nlp = results["steps"].get("oil_analysis", {})
                oil_px_nlp = oil_stats_for_nlp.get('oil_pixels', oil_stats_for_nlp.get('oil_pixel_count', 0))
                is_oil_pred = oil_px_nlp > 0
                
                print(f"  ▸ Using extracted coordinates: lat={lat_center:.4f}, lon={lon_center:.4f}")
                print(f"  ▸ Using timestamp: {release_time_iso}")
                
                # Prepare NLP PDF output path to save in run folder
                nlp_pdf_path = str(self.reports_dir / f"nlp_incident_report_{run_timestamp}.pdf")
                
                nlp_result = validate_detection(
                    csv_path=csv_path,
                    lat_input=lat_center,
                    lon_input=lon_center,
                    timestamp_input=release_time_iso,
                    is_oil_prediction=is_oil_pred,
                    generate_pdf=True,
                    pdf_output_path=nlp_pdf_path
                )
                
                # Extract and display NLP confidence and risk level
                nlp_confidence = nlp_result.get('confidence', 0.5)
                nlp_risk = nlp_result.get('risk_level', 'UNKNOWN')
                nlp_distance_matches = nlp_result.get('distance_matches', 0)
                nlp_time_matches = nlp_result.get('time_matches', 0)
                nlp_joint_matches = nlp_result.get('joint_matches', 0)
                nlp_pdf_path_result = nlp_result.get('pdf_path')
                
                print(f"  ▸ NLP Database Matches: {nlp_distance_matches} distance, {nlp_time_matches} time, {nlp_joint_matches} joint")
                print(f"  ✓ NLP completed: Risk={nlp_risk}, Conf={nlp_confidence:.2f}")
                
                if nlp_pdf_path_result:
                    print(f"  ✓ NLP PDF Report generated: {nlp_pdf_path_result}")
                
                # Display NLP report preview if available
                nlp_report = nlp_result.get('formatted_report')
                if not nlp_report and 'text' in nlp_result:
                    nlp_report = nlp_result.get('text')
                if not nlp_report and isinstance(nlp_result.get('report'), str):
                    nlp_report = nlp_result.get('report')
                
                if nlp_report:
                    print(f"  ▸ NLP Report Preview:")
                    # Show first 5 lines of the report
                    report_lines = str(nlp_report).split('\n')
                    for i, line in enumerate(report_lines[:5]):
                        if line.strip():
                            print(f"    {line}")
                    if len(report_lines) > 5:
                        print(f"    ... ({len(report_lines) - 5} more lines)")
                
                results["steps"]["nlp_validation"] = nlp_result if nlp_result else {}
            except Exception as e:
                print(f"  ✗ NLP Validation failed: {str(e)}")
                import traceback
                traceback.print_exc()
                results["steps"]["nlp_validation"] = {"error": str(e), "status": "failed"}
                nlp_result = None
        else:
            print("  ⊘  NLP skipped (no CSV provided)")
        
        # STEP 8: Ensemble Decision (CV + PG + NLP; RF removed)
        print("\n[STEP 8] Ensemble Decision Making...")
        try:
            # Prepare results for ensemble
            pg_result = results["steps"].get("pg_classification", {})
            nlp_check = results["steps"].get("nlp_validation", {})

            # Determine CV confidence if available
            cv_score = None
            cv_step = results["steps"].get("cv")
            if cv_step and cv_step.get("confidence") is not None:
                try:
                    cv_score = float(cv_step.get("confidence", 0))
                except Exception:
                    cv_score = None
            
            # Prepare robust PG and NLP results with fallback confidence values
            pg_for_ensemble = pg_result if pg_result and not pg_result.get("error") else {"classification": "Not performed", "confidence": 0.0}
            nlp_for_ensemble = nlp_check if nlp_check and not nlp_check.get("error") else None
            
            # Show input scores
            cv_score_display = f"{cv_score:.2f}" if cv_score is not None else "N/A"
            pg_score_display = f"{pg_for_ensemble.get('confidence', 0):.2f}"
            nlp_score_display = f"{nlp_for_ensemble.get('confidence', 0):.2f}" if nlp_for_ensemble else "N/A"
            
            print(f"  ▸ Ensemble inputs: CV={cv_score_display}, PG={pg_score_display}, NLP={nlp_score_display}")
            
            # Use make_ensemble_decision with updated default weights (CV: 0.45, PG: 0.35, NLP: 0.20)
            ensemble = make_ensemble_decision(
                pg_result=pg_for_ensemble,
                nlp_result=nlp_for_ensemble,
                cv_score=cv_score
            )
            
            # Show decision details
            final_pred = ensemble.get('final_prediction', 'UNKNOWN')
            final_conf = ensemble.get('final_confidence', 0)
            summary = ensemble.get('decision_summary', {}) or {}
            model_votes = summary.get('model_votes', {}) or {}
            oil_evidence = summary.get('oil_evidence', None)
            nonoil_evidence = summary.get('nonoil_evidence', None)

            # Print decision weights as actually used
            cv_w = model_votes.get('CV Detection', {}).get('weight', None)
            pg_w = model_votes.get('Physics-Guided', {}).get('weight', None)
            nlp_w = model_votes.get('NLP', {}).get('weight', None)
            if cv_w is not None or pg_w is not None or nlp_w is not None:
                print(
                    "  ▸ Decision weights - "
                    f"CV: {cv_w:.2f} " if cv_w is not None else "CV: N/A ",
                    end=""
                )
                print(
                    f"PG: {pg_w:.2f} " if pg_w is not None else "PG: N/A ",
                    end=""
                )
                print(
                    f"NLP: {nlp_w:.2f}" if nlp_w is not None else "NLP: N/A"
                )
            else:
                print("  ▸ Decision weights unavailable in summary")

            # Show calculation breakdown from model_votes and evidence
            if model_votes:
                contrib_parts = []
                for model_name, info in model_votes.items():
                    contrib = info.get('contribution', 0.0)
                    contrib_parts.append(f"{model_name}={contrib:.3f}")
                if oil_evidence is not None or nonoil_evidence is not None:
                    print(
                        f"  ▸ Weighted contributions: {', '.join(contrib_parts)}; "
                        f"Oil evidence={oil_evidence:.3f} "
                        f"Non-Oil evidence={nonoil_evidence:.3f}"
                    )
                else:
                    print(f"  ▸ Weighted contributions: {', '.join(contrib_parts)}")
            
            print(f"  ✓ Final Decision: {final_pred}")
            print(f"  ✓ Confidence: {final_conf:.2%}")
            
            results["steps"]["ensemble_decision"] = ensemble
        except Exception as e:
            print(f"  ✗ Ensemble Decision failed: {str(e)}")
            results["steps"]["ensemble_decision"] = {"error": str(e)}
        
        # STEP 9: Report Generation (one HTML + one PDF, using run_timestamp for safe filenames)
        print("\n[STEP 9] Report Generation...")
        try:
            # One HTML report
            html_report_path = str(self.reports_dir / f"oil_spill_report_{run_timestamp}.html")
            html_result = generate_html_report(results, html_report_path)
            if html_result:
                print(f"  ✓ HTML Report generated: {html_result}")
            else:
                html_result = None
            
            # One PDF report (detailed)
            pdf_report_path = str(self.reports_dir / f"oil_spill_report_{run_timestamp}.pdf")
            pdf_result = generate_pdf_report(results, pdf_report_path)
            if pdf_result:
                print(f"  ✓ PDF Report generated: {pdf_result}")
                
            results["steps"]["report_generation"] = {
                "status": "success",
                "html_path": html_result,
                "pdf_path": pdf_result
            }
        except Exception as e:
            print(f"  ✗ Report Generation failed: {str(e)}")
            results["steps"]["report_generation"] = {"error": str(e), "status": "failed"}
        
        # Save final results into the run folder (and keep a copy in processed_dir for latest)
        output_path = self.run_dir / "pipeline_results.json"
        def json_serial(obj):
            import numpy as np
            import pandas as pd
            from datetime import datetime, date
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            if isinstance(obj, (np.integer, np.floating)):
                return obj.item()
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if hasattr(obj, 'to_dict'):
                return obj.to_dict()
            if hasattr(obj, '__str__'):
                return str(obj)
            raise TypeError(f"Type {type(obj)} not serializable")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, default=json_serial)
        generate_detailed_report(results, self.run_dir)
        print(f"\n{'='*70}")
        print(f"✓ PIPELINE COMPLETE")
        print(f"All results saved to: {self.run_dir}")
        print(f"  pipeline_results.json, visualizations/, reports/, simulation .nc")
        print(f"{'='*70}\n")
        return results


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Comprehensive Oil Spill Analysis Pipeline")
    parser.add_argument("--image", required=True, help="Path to SAR image")
    parser.add_argument("--config", help="Path to config.json")
    parser.add_argument("--cv-env", default="mados", help="Conda environment for CV")
    parser.add_argument("--csv", help="Path to incidents CSV for NLP validation")
    parser.add_argument("--no-cv", action="store_true", help="Skip CV, use threshold detector")
    
    args = parser.parse_args()
    
    try:
        pipeline = HybridPipeline(config_path=args.config, conda_env=args.cv_env)
        results = pipeline.run_full_pipeline(
            image_path=args.image,
            run_cv=not args.no_cv,
            csv_path=args.csv
        )
        return 0
    
    except Exception as e:
        print(f"PIPELINE ERROR: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())