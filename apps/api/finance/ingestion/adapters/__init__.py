"""Registry of bank statement adapters and detection by first-page text."""

from finance.ingestion.adapters.base import BankAdapter, pdf_pages_text
from finance.ingestion.adapters.bbva_pdf import BbvaPdfAdapter
from finance.ingestion.adapters.caixabank_pdf import CaixaBankPdfAdapter

ADAPTERS: list[BankAdapter] = [BbvaPdfAdapter(), CaixaBankPdfAdapter()]


class UnsupportedStatement(ValueError):
    """The PDF is not a statement from a supported bank."""


def detect_adapter(pdf_bytes: bytes) -> BankAdapter:
    pages = pdf_pages_text(pdf_bytes, x_tolerance=1)
    if not pages:
        raise UnsupportedStatement("The PDF has no pages to read")
    first_page = pages[0]
    for adapter in ADAPTERS:
        if adapter.sniff(first_page):
            return adapter
    supported = ", ".join(adapter.bank for adapter in ADAPTERS)
    raise UnsupportedStatement(
        f"No adapter recognises this statement; supported banks: {supported}"
    )
