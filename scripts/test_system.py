#!/usr/bin/env python3
"""
Test script to verify SiteSync system functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import json
from pathlib import Path

# API base URL
BASE_URL = "http://localhost:8000"

def test_health_endpoint():
    """Test basic health endpoint"""
    print("🔍 Testing health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("✅ Health endpoint working")
            return True
        else:
            print(f"❌ Health endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health endpoint error: {e}")
        return False

def test_feasibility_template():
    """Test feasibility form template endpoint"""
    print("🔍 Testing feasibility template endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/feasibility/form-templates")
        if response.status_code == 200:
            data = response.json()
            print("✅ Form template endpoint working")
            print(f"   Templates available: {len(data.get('templates', {}))}")
            return True
        else:
            print(f"❌ Template endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Template endpoint error: {e}")
        return False

def test_sites_endpoint():
    """Test sites listing"""
    print("🔍 Testing sites endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/sites/")
        if response.status_code == 200:
            sites = response.json()
            print(f"✅ Sites endpoint working - found {len(sites)} sites")
            if sites:
                site = sites[0]
                print(f"   Sample site: {site.get('name')} (ID: {site.get('id')})")
                return site.get('id')
            return True
        else:
            print(f"❌ Sites endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Sites endpoint error: {e}")
        return False

def test_protocols_endpoint():
    """Test protocols listing"""
    print("🔍 Testing protocols endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/protocols")
        if response.status_code == 200:
            protocols = response.json()
            print(f"✅ Protocols endpoint working - found {len(protocols)} protocols")
            if protocols:
                protocol = protocols[0]
                print(f"   Sample protocol: {protocol.get('name')} (ID: {protocol.get('id')})")
                return protocol.get('id')
            return True
        else:
            print(f"❌ Protocols endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Protocols endpoint error: {e}")
        return False

def test_scoring_endpoint(site_id, protocol_id):
    """Test scoring endpoint with demo data"""
    if not site_id or not protocol_id:
        print("⏭️  Skipping scoring test - no demo data available")
        return True

    print("🔍 Testing scoring endpoint...")
    try:
        response = requests.post(f"{BASE_URL}/protocols/{protocol_id}/score?site_id={site_id}")
        if response.status_code == 200:
            score_data = response.json()
            print("✅ Scoring endpoint working")
            print(f"   Score: {score_data.get('score', 'N/A')}/{score_data.get('total_weight', 'N/A')}")
            print(f"   Confidence: {score_data.get('confidence', 'N/A')}%")
            print(f"   Matches: {len(score_data.get('matches', []))}")
            print(f"   Misses: {len(score_data.get('misses', []))}")
            return True
        else:
            print(f"❌ Scoring endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Scoring endpoint error: {e}")
        return False

def create_test_pdf():
    """Create a simple test PDF for upload testing"""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        import io

        # Create a simple test PDF in memory
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)

        # Add some test content that looks like a protocol
        p.drawString(100, 750, "CLINICAL STUDY PROTOCOL")
        p.drawString(100, 720, "Protocol Title: A Phase II Study of ABC-123 in Advanced NASH")
        p.drawString(100, 690, "Protocol Number: NCT05999999")
        p.drawString(100, 660, "Phase: Phase II")
        p.drawString(100, 630, "Sponsor: Test Pharma Inc")
        p.drawString(100, 600, "")
        p.drawString(100, 570, "STUDY POPULATION:")
        p.drawString(120, 540, "- Adults aged 18-75 years")
        p.drawString(120, 510, "- Diagnosed with NASH")
        p.drawString(120, 480, "- Adequate liver function")
        p.drawString(100, 450, "")
        p.drawString(100, 420, "STUDY PROCEDURES:")
        p.drawString(120, 390, "- Physical examinations")
        p.drawString(120, 360, "- Laboratory assessments")
        p.drawString(120, 330, "- Imaging studies (MRI required)")
        p.drawString(120, 300, "- PK sampling: Yes")
        p.drawString(100, 270, "")
        p.drawString(100, 240, "TARGET ENROLLMENT: 50 patients")

        p.save()
        buffer.seek(0)
        return buffer.getvalue()

    except ImportError:
        # If reportlab not available, create a simple text-based PDF
        # This is a very basic PDF structure
        pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 200
>>
stream
BT
/F1 12 Tf
100 700 Td
(CLINICAL STUDY PROTOCOL) Tj
0 -20 Td
(Protocol Title: Phase II Study of ABC-123) Tj
0 -20 Td
(Protocol Number: NCT05999999) Tj
0 -20 Td
(Phase: Phase II) Tj
0 -20 Td
(Expected Enrollment: 50) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000010 00000 n
0000000053 00000 n
0000000110 00000 n
0000000200 00000 n
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
450
%%EOF"""
        return pdf_content

