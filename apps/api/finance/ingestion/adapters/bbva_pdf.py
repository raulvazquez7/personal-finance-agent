"""BBVA monthly statement PDF: dated rows followed by one detail line each."""

import calendar
import re
from datetime import date

from finance.ingestion.adapters.base import pdf_pages_text
from finance.ingestion.normalize import normalize_merchant, parse_amount_es, parse_date_es
from finance.models import NormalizedTransaction, ParsedStatement, StatementHeader

_MONTHS = {
    "ENERO": 1,
    "FEBRERO": 2,
    "MARZO": 3,
    "ABRIL": 4,
    "MAYO": 5,
    "JUNIO": 6,
    "JULIO": 7,
    "AGOSTO": 8,
    "SEPTIEMBRE": 9,
    "OCTUBRE": 10,
    "NOVIEMBRE": 11,
    "DICIEMBRE": 12,
}
_HEADER = re.compile(r"EXTRACTO DE ([A-ZÑ]+) (\d{4})")
_IBAN = re.compile(r"IBAN ((?:[A-Z]{2}\d{2})(?: ?[A-Z0-9]{4}){5})")
_ROW = re.compile(
    r"^(?P<op>\d{2}/\d{2}) (?P<val>\d{2}/\d{2}) (?P<concept>.+?) "
    r"(?P<amount>-?[\d.]*\d,\d{2}) (?P<balance>[\d.]*\d,\d{2})$"
)
_FOOTER = "Todos los importes"


class BbvaPdfAdapter:
    bank = "bbva"

    def sniff(self, first_page_text: str) -> bool:
        compact = first_page_text.replace(" ", "")
        return "EXTRACTODE" in compact and "F.Oper." in compact

    def parse(self, pdf_bytes: bytes) -> ParsedStatement:
        return parse_pages(pdf_pages_text(pdf_bytes, x_tolerance=1))


def parse_pages(pages: list[str]) -> ParsedStatement:
    head, iban = _HEADER.search(pages[0]), _IBAN.search(pages[0])
    if not head or not iban:
        raise ValueError(
            "BBVA statement header not found (expected EXTRACTO DE <month> <year> and IBAN)"
        )
    month, year = _MONTHS[head.group(1)], int(head.group(2))
    header = StatementHeader(
        bank="bbva",
        iban=iban.group(1).replace(" ", ""),
        period_start=date(year, month, 1),
        period_end=date(year, month, calendar.monthrange(year, month)[1]),
    )
    transactions = [tx for page in pages for tx in _parse_page(page, month, year)]
    return ParsedStatement(header=header, transactions=transactions)


def _parse_page(text: str, month: int, year: int) -> list[NormalizedTransaction]:
    lines = text.splitlines()
    rows = []
    for index, line in enumerate(lines):
        if line.startswith(_FOOTER):
            break
        match = _ROW.match(line)
        if not match:
            continue
        detail = lines[index + 1] if index + 1 < len(lines) else ""
        if _ROW.match(detail) or detail.startswith(_FOOTER):
            detail = ""
        rows.append(
            NormalizedTransaction(
                booked_at=_row_date(match["op"], month, year),
                value_date=_row_date(match["val"], month, year),
                amount=parse_amount_es(match["amount"]),
                balance_after=parse_amount_es(match["balance"]),
                description_raw=f"{match['concept']} | {detail}".strip(" |"),
                merchant=normalize_merchant(detail),
            )
        )
    return rows


def _row_date(day_month: str, statement_month: int, statement_year: int) -> date:
    row_month = int(day_month[3:5])
    year = statement_year - 1 if statement_month == 1 and row_month == 12 else statement_year
    return parse_date_es(day_month, year=year)
