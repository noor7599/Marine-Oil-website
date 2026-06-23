"""
Report Generator Module for Oil Spill Detection Pipeline
Generates professional PDF reports for authorities
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


def format_nlp_report_text(nlp_result: Dict) -> str:
    """
    Format NLP validation result as readable text
    
    Parameters:
    -----------
    nlp_result : dict
        NLP validation result dictionary
    
    Returns:
    --------
    str
        Formatted report text
    """
    if not nlp_result or isinstance(nlp_result, dict) and nlp_result.get('error'):
        return "NLP validation not performed or failed."
    
    lines = []
    lines.append("═" * 60)
    lines.append("NLP VALIDATION REPORT")
    lines.append("═" * 60)
    lines.append("")
    
    if isinstance(nlp_result, dict):
        # Extract key information
        confidence = nlp_result.get('confidence', 'N/A')
        risk_level = nlp_result.get('risk_level', 'UNKNOWN')
        distance_matches = nlp_result.get('distance_matches', 0)
        time_matches = nlp_result.get('time_matches', 0)
        joint_matches = nlp_result.get('joint_matches', 0)
        
        lines.append(f"Risk Level: {risk_level}")
        lines.append(f"Confidence: {confidence}")
        lines.append("")
        lines.append("Database Matches:")
        lines.append(f"  • Distance Matches: {distance_matches}")
        lines.append(f"  • Time Matches: {time_matches}")
        lines.append(f"  • Joint Matches: {joint_matches}")
        lines.append("")
        
        # Try to include formatted report if available
        if 'formatted_report' in nlp_result:
            lines.append("Historical Incident Matches:")
            lines.append("─" * 60)
            lines.append(str(nlp_result['formatted_report']))
    else:
        lines.append(str(nlp_result))
    
    lines.append("")
    lines.append("═" * 60)
    
    return "\n".join(lines)


def generate_html_report(
    results: Dict,
    output_path: str
) -> str:
    """
    Generate HTML report for web viewing
    
    Parameters:
    -----------
    results : dict
        Pipeline results dictionary
    output_path : str
        Path to save HTML report
    
    Returns:
    --------
    str
        Path to saved HTML file
    """
    try:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Extract key information
        cv_results = results.get('steps', {}).get('cv', {})
        pg_results = results.get('steps', {}).get('pg_classification', {})
        rf_results = results.get('steps', {}).get('rf_classification', {})
        nlp_results = results.get('steps', {}).get('nlp_validation', {})
        ensemble_results = results.get('steps', {}).get('ensemble_decision', {})
        
        # Build HTML
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Oil Spill Analysis Report</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
            background-color: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #1a3a52;
            border-bottom: 3px solid #4a90e2;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #2c5aa0;
            margin-top: 30px;
        }}
        .metric {{
            background-color: #f0f7ff;
            padding: 15px;
            margin: 10px 0;
            border-left: 4px solid #4a90e2;
            border-radius: 4px;
        }}
        .metric-label {{
            font-weight: bold;
            color: #2c5aa0;
        }}
        .metric-value {{
            font-size: 1.2em;
            color: #333;
        }}
        .success {{
            color: #27ae60;
            font-weight: bold;
        }}
        .warning {{
            color: #e67e22;
            font-weight: bold;
        }}
        .error {{
            color: #c0392b;
            font-weight: bold;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #2c5aa0;
            color: white;
        }}
        .timestamp {{
            color: #666;
            font-size: 0.9em;
        }}
        footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            font-size: 0.85em;
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🛰️ Oil Spill Analysis Report</h1>
        <p class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        
        <h2>📊 Final Decision</h2>
        <div class="metric">
            <div class="metric-label">Prediction:</div>
            <div class="metric-value {('success' if ensemble_results.get('final_prediction') == 'Oil-like' else 'error')}">{ensemble_results.get('final_prediction', 'Unknown')}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Confidence Score:</div>
            <div class="metric-value">{ensemble_results.get('final_confidence', 0):.2%}</div>
        </div>
        
        <h2>🔍 Detection Module Results</h2>
        <table>
            <tr>
                <th>Module</th>
                <th>Prediction</th>
                <th>Confidence</th>
                <th>Weight</th>
            </tr>
"""
        
        # Add module results
        if 'individual_decisions' in ensemble_results:
            for decision in ensemble_results['individual_decisions']:
                html_content += f"""
            <tr>
                <td>{decision['model_name']}</td>
                <td>{decision['prediction']}</td>
                <td>{decision['confidence']:.2%}</td>
                <td>{decision['weight']:.2f}</td>
            </tr>
"""
        
        html_content += """
        </table>
        
        <h2>📈 Ensemble Calculation</h2>
"""
        
        if 'decision_summary' in ensemble_results:
            contrib = ensemble_results['decision_summary'].get('ensemble_contributions', {})
            if contrib:
                html_content += f"<div class='metric'><div class='metric-label'>Ensemble Score: {ensemble_results['decision_summary'].get('ensemble_score', 0):.3f}</div></div>"
        
        html_content += """
        <h2>📝 Notes</h2>
        <p>This report was automatically generated by the Oil Spill Detection Pipeline.</p>
        <p>For detailed analysis, please refer to the accompanying PDF report and data files.</p>
        
        <footer>
            <p>Oil Spill Detection System | Graduation Project in AI</p>
            <p><strong>Disclaimer:</strong> This report is for informational purposes. Final decisions should be made by qualified environmental authorities.</p>
        </footer>
    </div>
</body>
</html>
"""
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"HTML report saved: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Error generating HTML report: {e}")
        return ""


