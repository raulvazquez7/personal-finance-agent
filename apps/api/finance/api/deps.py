"""Request-scoped dependencies shared by the routers."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from psycopg import Connection

from finance.db import connection
from finance.settings import get_settings

_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def db() -> Iterator[Connection]:
    with connection() as conn:
        yield conn


Db = Annotated[Connection, Depends(db, scope="function")]


def same_origin(request: Request) -> None:
    """CORS limits who can read a response, not who can send a request: a page on another site
    could still POST here (a body-less POST needs no preflight). Browsers name the page in
    Origin; the CLI, curl and tests send none and pass."""
    origin = request.headers.get("origin")
    if request.method in _UNSAFE_METHODS and origin is not None:
        if origin not in get_settings().cors_origins:
            raise HTTPException(status_code=403, detail=f"Origin {origin} is not allowed")
