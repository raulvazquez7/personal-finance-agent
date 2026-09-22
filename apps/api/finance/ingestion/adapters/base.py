"""Adapter protocol and the one PDF helper every adapter shares."""

import io
from typing import Protocol

import pdfplumber

from finance.models import ParsedStatement


class BankAdapter(Protocol):
    bank: str

    def sniff(self, first_page_text: str) -> bool: ...

    def parse(self, pdf_bytes: bytes) -> ParsedStatement: ...


def pdf_pages_text(pdf_bytes: bytes, x_tolerance: float = 3) -> list[str]:
    """Text of every page. Lower x_tolerance inserts spaces between tightly packed glyphs."""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return [page.extract_text(x_tolerance=x_tolerance) or "" for page in pdf.pages]
