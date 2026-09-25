from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from finance.api import categorize, imports
from finance.api.deps import db
from finance.api.main import app
from finance.categorization import store
from finance.ingestion import adapters
from finance.models import ImportSummary
from finance.settings import get_settings
from tests.malformed_pdfs import MALFORMED_PDFS

app.dependency_overrides[db] = lambda: None  # routes under test never reach the database
client = TestClient(app)


@pytest.fixture(autouse=True)
def scheduled(monkeypatch):
    """Records the background runs the routes schedule instead of starting real, paid ones."""
    runs = []

    def _record(include_all=False):
        runs.append(include_all)

    monkeypatch.setattr(imports, "run_categorization_logged", _record)
    monkeypatch.setattr(categorize, "run_categorization_logged", _record)
    return runs


def test_import_rejects_non_pdf_uploads(scheduled):
    response = client.post("/imports", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert response.status_code == 415 and scheduled == []


def test_import_rejects_pdf_without_pages(monkeypatch, scheduled):
    monkeypatch.setattr(adapters, "pdf_pages_text", lambda _pdf, x_tolerance=3: [])
    response = client.post("/imports", files={"file": ("empty.pdf", b"%PDF", "application/pdf")})
    assert response.status_code == 422 and scheduled == []


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
    assert {
        "Account",
        "ImportRecord",
        "ImportSummary",
        "RunQueued",
        "Transaction",
        "TransactionPage",
    } <= set(schemas)


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
    # The real background runner this time, with the paid run inside it failing.
    monkeypatch.setattr(imports, "run_categorization_logged", store.run_categorization_logged)
    monkeypatch.setattr(store, "run_categorization", _fail)
    upload = ("statement.pdf", b"%PDF", "application/pdf")
    response = client.post("/imports", files={"file": upload})
    assert response.status_code == 201 and response.json()["rows_new"] == 2
    assert attempts == [False]  # the background run happened after the response


def test_categorize_run_queues_a_background_run(scheduled):
    response = client.post("/categorize/run", params={"all": "true"})
    assert response.status_code == 202 and response.json() == {"status": "queued"}
    assert scheduled == [True]


def test_categorize_run_defaults_to_pending_rows_only(scheduled):
    assert client.post("/categorize/run").status_code == 202
    assert scheduled == [False]


PDF = ("statement.pdf", b"%PDF", "application/pdf")


def _summary():
    return ImportSummary(
        import_id=uuid4(),
        account_id=uuid4(),
        bank="bbva",
        iban_last4="0001",
        filename="statement.pdf",
        rows_total=1,
        rows_new=1,
        rows_duplicate=0,
    )


def test_a_page_on_another_site_can_neither_import_nor_start_a_run(monkeypatch, scheduled):
    imported = []
    monkeypatch.setattr(imports, "import_statement", lambda *args: imported.append(args))
    foreign = {"Origin": "https://attacker.example"}
    run = client.post("/categorize/run", params={"all": "true"}, headers=foreign)
    upload = client.post("/imports", files={"file": PDF}, headers=foreign)
    assert (run.status_code, upload.status_code) == (403, 403)
    assert scheduled == [] and imported == []


def test_the_web_origin_and_requests_without_an_origin_are_accepted(monkeypatch, scheduled):
    monkeypatch.setattr(imports, "import_statement", lambda *args: _summary())
    web = {"Origin": get_settings().cors_origins[0]}
    assert client.post("/categorize/run", headers=web).status_code == 202
    assert client.post("/imports", files={"file": PDF}, headers=web).status_code == 201
    assert client.post("/categorize/run").status_code == 202  # the CLI, curl and tests
    assert scheduled == [False, False, False]


def test_label_rejects_a_missing_category():
    response = client.post(
        "/transactions/00000000-0000-0000-0000-000000000001/label", json={"is_subscription": True}
    )
    assert response.status_code == 422


def test_openapi_exposes_review_schemas():
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    assert {"ReviewItem", "ReviewCount", "CategoryOut", "MerchantOut", "ConfirmMerchant"} <= set(
        schemas
    )