def test_pdf_upload(site_id):
    """Test PDF upload and processing"""
    if not site_id:
        print("⏭️  Skipping PDF upload test - no site available")
        return True

    print("🔍 Testing PDF upload and processing...")
    try:
        # Create test PDF
        pdf_content = create_test_pdf()

        # Upload the PDF
        files = {'protocol_file': ('test_protocol.pdf', pdf_content, 'application/pdf')}
        data = {'site_id': site_id}

        response = requests.post(f"{BASE_URL}/feasibility/process-protocol", files=files, params=data)

        if response.status_code == 200:
            result = response.json()
            print("✅ PDF processing working")
            if result.get('success'):
                completion_stats = result.get('data', {}).get('completion_stats', {})
                print(f"   Auto-filled: {completion_stats.get('auto_filled', 0)} questions")
                print(f"   Completion: {completion_stats.get('completion_percentage', 0)}%")
                print(f"   Time saved: {completion_stats.get('estimated_time_saved_minutes', 0)} minutes")
            return True
        else:
            print(f"❌ PDF processing failed: {response.status_code}")
            if response.text:
                print(f"   Error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ PDF processing error: {e}")
        return False

def main():
    """Run all system tests"""
    print("🚀 Starting SiteSync System Tests")
    print("=" * 50)

    tests_passed = 0
    total_tests = 0

    # Test 1: Health endpoint
    total_tests += 1
    if test_health_endpoint():
        tests_passed += 1
    print()

    # Test 2: Feasibility template
    total_tests += 1
    if test_feasibility_template():
        tests_passed += 1
    print()

    # Test 3: Sites endpoint
    total_tests += 1
    site_id = test_sites_endpoint()
    if site_id:
        tests_passed += 1
    print()

    # Test 4: Protocols endpoint
    total_tests += 1
    protocol_id = test_protocols_endpoint()
    if protocol_id:
        tests_passed += 1
    print()

    # Test 5: Scoring endpoint
    total_tests += 1
    if test_scoring_endpoint(site_id, protocol_id):
        tests_passed += 1
    print()

    # Test 6: PDF upload and processing
    total_tests += 1
    if test_pdf_upload(site_id):
        tests_passed += 1
    print()

    # Summary
    print("=" * 50)
    print(f"🎯 Test Results: {tests_passed}/{total_tests} tests passed")

    if tests_passed == total_tests:
        print("🎉 All tests passed! SiteSync system is working correctly.")
        print("\n📋 Next steps:")
        print("1. Visit http://localhost:8000/docs for API documentation")
        print("2. Try the feasibility form template endpoint")
        print("3. Upload a real protocol PDF to test AI extraction")
        print("4. Build the frontend interface")
        return True
    else:
        print("❌ Some tests failed. Check the Docker containers and database.")
        print("\n🔧 Troubleshooting:")
        print("1. Make sure Docker containers are running: docker ps")
        print("2. Check API logs: docker logs sitesync_api")
        print("3. Verify database connection: docker logs sitesync_db")
        return False

if __name__ == "__main__":
    main()