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


def test_notes_travel_even_without_a_label(db_conn, make_tx, tmp_path):
    tx = make_tx("-51.00", "PAGO | ZZTEST SHOP", booked_at=date(1999, 1, 1))
    db_conn.execute("update transactions set note = 'AirPods case' where id = %s", (tx,))
    path = tmp_path / "labels.csv"
    export_labels(db_conn, path)
    db_conn.execute("update transactions set note = null where id = %s", (tx,))
    result = import_labels(db_conn, path)
    assert result.notes >= 1
    assert (
        db_conn.execute("select note from transactions where id = %s", (tx,)).fetchone()["note"]
        == "AirPods case"
    )


def test_an_old_csv_imports_and_a_bad_row_is_reported_by_line(db_conn, make_tx, tmp_path):
    good = make_tx("-9.90", "PAGO | ZZTEST ACME", booked_at=date(1999, 1, 1))
    key = db_conn.execute("select dedup_key from transactions where id = %s", (good,)).fetchone()[
        "dedup_key"
    ]
    path = tmp_path / "old.csv"
    path.write_text(
        "dedup_key,category_slug,is_subscription,merchant\n"
        f"{key},groceries,false,ZZTEST ACME\n"
        f"{key},no_such_category,false,\n"
    )
    result = import_labels(db_conn, path)
    assert result.imported == 1
    assert len(result.errors) == 1 and result.errors[0].startswith("line 3:")


def test_a_note_over_500_characters_is_reported_and_the_rest_imports(db_conn, make_tx, tmp_path):
    too_long = make_tx("-9.90", "PAGO | ZZTEST LONG NOTE", booked_at=SYNTHETIC_DAY)
    fine = make_tx("-4.00", "PAGO | ZZTEST SHORT NOTE", booked_at=SYNTHETIC_DAY)
    path = tmp_path / "notes.csv"
    path.write_text(
        "dedup_key,category_slug,is_subscription,merchant,note\n"
        f"{_dedup_key(db_conn, too_long)},,,,{'x' * 501}\n"
        f"{_dedup_key(db_conn, fine)},,,,gift\n"
    )
    result = import_labels(db_conn, path)
    assert result.errors == ["line 2: a note has at most 500 characters"]
    assert result.notes == 1
    note = "select note from transactions where id = %s"
    assert db_conn.execute(note, (fine,)).fetchone()["note"] == "gift"
    assert db_conn.execute(note, (too_long,)).fetchone()["note"] is None
