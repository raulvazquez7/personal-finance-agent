import asyncio

from finance.agent.models import QueryResult
from finance.agent.tools import format_for_model, make_run_sql

ROWS = QueryResult(
    sql="SELECT month, spend FROM t",
    columns=["month", "spend"],
    rows=[["2026-07", "120.50"], ["2026-08", None]],
    row_count=2,
)


def test_rows_read_as_a_compact_table():
    assert format_for_model(ROWS, rows_shown=50, max_chars=8000) == (
        "rows: 2\nmonth | spend\n2026-07 | 120.50\n2026-08 | "
    )


def test_a_cut_result_says_how_to_narrow_it():
    many = QueryResult(
        sql="s", columns=["n"], rows=[[str(n)] for n in range(5)], row_count=5, truncated=True
    )
    text = format_for_model(many, rows_shown=2, max_chars=8000)
    assert text.splitlines()[0] == "rows: more than 5"
    assert text.splitlines()[-1] == (
        "(showing 2 of more than 5 rows: aggregate, filter or add ORDER BY ... LIMIT)"
    )


def test_the_character_cap_cuts_rows_too():
    wide = QueryResult(sql="s", columns=["t"], rows=[["x" * 100]] * 10, row_count=10)
    text = format_for_model(wide, rows_shown=50, max_chars=350)
    assert len(text) < 450 and "(showing 3 of 10 rows" in text  # header + 3 rows of 101 fit in 350


def test_errors_and_empty_results_are_short():
    error = QueryResult(sql="s", error='column "x" does not exist', hint="Use the listed columns.")
    assert format_for_model(error, 50, 8000) == (
        'error: column "x" does not exist\nhint: Use the listed columns.'
    )
    assert format_for_model(QueryResult(sql="s"), 50, 8000) == "rows: 0 (nothing matched)"


def test_the_tool_returns_the_text_for_the_model_and_the_whole_result_as_artifact():
    async def run_query(sql):
        return ROWS

    tool = make_run_sql(run_query, rows_shown=50, max_chars=8000)
    message = asyncio.run(
        tool.ainvoke({"type": "tool_call", "name": "run_sql", "args": {"sql": "x"}, "id": "c1"})
    )
    assert message.content.startswith("rows: 2")
    assert message.artifact == ROWS.model_dump()
