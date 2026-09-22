"""CaixaBank movements PDF: one regex per row, header with IBAN and period."""

import re

from finance.ingestion.adapters.base import pdf_pages_text
from finance.ingestion.normalize import normalize_merchant, parse_amount_es, parse_date_es
from finance.models import NormalizedTransaction, ParsedStatement, StatementHeader

_IBAN = re.compile(r"IBAN ((?:[A-Z]{2}\d{2})(?: ?[A-Z0-9]{4}){5})")
_PERIOD = re.compile(r"Periodo (\d{2}/\d{2}/\d{4}) - (\d{2}/\d{2}/\d{4})")
_ROW = re.compile(
    r"^(?P<concept>.+?) (?P<date>\d{2}/\d{2}/\d{4}) "
    r"(?P<amount>[+-]?[\d.]*\d,\d{2})€ ?(?P<balance>[\d.]*\d,\d{2})€$"
)


class CaixaBankPdfAdapter:
    bank = "caixabank"

    def sniff(self, first_page_text: str) -> bool:
        compact = first_page_text.replace(" ", "")
        return "ConceptoFechaImporteSaldo" in compact and "Periodo" in compact

    def parse(self, pdf_bytes: bytes) -> ParsedStatement:
        return parse_text("\n".join(pdf_pages_text(pdf_bytes)))


def parse_text(text: str) -> ParsedStatement:
    iban, period = _IBAN.search(text), _PERIOD.search(text)
    if not iban or not period:
        raise ValueError("CaixaBank statement header not found (expected IBAN and Periodo)")
    header = StatementHeader(
        bank="caixabank",
        iban=iban.group(1).replace(" ", ""),
        period_start=parse_date_es(period.group(1)),
        period_end=parse_date_es(period.group(2)),
    )
    transactions = [_row(match) for match in map(_ROW.match, text.splitlines()) if match]
    return ParsedStatement(header=header, transactions=transactions)


def _row(match: re.Match[str]) -> NormalizedTransaction:
    return NormalizedTransaction(
        booked_at=parse_date_es(match["date"]),
        amount=parse_amount_es(match["amount"]),
        description_raw=match["concept"],
        merchant=normalize_merchant(match["concept"]),
        balance_after=parse_amount_es(match["balance"]),
    )
