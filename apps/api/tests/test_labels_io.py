import csv
from datetime import date

import pytest

from finance.categorization.labels import label_transaction
from finance.evals.labels_io import FIELDS, export_labels, import_labels

pytestmark = pytest.mark.integration

# The real ledger has no rows before 2000, so its rows never compete with these.
SYNTHETIC_DAY = date(1999, 1, 1)


def _dedup_key(conn, tx):
    return conn.execute("select dedup_key from transactions where id = %s", (tx,)).fetchone()[
        "dedup_key"
    ]


def test_labels_travel_by_dedup_key(db_conn, make_tx, tmp_path):
    labelled = make_tx(
        "-9.90", "PAGO | ZZTEST ACME", merchant="ZZTEST ACME", booked_at=SYNTHETIC_DAY
    )
    label_transaction(db_conn, labelled, "groceries", False, new_merchant_name="ZZTEST ACME")
    exported = tmp_path / "labels.csv"
    assert export_labels(db_conn, exported) >= 1
    key = _dedup_key(db_conn, labelled)
    rows = {row["dedup_key"]: row for row in csv.DictReader(exported.open())}
    assert rows[key]["category_slug"] == "groceries" and rows[key]["merchant"] == "ZZTEST ACME"

    fresh = make_tx(
        "-4.00", "PAGO | ZZTEST TOBACCO", merchant="ZZTEST TOBACCO", booked_at=SYNTHETIC_DAY
    )
    incoming = tmp_path / "incoming.csv"
    with incoming.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow(
            {
                "dedup_key": _dedup_key(db_conn, fresh),
                "category_slug": "tobacco",
                "is_subscription": "false",
                "merchant": "ZZTEST TOBACCO",
            }
        )
        writer.writerow(
            {
                "dedup_key": "missing",
                "category_slug": "tobacco",
                "is_subscription": "false",
                "merchant": "",
            }
        )
    result = import_labels(db_conn, incoming)
    assert (result.imported, result.missing) == (1, 1)
    row = db_conn.execute(
        "select category_slug, category_source from transactions where id = %s", (fresh,)
    ).fetchone()
    assert (row["category_slug"], row["category_source"]) == ("tobacco", "user")
