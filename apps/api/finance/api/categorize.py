"""Re-run the categorization cascade in the background."""

from fastapi import APIRouter, BackgroundTasks

from finance.categorization.store import run_categorization_logged

router = APIRouter(prefix="/categorize", tags=["categorize"])


@router.post("/run", status_code=202)
def run(background: BackgroundTasks, all: bool = False) -> dict[str, str]:
    background.add_task(run_categorization_logged, all)
    return {"status": "queued"}
