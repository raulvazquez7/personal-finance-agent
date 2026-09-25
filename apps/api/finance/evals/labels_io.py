"""User labels as CSV keyed by dedup_key, so the golden set survives database resets."""

import csv
from pathlib import Path

from psycopg import Connection
from pydantic import BaseModel

from finance.categorization.labels import NotFound, label_transaction, set_note

FIELDS = ("dedup_key", "category_slug", "is_subscription", "merchant", "note")

_EXPORT = """
with labels as (
  select distinct on (l.transaction_id) l.transaction_id, l.category_slug, l.is_subscription,
         coalesce(m.name, '') as merchant
  from transaction_labels l
  left join merchants m on m.id = l.merchant_id
  where l.source = 'user'
  order by l.transaction_id, l.labeled_at desc
)
select t.dedup_key, coalesce(lb.category_slug, '') as category_slug,
       coalesce(lb.is_subscription::text, '') as is_subscription,
       coalesce(lb.merchant, '') as merchant, coalesce(t.note, '') as note
from transactions t
left join labels lb on lb.transaction_id = t.id
where lb.transaction_id is not null or t.note is not null
order by t.dedup_key
"""


class LabelsImport(BaseModel):
    imported: int
    missing: int
    notes: int = 0
    errors: list[str] = []


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
    """A CSV exported before slice 3 has no note column. A bad row is reported by its line
    number and skipped; the others still import."""
    result = LabelsImport(imported=0, missing=0)
    with path.open(newline="", encoding="utf-8") as handle:
        for line, row in enumerate(csv.DictReader(handle), start=2):
            found = conn.execute(
                "select id from transactions where dedup_key = %s", (row["dedup_key"],)
            ).fetchone()
            if found is None:
                result.missing += 1
                continue
            label, note = row["category_slug"], row.get("note")
            try:
                with conn.transaction():  # a bad row rolls back whole: its label and its note
                    if label:
                        label_transaction(
                            conn,
                            found["id"],
                            label,
                            row["is_subscription"].strip().lower() in ("1", "true"),
                            new_merchant_name=row["merchant"] or None,
                        )
                    if note:
                        set_note(conn, found["id"], note)
            except (NotFound, ValueError) as error:
                result.errors.append(f"line {line}: {error}")
                continue
            if label:
                result.imported += 1
            if note:
                result.notes += 1
    return result
