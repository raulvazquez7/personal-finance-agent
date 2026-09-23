import pytest
from fastapi.testclient import TestClient

from finance.api.deps import db
from finance.api.main import app
from finance.ingestion import adapters
from tests.malformed_pdfs import MALFORMED_PDFS

app.dependency_overrides[db] = lambda: None  # routes under test never reach the database
client = TestClient(app)


def test_import_rejects_non_pdf_uploads():
    response = client.post("/imports", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert response.status_code == 415


def test_import_rejects_pdf_without_pages(monkeypatch):
    monkeypatch.setattr(adapters, "pdf_pages_text", lambda _pdf, x_tolerance=3: [])
    response = client.post("/imports", files={"file": ("empty.pdf", b"%PDF", "application/pdf")})
    assert response.status_code == 422


@pytest.mark.parametrize("shape", sorted(MALFORMED_PDFS))
def test_import_rejects_unreadable_pdf(shape):
    upload = ("broken.pdf", MALFORMED_PDFS[shape], "application/pdf")
    response = client.post("/imports", files={"file": upload})
    assert response.status_code == 422


def test_transactions_rejects_malformed_month():
    response = client.get("/transactions", params={"month": "2026-7"})
    assert response.status_code == 422


def test_openapi_exposes_web_schemas():
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    assert {"Account", "ImportRecord", "ImportSummary", "Transaction"} <= set(schemas)
