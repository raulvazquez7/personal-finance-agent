"""Re-run the categorization cascade in the background."""

from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Query
from pydantic import BaseModel

from finance.categorization.store import run_categorization_logged

router = APIRouter(prefix="/categorize", tags=["categorize"])


class RunQueued(BaseModel):
    status: Literal["queued"]


@router.post("/run", status_code=202)
def run(
    background: BackgroundTasks, include_all: Annotated[bool, Query(alias="all")] = False
) -> RunQueued:
    background.add_task(run_categorization_logged, include_all)
    return RunQueued(status="queued")