def generate_text_report(
    results: Dict,
    output_path: str
) -> str:
    """
    Generate comprehensive text report
    
    Parameters:
    -----------
    results : dict
        Pipeline results dictionary
    output_path : str
        Path to save text report
    
    Returns:
    --------
    str
        Path to saved text file
    """
    try:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        lines = []
        now = datetime.now()
        
        # Header
        lines.append("=" * 70)
        lines.append("OIL SPILL DETECTION ANALYSIS REPORT")
        lines.append("=" * 70)
        lines.append(f"Generated: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        lines.append(f"Input Image: {results.get('input_image', 'N/A')}")
        lines.append("")
        
        # Final Decision
        ensemble = results.get('steps', {}).get('ensemble_decision', {})
        lines.append("FINAL DECISION")
        lines.append("-" * 70)
        lines.append(f"Prediction: {ensemble.get('final_prediction', 'Unknown')}")
        lines.append(f"Confidence: {ensemble.get('final_confidence', 0):.2%}")
        lines.append("")
        
        # Module Results
        lines.append("MODULE RESULTS")
        lines.append("-" * 70)
        
        cv_results = results.get('steps', {}).get('cv', {})
        lines.append(f"CV Detection: {cv_results.get('confidence', 'N/A')}")
        
        pg_results = results.get('steps', {}).get('pg_classification', {})
        lines.append(f"Physics-Guided: {pg_results.get('classification', 'N/A')} "
                    f"(conf: {pg_results.get('confidence', 'N/A')})")
        
        rf_results = results.get('steps', {}).get('rf_classification', {})
        lines.append(f"Random Forest: {rf_results.get('label', 'N/A')} "
                    f"(conf: {rf_results.get('confidence', 'N/A')})")
        
        nlp_results = results.get('steps', {}).get('nlp_validation', {})
        nlp_conf = nlp_results.get('confidence', 'N/A')
        nlp_risk = nlp_results.get('risk_level', 'N/A')
        lines.append(f"NLP: Risk={nlp_risk}, Conf={nlp_conf}")
        lines.append("")
        
        # NLP Report (if available)
        if nlp_results and not nlp_results.get('error'):
            lines.append("NLP VALIDATION DETAILS")
            lines.append("-" * 70)
            lines.append(format_nlp_report_text(nlp_results))
            lines.append("")
        
        # Footer
        lines.append("=" * 70)
        lines.append("END OF REPORT")
        lines.append("=" * 70)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
        
        logger.info(f"Text report saved: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Error generating text report: {e}")
        return ""


def generate_pdf_report(
    results: Dict,
    output_path: str
) -> str:
    """
    Generate professional PDF report using fpdf2 or reportlab.
    Falls back to HTML if PDF libraries unavailable.
    
    Parameters:
    -----------
    results : dict
        Pipeline results dictionary
    output_path : str
        Path to save PDF report
    
    Returns:
    --------
    str
        Path to saved PDF (or HTML if PDF unavailable)
    """
    try:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Try fpdf2 first (lightweight)
        try:
            from fpdf import FPDF
            return _generate_pdf_with_fpdf(results, output_path)
        except ImportError:
            pass
        
        # Try reportlab (more powerful)
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            return _generate_pdf_with_reportlab(results, output_path)
        except ImportError:
            pass
        
        # Fallback to HTML
        logger.warning("PDF libraries not available, generating HTML report instead")
        html_path = output_path.replace('.pdf', '.html')
        html_result = generate_html_report(results, html_path)
        logger.info(f"Report saved as HTML: {html_path}")
        return html_path
        
    except Exception as e:
        logger.error(f"Error generating PDF report: {e}")
        return ""


def _generate_pdf_with_fpdf(results: Dict, output_path: str) -> str:
    """
    Generate a professional A4 PDF using fpdf2 that follows the
    decision-maker-oriented structure and hides technical clutter.
    """
    from fpdf import FPDF

    class ReportPDF(FPDF):
        def footer(self):
            # Position 15 mm from bottom
            self.set_y(-15)
            self.set_font("Arial", "I", 8)
            self.set_text_color(120, 120, 120)
            # Page number
            self.cell(0, 5, f"Page {self.page_no()}/{{nb}}", align="R", ln=1)
            # Disclaimer
            disclaimer = (
                "This report is automatically generated for informational purposes. "
                "Final decisions must be made by qualified environmental authorities."
            )
            self.multi_cell(0, 4, disclaimer[:200].encode("latin-1", "replace").decode("latin-1"))

    def fpdf_safe_text(value) -> str:
        """
        fpdf core fonts (Helvetica/Times/Courier) are not Unicode.
        Convert common Unicode punctuation to ASCII and then enforce latin-1.
        """
        if value is None:
            return "N/A"
        text = str(value)
        text = (
            text.replace("–", "-")
            .replace("—", "--")
            .replace("’", "'")
            .replace("‘", "'")
            .replace("“", '"')
            .replace("”", '"')
            .replace("…", "...")
        )
        return text.encode("latin-1", "replace").decode("latin-1")

    def fmt_percent(value) -> str:
        try:
            return f"{float(value) * 100:.1f}%"
        except Exception:
            return "N/A"

    def fmt_float(value, decimals: int = 2) -> str:
        try:
            return f"{float(value):.{decimals}f}"
        except Exception:
            return "N/A"

    def clean_basename(val: str) -> str:
        if not isinstance(val, str):
            return str(val)
        try:
            return os.path.basename(val)
        except Exception:
            return val

    def add_section_header(pdf: ReportPDF, title: str):
        # Use only fpdf "core fonts" to avoid external font registration issues.
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(50, 70, 100)
        pdf.ln(3)
        pdf.cell(0, 7, title, ln=True)
        pdf.set_draw_color(220, 220, 220)
        y = pdf.get_y()
        pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
        pdf.ln(3)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(0, 0, 0)

    def add_key_value_table(pdf: ReportPDF, rows, max_lines: int = 50):
        """
        rows: list of (label, value) tuples. Skips None/empty.
        Enforces max_lines; prints '...' if truncated.
        """
        lines_used = 0
        for label, value in rows:
            if value is None or value == "" or value == "N/A":
                continue
            if lines_used >= max_lines:
                pdf.multi_cell(0, 5, "...")
                break
            safe_label = fpdf_safe_text(str(label)[:40])
            safe_value = fpdf_safe_text(str(value)[:70])
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(50, 5, safe_label + ":", ln=0)
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(0, 5, safe_value)
            lines_used += 1

    pdf = ReportPDF(orientation="P", unit="mm", format="A4")
    pdf.alias_nb_pages()
    pdf.set_margins(left=18, top=18, right=18)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    steps = results.get("steps", {}) or {}
    ensemble = steps.get("ensemble_decision", {}) or {}
    cv = steps.get("cv", {}) or {}
    pg = steps.get("pg_classification", {}) or {}
    nlp = steps.get("nlp_validation", {}) or {}
    env = steps.get("environmental_data", {}) or {}

    final_pred_raw = ensemble.get("final_prediction", "Unknown")
    is_oil = final_pred_raw == "Oil-like"
    final_status = "Oil" if is_oil else "No Oil"
    final_conf = float(ensemble.get("final_confidence", 0.0) or 0.0)

    # ----- 1. Header (Title, Date, Input Filename) -----
    pdf.set_fill_color(26, 58, 82)  # dark blue header
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, "Oil Spill Detection Report", ln=True, align="C", fill=True)
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 5, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True, align="C")
    input_name = clean_basename(results.get("input_image", ""))
    if input_name:
        pdf.cell(0, 5, f"Input image: {input_name}", ln=True, align="C")
    pdf.ln(4)

    # ----- 2. Executive Summary (Final Decision + Confidence + Color Alert) -----
    if is_oil:
        pdf.set_fill_color(200, 0, 0)  # red
    else:
        pdf.set_fill_color(0, 128, 0)  # green
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 12)
    alert_text = (
        "OIL DETECTED – IMMEDIATE ACTION RECOMMENDED"
        if is_oil
        else "NO OIL DETECTED"
    )
    pdf.multi_cell(0, 7, fpdf_safe_text(alert_text), align="C", fill=True)

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 10)
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(
        0,
        6,
        f"DETECTION STATUS: {final_status}   (Confidence: {fmt_percent(final_conf)})",
        ln=True,
    )
    pdf.ln(1)
    pdf.set_font("Helvetica", "", 9)
    summary_line = (
        "The decision is based on combined evidence from computer vision, physics-guided analysis, "
        "and text-based validation of historical maritime incidents."
    )
    pdf.multi_cell(0, 5, fpdf_safe_text(summary_line))
    pdf.ln(3)

    # ----- 3. Computer Vision Results -----
    add_section_header(pdf, "1. Computer Vision Results")
    cv_rows = [
        ("Prediction", cv.get("classification")),
        ("Confidence", fmt_percent(cv.get("confidence", 0))),
        (
            "Oil pixels",
            f"{cv.get('oil_pixels', 0):,}"
            if cv.get("oil_pixels") is not None
            else None,
        ),
        (
            "Total pixels",
            f"{cv.get('total_pixels', 0):,}"
            if cv.get("total_pixels") is not None
            else None,
        ),
        (
            "Oil coverage",
            f"{fmt_float(cv.get('oil_percentage', 0))}%"
            if cv.get("oil_percentage") is not None
            else None,
        ),
    ]
    add_key_value_table(pdf, cv_rows, max_lines=50)

    # ----- 4. Physics-Guided Classification -----
    add_section_header(pdf, "2. Physics-Guided Classification")
    pg_rows = [
        ("Classification", pg.get("classification")),
        ("Confidence", fmt_percent(pg.get("confidence", 0))),
    ]
    add_key_value_table(pdf, pg_rows, max_lines=10)

    rules = pg.get("rule_results") or {}
    if rules:
        pdf.set_font("Helvetica", "B", 9)
        pdf.ln(1)
        pdf.cell(0, 5, "Rule evaluation:", ln=True)
        pdf.set_font("Helvetica", "", 9)
        rule_map = [
            ("Darkness rule", rules.get("darkness_pass")),
            ("Smoothness rule", rules.get("smoothness_pass")),
            ("Shape rule", rules.get("shape_pass")),
            ("Alignment rule", rules.get("alignment_pass")),
        ]
        for label, passed in rule_map:
            if passed is None:
                continue
            status = "PASS" if passed else "FAIL"
            status_color = (0, 128, 0) if passed else (200, 0, 0)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(0, 0, 0)
            pdf.cell(60, 5, f"{label}:", ln=0)
            pdf.set_text_color(*status_color)
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 5, status, ln=True)
        pdf.set_text_color(0, 0, 0)

    # ----- 5. NLP Validation -----
    add_section_header(pdf, "3. NLP Validation")
    nlp_rows = [
        ("Label", nlp.get("label")),
        ("Risk level", nlp.get("risk_level")),
        ("Cause", nlp.get("cause")),
        ("Confidence", fmt_percent(nlp.get("confidence", 0))),
        ("Distance matches", nlp.get("distance_matches")),
        ("Time matches", nlp.get("time_matches")),
        ("Joint matches", nlp.get("joint_matches")),
    ]
    add_key_value_table(pdf, nlp_rows, max_lines=50)

    # ----- 6. Environmental Conditions -----
    add_section_header(pdf, "4. Environmental Conditions")
    env_rows = [
        (
            "Wind speed (m/s)",
            fmt_float(env.get("wind_speed"))
            if env.get("wind_speed") is not None
            else None,
        ),
        (
            "Current speed (m/s)",
            fmt_float(env.get("current_speed"))
            if env.get("current_speed") is not None
            else None,
        ),
        (
            "Water temperature (°C)",
            fmt_float(env.get("temperature"))
            if env.get("temperature") is not None
            else None,
        ),
        (
            "Humidity (%)",
            fmt_float(env.get("humidity"))
            if env.get("humidity") is not None
            else None,
        ),
    ]
    add_key_value_table(pdf, env_rows, max_lines=20)

    # ----- 7. Ensemble Decision -----
    add_section_header(pdf, "5. Ensemble Decision")
    ens_rows = [
        ("Final classification", final_status),
        ("Overall confidence", fmt_percent(final_conf)),
        (
            "Decision method",
            ensemble.get(
                "method",
                "Weighted combination of computer vision, physics-guided and NLP modules",
            ),
        ),
    ]
    add_key_value_table(pdf, ens_rows, max_lines=10)

    indiv = ensemble.get("individual_decisions") or []
    if indiv:
        pdf.set_font("Arial", "B", 9)
        pdf.ln(1)
        pdf.cell(0, 5, "Model contributions:", ln=True)
        pdf.set_font("Arial", "", 9)
        lines_left = 50
        for d in indiv:
            if lines_left <= 0:
                pdf.multi_cell(0, 5, "...")
                break
            name = d.get("model_name", "Model")
            pred = d.get("prediction", "N/A")
            conf = fmt_percent(d.get("confidence", 0))
            weight = fmt_float(d.get("weight", 0), 2)
            line = f"{name}: {pred}  (Conf: {conf}, Weight: {weight})"
            safe_line = line[:110].encode("latin-1", "replace").decode("latin-1")
            pdf.multi_cell(0, 5, safe_line)
            lines_left -= 1

    pdf.output(output_path)
    logger.info(f"PDF report saved: {output_path}")
    return output_path


