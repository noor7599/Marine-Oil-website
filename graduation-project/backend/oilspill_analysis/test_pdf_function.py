#!/usr/bin/env python
"""Test the generate_pdf_report function to diagnose issues"""

import logging
import sys

# Setup logging to see everything
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

print("=" * 60)
print("PDF Function Test")
print("=" * 60)

try:
    print("\n[1] Importing src.model...")
    from src.model import generate_pdf_report
    print("✅ Successfully imported generate_pdf_report")
    
    print("\n[2] Preparing test data...")
    reports = {
        'by_distance': [],
        'by_time': None,
        'by_joint': None
    }
    detection_info = {
        'lat': 50.702,
        'lon': -70.123,
        'timestamp': '2015-07-15 12:00:00',
        'is_oil': True
    }
    print("✅ Test data prepared")
    
    print("\n[3] Calling generate_pdf_report()...")
    result = generate_pdf_report(reports, detection_info, 'test_report.pdf')
    print(f"✅ Function returned: {result}")
    
    if result:
        print("\n✅ SUCCESS: PDF was generated!")
    else:
        print("\n❌ FAILED: PDF generation returned None (check logs above)")
    
except Exception as e:
    print(f"\n❌ ERROR: {type(e).__name__}: {e}")
    import traceback
    print("\nFull traceback:")
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
