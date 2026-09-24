from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from finance.api import accounts, categorize, imports, transactions
from finance.settings import get_settings

app = FastAPI(title="personal-finance-agent API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(accounts.router)
app.include_router(categorize.router)
app.include_router(imports.router)
app.include_router(transactions.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
