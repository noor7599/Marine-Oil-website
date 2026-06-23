# nlp_module/unified_validator.py
"""
Unified NLP Validator: Combines distance/time/joint matching with AI report generation
Output: 5 reports (3 closest by distance, 1 by time, 1 by joint score)
"""

import pandas as pd
import numpy as np
import math
import textwrap
import joblib
import logging
from datetime import datetime
from pathlib import Path
from geopy.distance import geodesic
import re 

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ---------------------- CONFIGURATION ----------------------
CAUSE_MODEL_PATH = "/Users/mac/Downloads/all project 2/graduation-project/backend/oilspill_analysis/cause_classifier_model.joblib"
# Note: PDF output path is now dynamic and passed per-function-call
# Previously was set at module load time (now removed)

# Optional: AI report generation (set to False if PyTorch not available)
USE_AI_REPORTS = False  # Set to True only if you have PyTorch + transformers installed

# ---------------------- LOAD CAUSE CLASSIFIER ----------------------
try:
    cause_model = joblib.load(CAUSE_MODEL_PATH)
    logger.info("✅ Cause classifier loaded successfully")
except FileNotFoundError:
    logger.error(f"Cause model not found: {CAUSE_MODEL_PATH}")
    raise

# ---------------------- DATA NORMALIZATION ----------------------
def parse_date(val):
    if pd.isna(val):
        return pd.NaT
    val = str(val).strip().replace('\n', '').replace('\r', '')
    if val.isdigit():
        as_int = int(val)
        if 20000 < as_int < 80000:
            return pd.Timestamp('1900-01-01') + pd.Timedelta(days=as_int - 2)
    fmts = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y",
            "%d.%m.%Y", "%Y.%m.%d", "%Y/%m/%d"]
    for fmt in fmts:
        try:
            return pd.to_datetime(val, format=fmt, dayfirst=True)
        except:
            continue
    try:
        return pd.to_datetime(val, dayfirst=True, errors='coerce')
    except:
        return pd.NaT

def normalize_incidents(csv_path, xlsx_path=None):
    """Load and normalize incident data from CSV/XLSX"""
    df_csv = pd.read_csv(csv_path, dtype=str)
    df_csv.columns = df_csv.columns.str.strip().str.lower()
    
    if xlsx_path and Path(xlsx_path).exists():
        df_xlsx = pd.read_excel(xlsx_path, dtype=str)
        df_xlsx.columns = df_xlsx.columns.str.strip().str.lower()
        df = pd.concat([df_csv, df_xlsx], ignore_index=True)
    else:
        df = df_csv
    
    df['open_date_raw'] = df['open_date']
    df['open_date'] = df['open_date_raw'].apply(parse_date)
    df['timestamp'] = df['open_date']
    df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
    df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
    
    for col in ['commodity', 'description', 'name', 'location']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.lower().str.strip()
    
    def is_oil(row):
        oil_terms = ['oil', 'petroleum', 'crude', 'jp-5', 'diesel', 'fuel']
        if any(term in row.get('commodity', '') for term in oil_terms):
            if 'algal bloom' in row.get('description', '') or 'whale carcass' in row.get('description', ''):
                return False
            return True
        return False
    
    def ml_cause(row):
        text = f"{row.get('name','')} {row.get('location','')} {row.get('description','')}"
        try:
            return cause_model.predict([text])[0]
        except:
            return 'Unknown / other'
    
    df['is_oil'] = df.apply(is_oil, axis=1)
    df['cause_category'] = df.apply(ml_cause, axis=1)
    df = df.dropna(subset=['lat', 'lon', 'timestamp'])
    
    return df

# ---------------------- Haversine Distance ----------------------
def haversine(lat1, lon1, lat2, lon2):
    """Calculate distance between two coordinates in km"""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

