"""User labels as CSV keyed by dedup_key, so the golden set survives database resets."""

import csv
from pathlib import Path

from psycopg import Connection
from pydantic import BaseModel

from finance.categorization.labels import label_transaction

FIELDS = ("dedup_key", "category_slug", "is_subscription", "merchant")

_EXPORT = """
select distinct on (l.transaction_id) t.dedup_key, l.category_slug, l.is_subscription,
       coalesce(m.name, '') as merchant
from transaction_labels l
join transactions t on t.id = l.transaction_id
left join merchants m on m.id = l.merchant_id
where l.source = 'user'
order by l.transaction_id, l.labeled_at desc
"""


class LabelsImport(BaseModel):
    imported: int
    missing: int


def export_labels(conn: Connection, path: Path, overwrite: bool = False) -> int:
    """Raises FileExistsError for an existing file unless `overwrite`: it may be the only
    backup of the golden set."""
    rows = conn.execute(_EXPORT).fetchall()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w" if overwrite else "x", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def import_labels(conn: Connection, path: Path) -> LabelsImport:
    imported = missing = 0
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            found = conn.execute(
                "select id from transactions where dedup_key = %s", (row["dedup_key"],)
            ).fetchone()
            if found is None:
                missing += 1
                continue
            label_transaction(
                conn,
                found["id"],
                row["category_slug"],
                row["is_subscription"].strip().lower() in ("1", "true"),
                new_merchant_name=row["merchant"] or None,
            )
            imported += 1
    return LabelsImport(imported=imported, missing=missing)
