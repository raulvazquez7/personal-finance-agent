# Categorization benchmark history

One line per run of `finance eval-categorization` (spec section 13.1), newest
last. Metrics only: row-level results stay in the git-ignored `eval-output/`.
Golden set: the user labels in `transaction_labels`. Run-to-run noise of jev is
about ten rows, so smaller differences mean nothing.

Columns: level-2 and level-1 accuracy over all golden rows; at the 0.95
acceptance threshold, the precision of what is accepted and the rows sent to
review; subscription precision and recall at noul > 0.7 (expenses). Golden
rows are the rows scored; `failed=N` in the Note means N rows were left out
because jev failed on them.

Golden set changes between runs, which make the next line not directly
comparable with the previous one:

- After the 2026-09-24 eval: the March statement's review labels joined the
  set, and 6 Apple labels changed from `entertainment` to `other_insurance`
  (AppleCare) or `software_ai` (iCloud+ storage).

| Date | Source | jev | Golden rows | L2 acc | L1 acc | Precision @0.95 | Review @0.95 | Subs P / R | Note |
|---|---|---|---|---|---|---|---|---|---|
| 2026-09-23 | spike v6 | jev-1.13.0 | 412 | 84.2% | 86.4% | 97.2% | 158 | 26/26 · 26/30 | final taxonomy; jev only, no pairing or rules |
| 2026-09-23 | spike v7 | jev-1.13.0 | 412 | 83.3% | 85.7% | 97.6% | 162 | 26/26 · 26/30 | subscription wording; jev only |
| 2026-09-23 | spike v7b | jev-1.13.0 | 412 | 84.0% | 86.2% | 97.2% | 164 | 26/26 · 26/30 | v7 repeated to measure noise |
| 2026-09-24 | eval | jev-1.13.0 | 412 | 87.4% | 89.6% | 98.9% | 147 | 26/26 · 26/30 | first production run: pairing, system rules, jev |