# ---------------------- PREVENTION MESSAGES ----------------------
def prevention_message(cause_category):
    cause = cause_category or 'Unknown / other'
    messages = {
        'Grounding / aground': 'Enhanced navigation, electronic charts, and routing away from shallow/high-risk areas.',
        'Collision / allision': 'Traffic separation schemes, bridge team training, and collision-avoidance systems.',
        'Fire / explosion': 'Strict control of ignition sources, gas monitoring, and emergency response drills.',
        'Structural / hull failure': 'Regular hull inspections, corrosion control, and timely maintenance.',
        'Equipment / pipeline failure': 'Preventive maintenance, real-time monitoring, and redundancy in critical systems.',
        'Loading / transfer error': 'Standardized transfer procedures, supervision, and leak detection during cargo/bunkering operations.',
        'Weather / natural hazard': 'Weather routing, operational limits in severe conditions, and dynamic risk assessments.',
        'Human / procedural error': 'Enhanced training, clear procedures, and use of checklists to reduce human error.'
    }
    return messages.get(cause, 'Improved monitoring, maintenance, and operational procedures tailored to local conditions.')

# ---------------------- FIND MATCHES ----------------------
def find_all_matches(df, lat_input, lon_input, timestamp_input, is_oil_prediction, 
                     dist_km=100, time_years=3):
    """
    Find 5 reports: 3 closest by distance, 1 by time, 1 by joint score
    Returns dictionary with all 5 match reports
    """
    logger.info(f"Finding matches for location ({lat_input}, {lon_input}) at {timestamp_input}")
    
    target_time = pd.to_datetime(timestamp_input)
    df_local = df.copy()
    
    # Calculate distances and time differences
    df_local['distance_km'] = df_local.apply(
        lambda r: geodesic((lat_input, lon_input), (r['lat'], r['lon'])).km, 
        axis=1
    )
    df_local['time_diff_years'] = df_local['timestamp'].apply(
        lambda t: abs((target_time - t).days) / 365.25 if pd.notna(t) else np.nan
    )
    
    # Normalize for joint score
    df_local['norm_distance'] = (df_local['distance_km'] / dist_km).clip(0, 1)
    df_local['norm_time'] = (df_local['time_diff_years'] / time_years).clip(0, 1)
    df_local['joint_score'] = df_local['norm_distance'] + df_local['norm_time']
    
    # Get 3 closest by distance
    top3_distance = df_local.sort_values('distance_km').head(3)
    
    # Get 1 closest by time
    closest_time = df_local.sort_values('time_diff_years').head(1)
    
    # Get 1 closest by joint score
    closest_joint = df_local.sort_values('joint_score').head(1)
    
    # Build reports
    reports = {
        'by_distance': [],
        'by_time': None,
        'by_joint': None
    }
    
    # Distance reports (3)
    for idx, row in top3_distance.iterrows():
        reports['by_distance'].append({
            'type': 'distance',
            'rank': len(reports['by_distance']) + 1,
            'name': row.get('name', 'Unknown'),
            'location': row.get('location', ''),
            'lat': row['lat'],
            'lon': row['lon'],
            'distance_km': row['distance_km'],
            'time_diff_years': row['time_diff_years'],
            'date': row.get('open_date', ''),
            'threat': row.get('threat', ''),
            'commodity': row.get('commodity', ''),
            'description': row.get('description', ''),
            'is_oil': row['is_oil'],
            'cause_category': row['cause_category'],
            'prevention_focus': prevention_message(row['cause_category']),
            'match_status': 'MATCH' if row['is_oil'] == is_oil_prediction else 'MISMATCH',
        })
    
    # Time report (1)
    if not closest_time.empty:
        row = closest_time.iloc[0]
        reports['by_time'] = {
            'type': 'time',
            'name': row.get('name', 'Unknown'),
            'location': row.get('location', ''),
            'lat': row['lat'],
            'lon': row['lon'],
            'distance_km': row['distance_km'],
            'time_diff_years': row['time_diff_years'],
            'date': row.get('open_date', ''),
            'threat': row.get('threat', ''),
            'commodity': row.get('commodity', ''),
            'description': row.get('description', ''),
            'is_oil': row['is_oil'],
            'cause_category': row['cause_category'],
            'prevention_focus': prevention_message(row['cause_category']),
            'match_status': 'MATCH' if row['is_oil'] == is_oil_prediction else 'MISMATCH'
        }
    
    # Joint report (1)
    if not closest_joint.empty:
        row = closest_joint.iloc[0]
        reports['by_joint'] = {
            'type': 'joint',
            'name': row.get('name', 'Unknown'),
            'location': row.get('location', ''),
            'lat': row['lat'],
            'lon': row['lon'],
            'distance_km': row['distance_km'],
            'time_diff_years': row['time_diff_years'],
            'date': row.get('open_date', ''),
            'threat': row.get('threat', ''),
            'commodity': row.get('commodity', ''),
            'description': row.get('description', ''),
            'is_oil': row['is_oil'],
            'cause_category': row['cause_category'],
            'prevention_focus': prevention_message(row['cause_category']),
            'match_status': 'MATCH' if row['is_oil'] == is_oil_prediction else 'MISMATCH',
            
        }
    
    logger.info(f"Found {len(reports['by_distance'])} distance matches, 1 time match, 1 joint match")
    return reports

