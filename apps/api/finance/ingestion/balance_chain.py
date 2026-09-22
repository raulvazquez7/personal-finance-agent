"""Backstop against silently dropped rows: the printed running balance must add up.

Both supported banks print a balance after every movement, so consecutive rows satisfy
`balance_after[n-1] + amount[n] == balance_after[n]`. A row the adapter's regex failed to
match breaks that chain, which turns the whole silent-drop class into a loud failure.
"""

from typing import Literal

from finance.models import NormalizedTransaction

RowOrder = Literal["ascending", "descending"]


def check_balance_chain(
    transactions: list[NormalizedTransaction], *, bank: str, order: RowOrder
) -> None:
    """Raise ValueError when the running balance breaks between two consecutive rows.

    `order` is how the statement prints its rows: "ascending" oldest first (BBVA),
    "descending" newest first (CaixaBank). The check is skipped, deliberately, when it
    cannot apply: fewer than two rows, or any row without a printed balance.
    """
    if len(transactions) < 2 or any(tx.balance_after is None for tx in transactions):
        return

    oldest_first = transactions if order == "ascending" else list(reversed(transactions))
    pairs = zip(oldest_first, oldest_first[1:], strict=False)
    for position, (previous, current) in enumerate(pairs, start=1):
        expected = previous.balance_after + current.amount
        if expected != current.balance_after:
            index = position if order == "ascending" else len(transactions) - 1 - position
            raise ValueError(
                f"{bank} statement balance chain breaks at row {index} "
                f"({current.booked_at} {current.description_raw!r}): "
                f"expected {expected}, statement prints {current.balance_after}; "
                "a row was probably dropped while parsing"
            )
