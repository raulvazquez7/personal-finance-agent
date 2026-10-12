"""The first check on `run_sql`: one read-only SELECT over the agent's views.

The database is the real guarantee: every query runs as `agent_reader` in a read-only transaction
(slice 4 spec, section 4.2). This check fails early with a reason and a hint the model can act on.
It walks the whole syntax tree, so a DELETE hidden in a CTE is caught, and it never matches
keywords in the raw text, so a search for '%drop%' still works.
"""

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

VIEWS = frozenset({"transactions", "subscriptions"})

_WRITES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Merge,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.Command,
    exp.Copy,
    exp.Set,
    exp.Lock,
    exp.TruncateTable,
    exp.Into,
)
# set_config is the only way to change role from a SELECT; the rest read files, sleep or reach
# other servers.
_DENIED_FUNCTION_PREFIXES = ("set_config", "pg_sleep", "dblink", "pg_read", "lo_")


class RejectedQuery(Exception):
    def __init__(self, reason: str, hint: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.hint = hint


def check_query(sql: str) -> str:
    """Return the query without trailing semicolons, or raise RejectedQuery."""
    cleaned = sql.strip().rstrip("; \t\r\n")
    try:
        statements = [s for s in sqlglot.parse(cleaned, read="postgres") if s is not None]
    except SqlglotError as error:
        first_line = str(error).splitlines()[0]
        raise RejectedQuery(
            f"the query does not parse: {first_line}", "Write one PostgreSQL SELECT."
        ) from error
    if len(statements) != 1:
        raise RejectedQuery(
            f"found {len(statements)} statements", "Send exactly one SELECT per call."
        )
    root = statements[0]
    if not isinstance(root, exp.Query):
        raise RejectedQuery(f"{root.key.upper()} is not a SELECT", "Only read, with one SELECT.")
    for node in root.walk():
        if isinstance(node, _WRITES):
            raise RejectedQuery(f"{node.key.upper()} is not allowed", "Only read, with one SELECT.")
    ctes = {cte.alias_or_name.lower() for cte in root.find_all(exp.CTE)}
    for table in root.find_all(exp.Table):
        if not isinstance(table.this, exp.Identifier):
            continue  # a table function such as generate_series: its name is checked below
        if table.db or table.name.lower() not in VIEWS | ctes:
            raise RejectedQuery(
                f"unknown table {table.sql(dialect='postgres')}",
                "Read only the views transactions and subscriptions, without a schema.",
            )
    for function in root.find_all(exp.Func):
        name = function.name if isinstance(function, exp.Anonymous) else function.sql_name()
        if name.lower().startswith(_DENIED_FUNCTION_PREFIXES):
            raise RejectedQuery(
                f"function {name.lower()} is not allowed", "Use ordinary SQL functions only."
            )
    return cleaned
