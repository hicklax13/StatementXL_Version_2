"""
Diagnostic script for PDF Extraction.

Checks:
1. Text layer presence (Native vs Scanned).
2. Tesseract availability.
3. Table detection results with current settings.
"""
import os
import sys
import structlog
import pdfplumber
from pathlib import Path

# Setup simple logging
structlog.configure(
    processors=[
        structlog.processors.JSONRenderer(sort_keys=True)
    ]
)

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.services.table_detector import get_table_detector
from backend.services.ocr_service import get_ocr_service

PDF_DIR = Path("Test_Financial_Statement_PDFs")
TEST_FILE = "Test_Income_Statement_EASY.pdf"

def diagnose_pdf(pdf_name):
    pdf_path = PDF_DIR / pdf_name
    print(f"\n--- Diagnosing: {pdf_name} ---")
    
    if not pdf_path.exists():
        print(f"File not found: {pdf_path}")
        return

    # 1. Check Text Layer (pdfplumber)
    print("Checking Text Layer...")
    with pdfplumber.open(pdf_path) as pdf:
        if not pdf.pages:
            print("  No pages found!")
            return
            
        page = pdf.pages[0]
        text = page.extract_text()
        text_len = len(text) if text else 0
        print(f"  Page 1 Text Length: {text_len}")
        if text_len < 50:
            print("  -> SCANNED or Low Text Content (OCR Required)")
        else:
            print("  -> NATIVE text detected.")
            print(f"  Sample: {text[:100]}...")

    # 2. Check OCR Capability
    print("\nChecking OCR Service...")
    ocr = get_ocr_service()
    if ocr._tesseract_available:
        print("  Tesseract is AVAILABLE.")
    else:
        print("  Tesseract is MISSING.")
        
    # 3. Test Table Detector (Current Pipeline)
    print("\nTesting TableDetector (Standard Pipeline)...")
    detector = get_table_detector()
    try:
        result = detector.detect_tables(pdf_path)
        print(f"  Tables Found: {len(result.tables)}")
        for i, t in enumerate(result.tables):
            print(f"    Table {i+1}: {len(t.rows)} rows, Method: {t.detection_method}, Conf: {t.confidence}")
            if t.rows:
                print(f"      Row 1: {[c.value for c in t.rows[0].cells]}")
    except Exception as e:
        print(f"  Detector Failed: {e}")

if __name__ == "__main__":
    # Test specific file
    diagnose_pdf(TEST_FILE)
    
    # Optional: Test a HARD file
    diagnose_pdf("Test_Income_Statement_Multi_Column_HARD.pdf")
