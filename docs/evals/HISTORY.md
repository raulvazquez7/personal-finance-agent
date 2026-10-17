# Categorization benchmark history

One line per run of `finance eval-categorization` (spec section 13.1), newest
last. Metrics only: row-level results stay in the git-ignored `eval-output/`.
Golden set: the user labels in `transaction_labels`. Run-to-run noise of jev is
about ten rows, so smaller differences mean nothing.

Columns: level-2 and level-1 accuracy over all golden rows; at the 0.95
acceptance threshold, the precision of what is accepted and the rows sent to
review; subscription precision and recall at noul > 0.7 (expenses); merchant
duplicates (extra predicted names per golden merchant) and wrong joins (extra
golden merchants per predicted name), by match key. Golden
rows are the rows scored; `failed=N` in the Note means N rows were left out
because jev failed on them.

Golden set changes between runs, which make the next line not directly
comparable with the previous one:

- After the 2026-09-24 eval: the review labels of a newly imported monthly
  statement joined the set, and 6 labels of a mixed merchant were corrected
  from one category to per-charge categories.
- Before the 2026-10-17 evals: duplicate merchants were merged, so golden
  merchant names follow the merged names, and 22 rows of one bank text took
  the label the user had given the same text.

| Date | Source | jev | Golden rows | L2 acc | L1 acc | Precision @0.95 | Review @0.95 | Subs P / R | Merchants dup / joins | Note |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-09-23 | spike v6 | jev-1.13.0 | 412 | 84.2% | 86.4% | 97.2% | 158 | 26/26 · 26/30 | — | final taxonomy; jev only, no pairing or rules |
| 2026-09-23 | spike v7 | jev-1.13.0 | 412 | 83.3% | 85.7% | 97.6% | 162 | 26/26 · 26/30 | — | subscription wording; jev only |
| 2026-09-23 | spike v7b | jev-1.13.0 | 412 | 84.0% | 86.2% | 97.2% | 164 | 26/26 · 26/30 | — | v7 repeated to measure noise |
| 2026-09-24 | eval | jev-1.13.0 | 412 | 87.4% | 89.6% | 98.9% | 147 | 26/26 · 26/30 | — | first production run: pairing, system rules, jev |
| 2026-09-25 | eval | jev-1.13.0 | 480 | 82.3% | 84.6% | 98.2% | 196 | 31/32 · 31/36 | — | slice 3 taxonomy: refunds take the purchase category, loans, unitemized card spending |
| 2026-09-26 | eval | jev-1.13.0 | 684 | 86.0% | 88.5% | 98.2% | 302 | 50/51 · 50/60 | — | baseline before prompt hints (expendeduria, restaurants, petrol stations, IKEA) |
| 2026-09-26 | eval | jev-1.13.0 | 684 | 85.8% | 88.0% | 98.0% | 290 | 50/51 · 50/60 | — | prompt hints: expendeduria, RESTAURANTES Y CAFETERIAS, GASOLINERAS, IKEA |
| 2026-09-26 | eval | jev-1.13.0 | 684 | 86.8% | 89.2% | 98.5% | 291 | 50/51 · 50/60 | — | prompt hints v2: stronger GASOLINERAS and IKEA wording |
| 2026-09-27 | eval | jev-1.13.0 | 684 | 87.0% | 89.2% | 98.2% | 287 | 50/51 · 50/60 | — | restaurants not_for: Amazon and Prime Video |
| 2026-10-17 | eval | jev-1.13.0 | 824 | 82.9% | 84.8% | 96.7% | 344 | 56/59 · 56/66 | 38 / 2 | baseline after the 2026-10-17 merchant merge |
| 2026-10-17 | eval | jev-1.13.0 | 824 | 82.5% | 84.7% | 97.1% | 347 | 56/59 · 56/66 | 40 / 2 | baseline repeated to measure noise |
| 2026-10-17 | eval | jev-1.13.0 | 824 | 83.3% | 85.3% | 96.7% | 342 | 56/59 · 56/66 | 24 / 2 | experiment: merge_threshold 0.5 |
| 2026-10-17 | eval | jev-1.13.0 | 824 | 83.9% | 85.7% | 96.9% | 345 | 56/58 · 56/66 | 25 / 2 | experiment: merge_threshold 0.5, shortlist finds cut-off and joined names (not kept) |
| 2026-10-17 | eval | jev-1.13.0 | 824 | 83.3% | 85.3% | 97.1% | 348 | 56/58 · 56/66 | 24 / 3 | experiment: merge_threshold 0.6, shortlist finds cut-off and joined names (not kept) |
| 2026-10-17 | eval | jev-1.13.0 | 824 | 83.6% | 85.4% | 97.0% | 354 | 56/58 · 56/66 | 25 / 2 | experiment: merge_threshold 0.5, skip card processor prefix (run 1, not kept) |
| 2026-10-17 | eval | jev-1.13.0 | 824 | 83.0% | 85.4% | 96.7% | 345 | 56/59 · 56/66 | 21 / 2 | experiment: merge_threshold 0.5, skip card processor prefix (run 2, not kept) |
| 2026-10-17 | eval | jev-1.13.0 | 824 | 83.0% | 85.1% | 97.1% | 348 | 56/58 · 56/66 | 26 / 2 | merge at 0.5, suggest from 0.3 (new defaults) |
