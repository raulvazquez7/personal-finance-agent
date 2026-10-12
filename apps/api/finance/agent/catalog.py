"""What the database tells the agent: column types, the app-defined values (taxonomy, accounts
with their statement coverage) and the latest imported day. Also proves at startup that the
semantic layer matches the views and that every metric and example compiles."""

from dataclasses import dataclass
from datetime import date

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from finance.agent.semantic_layer import SemanticLayer, SemanticLayerError, check_layer
from finance.agent.sql_guard import RejectedQuery, check_query
from finance.agent.sql_runner import explain


@dataclass(frozen=True)
class Category:
    slug: str
    level1: str
    tx_type: str
    what: str
    not_for: str | None


@dataclass(frozen=True)
class Account:
    name: str
    bank: str
    data_from: date | None
    data_to: date | None


@dataclass(frozen=True)
class Catalog:
    categories: list[Category]
    accounts: list[Account]
    latest_day: date | None


async def read_columns(conn: AsyncConnection) -> dict[str, dict[str, str]]:
    rows = await (
        await conn.execute(
            "select table_name, column_name, data_type from information_schema.columns"
            " where table_schema = 'agent' order by table_name, ordinal_position"
        )
    ).fetchall()
    columns: dict[str, dict[str, str]] = {}
    for row in rows:
        columns.setdefault(row["table_name"], {})[row["column_name"]] = row["data_type"]
    return columns


async def read_catalog(pool: AsyncConnectionPool) -> Catalog:
    async with pool.connection() as conn:
        categories = await (
            await conn.execute(
                "select slug, level1, tx_type, what, not_for from categories order by position"
            )
        ).fetchall()
        accounts = await (
            await conn.execute(
                "select a.name, a.bank::text as bank, min(i.period_start) as data_from,"
                " max(i.period_end) as data_to"
                " from accounts a left join imports i on i.account_id = a.id"
                " group by a.id, a.name, a.bank order by a.name"
            )
        ).fetchall()
        latest = await (
            await conn.execute("select max(booked_at) as day from transactions")
        ).fetchone()
    return Catalog(
        categories=[Category(**row) for row in categories],
        accounts=[Account(**row) for row in accounts],
        latest_day=latest["day"],
    )


async def validate_layer(
    pool: AsyncConnectionPool, layer: SemanticLayer
) -> dict[str, dict[str, str]]:
    """Return the view columns and their types, or raise SemanticLayerError."""
    async with pool.connection() as conn:
        columns = await read_columns(conn)
    check_layer(layer, columns)
    statements = [(f"metric {m.name}", f"SELECT {m.sql} FROM {m.model}") for m in layer.metrics]
    statements += [
        (f"example {n} step {s}", sql)
        for n, example in enumerate(layer.examples, start=1)
        for s, sql in enumerate(example.sql, start=1)
    ]
    problems = []
    for label, sql in statements:
        try:
            check_query(sql)
        except RejectedQuery as rejected:
            problems.append(f"{label}: {rejected.reason}")
            continue
        if error := await explain(pool, sql):
            problems.append(f"{label}: {error}")
    if problems:
        raise SemanticLayerError("semantic layer SQL does not compile:\n- " + "\n- ".join(problems))
    return columns