# ---------------------- AI REPORT GENERATION (Optional) ----------------------
def generate_ai_summary(incident_info):
    """Generate AI summary using LLM (if available)"""
    if not USE_AI_REPORTS:
        return "AI summary not available (LLM disabled)"
    
    try:
        from transformers import AutoTokenizer, AutoModelForCausalLM
        import torch
        
        MODEL_NAME = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
        device = "cuda" if torch.cuda.is_available() else "cpu"
        
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            device_map="auto" if device == "cuda" else "cpu",
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            low_cpu_mem_usage=True
        )
        
        prompt = (
            "Write a concise, professional incident report summary. "
            "Focus on key facts, cause analysis, and recommendations.\n\n"
            f"{incident_info}\n\n"
            "Summary:"
        )
        
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        outputs = model.generate(**inputs, max_new_tokens=150, temperature=0.7)
        summary = tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        if "Summary:" in summary:
            summary = summary.split("Summary:")[-1].strip()
        
        return summary[:500]  # Limit to 500 chars
    
    except Exception as e:
        logger.warning(f"AI summary generation failed: {e}")
        return f"AI generation failed: {str(e)}"

# ---------------------- PDF GENERATION ----------------------
def _sanitize_text_for_pdf(text):
    """
    Convert Unicode characters to ASCII equivalents for PDF generation.
    Reportlab's Helvetica font has limited Unicode support.
    
    IMPORTANT: Only sanitizes actual text strings, preserves numeric types.
    
    Converts:
    - en-dash (–) to hyphen (-)
    - em-dash (—) to double hyphen (--)
    - smart quotes ("", '') to regular quotes ("', '')
    - other common Unicode chars to ASCII equivalents
    """
    # Keep numeric types as-is (don't convert to string)
    if isinstance(text, (int, float, bool, type(None))):
        return text
    
    if not text:
        return text
    
    text = str(text)
    
    # Unicode to ASCII replacements
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
        '°': 'deg',    # degree
        '™': '(TM)',   # trademark
        '©': '(C)',    # copyright
        '®': '(R)',    # registered
        'é': 'e',
        'è': 'e',
        'ê': 'e',
        'ë': 'e',
        'à': 'a',
        'á': 'a',
        'ü': 'u',
        'ö': 'o',
        'ñ': 'n',
    }
    
    for unicode_char, ascii_char in replacements.items():
        text = text.replace(unicode_char, ascii_char)
    
    # Remove any remaining non-ASCII characters
    text = text.encode('ascii', errors='ignore').decode('ascii')
    
    return text


