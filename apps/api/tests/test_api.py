from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from finance.api import categorize, imports
from finance.api.deps import db
from finance.api.main import app
from finance.categorization import store
from finance.ingestion import adapters
from finance.models import ImportSummary
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


def test_import_succeeds_and_reports_counts_even_when_categorization_fails(monkeypatch):
    summary = ImportSummary(
        import_id=uuid4(),
        account_id=uuid4(),
        bank="bbva",
        iban_last4="0001",
        filename="statement.pdf",
        rows_total=2,
        rows_new=2,
        rows_duplicate=0,
    )
    attempts = []

    def _fail(include_all=False):
        attempts.append(include_all)
        raise RuntimeError("jev is down")

    monkeypatch.setattr(imports, "import_statement", lambda *args: summary)
    monkeypatch.setattr(store, "run_categorization", _fail)
    upload = ("statement.pdf", b"%PDF", "application/pdf")
    response = client.post("/imports", files={"file": upload})
    assert response.status_code == 201 and response.json()["rows_new"] == 2
    assert attempts == [False]  # the background run happened after the response


def test_categorize_run_queues_a_background_run(monkeypatch):
    calls = []
    monkeypatch.setattr(categorize, "run_categorization_logged", calls.append)
    response = client.post("/categorize/run", params={"all": "true"})
    assert response.status_code == 202 and response.json() == {"status": "queued"}
    assert calls == [True]
