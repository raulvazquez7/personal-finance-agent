"""Summarize a spike run and write the review CSV next to it: python report.py v4

The CSV is sorted by merchant so wrong merges and missed duplicates sit next to each other.
"""

import collections
import csv
import json
import sys
from pathlib import Path

OUT_DIR = Path(__file__).parent / "output"


def bucket(x: float) -> str:
    return "<0.5" if x < 0.5 else "0.5-0.85" if x < 0.85 else ">=0.85"


def main(run: str) -> None:
    rows = [json.loads(line) for line in (OUT_DIR / f"results_{run}.jsonl").open()]
    groups = collections.defaultdict(set)
    for r in rows:
        if r["merchant"]:
            groups[r["merchant"]].add(r["state"]["merchant_text"])

    print(f"== {run}: {len(rows)} rows, model {rows[0]['model']}, {len(groups)} merchants")
    print("merchant resolution", dict(collections.Counter(r["merchant_how"] for r in rows)))
    print("brand confidence   ", dict(collections.Counter(bucket(r["brand_conf"]) for r in rows if r["merchant"])))
    print("level-2 confidence ", dict(collections.Counter(bucket(r["cat_conf"]) for r in rows)))
    print("level-1 confidence ", dict(collections.Counter(bucket(r["level1_conf"]) for r in rows)))
    print("\nmerchants built from more than one raw text:")
    for name, texts in sorted(groups.items(), key=lambda item: -len(item[1])):
        if len(texts) > 1:
            print(f"  {name:28} <= {' | '.join(sorted(texts)[:5])}")

    table = sorted(
        (
            {
                "1_text_jev_reads": (r["state"]["bank_concept"] + " | " if r["state"]["bank_concept"] else "") + r["state"]["merchant_text"],
                "2_amount": r["state"]["amount"],
                "3_jev_merchant": r["merchant"] or "(none)",
                "4_jev_brand_conf": r["brand_conf"],
                "5_jev_category_level2": r["category"],
                "6_jev_category_conf": r["cat_conf"],
                "7_jev_subscription_prob": r["sub"],
                "8_level1_python": r["level1"],
            }
            for r in rows
        ),
        key=lambda row: (row["3_jev_merchant"], row["1_text_jev_reads"]),
    )
    with (OUT_DIR / f"review_{run}.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=table[0].keys())
        writer.writeheader()
        writer.writerows(table)


if __name__ == "__main__":
    main(sys.argv[1])