def _generate_pdf_with_reportlab(results: Dict, output_path: str) -> str:
    """Generate detailed PDF using reportlab: all pipeline steps."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Preformatted
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    
    doc = SimpleDocTemplate(output_path, pagesize=letter, topMargin=0.75*inch)
    story = []
    styles = getSampleStyleSheet()
    steps = results.get('steps', {})
    
    title_style = ParagraphStyle(
        'CustomTitle', parent=styles['Heading1'],
        fontSize=20, textColor=colors.HexColor('#1a3a52'),
        spaceAfter=12, alignment=TA_CENTER
    )
    story.append(Paragraph("Oil Spill Detection - Detailed Report", title_style))
    story.append(Spacer(1, 0.15*inch))
    meta_text = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Input: {Path(results.get('input_image', '')).name}"
    story.append(Paragraph(meta_text, styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    ensemble = steps.get('ensemble_decision', {})
    story.append(Paragraph("Executive Summary", styles['Heading2']))
    pred = ensemble.get('final_prediction', 'N/A')
    conf = ensemble.get('final_confidence', 0)
    story.append(Paragraph(f"<b>Final decision:</b> {pred} &nbsp; <b>Confidence:</b> {conf:.1%}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))
    
    # Stick to built-in reportlab fonts to avoid missing font registrations.
    code_style = ParagraphStyle('Code', parent=styles['Normal'], fontName='Courier', fontSize=8, leftIndent=20)
    
    section_titles = [
        ("1. Computer Vision Detection", "cv"),
        ("2. Coordinate Extraction", "coordinate_extraction"),
        ("3. Environmental Data", "environmental_data"),
        ("4. Oil Analysis", "oil_analysis"),
        ("5. Simulation", "simulation"),
        ("6. Physics-Guided Classification", "pg_classification"),
        ("7. NLP Validation", "nlp_validation"),
        ("8. Ensemble Decision", "ensemble_decision"),
        ("9. Generated Reports", "report_generation"),
    ]
    for title, key in section_titles:
        if not steps.get(key):
            continue
        story.append(Paragraph(title, styles['Heading2']))
        text = _safe_str(steps[key])[:2500]
        # Sanitize Unicode characters before passing to reportlab
        text = _sanitize_unicode(text)
        story.append(Preformatted(text, code_style))
        story.append(Spacer(1, 0.15*inch))
    
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph("Disclaimer: This report is for informational purposes. Final decisions should be made by qualified environmental authorities.",
        ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey)))
    doc.build(story)
    logger.info(f"PDF report saved: {output_path}")
    return output_path


def _safe_str(obj) -> str:
    """Convert object to string for PDF text, handling dict/list/nested."""
    if obj is None:
        return "N/A"
    if isinstance(obj, (str, int, float, bool)):
        return str(obj)
    if isinstance(obj, dict):
        lines = []
        for k, v in obj.items():
            vstr = _safe_str(v)
            if "\n" in vstr or len(vstr) > 80:
                lines.append(f"  {k}:")
                for line in vstr.split("\n"):
                    lines.append(f"    {line}")
            else:
                lines.append(f"  {k}: {vstr}")
        return "\n".join(lines)
    if isinstance(obj, list):
        if not obj:
            return "[]"
        if isinstance(obj[0], dict):
            return "\n".join([_safe_str(item) for item in obj[:20]]) + ("\n  ..." if len(obj) > 20 else "")
        return ", ".join(_safe_str(x) for x in obj[:30]) + (" ..." if len(obj) > 30 else "")
    return str(obj)


def _sanitize_unicode(text: str) -> str:
    """
    Sanitize Unicode characters that reportlab cannot render.
    Converts problematic Unicode to ASCII equivalents.
    """
    if not text:
        return text
    
    text = str(text)
    
    # Common replacements for reportlab compatibility
    replacements = {
        '–': '-',      # en-dash
        '—': '--',     # em-dash
        ''': "'",      # right single quote
        ''': "'",      # left single quote
        '"': '"',      # left double quote
        '"': '"',      # right double quote
        '…': '...',    # ellipsis
        '•': '*',      # bullet
        '≈': '~',      # approximately equal
        '±': '+/-',    # plus-minus
        '×': 'x',      # multiplication sign
        '·': '.',      # middle dot
    }
    
    for unicode_char, ascii_char in replacements.items():
        text = text.replace(unicode_char, ascii_char)
    
    # Encode/decode to remove remaining non-ASCII characters
    text = text.encode('ascii', errors='ignore').decode('ascii')
    
    return text


def generate_final_pdf_report(pipeline_results: Dict, output_path: str) -> Optional[str]:
    """
    Generate a final PDF report containing all information from pipeline_results.json.
    """
    try:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"Cannot create output dir for final PDF: {e}")
        return None
    try:
        from fpdf import FPDF
    except ImportError:
        logger.warning("fpdf2 not available; skipping final PDF.")
        return None
    steps = pipeline_results.get("steps", {})
    input_image = pipeline_results.get("input_image", "N/A")

    def add_section(pdf, title: str, data):
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, title, ln=True)
        pdf.set_font("Arial", "", 9)
        text = _safe_str(data)
        for line in text.split("\n")[:60]:
            # Sanitize Unicode characters: en-dash, em-dash, smart quotes, etc.
            line = line.replace('–', '-').replace('—', '--').replace(''', "'").replace(''', "'")
            line = line.replace('"', '"').replace('"', '"').replace('…', '...')
            # Encode to latin-1 with error replacement for any remaining incompatible chars
            line = line[:95].encode('latin-1', errors='replace').decode('latin-1')
            pdf.multi_cell(0, 5, line)
        pdf.ln(3)

    try:
        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "Oil Spill Analysis - Final Report", ln=True, align="C")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True)
        pdf.cell(0, 6, f"Input image: {Path(input_image).name}", ln=True)
        pdf.ln(8)
        add_section(pdf, "1. Input", {"input_image": input_image})
        if "cv" in steps:
            add_section(pdf, "2. CV Detection", steps["cv"])
        if "coordinate_extraction" in steps:
            add_section(pdf, "3. Coordinate Extraction", steps["coordinate_extraction"])
        if "environmental_data" in steps:
            add_section(pdf, "4. Environmental Data", steps["environmental_data"])
        if "oil_analysis" in steps:
            add_section(pdf, "5. Oil Analysis", steps["oil_analysis"])
        if "simulation" in steps:
            add_section(pdf, "6. Simulation", steps["simulation"])
        if "pg_classification" in steps:
            add_section(pdf, "7. Physics-Guided Classification", steps["pg_classification"])
        if "nlp_validation" in steps:
            add_section(pdf, "8. NLP Validation", steps["nlp_validation"])
        if "ensemble_decision" in steps:
            add_section(pdf, "9. Ensemble Decision", steps["ensemble_decision"])
        if "report_generation" in steps:
            add_section(pdf, "10. Report Generation", steps["report_generation"])
        pdf.set_font("Arial", "", 8)
        pdf.ln(5)
        pdf.multi_cell(0, 4, "This report was generated automatically from the pipeline. Verify with qualified environmental authorities.")
        pdf.output(output_path)
        logger.info(f"Final comprehensive PDF report saved: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Failed to generate final PDF: {e}")
        import traceback
        traceback.print_exc()
        return None


def generate_professional_html_report(results: Dict, output_path: str = None) -> str:
    """
    Generate professional HTML report with comprehensive styling and all pipeline details.
    
    Parameters:
    -----------
    results : dict
        Complete pipeline results
    output_path : str, optional
        Custom output path
    
    Returns:
    --------
    str
        Path to generated HTML report
    """
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"data/processed/professional_report_{timestamp}.html"
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    # Extract decision and metrics
    ensemble = results.get('steps', {}).get('ensemble_decision', {})
    is_spill = ensemble.get('final_prediction', 'Unknown') == 'Oil-like'
    confidence = ensemble.get('final_confidence', 0)
    
    cv_data = results.get('steps', {}).get('cv', {})
    pg_data = results.get('steps', {}).get('pg_classification', {})
    nlp_data = results.get('steps', {}).get('nlp_validation', {})
    env_data = results.get('steps', {}).get('environmental_data', {})
    
    # HTML content
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Oil Spill Detection Report</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            line-height: 1.6;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1100px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 15px 50px rgba(0,0,0,0.4);
            overflow: hidden;
        }}
        
        header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 50px 30px;
            text-align: center;
        }}
        
        header h1 {{
            font-size: 2.8em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}
        
        .alert {{
            padding: 25px 30px;
            text-align: center;
            font-size: 1.3em;
            font-weight: bold;
            color: white;
        }}
        
        .alert.danger {{
            background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
        }}
        
        .alert.success {{
            background: linear-gradient(135deg, #27ae60 0%, #229954 100%);
        }}
        
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            padding: 30px;
            background: #f8f9fa;
            border-bottom: 2px solid #eee;
        }}
        
        .info-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
            box-shadow: 0 3px 10px rgba(0,0,0,0.1);
        }}
        
        .info-card h3 {{
            color: #667eea;
            margin-bottom: 10px;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1.5px;
        }}
        
        .info-card p {{
            font-size: 1.5em;
            font-weight: bold;
            color: #333;
        }}
        
        .section {{
            padding: 30px;
            border-bottom: 2px solid #eee;
        }}
        
        .section h2 {{
            color: #667eea;
            margin-bottom: 20px;
            font-size: 1.6em;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
        }}
        
        .classifier-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        
        .classifier-card {{
            background: #f8f9fa;
            border: 2px solid #ddd;
            border-radius: 8px;
            padding: 25px;
            transition: all 0.3s ease;
        }}
        
        .classifier-card:hover {{
            border-color: #667eea;
            box-shadow: 0 8px 20px rgba(102, 126, 234, 0.3);
            transform: translateY(-2px);
        }}
        
        .classifier-card h3 {{
            color: #333;
            margin-bottom: 15px;
            font-size: 1.15em;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .metric {{
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #eee;
        }}
        
        .metric:last-child {{
            border-bottom: none;
        }}
        
        .metric-label {{
            font-weight: 600;
            color: #666;
        }}
        
        .metric-value {{
            color: #667eea;
            font-weight: bold;
        }}
        
        .confidence-bar {{
            height: 40px;
            background: linear-gradient(90deg, #e74c3c 0%, #f39c12 50%, #27ae60 100%);
            border-radius: 5px;
            margin: 20px 0;
            overflow: hidden;
            box-shadow: 0 3px 8px rgba(0,0,0,0.2);
        }}
        
        .confidence-fill {{
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            display: flex;
            align-items: center;
            justify-content: flex-end;
            padding-right: 15px;
            color: white;
            font-weight: bold;
            font-size: 1.1em;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background: white;
            border-radius: 5px;
            overflow: hidden;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        
        th {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: 600;
        }}
        
        td {{
            padding: 12px 15px;
            border-bottom: 1px solid #ddd;
        }}
        
        tr:hover {{
            background: #f5f5f5;
        }}
        
        .details {{
            background: #f0f4ff;
            padding: 15px;
            border-radius: 5px;
            margin-top: 10px;
            font-size: 0.95em;
            line-height: 1.8;
            border-left: 4px solid #667eea;
        }}
        
        .badge {{
            display: inline-block;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: bold;
            margin-right: 8px;
        }}
        
        .badge.positive {{
            background: #d4edda;
            color: #155724;
        }}
        
        .badge.negative {{
            background: #f8d7da;
            color: #721c24;
        }}
        
        .badge.neutral {{
            background: #e2e3e5;
            color: #383d41;
        }}
        
        footer {{
            background: #2c3e50;
            color: white;
            text-align: center;
            padding: 25px;
            font-size: 0.9em;
        }}
        
        footer p {{
            margin: 5px 0;
        }}
        
        .icon {{
            font-size: 1.3em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1><span class="icon">🛰️</span> Oil Spill Detection Report</h1>
            <p>Automated Ensemble Analysis Pipeline</p>
        </header>
        
        <div class="alert {'danger' if is_spill else 'success'}">
            {'🚨 OIL SPILL DETECTED - IMMEDIATE ACTION REQUIRED' if is_spill else '✓ NO OIL SPILL DETECTED'}
        </div>
        
        <div class="info-grid">
            <div class="info-card">
                <h3>Final Decision</h3>
                <p>{'YES' if is_spill else 'NO'}</p>
            </div>
            <div class="info-card">
                <h3>Confidence Level</h3>
                <p>{confidence*100:.1f}%</p>
            </div>
            <div class="info-card">
                <h3>Report Date</h3>
                <p>{datetime.now().strftime('%Y-%m-%d')}</p>
            </div>
            <div class="info-card">
                <h3>Analysis Status</h3>
                <p>✓ Complete</p>
            </div>
        </div>
        
        <div class="section">
            <h2>Decision Confidence Score</h2>
            <div class="confidence-bar">
                <div class="confidence-fill" style="width: {confidence*100:.1f}%;">
                    {confidence*100:.1f}%
                </div>
            </div>
            <p>The ensemble model has <strong>{confidence*100:.1f}%</strong> confidence in the decision based on weighted analysis from three independent classifiers: Computer Vision (40%), Physics-Guided (30%), and Natural Language Processing (30%).</p>
        </div>
        
        <div class="section">
            <h2>Classifier Analysis</h2>
            <div class="classifier-grid">
                <div class="classifier-card">
                    <h3><span class="icon">🤖</span> Computer Vision</h3>
                    <div class="metric">
                        <span class="metric-label">Prediction:</span>
                        <span class="metric-value">{cv_data.get('classification', 'N/A')}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Confidence:</span>
                        <span class="metric-value">{cv_data.get('confidence', 0)*100:.1f}%</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Oil Pixels:</span>
                        <span class="metric-value">{cv_data.get('oil_pixels', 0):,}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Model:</span>
                        <span class="metric-value">MariNeXt</span>
                    </div>
                    <div class="details">
                        MariNeXt 15-class semantic segmentation for marine object detection. Processing time: {cv_data.get('processing_time', 0):.2f}s
                    </div>
                </div>
                
                <div class="classifier-card">
                    <h3><span class="icon">📊</span> Physics-Guided</h3>
                    <div class="metric">
                        <span class="metric-label">Prediction:</span>
                        <span class="metric-value">{pg_data.get('classification', 'N/A')}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Confidence:</span>
                        <span class="metric-value">{pg_data.get('confidence', 0)*100:.1f}%</span>
                    </div>
                    <div class="details">
                        Analyzes SAR properties, wind patterns, ocean currents, and water temperature. Processing time: {pg_data.get('processing_time', 0):.2f}s
                    </div>
                </div>
                
                <div class="classifier-card">
                    <h3><span class="icon">📝</span> NLP Validation</h3>
                    <div class="metric">
                        <span class="metric-label">Prediction:</span>
                        <span class="metric-value">{nlp_data.get('label', 'N/A')}</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Confidence:</span>
                        <span class="metric-value">{nlp_data.get('confidence', 0)*100:.1f}%</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Risk Level:</span>
                        <span class="metric-value">{nlp_data.get('risk_level', 'N/A')}</span>
                    </div>
                    <div class="details">
                        Maritime incident text analysis and database correlation. Processing time: {nlp_data.get('processing_time', 0):.2f}s
                    </div>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2>Environmental Conditions</h2>
            <table>
                <tr>
                    <th>Parameter</th>
                    <th>Value</th>
                    <th>Impact on Detection</th>
                </tr>
                <tr>
                    <td><strong>Wind Speed</strong></td>
                    <td>{env_data.get('wind_speed', 'N/A')} m/s</td>
                    <td>Affects oil dispersion and surface roughness patterns</td>
                </tr>
                <tr>
                    <td><strong>Current Speed</strong></td>
                    <td>{env_data.get('current_speed', 'N/A')} m/s</td>
                    <td>Drives oil drift direction and velocity</td>
                </tr>
                <tr>
                    <td><strong>Water Temperature</strong></td>
                    <td>{env_data.get('temperature', 'N/A')} °C</td>
                    <td>Influences oil viscosity and emulsification</td>
                </tr>
                <tr>
                    <td><strong>Humidity</strong></td>
                    <td>{env_data.get('humidity', 'N/A')}%</td>
                    <td>Affects sensor data acquisition quality</td>
                </tr>
            </table>
        </div>
        
        <div class="section">
            <h2>Ensemble Decision Logic</h2>
            <p><strong>Method:</strong> Weighted Average Ensemble</p>
            <table>
                <tr>
                    <th>Component</th>
                    <th>Weight</th>
                    <th>Rationale</th>
                </tr>
                <tr>
                    <td><strong>Computer Vision</strong></td>
                    <td>40%</td>
                    <td>Direct pixel-level detection from SAR segments</td>
                </tr>
                <tr>
                    <td><strong>Physics-Guided</strong></td>
                    <td>30%</td>
                    <td>Validates patterns against oceanographic models</td>
                </tr>
                <tr>
                    <td><strong>NLP Analysis</strong></td>
                    <td>30%</td>
                    <td>Correlates with historical incident patterns</td>
                </tr>
            </table>
            <p style="margin-top: 15px;"><strong>Decision Threshold:</strong> Confidence ≥ 50% = Oil Spill Detected</p>
        </div>
        
        <div class="section">
            <h2>Recommendations</h2>
            <ul style="margin-left: 20px;">
                <li>{'<strong>ALERT AUTHORITIES:</strong> Oil spill has been detected. Immediate response and containment action is recommended.' if is_spill else 'Continue standard monitoring of the region.'}</li>
                <li>Analyze satellite imagery at higher resolution if available for more precise boundary estimation.</li>
                <li>Cross-reference with Coast Guard and maritime authority reports.</li>
                <li>Deploy environmental response resources if spill is confirmed.</li>
                <li>Monitor environmental conditions for drift prediction simulation.</li>
            </ul>
        </div>
        
        <footer>
            <p><strong>Oil Spill Detection System</strong></p>
            <p>Graduation Project in AI - Integration Layer</p>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
            <p style="margin-top: 15px; font-size: 0.85em;"><em>DISCLAIMER: This report is for informational purposes. Final decisions should be made by qualified environmental authorities based on multiple data sources.</em></p>
        </footer>
    </div>
</body>
</html>
"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    logger.info(f"Professional HTML report generated: {output_path}")
    return output_path


def generate_comprehensive_report(
    pipeline_results: Dict,
    output_dir: str
) -> Dict[str, str]:
    """
    Generate comprehensive HTML report with ALL pipeline information.
    Includes CV, PG, NLP, and Ensemble results with full details.
    
    Parameters:
    -----------
    pipeline_results : dict
        Complete pipeline results from pipeline_results.json
    output_dir : str
        Directory to save report files
    
    Returns:
    --------
    dict
        Paths to generated report files
    """
    try:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Extract components from pipeline structure
        cv = pipeline_results.get('step_0_cv_inference', {}) or {}
        pg = pipeline_results.get('step_4_pg_classification', {}) or {}
        nlp = pipeline_results.get('step_6_nlp_classification', {}) or {}
        ensemble = pipeline_results.get('step_7_final_decision', {}) or {}
        
        # Determine overall result
        final_pred = ensemble.get('final_classification', 'Unknown')
        final_conf = ensemble.get('confidence', 0)
        alert_status = "🚨 OIL SPILL DETECTED" if final_conf > 0.5 else "✓ NO OIL SPILL"
        alert_color = "#d32f2f" if final_conf > 0.5 else "#388e3c"
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Oil Spill Detection - Comprehensive Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f5f5f5; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        
        .header {{ text-align: center; border-bottom: 3px solid #1976d2; padding-bottom: 20px; margin-bottom: 30px; }}
        .header h1 {{ color: #1976d2; font-size: 28px; margin-bottom: 10px; }}
        .alert {{ background: {alert_color}; color: white; padding: 15px 20px; border-radius: 5px; font-size: 16px; font-weight: bold; margin-bottom: 20px; }}
        
        .section {{ margin: 30px 0; padding: 20px; background: #fafafa; border-left: 4px solid #1976d2; border-radius: 4px; }}
        .section h2 {{ color: #1976d2; font-size: 18px; margin-bottom: 15px; border-bottom: 2px solid #e0e0e0; padding-bottom: 10px; }}
        .subsection {{ margin: 15px 0; padding: 15px; background: white; border-radius: 4px; border: 1px solid #e0e0e0; }}
        .subsection h3 {{ color: #424242; font-size: 14px; margin-bottom: 10px; }}
        
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f5f5f5; font-weight: bold; color: #424242; }}
        tr:hover {{ background: #f9f9f9; }}
        
        .metric {{ display: inline-block; margin: 10px 15px 10px 0; }}
        .metric-label {{ font-size: 12px; color: #666; }}
        .metric-value {{ font-size: 20px; font-weight: bold; color: #1976d2; }}
        
        .confidence-bar {{ width: 100%; height: 30px; background: #e0e0e0; border-radius: 4px; overflow: hidden; margin: 10px 0; }}
        .confidence-fill {{ height: 100%; background: linear-gradient(90deg, #ff6f00 0%, #fdd835 50%, #4caf50 100%); transition: width 0.3s; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; }}
        
        .model-result {{ background: white; padding: 15px; margin: 10px 0; border-left: 4px solid #1976d2; border-radius: 4px; }}
        .model-name {{ font-weight: bold; color: #424242; }}
        .model-decision {{ font-size: 14px; color: #666; margin: 5px 0; }}
        
        .rule-pass {{ color: #4caf50; font-weight: bold; }}
        .rule-fail {{ color: #f44336; font-weight: bold; }}
        
        .nlp-matches {{ background: white; padding: 15px; margin: 10px 0; border-radius: 4px; }}
        .match-item {{ padding: 10px; margin: 8px 0; background: #f5f5f5; border-left: 3px solid #ff9800; border-radius: 3px; }}
        .match-rank {{ font-weight: bold; color: #ff9800; }}
        
        .detail-text {{ color: #666; font-size: 12px; margin-top: 5px; }}
        
        footer {{ margin-top: 50px; padding-top: 20px; border-top: 1px solid #ddd; text-align: center; color: #999; font-size: 12px; }}
        .timestamp {{ color: #999; font-size: 12px; margin-top: 20px; }}
        
        ul, ol {{ margin-left: 20px; line-height: 1.8; }}
        li {{ margin: 5px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Oil Spill Detection Pipeline Report</h1>
            <p>Comprehensive Analysis from Multi-Modal Integration</p>
        </div>
        
        <div class="alert">{alert_status}</div>
        
        <!-- EXECUTIVE SUMMARY -->
        <div class="section">
            <h2>Executive Summary</h2>
            <div class="metric">
                <div class="metric-label">Final Decision</div>
                <div class="metric-value">{final_pred}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Ensemble Confidence</div>
                <div class="metric-value">{final_conf*100:.1f}%</div>
            </div>
            <div class="confidence-bar">
                <div class="confidence-fill" style="width: {min(final_conf*100, 100):.1f}%">{final_conf*100:.1f}%</div>
            </div>
            <p style="margin-top: 15px;"><strong>Decision Basis:</strong> Score {final_conf:.3f} vs Threshold 0.50 → <strong>{'DETECTION CONFIRMED' if final_conf > 0.5 else 'NO OIL DETECTED'}</strong></p>
        </div>
        
        <!-- COMPUTER VISION RESULTS -->
        <div class="section">
            <h2>1. Computer Vision Analysis (MariNeXt)</h2>
            <div class="subsection">
                <h3>Detection Results</h3>
                <table>
                    <tr>
                        <td><strong>Status</strong></td>
                        <td>{cv.get('status', 'N/A')}</td>
                    </tr>
                    <tr>
                        <td><strong>Oil Detected</strong></td>
                        <td>{'✓ YES' if cv.get('detected') else '✗ NO'}</td>
                    </tr>
                    <tr>
                        <td><strong>Oil Pixels</strong></td>
                        <td>{cv.get('oil_pixels', 0):,} / {cv.get('total_pixels', 0):,}</td>
                    </tr>
                    <tr>
                        <td><strong>Oil Percentage</strong></td>
                        <td>{cv.get('oil_percentage', 0):.2f}%</td>
                    </tr>
                    <tr>
                        <td><strong>CV Confidence</strong></td>
                        <td>{cv.get('confidence', 0):.2%}</td>
                    </tr>
                </table>
                <h3 style="margin-top: 15px;">Confidence Calculation</h3>
                <div class="detail-text">
                    <strong>Method:</strong> {cv.get('confidence_calculation', {}).get('method', 'N/A')}<br/>
                    <strong>Source:</strong> {cv.get('confidence_calculation', {}).get('source', 'N/A')}<br/>
                    <strong>Formula:</strong> {cv.get('confidence_calculation', {}).get('formula', 'N/A')}<br/>
                    <strong>Interpretation:</strong> {cv.get('confidence_calculation', {}).get('interpretation', 'N/A')}
                </div>
            </div>
        </div>
        
        <!-- PHYSICS-GUIDED RESULTS -->
        <div class="section">
            <h2>2. Physics-Guided Classification</h2>
            <div class="subsection">
                <h3>Classification Result</h3>
                <table>
                    <tr>
                        <td><strong>Classification</strong></td>
                        <td><strong>{pg.get('classification', 'N/A')}</strong></td>
                    </tr>
                    <tr>
                        <td><strong>Confidence Score</strong></td>
                        <td>{pg.get('confidence_score', 0):.2%}</td>
                    </tr>
                </table>"""
        
        # Add geometric features if available
        if 'geometric_features' in pg and pg['geometric_features']:
            geom = pg['geometric_features']
            html += f"""
                <h3 style="margin-top: 15px;">Geometric Features</h3>
                <table>
                    <tr>
                        <th>Feature</th>
                        <th>Value</th>
                        <th>Threshold/Expected</th>
                    </tr>
                    <tr>
                        <td>Area (pixels)</td>
                        <td>{geom.get('area', 'N/A')}</td>
                        <td>> 100</td>
                    </tr>
                    <tr>
                        <td>Elongation Ratio</td>
                        <td>{geom.get('elongation_ratio', 0):.2f}</td>
                        <td>> 1.8</td>
                    </tr>
                    <tr>
                        <td>Compactness</td>
                        <td>{geom.get('compactness', 0):.2f}</td>
                        <td>> 2.0</td>
                    </tr>
                    <tr>
                        <td>Orientation</td>
                        <td>{geom.get('orientation', 0):.1f}°</td>
                        <td>Within 40° of drift</td>
                    </tr>
                    <tr>
                        <td>Perimeter (pixels)</td>
                        <td>{geom.get('perimeter', 'N/A')}</td>
                        <td>N/A</td>
                    </tr>
                </table>"""
        
        # Add radiometric features if available
        if 'radiometric_features' in pg and pg['radiometric_features']:
            radio = pg['radiometric_features']
            html += f"""
                <h3 style="margin-top: 15px;">Radiometric Features (SAR)</h3>
                <table>
                    <tr>
                        <td>Mean Intensity</td>
                        <td>{radio.get('mean_intensity', 0):.2f} dB</td>
                        <td>< -15.0 dB</td>
                    </tr>
                    <tr>
                        <td>Std Deviation (Smoothness)</td>
                        <td>{radio.get('std_intensity', 0):.2f} dB</td>
                        <td>< 1.5 dB</td>
                    </tr>
                </table>"""
        
        # Add rule verification if available
        if 'rule_results' in pg and pg['rule_results']:
            rules = pg['rule_results']
            html += f"""
                <h3 style="margin-top: 15px;">Physical Guidance Rules</h3>
                <table>
                    <tr>
                        <th>Rule</th>
                        <th>Status</th>
                        <th>Details</th>
                    </tr>
                    <tr>
                        <td><strong>Darkness Rule</strong></td>
                        <td><span class="{'rule-pass' if rules.get('darkness_pass') else 'rule-fail'}">{'✓ PASS' if rules.get('darkness_pass') else '✗ FAIL'}</span></td>
                        <td>Mean SAR intensity below -15 dB threshold</td>
                    </tr>
                    <tr>
                        <td><strong>Smoothness Rule</strong></td>
                        <td><span class="{'rule-pass' if rules.get('smoothness_pass') else 'rule-fail'}">{'✓ PASS' if rules.get('smoothness_pass') else '✗ FAIL'}</span></td>
                        <td>Standard deviation below 1.5 dB</td>
                    </tr>
                    <tr>
                        <td><strong>Shape Rule</strong></td>
                        <td><span class="{'rule-pass' if rules.get('shape_pass') else 'rule-fail'}">{'✓ PASS' if rules.get('shape_pass') else '✗ FAIL'}</span></td>
                        <td>Elongation > 1.8 and Compactness > 2.0</td>
                    </tr>
                    <tr>
                        <td><strong>Alignment Rule</strong></td>
                        <td><span class="{'rule-pass' if rules.get('alignment_pass') else 'rule-fail'}">{'✓ PASS' if rules.get('alignment_pass') else '✗ FAIL'}</span></td>
                        <td>Orientation aligned with drift direction (±40°)</td>
                    </tr>
                </table>"""
        
        html += """
            </div>
        </div>
        
        <!-- NLP VALIDATION -->
        <div class="section">
            <h2>3. NLP Validation & Historical Correlation</h2>
            <div class="subsection">
                <h3>Analysis Results</h3>
                <table>
                    <tr>
                        <td><strong>Status</strong></td>
                        <td>{}</td>
                    </tr>
                    <tr>
                        <td><strong>Risk Level</strong></td>
                        <td><strong>{}</strong></td>
                    </tr>
                    <tr>
                        <td><strong>NLP Confidence</strong></td>
                        <td>{:.2%}</td>
                    </tr>
                    <tr>
                        <td><strong>Distance Matches</strong></td>
                        <td>{}</td>
                    </tr>
                    <tr>
                        <td><strong>Time Matches</strong></td>
                        <td>{}</td>
                    </tr>
                    <tr>
                        <td><strong>Joint Matches</strong></td>
                        <td>{}</td>
                    </tr>
                </table>""".format(
                    nlp.get('status', 'N/A'),
                    nlp.get('risk_level', 'N/A'),
                    nlp.get('confidence', 0),
                    nlp.get('distance_matches', 0),
                    nlp.get('time_matches', 0),
                    nlp.get('joint_matches', 0)
                )
        
        # Add NLP matches if available
        if nlp and 'reports' in nlp and nlp['reports']:
            reports = nlp['reports']
            
            if isinstance(reports, dict):
                if 'by_distance' in reports and reports['by_distance']:
                    html += "<h3>🗺️ Distance-Based Matches (Top 3)</h3>"
                    matches = reports['by_distance'] if isinstance(reports['by_distance'], list) else [reports['by_distance']]
                    for match in matches[:3]:
                        if isinstance(match, dict):
                            html += f"""
                    <div class="match-item">
                        <strong class="match-rank">#{match.get('rank', 'N/A')}</strong> - {match.get('name', 'Unknown')}<br/>
                        <strong>Location:</strong> {match.get('location', 'N/A')} (Lat: {match.get('lat', 'N/A')}, Lon: {match.get('lon', 'N/A')})<br/>
                        <strong>Distance:</strong> {match.get('distance_km', 0):.2f} km<br/>
                        <strong>Date:</strong> {match.get('date', 'N/A')}<br/>
                        <strong>Threat:</strong> {match.get('threat', 'N/A')} | <strong>Commodity:</strong> {match.get('commodity', 'N/A')}<br/>
                        <strong>Cause:</strong> {match.get('cause_category', 'N/A')}<br/>
                        <em>{match.get('description', '')[:150]}...</em>
                    </div>"""
        
        html += """
            </div>
        </div>
        
        <!-- ENSEMBLE DECISION -->
        <div class="section">
            <h2>4. Ensemble Decision Layer</h2>
            <div class="subsection">
                <h3>Final Verdict</h3>
                <table>
                    <tr>
                        <td><strong>Final Classification</strong></td>
                        <td><strong>{}</strong></td>
                    </tr>
                    <tr>
                        <td><strong>Ensemble Confidence</strong></td>
                        <td><strong>{:.2%}</strong></td>
                    </tr>
                    <tr>
                        <td><strong>Decision Method</strong></td>
                        <td>{}</td>
                    </tr>
                </table>""".format(
                    ensemble.get('final_classification', 'Unknown'),
                    ensemble.get('confidence', 0),
                    ensemble.get('method', 'Weighted voting of CV + PG + NLP')
                )
        
        html += """
            </div>
        </div>
        
        <!-- RECOMMENDATIONS -->
        <div class="section">
            <h2>Actions & Recommendations</h2>
            <h3>For Decision Makers:</h3>
            <ul>"""
        
        if final_conf > 0.5:
            html += """
                <li><strong>🚨 ALERT AUTHORITIES:</strong> Oil spill has been detected with {:.1f}% confidence. Immediate response coordination is recommended.</li>
                <li>Cross-reference with maritime authority reports and confirmed satellite imagery.</li>
                <li>Deploy specialized response teams if confirmed by authorities.</li>
                <li>Monitor environmental impact and coordinate with coastal protection agencies.</li>
            </ul>""".format(final_conf*100)
        else:
            html += """
                <li><strong>✓ CONTINUE MONITORING:</strong> No oil spill detected at this time ({:.1f}% confidence).</li>
                <li>Standard maritime surveillance protocols should continue.</li>
                <li>Maintain regular satellite monitoring schedule.</li>
                <li>Re-analyze if new suspicious SAR signatures emerge.</li>
            </ul>""".format((1-final_conf)*100)
        
        html += f"""
        </div>
        
        <footer>
            <p><strong>Oil Spill Detection Pipeline - Comprehensive Report</strong></p>
            <p>Multi-Modal Integration System: Computer Vision + Physics-Guided Classification + NLP Analysis</p>
            <p>Graduation Project in AI - Integration Layer</p>
            <div class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</div>
            <p style="margin-top: 15px;"><em>⚠️ DISCLAIMER: This report is generated by an automated system for informational purposes only. Final decisions regarding oil spill response should be made by qualified environmental authorities and response teams based on multiple independent data sources and expert analysis.</em></p>
        </footer>
    </div>
</body>
</html>
"""
        
        # Save HTML
        timestamp = datetime.now().strftime("%Y%m%dT%H%MZ")
        html_file = output_path / f"oil_spill_comprehensive_report_{timestamp}.html"
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html)
        
        logger.info(f"✓ Comprehensive report generated: {html_file}")
        
        return {
            'comprehensive_html': str(html_file),
            'timestamp': timestamp
        }
        
    except Exception as e:
        logger.error(f"Failed to generate comprehensive report: {e}")
        import traceback
        traceback.print_exc()
        return {}
