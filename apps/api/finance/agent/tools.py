"""`run_sql`, the agent's only tool: a compact table for the model, the full result as artifact."""

from collections.abc import Awaitable, Callable

from langchain.tools import tool
from langchain_core.tools import BaseTool

from finance.agent.models import QueryResult

RunQuery = Callable[[str], Awaitable[QueryResult]]


def format_for_model(result: QueryResult, rows_shown: int, max_chars: int) -> str:
    """The row count, a header and `|`-separated rows; cut by rows and characters, and said so."""
    if result.error:
        return f"error: {result.error}" + (f"\nhint: {result.hint}" if result.hint else "")
    if result.row_count == 0:
        return "rows: 0 (nothing matched)"
    total = f"more than {result.row_count}" if result.truncated else str(result.row_count)
    lines = [f"rows: {total}", " | ".join(result.columns)]
    size = sum(len(line) + 1 for line in lines)
    for row in result.rows[:rows_shown]:
        line = " | ".join("" if value is None else value for value in row)
        if size + len(line) + 1 > max_chars:
            break
        lines.append(line)
        size += len(line) + 1
    shown = len(lines) - 2
    if shown < result.row_count or result.truncated:
        lines.append(
            f"(showing {shown} of {total} rows: aggregate, filter or add ORDER BY ... LIMIT)"
        )
    return "\n".join(lines)


def make_run_sql(run_query: RunQuery, rows_shown: int, max_chars: int) -> BaseTool:
    @tool("run_sql", response_format="content_and_artifact", parse_docstring=True)
    async def run_sql(sql: str) -> tuple[str, dict]:
        """Run one read-only PostgreSQL SELECT over the views transactions and subscriptions.

        Use it for lookups (SELECT DISTINCT ... ILIKE ... LIMIT) and for the final query.
        Returns the row count and the rows as a compact table.

        Args:
            sql: One SELECT statement. No other statement runs.
        """
        result = await run_query(sql)
        return format_for_model(result, rows_shown, max_chars), result.model_dump()

    return run_sql
