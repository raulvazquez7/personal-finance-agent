"""Adapter protocol and the one PDF helper every adapter shares."""

import io
from typing import Protocol

import pdfplumber
from pdfplumber.utils.exceptions import PdfminerException

from finance.models import ParsedStatement


class UnsupportedStatement(ValueError):
    """The PDF is not a statement from a supported bank, or cannot be read at all."""


class BankAdapter(Protocol):
    bank: str

    def sniff(self, first_page_text: str) -> bool: ...

    def parse(self, pdf_bytes: bytes) -> ParsedStatement: ...


def pdf_pages_text(pdf_bytes: bytes, x_tolerance: float = 3) -> list[str]:
    """Text of every page. Lower x_tolerance inserts spaces between tightly packed glyphs."""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            return [page.extract_text(x_tolerance=x_tolerance) or "" for page in pdf.pages]
    except PdfminerException as error:
        raise UnsupportedStatement(
            "The file could not be read as a PDF; it may be empty, corrupt or truncated"
        ) from error
