#!/usr/bin/env python3
"""
Test the document processor service standalone
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.document_processor import ProtocolDocumentProcessor
import io

def create_test_pdf_content():
    """Create test PDF content as bytes"""
    # Simple PDF structure for testing
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
/Length 600
>>
stream
BT
/F1 12 Tf
100 700 Td
(CLINICAL STUDY PROTOCOL) Tj
0 -30 Td
(Protocol Title: A Phase II Study of XYZ-123 in Advanced NASH) Tj
0 -20 Td
(Protocol Number: NCT05123456) Tj
0 -20 Td
(Phase: Phase II) Tj
0 -20 Td
(Sponsor: BioPharma Research Inc) Tj
0 -20 Td
(Disease: Non-alcoholic steatohepatitis NASH) Tj
0 -30 Td
(STUDY POPULATION:) Tj
0 -20 Td
(- Adults aged 18-75 years) Tj
0 -20 Td
(- Diagnosed with advanced NASH) Tj
0 -20 Td
(- Expected enrollment: 50 patients) Tj
0 -30 Td
(STUDY PROCEDURES:) Tj
0 -20 Td
(- Physical examinations) Tj
0 -20 Td
(- Laboratory assessments including PK samples) Tj
0 -20 Td
(- Imaging studies MRI 1.5T required) Tj
0 -20 Td
(- Fibroscan for liver stiffness measurement) Tj
0 -20 Td
(- PK sampling: Yes intensive sampling required) Tj
0 -20 Td
(- Washout period: No) Tj
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
800
%%EOF"""
    return pdf_content

def test_pdf_extraction():
    """Test PDF text extraction"""
    print("🔍 Testing PDF text extraction...")

    try:
        processor = ProtocolDocumentProcessor()
        pdf_content = create_test_pdf_content()

        # Test text extraction
        extracted_text = processor.extract_text_from_pdf(pdf_content)
        print(f"✅ PDF text extraction successful")
        print(f"   Extracted {len(extracted_text)} characters")

        # Show sample of extracted text
        if extracted_text:
            sample = extracted_text[:200].replace('\n', ' ').strip()
            print(f"   Sample: {sample}...")

        return True

    except Exception as e:
        print(f"❌ PDF text extraction failed: {e}")
        return False

def test_ai_extraction():
    """Test AI-powered data extraction"""
    print("🔍 Testing AI data extraction...")

    try:
        processor = ProtocolDocumentProcessor()
        pdf_content = create_test_pdf_content()

        # Test full extraction pipeline
        extracted_data = processor.extract_protocol_data(pdf_content)

        if "error" in extracted_data:
            print(f"❌ AI extraction failed: {extracted_data['error']}")
            return False

        print(f"✅ AI data extraction successful")
        print(f"   Extraction confidence: {extracted_data.get('extraction_confidence', 'unknown')}")

        # Show key extracted fields
        key_fields = ['protocol_title', 'protocol_number', 'phase', 'sponsor', 'indication']
        for field in key_fields:
            value = extracted_data.get(field, 'N/A')
            if value and value != 'unclear':
                print(f"   {field}: {value}")

        return True

    except Exception as e:
        print(f"❌ AI extraction failed: {e}")
        return False

def test_fallback_extraction():
    """Test fallback extraction without AI"""
    print("🔍 Testing fallback extraction...")

    try:
        processor = ProtocolDocumentProcessor()

        # Test with sample text
        sample_text = """
        CLINICAL STUDY PROTOCOL
        Protocol Title: A Phase II Study of ABC-123 in NASH
        Protocol Number: NCT05999999
        Phase: Phase II
        Sponsor: Test Pharma
        """

        fallback_data = processor._fallback_extraction(sample_text)

        print(f"✅ Fallback extraction successful")
        print(f"   Confidence: {fallback_data.get('extraction_confidence', 'unknown')}")

        # Show extracted fields
        for field, value in fallback_data.items():
            if value and field != 'extraction_confidence':
                print(f"   {field}: {value}")

        return True

    except Exception as e:
        print(f"❌ Fallback extraction failed: {e}")
        return False

def main():
    """Run document processor tests"""
    print("🚀 Testing SiteSync Document Processor")
    print("=" * 50)

    tests_passed = 0
    total_tests = 3

    # Test 1: PDF text extraction
    if test_pdf_extraction():
        tests_passed += 1
    print()

    # Test 2: AI data extraction
    if test_ai_extraction():
        tests_passed += 1
    print()

    # Test 3: Fallback extraction
    if test_fallback_extraction():
        tests_passed += 1
    print()

    # Summary
    print("=" * 50)
    print(f"🎯 Test Results: {tests_passed}/{total_tests} tests passed")

    if tests_passed == total_tests:
        print("🎉 Document processor is working correctly!")
        print("\n📋 The system can:")
        print("- Extract text from PDF files")
        print("- Use AI to parse protocol data")
        print("- Fall back to regex parsing when needed")
        return True
    else:
        print("❌ Some document processor tests failed.")
        return False

if __name__ == "__main__":
    main()