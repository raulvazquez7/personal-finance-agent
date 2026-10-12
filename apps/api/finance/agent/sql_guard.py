"""The first check on `run_sql`: one read-only SELECT over the agent's views.

The database is the real guarantee: every query runs as `agent_reader` in a read-only transaction
(slice 4 spec, section 4.2). This check fails early with a reason and a hint the model can act on.
It walks the whole syntax tree, so a DELETE hidden in a CTE is caught, and it never matches
keywords in the raw text, so a search for '%drop%' still works.

A session can always reset its own role with set_config, also from SQL that a built-in such as
query_to_xml runs from a string. So this check is the barrier for functions: a function sqlglot
does not recognise runs only without a schema and when it is allowlisted.
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
# set_config changes the role; the rest read files, sleep or reach other servers. Kept even with
# the allowlist below: it also covers a function a future sqlglot learns to type.
_DENIED_FUNCTION_PREFIXES = ("set_config", "pg_sleep", "dblink", "pg_read", "lo_")
# Pure Postgres built-ins that sqlglot parses as anonymous functions; every other unknown function
# is rejected.
_ALLOWED_UNKNOWN_FUNCTIONS = frozenset({"age", "make_date"})
_FUNCTION_HINT = (
    "Use standard SQL functions such as SUM, COUNT, AVG, ROUND, COALESCE, NULLIF, to_char, "
    "date_trunc, EXTRACT or string_agg."
)


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
        if isinstance(function, exp.Anonymous):
            _check_unknown_function(function)
    return cleaned


def _check_unknown_function(function: exp.Anonymous) -> None:
    name = function.name.lower()
    parent = function.parent
    if (isinstance(parent, exp.Dot) and parent.expression is function) or (
        isinstance(parent, exp.Table) and (parent.db or parent.catalog)
    ):
        raise RejectedQuery(f"function {name} has a schema", "Call functions without a schema.")
    if name not in _ALLOWED_UNKNOWN_FUNCTIONS:
        raise RejectedQuery(
            f"function {name} is not allowed: only standard SQL functions are", _FUNCTION_HINT
        )
