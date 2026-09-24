"""Routes for uploading a statement and listing past imports."""

from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile
from pydantic import BaseModel

from finance.api.deps import Db
from finance.categorization.store import run_categorization_logged
from finance.ingestion.adapters import UnsupportedStatement
from finance.ingestion.importer import import_statement
from finance.models import ImportSummary

router = APIRouter(prefix="/imports", tags=["imports"])


class ImportRecord(BaseModel):
    id: UUID
    account_id: UUID
    account_name: str
    filename: str
    period_start: date | None
    period_end: date | None
    rows_total: int
    rows_new: int
    rows_duplicate: int
    imported_at: datetime


@router.post("", status_code=201)
def create_import(file: UploadFile, conn: Db, background: BackgroundTasks) -> ImportSummary:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=415, detail="Only PDF statements are supported")
    try:
        summary = import_statement(file.file.read(), file.filename or "statement.pdf", conn)
    except (UnsupportedStatement, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    background.add_task(run_categorization_logged)
    return summary


@router.get("")
def list_imports(conn: Db) -> list[ImportRecord]:
    rows = conn.execute(
        "select i.*, a.name as account_name from imports i join accounts a on a.id = i.account_id"
        " order by i.imported_at desc limit 100"
    ).fetchall()
    return [ImportRecord.model_validate(row) for row in rows]
