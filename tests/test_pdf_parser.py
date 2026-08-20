"""Unit tests for PDF text extraction service."""

import io
from pathlib import Path

import fitz  # PyMuPDF
import pytest

from app.services.pdf_parser import (
    MAX_PDF_SIZE_BYTES,
    ResumeExtractionError,
    extract_text_from_pdf,
    normalize_resume_text,
)


def create_synthetic_pdf(pages_text: list[str]) -> bytes:
    """Helper to generate a PDF in memory with specified page text contents."""
    doc = fitz.open()
    for text in pages_text:
        page = doc.new_page()
        if text.strip():
            page.insert_text((50, 50), text, fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_extract_valid_single_page():
    """Test extracting text from a valid single-page PDF."""
    content = "John Doe\nSoftware Engineer\nSkills: Python, FastAPI"
    pdf_bytes = create_synthetic_pdf([content])

    result = extract_text_from_pdf(pdf_bytes)
    assert "John Doe" in result
    assert "Software Engineer" in result
    assert "Skills: Python, FastAPI" in result


def test_extract_valid_multi_page():
    """Test extracting text from a multi-page PDF preserving page sequence."""
    pages = [
        "Page 1: Summary\nExperienced Developer",
        "Page 2: Skills\nPython, C++, Docker",
        "Page 3: Education\nB.Tech Computer Science",
    ]
    pdf_bytes = create_synthetic_pdf(pages)

    result = extract_text_from_pdf(pdf_bytes)

    # Verify all pages are present and sequential order is maintained
    pos1 = result.find("Page 1: Summary")
    pos2 = result.find("Page 2: Skills")
    pos3 = result.find("Page 3: Education")

    assert pos1 != -1 and pos2 != -1 and pos3 != -1
    assert pos1 < pos2 < pos3


def test_text_normalization_preserve_technical_terms():
    """Test that text normalization preserves technical terms, emails, phone numbers, and casing."""
    raw_text = (
        "Candidate Profile:\r\n"
        "Skills: C++, C#, .NET, Node.js, React.js, AWS, CI/CD\r\n\r\n\r\n\r\n"
        "Contact: dev@example.com | +1-555-0199\r\n"
        "  Trailing spaces line   \r\n"
    )
    normalized = normalize_resume_text(raw_text)

    # Check technical terms intact
    assert "C++" in normalized
    assert "C#" in normalized
    assert ".NET" in normalized
    assert "Node.js" in normalized
    assert "React.js" in normalized
    assert "AWS" in normalized
    assert "CI/CD" in normalized
    assert "dev@example.com" in normalized
    assert "+1-555-0199" in normalized

    # Check newline collapsing (4 newlines collapsed to 2)
    assert "\n\n\n" not in normalized


def test_input_type_flexibility(tmp_path: Path):
    """Test passing str path, Path object, bytes, and BytesIO to extract_text_from_pdf."""
    pdf_bytes = create_synthetic_pdf(["Flexible Input Test"])

    # 1. Bytes input
    res_bytes = extract_text_from_pdf(pdf_bytes)
    assert "Flexible Input Test" in res_bytes

    # 2. BytesIO input
    res_stream = extract_text_from_pdf(io.BytesIO(pdf_bytes))
    assert "Flexible Input Test" in res_stream

    # 3. Path object input
    temp_file = tmp_path / "test_resume.pdf"
    temp_file.write_bytes(pdf_bytes)
    res_path = extract_text_from_pdf(temp_file)
    assert "Flexible Input Test" in res_path

    # 4. Str path input
    res_str_path = extract_text_from_pdf(str(temp_file))
    assert "Flexible Input Test" in res_str_path


def test_empty_pdf_raises_error():
    """Test that a PDF containing no text raises ResumeExtractionError."""
    empty_pdf_bytes = create_synthetic_pdf(["   "])

    with pytest.raises(ResumeExtractionError, match="PDF contains no extractable text"):
        extract_text_from_pdf(empty_pdf_bytes)


def test_corrupt_pdf_raises_error():
    """Test that a corrupted PDF raises ResumeExtractionError."""
    corrupt_pdf_bytes = b"%PDF-1.4\n%Malformed data buffer\n" + b"X" * 200

    with pytest.raises(ResumeExtractionError):
        extract_text_from_pdf(corrupt_pdf_bytes)


def test_non_pdf_input_raises_error():
    """Test that non-PDF data (missing %PDF- header) raises ResumeExtractionError."""
    plain_text_bytes = b"Hello, this is just plain text content without PDF header."

    with pytest.raises(ResumeExtractionError, match="missing valid PDF header signature"):
        extract_text_from_pdf(plain_text_bytes)


def test_oversized_pdf_raises_error():
    """Test that input exceeding the maximum size limit raises ResumeExtractionError."""
    large_dummy_bytes = b"%PDF-1.4\n" + b"A" * (MAX_PDF_SIZE_BYTES + 10)

    with pytest.raises(ResumeExtractionError, match="exceeds maximum limit"):
        extract_text_from_pdf(large_dummy_bytes)


def test_nonexistent_file_path_raises_error():
    """Test that a non-existent file path raises ResumeExtractionError."""
    with pytest.raises(ResumeExtractionError, match="File not found"):
        extract_text_from_pdf(Path("/nonexistent/file/path/resume.pdf"))
