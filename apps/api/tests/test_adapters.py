import pytest

from finance.ingestion import adapters
from finance.ingestion.adapters import UnsupportedStatement, detect_adapter, pdf_pages_text
from tests.malformed_pdfs import MALFORMED_PDFS, VALID_PAGE_PDF

BBVA_PAGE = (
    "EXTRACTO DE JULIO 2026\n"
    "IBAN ES91 0182 0418 4502 0005 1332\n"
    "F.Oper. F.Valor Concepto Importe Saldo\n"
)
CAIXA_PAGE = (
    "Titular X IBAN ES91 2100 0418 4502 0005 1332\n"
    "Periodo 01/06/2026 - 05/08/2026\n"
    "Concepto Fecha Importe Saldo\n"
)


def test_detects_bbva(monkeypatch):
    monkeypatch.setattr(adapters, "pdf_pages_text", lambda _pdf, x_tolerance=3: [BBVA_PAGE])
    assert detect_adapter(b"%PDF").bank == "bbva"


def test_detects_caixabank(monkeypatch):
    monkeypatch.setattr(adapters, "pdf_pages_text", lambda _pdf, x_tolerance=3: [CAIXA_PAGE])
    assert detect_adapter(b"%PDF").bank == "caixabank"


def test_unknown_statement_raises(monkeypatch):
    monkeypatch.setattr(adapters, "pdf_pages_text", lambda _pdf, x_tolerance=3: ["Dear customer"])
    with pytest.raises(UnsupportedStatement, match="bbva, caixabank"):
        detect_adapter(b"%PDF")


def test_well_formed_page_reads():
    # Control for the builder: the MediaBox cases below fail because of the MediaBox alone.
    assert pdf_pages_text(VALID_PAGE_PDF) == [""]


@pytest.mark.parametrize("shape", sorted(MALFORMED_PDFS))
def test_unreadable_file_raises_unsupported_statement(shape):
    with pytest.raises(UnsupportedStatement, match="could not be read as a PDF"):
        pdf_pages_text(MALFORMED_PDFS[shape])


@pytest.mark.parametrize("shape", sorted(MALFORMED_PDFS))
def test_unreadable_file_reaches_detect_adapter_as_unsupported(shape):
    with pytest.raises(UnsupportedStatement):
        detect_adapter(MALFORMED_PDFS[shape])
