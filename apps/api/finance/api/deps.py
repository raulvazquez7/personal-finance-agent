"""Request-scoped dependencies shared by the routers."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from psycopg import Connection

from finance.db import connection


def db() -> Iterator[Connection]:
    with connection() as conn:
        yield conn


Db = Annotated[Connection, Depends(db)]