def generate_pdf_report(reports, detection_info, output_path=None):
    """
    Generate comprehensive PDF report with all 5 incident matches
    
    Parameters:
    -----------
    reports : dict
        Dictionary with keys 'by_distance', 'by_time', 'by_joint'
    detection_info : dict
        Dictionary with 'lat', 'lon', 'timestamp', 'is_oil'
    output_path : str, optional
        Custom output path. If None, saves to outputs/ with timestamp.
    """
    # Generate dynamic output path if not provided
    if output_path is None:
        output_path = f"outputs/nlp_incident_reports_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    
    # Sanitize all report data before PDF generation
    def sanitize_report(report):
        """Recursively sanitize report dictionary"""
        if isinstance(report, dict):
            return {k: sanitize_report(v) for k, v in report.items()}
        elif isinstance(report, list):
            return [sanitize_report(item) for item in report]
        else:
            return _sanitize_text_for_pdf(report)
    
    reports = sanitize_report(reports)
    detection_info = sanitize_report(detection_info)
    
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        
        # Ensure output directory exists
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Starting PDF generation to: {output_file.absolute()}")
        c = canvas.Canvas(str(output_file), pagesize=A4)
        width, height = A4
        y_start = height - 60
        line_height = 16
        indent = 25
        wrap_width = 85
        
        def check_page(y):
            if y < 100:
                c.showPage()
                y = y_start
                c.setFont("Helvetica", 10)
            return y
        
        # ===== TITLE PAGE =====
        c.setFont("Helvetica-Bold", 18)
        c.drawString(50, y_start, "Oil Spill Detection: Historical Incident Analysis")
        y = y_start - 50
        
        c.setFont("Helvetica", 11)
        c.drawString(50, y, f"Detection Location: ({detection_info['lat']:.4f}, {detection_info['lon']:.4f})")
        y -= line_height
        c.drawString(50, y, f"Detection Time: {detection_info['timestamp']}")
        y -= line_height
        c.drawString(50, y, f"Oil Prediction: {'YES' if detection_info['is_oil'] else 'NO'}")
        y -= line_height * 2
        
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, "Executive Summary")
        y -= line_height * 1.5
        c.setFont("Helvetica", 10)
        summary_lines = [
            f"• Analyzed {len(reports['by_distance'])} closest incidents by distance",
            f"• Compared with {1 if reports['by_time'] else 0} closest incident by time",
            f"• Evaluated {1 if reports['by_joint'] else 0} closest incident by combined score",
            f"• Generated comprehensive risk assessment and prevention recommendations"
        ]
        for line in summary_lines:
            y = check_page(y)
            c.drawString(50, y, line)
            y -= line_height
        
        c.showPage()
        y = y_start
        
        # ===== DISTANCE REPORTS (3) =====
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, y, "Top 3 Closest Incidents by Distance")
        y -= line_height * 2
        
        for report in reports['by_distance']:
            y = check_page(y)
            
            # Header
            c.setFont("Helvetica-Bold", 12)
            c.setFillColorRGB(0.2, 0.4, 0.8)
            c.drawString(50, y, f"#{report['rank']}: {report['name']}")
            c.setFillColorRGB(0, 0, 0)
            y -= line_height
            
            c.setFont("Helvetica", 9)
            c.setFillColorRGB(0.5, 0.5, 0.5)
            meta = f"Distance: {report['distance_km']:.1f} km | Time Diff: {report['time_diff_years']:.1f} years"
            c.drawString(50, y, meta)
            c.setFillColorRGB(0, 0, 0)
            y -= line_height * 1.5
            
            # Fields
            c.setFont("Helvetica-Bold", 10)
            fields = [
                ("Location", report['location']),
                ("Coordinates", f"{report['lat']:.4f}, {report['lon']:.4f}"),
                ("Date", str(report['date'])),
                ("Threat Level", report['threat']),
                ("Commodity", report['commodity']),
                ("Cause Category", report['cause_category']),
                ("Match Status", report['match_status']),
            ]
            
            for title, value in fields:
                if not value or str(value).strip() == "":
                    continue
                c.drawString(50, y, f"{title}:")
                y -= line_height
                y = check_page(y)
                c.setFont("Helvetica", 9)
                c.drawString(50 + indent, y, str(value))
                y -= line_height * 0.8
                c.setFont("Helvetica-Bold", 10)
            
            y -= line_height
            
            # Description
            c.setFont("Helvetica-Bold", 10)
            c.drawString(50, y, "Description:")
            y -= line_height
            y = check_page(y)
            c.setFont("Helvetica", 9)
            desc_lines = textwrap.wrap(report['description'], width=wrap_width)
            for line in desc_lines[:4]:  # Limit to 4 lines
                c.drawString(50 + indent, y, line)
                y -= line_height * 0.9
                y = check_page(y)
            
            y -= line_height * 0.5
            
            # Prevention focus
            c.setFont("Helvetica-Bold", 10)
            c.drawString(50, y, "Prevention Focus:")
            y -= line_height
            y = check_page(y)
            c.setFont("Helvetica", 9)
            c.setFillColorRGB(0.3, 0.6, 0.3)
            prevention_lines = textwrap.wrap(report['prevention_focus'], width=wrap_width)
            for line in prevention_lines[:2]:
                c.drawString(50 + indent, y, line)
                y -= line_height * 0.9
                y = check_page(y)
            c.setFillColorRGB(0, 0, 0)
            
            y -= line_height * 1.5
            c.line(50, y, width - 50, y)
            y -= line_height
        
        # ===== TIME REPORT (1) =====
        if reports['by_time']:
            c.showPage()
            y = y_start
            
            c.setFont("Helvetica-Bold", 16)
            c.drawString(50, y, "Closest Incident by Time")
            y -= line_height * 2
            
            report = reports['by_time']
            c.setFont("Helvetica-Bold", 12)
            c.setFillColorRGB(0.8, 0.3, 0.3)
            c.drawString(50, y, f"Time Match: {report['name']}")
            c.setFillColorRGB(0, 0, 0)
            y -= line_height
            
            c.setFont("Helvetica", 9)
            c.setFillColorRGB(0.5, 0.5, 0.5)
            meta = f"Time Diff: {report['time_diff_years']:.1f} years | Distance: {report['distance_km']:.1f} km"
            c.drawString(50, y, meta)
            c.setFillColorRGB(0, 0, 0)
            y -= line_height * 1.5
            
            # Show key fields (same as distance reports)
            c.setFont("Helvetica-Bold", 10)
            fields = [
                ("Location", report['location']),
                ("Coordinates", f"{report['lat']:.4f}, {report['lon']:.4f}"),
                ("Date", str(report['date'])),
                ("Threat Level", report['threat']),
                ("Commodity", report['commodity']),
                ("Cause Category", report['cause_category']),
                ("Match Status", report['match_status']),
            ]
            
            for title, value in fields:
                if not value or str(value).strip() == "":
                    continue
                c.drawString(50, y, f"{title}:")
                y -= line_height
                y = check_page(y)
                c.setFont("Helvetica", 9)
                c.drawString(50 + indent, y, str(value))
                y -= line_height * 0.8
                c.setFont("Helvetica-Bold", 10)
        
        # ===== JOINT REPORT (1) =====
        if reports['by_joint']:
            c.showPage()
            y = y_start
            
            c.setFont("Helvetica-Bold", 16)
            c.drawString(50, y, "Closest Incident by Combined Score (Distance + Time)")
            y -= line_height * 2
            
            report = reports['by_joint']
            c.setFont("Helvetica-Bold", 12)
            c.setFillColorRGB(0.7, 0.3, 0.7)
            c.drawString(50, y, f"Best Overall Match: {report['name']}")
            c.setFillColorRGB(0, 0, 0)
            y -= line_height
            
            c.setFont("Helvetica", 9)
            c.setFillColorRGB(0.5, 0.5, 0.5)
            meta = f"Joint Score: {report['distance_km']:.1f} km + {report['time_diff_years']:.1f} years"
            c.drawString(50, y, meta)
            c.setFillColorRGB(0, 0, 0)
            y -= line_height * 1.5
            
            # Show key fields
            c.setFont("Helvetica-Bold", 10)
            fields = [
                ("Location", report['location']),
                ("Coordinates", f"{report['lat']:.4f}, {report['lon']:.4f}"),
                ("Date", str(report['date'])),
                ("Threat Level", report['threat']),
                ("Commodity", report['commodity']),
                ("Cause Category", report['cause_category']),
                ("Match Status", report['match_status']),
            ]
            
            for title, value in fields:
                if not value or str(value).strip() == "":
                    continue
                c.drawString(50, y, f"{title}:")
                y -= line_height
                y = check_page(y)
                c.setFont("Helvetica", 9)
                c.drawString(50 + indent, y, str(value))
                y -= line_height * 0.8
                c.setFont("Helvetica-Bold", 10)
        
        # Save PDF
        c.save()
        logger.info(f"✅ PDF report generated: {output_path}")
        return output_path
        
    except ImportError as e:
        logger.error(f"❌ ReportLab not installed. Install with: pip install reportlab. Error: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ PDF generation failed: {type(e).__name__}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

# ---------------------- MAIN VALIDATOR FUNCTION ----------------------
def validate_detection(
    csv_path,
    lat_input,
    lon_input,
    timestamp_input,
    is_oil_prediction=True,
    xlsx_path=None,
    generate_pdf=True,
    pdf_output_path=None
):
    """
    Main function: Validates detection against historical incidents
    
    Args:
        csv_path: Path to incidents CSV file
        lat_input: Detection latitude
        lon_input: Detection longitude
        timestamp_input: Detection timestamp (string or datetime)
        is_oil_prediction: Boolean - whether detection predicts oil spill
        xlsx_path: Optional path to additional XLSX data
        generate_pdf: Whether to generate PDF report
        pdf_output_path: Optional custom path for PDF output (e.g., run folder). 
                        If None and generate_pdf=True, uses default outputs/
    
    Returns:
        dict with keys:
            - confidence: Numeric score (0-1) based on matches
            - risk_level: Risk classification (HIGH, MEDIUM, LOW, VERY_LOW)
            - distance_matches: Count of spatial matches
            - time_matches: Count of temporal matches
            - joint_matches: Count of spatial+temporal matches
            - reports: Dictionary with 5 reports (3 distance, 1 time, 1 joint)
            - summary: Overall assessment
            - pdf_path: Path to generated PDF (if generate_pdf=True)
    """
    logger.info(f"Starting validation for detection at ({lat_input}, {lon_input})")
    
    # Load and normalize data
    df = normalize_incidents(csv_path, xlsx_path)
    logger.info(f"Loaded {len(df)} incidents from database")
    
    # Find all matches
    reports = find_all_matches(
        df, 
        lat_input, 
        lon_input, 
        timestamp_input, 
        is_oil_prediction
    )
    
    # Count different types of matches
    distance_matches = len(reports.get('by_distance', []))
    time_matches = 1 if reports.get('by_time') else 0
    joint_matches = 1 if reports.get('by_joint') else 0
    
    # Calculate confidence score and risk level based on matches
    # Using the structure: joint > distance+time > distance only
    if joint_matches > 0:
        confidence = 0.90
        risk_level = "HIGH"
    elif distance_matches >= 3 and time_matches >= 1:
        confidence = 0.75
        risk_level = "MEDIUM"
    elif distance_matches >= 1 and time_matches >= 1:
        confidence = 0.65
        risk_level = "MEDIUM"
    elif distance_matches >= 3:
        confidence = 0.70
        risk_level = "MEDIUM"
    elif distance_matches >= 1:
        confidence = 0.60
        risk_level = "LOW"
    else:
        confidence = 0.40
        risk_level = "VERY_LOW"
    
    # Generate summary
    oil_matches = sum(1 for r in reports.get('by_distance', []) if r.get('is_oil'))
    total_distance = len(reports.get('by_distance', []))
    
    summary = {
        'total_incidents_analyzed': len(df),
        'distance_matches_found': total_distance,
        'time_matches': time_matches,
        'joint_matches': joint_matches,
        'oil_incidents_in_area': oil_matches,
        'oil_match_percentage': round((oil_matches / total_distance * 100), 1) if total_distance > 0 else 0,
        'closest_distance_km': reports.get('by_distance', [{}])[0].get('distance_km') if reports.get('by_distance') else None,
        'closest_time_years': reports.get('by_time', {}).get('time_diff_years') if reports.get('by_time') else None,
        'recommendation': risk_level
    }
    
    # Generate PDF if requested
    pdf_path = None
    if generate_pdf:
        detection_info = {
            'lat': lat_input,
            'lon': lon_input,
            'timestamp': timestamp_input,
            'is_oil': is_oil_prediction
        }
        pdf_path = generate_pdf_report(reports, detection_info, output_path=pdf_output_path)
    
    return {
        'confidence': float(confidence),
        'risk_level': risk_level,
        'distance_matches': distance_matches,
        'time_matches': time_matches,
        'joint_matches': joint_matches,
        'reports': reports,
        'summary': summary,
        'pdf_path': pdf_path
    }

# ---------------------- EXAMPLE USAGE ----------------------
if __name__ == "__main__":
    # Example: Validate a detection
    result = validate_detection(
        csv_path="incidents_balanced_cleaned.csv",
        lat_input=50.702,      # Gulf of Mexico
        lon_input=-70.123,
        timestamp_input="2015-07-15 12:00:00",
        is_oil_prediction=True,
        xlsx_path=None,         # Optional: add XLSX path if available
        generate_pdf=True
    )
    
    # Print summary
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)
    print(f"Total incidents in database: {result['summary']['total_incidents_analyzed']}")
    print(f"Oil incidents in area: {result['summary']['oil_incidents_in_area']}/3")
    print(f"Oil match percentage: {result['summary']['oil_match_percentage']}%")
    print(f"Closest incident: {result['summary']['closest_distance_km']:.1f} km away")
    print(f"Risk assessment: {result['summary']['recommendation']}")
    print(f"PDF report: {result['pdf_path']}")
    print("="*60)