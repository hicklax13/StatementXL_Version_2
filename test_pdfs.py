"""
Comprehensive PDF test script for StatementXL.
Tests all PDFs in Test_Financial_Statement_PDFs directory.
"""
import json
import os
import sys
from pathlib import Path
import requests

TEST_DIR = Path(r"C:\Users\conno\OneDrive\Desktop\StatementXL_Version_2\Test_Financial_Statement_PDFs")
UPLOAD_URL = "http://localhost:8000/api/v1/upload"

def test_pdf(file_path: Path) -> dict:
    """Test a single PDF file."""
    try:
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f, "application/pdf")}
            response = requests.post(UPLOAD_URL, files=files, timeout=120)
        
        result = {
            "file": file_path.name,
            "status_code": response.status_code,
            "success": response.status_code == 200,
        }
        
        if response.status_code == 200:
            data = response.json()
            tables = data.get("tables", [])
            result["tables"] = len(tables)
            result["processing_time_ms"] = data.get("processing_time_ms", 0)
            result["table_details"] = []
            
            for i, table in enumerate(tables):
                rows = table.get("rows", [])
                conf = table.get("confidence", 0)
                result["table_details"].append({
                    "table_num": i + 1,
                    "rows": len(rows),
                    "confidence": round(conf, 2),
                })
        else:
            result["error"] = response.text[:200]
        
        return result
    except Exception as e:
        return {
            "file": file_path.name,
            "status_code": 0,
            "success": False,
            "error": str(e),
        }

def main():
    print("=" * 70)
    print("StatementXL PDF Test Suite")
    print("=" * 70)
    
    # Get all PDF files
    pdf_files = sorted(TEST_DIR.glob("*.pdf"))
    print(f"\nFound {len(pdf_files)} PDF files to test\n")
    
    results = []
    passed = 0
    failed = 0
    
    for pdf_file in pdf_files:
        print(f"Testing: {pdf_file.name}")
        result = test_pdf(pdf_file)
        results.append(result)
        
        if result["success"]:
            passed += 1
            print(f"  ✓ Status: {result['status_code']}")
            print(f"  ✓ Tables: {result['tables']}")
            print(f"  ✓ Time: {result['processing_time_ms']:.0f}ms")
            for td in result.get("table_details", []):
                print(f"    - Table {td['table_num']}: {td['rows']} rows, confidence={td['confidence']}")
        else:
            failed += 1
            print(f"  ✗ Status: {result['status_code']}")
            print(f"  ✗ Error: {result.get('error', 'Unknown')}")
        print()
    
    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total Files: {len(pdf_files)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {passed/len(pdf_files)*100:.1f}%")
    print()
    
    # Save results
    results_file = TEST_DIR / "test_results.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to: {results_file}")
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
