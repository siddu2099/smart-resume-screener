"""Deterministic PDF resume text extraction service using PyMuPDF (fitz)."""

import io
import re
from pathlib import Path
from typing import BinaryIO, Union

import fitz  # PyMuPDF

MAX_PDF_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit
PDF_SIGNATURE = b"%PDF-"


class ResumeExtractionError(Exception):
    """Custom exception raised when resume PDF extraction or validation fails."""

    pass


def normalize_resume_text(text: str) -> str:
    """Normalize extracted resume text while preserving technical terms, symbols, and layout structure.

    Args:
        text: Raw extracted text string.

    Returns:
        Normalized text string with standardized newlines and clean spacing.
    """
    if not text:
        return ""

    # Normalize CRLF and CR to LF
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove trailing whitespace from each line while keeping leading indentation
    lines = [line.rstrip(" \t") for line in text.split("\n")]
    text = "\n".join(lines)

    # Collapse 3 or more consecutive newlines down to 2 to preserve paragraph spacing
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def extract_text_from_pdf(
    pdf_input: Union[str, Path, bytes, BinaryIO]
) -> str:
    """Extract and normalize plain text from a PDF document.

    Args:
        pdf_input: PDF file path (str or Path), raw bytes, or a binary file-like object.

    Returns:
        Normalized plain text extracted from the PDF pages in sequential order.

    Raises:
        ResumeExtractionError: If file is oversized, corrupted, empty, non-PDF, or unreadable.
    """
    pdf_bytes: bytes

    try:
        if isinstance(pdf_input, (str, Path)):
            path = Path(pdf_input)
            if not path.is_file():
                raise ResumeExtractionError(f"File not found: {path}")
            file_size = path.stat().st_size
            if file_size > MAX_PDF_SIZE_BYTES:
                raise ResumeExtractionError(
                    f"File size ({file_size} bytes) exceeds maximum limit of {MAX_PDF_SIZE_BYTES} bytes (10 MB)"
                )
            pdf_bytes = path.read_bytes()

        elif isinstance(pdf_input, bytes):
            pdf_bytes = pdf_input
            if len(pdf_bytes) > MAX_PDF_SIZE_BYTES:
                raise ResumeExtractionError(
                    f"File size ({len(pdf_bytes)} bytes) exceeds maximum limit of {MAX_PDF_SIZE_BYTES} bytes (10 MB)"
                )

        elif hasattr(pdf_input, "read"):
            content = pdf_input.read()
            pdf_bytes = content if isinstance(content, bytes) else content.encode("utf-8")
            if len(pdf_bytes) > MAX_PDF_SIZE_BYTES:
                raise ResumeExtractionError(
                    f"File size ({len(pdf_bytes)} bytes) exceeds maximum limit of {MAX_PDF_SIZE_BYTES} bytes (10 MB)"
                )

        else:
            raise ResumeExtractionError("Unsupported input type for PDF extraction")

    except ResumeExtractionError:
        raise
    except Exception as err:
        raise ResumeExtractionError(f"Failed to read PDF input: {err}") from err

    # Validate PDF signature
    if len(pdf_bytes) < 4 or not pdf_bytes.startswith(PDF_SIGNATURE):
        raise ResumeExtractionError(
            "Invalid file format: File missing valid PDF header signature (%PDF-)"
        )

    # Open PDF using PyMuPDF
    doc = None
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as err:
        raise ResumeExtractionError(f"Failed to parse corrupt or invalid PDF document: {err}") from err

    try:
        if doc.page_count == 0:
            raise ResumeExtractionError("PDF document contains no pages")

        extracted_pages: list[str] = []
        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            page_text = page.get_text("text")
            if page_text:
                extracted_pages.append(page_text)

        raw_combined_text = "\n\n".join(extracted_pages)
        if not raw_combined_text.strip():
            raise ResumeExtractionError("PDF contains no extractable text")

        normalized_text = normalize_resume_text(raw_combined_text)
        if not normalized_text:
            raise ResumeExtractionError("PDF contains no extractable text after normalization")

        return normalized_text

    finally:
        if doc is not None:
            doc.close()
