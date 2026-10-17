---
type: workflow
title: Run the categorization eval
description: How to dry-run the production categorizer against user labels, read the eleven-cell HISTORY.md line, and why lines after a golden-set change are not a trend.
tags: [evals, categorization, golden-set, langfuse, workflow]
sources:
  - id: openwiki-source-ea70eb6c045047448e446296
    resource: repo://.gitignore
  - id: openwiki-source-ba82ed278ec1910952d1d20d
    resource: repo://apps/api/finance/categorization/categorizer.py
  - id: openwiki-source-7558424c93dbbbe89f1ba7d6
    resource: repo://apps/api/finance/categorization/jev_client.py
  - id: openwiki-source-27ff1f909b76856ba6837b9a
    resource: repo://apps/api/finance/categorization/jev_questions.py
  - id: openwiki-source-2879b42a69194995581fcbd2
    resource: repo://apps/api/finance/categorization/pairing.py
  - id: openwiki-source-83c03eca02f158255cf5b496
    resource: repo://apps/api/finance/cli.py
  - id: openwiki-source-6b87b35cd25d24e6d9553c5c
    resource: repo://apps/api/finance/evals/metrics.py
  - id: openwiki-source-fbf18f0eed42a1e67180097c
    resource: repo://apps/api/finance/evals/report.py
  - id: openwiki-source-aca7b65d058b5d247f8196e0
    resource: repo://apps/api/finance/evals/run.py
  - id: openwiki-source-03ce6f667ac18e4ea0a87710
    resource: repo://apps/api/finance/settings.py
  - id: openwiki-source-09c8920d10c1a9bdfd122560
    resource: repo://apps/api/tests/test_cli.py
  - id: openwiki-source-ac1b2ae7ef421b0e00c93c45
    resource: repo://apps/api/tests/test_eval_metrics.py
  - id: openwiki-source-3f082313f7464eeb112370d9
    resource: repo://apps/api/tests/test_eval_run.py
  - id: openwiki-source-115b2dad781e2a2c5b5a980d
    resource: repo://docs/architecture.md
  - id: openwiki-source-99266e9b02d0a104ddcc727e
    resource: repo://docs/evals/HISTORY.md
generated: { by: "openwiki/0.7.2", at: "2026-10-17T21:01:31.912Z" }
verified:
  - by: openwiki/0.7.2
    at: 2026-10-17T21:18:38.741Z
---

# Run the categorization eval

`finance eval-categorization` scores the production cascade against the golden set: the latest `source = 'user'` label of each transaction. It is a dry run. It does not update categories, merchants, notes, or defaults. Use it after a change to criteria, rules, thresholds, or the jev version. It is not a CI command, and it is not a chat eval.

The cascade it reuses is [Categorization cascade](../concepts/categorization-cascade.md). The labels it scores are written by [Review and labels](review-and-labels.md). Which test to run instead of a paid benchmark is [Verify a change](../operations/verify-a-change.md). Threshold names live in [Configuration](../operations/configuration.md).

## Run it

From `apps/api`, with the repo-root `.env` already pointing at the database that holds the labels:

```bash
uv run finance eval-categorization --note "what changed"
```

`--note` is the text that lands in the Note cell of `docs/evals/HISTORY.md`. Write what changed, not a score. A pipe in the note becomes `/`, and a line break becomes a space, so the table stays one line of eleven cells. `--limit N` scores only the first N golden rows after the query's order (`N` must be at least 1). Omit it for the full set. A limit is a smoke check, not a number you can compare with a full-set line.

The command prints `report.md` and `saved to <directory>`. Exit 1 means nothing was recorded: `TYPESAFE_API_KEY` is unset, there are no user labels, or jev failed on every golden row. The stderr line is `eval-categorization: ...`. A limit below 1 exits 2 before any run starts.

The run needs `SUPABASE_DB_URL` (the same connection the CLI uses for import and categorize) and `TYPESAFE_API_KEY`. Langfuse keys are optional. Without them the SDK logs a warning and records nothing. The eval does not skip jev the way `finance categorize` does when the key is missing.

This spends money. The report estimates cost as input tokens times `0.042 / 1_000_000`. The v1 spec's planning figure was about $0.05 per 400 labelled rows. That is why the command stays out of CI. Do not set `RUN_LIVE_JEV=1` to turn the unit suite into this benchmark. That flag only un-skips the live client test in `tests/test_jev_client.py`.

## What one run does

`run_eval` loads the taxonomy and enabled rules, opens one Langfuse span named `eval`, and calls the production `categorize` with a `TypesafeJev` client tagged `eval`. Concurrency is `jev_concurrency` (default 8). Every `jev.categorize` generation nests under that span, and a same-merchant question nests there too. The span output is only the scored-row count and the failed count. The client flushes Langfuse when it closes.

The golden query is `distinct on (transaction_id)` over `transaction_labels` where `source = 'user'`, latest `labeled_at` first, joined to the transaction, account, and labelled merchant. System, rule, and merchant history rows are not the golden set. A confirm that relabelled rows is in the set, because each of those rows got a `user` history row. A rename or merge that was not a confirm is not, except that a merge changes the name the join reads. Notes are not scored.

Two things are deliberately different from a production run, so the labels are not scored against themselves:

- Merchant defaults are off (`use_merchant_defaults=False`), and the roster passed in is empty. A default and a known merchant both come from the labels being scored. The roster still grows inside the run as names resolve, in booking order.
- Pairing is computed in memory with `find_pairs` over every transaction, using `transfer_pattern` and `transfer_window_days`. It does not call `pair_transfers`, so it does not write `transfer_pair_id` or a rule label. A golden row that pairs in that pass is scored as `own_accounts` with confidence 1, the same rule the cascade would apply.

Everything else is the production path. A paired row never calls jev. Otherwise the first matching categorize rule wins. Remaining rows get one jev call (`merchant_name`, `category`, `is_subscription`), then merchant resolution against the roster built so far. Refund rules still narrow the options jev sees. `link_loans` does not run. The eval never calls `save`.

Merchant resolution still uses the settings on that run. An exact `match_key` hit returns the known merchant. A new name below `brand_threshold` (default 0.5) is dropped. A same-merchant answer at or above `merge_threshold` (default 0.5) joins the known merchant. From `merge_suggestion_floor` (default 0.3) up to that threshold, the run keeps a new name and records a merge candidate. The history merchant counts follow those decisions. They do not follow the suggestion.

A row whose jev call fails, or whose answer cannot be used, is left out of every metric. The others are still scored. The history Note cell then contains `failed=N`. If that drops the scored set to zero, the command raises and writes neither the output directory nor a history line.

```mermaid
sequenceDiagram
    participant CLI as finance eval-categorization
    participant Eval as run_eval
    participant DB as Postgres
    participant LF as Langfuse
    participant Jev as TypesafeJev

    CLI->>Eval: connection, settings, limit, note
    Eval->>DB: load taxonomy, rules, golden labels, all transactions
    Note over Eval: pair in memory, empty roster, defaults off
    Eval->>LF: span named eval
    Eval->>Jev: categorize, tag eval
    Jev-->>Eval: scored rows, failed rows omitted
    LF-->>Eval: generations nested under the span
    alt no scored row
        Eval-->>CLI: RuntimeError, nothing written
    else scored
        Eval->>Eval: eval-output timestamp files
        Eval->>Eval: append one HISTORY.md line
        Eval-->>CLI: print report.md and the directory
    end
```

One eval: read the golden set, score it with the production cascade without writing the database, then record metrics only if at least one row scored.

## Where the results go

| Output | Tracked? | What it is |
| --- | --- | --- |
| `eval-output/<YYYYMMDD-HHMMSS>/report.md` | No (git-ignored) | The readable tables. This is what the command prints. |
| `eval-output/<YYYYMMDD-HHMMSS>/summary.json` | No | `meta` (time, jev model, fingerprint, note, input tokens, failed) and the full `metrics` object. |
| `eval-output/<YYYYMMDD-HHMMSS>/rows.csv` | No | One row per scored transaction. Failed rows are absent. |
| `docs/evals/HISTORY.md` | Yes | One appended metrics line. No bank text. |
| Langfuse span `eval` | Remote | The run, with nested `jev.categorize` generations tagged `eval`. |

`rows.csv` columns are the `EvalRow` fields: transaction id, the text sent as `bank_concept | merchant`, direction, golden and predicted slug and level 1, confidences, subscription flag and score, and merchant names. That file is the place to see which rows moved. Do not paste it into the history note, a commit message, or this wiki. It contains bank text.

`summary.json` also holds the confidence buckets, the threshold table, merchant accuracy, and the duplicate and wrong-join counts that the history line compresses. The fingerprint is the first 8 hex characters of a SHA-256 over categories in the order jev sees them, plus the rules, with display names excluded. Renaming a category does not change it. Reordering categories or editing a rule does. It is in the report header and in `summary.json`. It is not a HISTORY.md column.

The report header names the jev model, that fingerprint, the scored-row count, an approximate dollar cost, and the note. If any golden row was left out, it adds `N left out: jev failed`.

## How to read a run

The history table is the comparison surface. `history_line` writes eleven cells, in this order. The Merchants dup / joins column is one of them. Older lines leave it as `—` because that count was not recorded yet. Do not read the table as ten columns.

| Column | Meaning |
| --- | --- |
| Date | Local date of the run. |
| Source | `eval` for this command. The 2026-09-23 `spike v6`, `v7`, and `v7b` lines are the pre-production spike, jev only, with no pairing or rules. |
| jev | Model string returned by the call. Current lines are `jev-1.13.0`. |
| Golden rows | Rows scored, not rows left out. A `failed=N` note means N golden rows were excluded. |
| L2 acc | Level-2 accuracy: predicted slug equals the golden slug, over every scored row. A missing confidence counts as 0 for the buckets, not as a skip. |
| L1 acc | Level-1 accuracy: the predicted level-1 group equals the golden level-1 group, over every scored row. The confidence beside that comparison is level-1 confidence. A wrong leaf in the right group is still right here. |
| Precision @0.95 | Of rows whose level-2 confidence is at least 0.95, the share whose slug matched. This is the acceptance threshold (`category_threshold`, default 0.95). |
| Review @0.95 | Scored rows below 0.95. The report's threshold table also has 0.80, 0.85, and 0.90. The history line does not. |
| Subs P / R | Subscription precision and recall as `hits/total · hits/total`, expenses only, flag on when noul is above 0.7. |
| Merchants dup / joins | Extra predicted names per golden merchant, then extra golden merchants per predicted name. Both use `match_key`. A row with no predicted name votes for neither. |
| Note | What changed, plus `failed=N` when any row was left out. |

Subscription precision is: among outgoing rows the run flagged, how many the user had marked as subscriptions. Recall is: among rows the user marked, how many the run flagged and that were outgoing. Rows with a null golden subscription are left out of both. A rule row has no noul, so it is not flagged.

Duplicates and wrong joins count only rows that have a golden merchant and a predicted name. `compute_metrics` pairs those names by `match_key` (letters and digits only, case-insensitive). Duplicates are the extra predicted keys beyond one for each golden key. Wrong joins are the extra golden keys beyond one for each predicted key. A golden merchant with no predicted name is in the merchant-accuracy denominator and in neither of these counts. Merchant accuracy itself stays in the report and in `summary.json`. The history line does not repeat it.

The report also breaks level 2 and level 1 into confidence buckets `0.00–0.50`, `0.50–0.70`, `0.70–0.85`, `0.85–0.95`, and `0.95–1.00`, each with a row count and the share that were right. Use that table when a headline accuracy move is really a shift of mass across the 0.95 gate.

## Do not read the history as a trend

Two facts in [HISTORY.md](../../docs/evals/HISTORY.md) make a later line not a continuation of the previous one.

The golden set changed size, and one change did not change the row count:

- The 2026-09-23 spike lines and the 2026-09-24 production line score **412** rows.
- The 2026-09-25 line scores **480**. After the 2026-09-24 eval, review labels from a newly imported monthly statement joined the set, and 6 labels of a mixed merchant were corrected from one category to per-charge categories.
- The 2026-09-26 and 2026-09-27 lines score **684**.
- The 2026-10-17 lines score **824**. Before those evals, duplicate merchants were merged, so golden merchant names follow the merged names, and 22 rows of one bank text took the label the user had given the same text. That relabel is a set change even where the row count would have matched.

Compare a line only with another line of the same golden-set size, and say which size. A drop from 87.4% (412) to 82.3% (480) is a different set, not a regression. The 2026-09-23 spike lines are also a different system: jev only, no pairing and no system rules. The first production line is 2026-09-24. The 824-row lines are not a continuation of the 684-row lines.

jev noise is about ten rows between identical runs. The 2026-09-23 v7 and v7b lines exist to measure that: 83.3% then 84.0% level-2 on the same 412 rows. The 2026-10-17 baseline and its repeat measure it again on 824 rows: 82.9% then 82.5% level-2, and merchant duplicates 38 then 40. A move smaller than about ten rows is noise. On 824 rows, ten rows is about 1.2 percentage points. The 2026-09-26 hint lines (86.0%, 85.8%, 86.8% level-2) and the 2026-09-27 line (87.0% level-2) sit inside that band on 684 rows. Do not call a one-point move a win.

The latest kept line in the file is 2026-10-17, 824 golden rows, merge at 0.5 and suggest from 0.3: level-2 83.0%, level-1 85.1%, precision at 0.95 of 97.1%, 348 rows to review, subscription precision 56/58 and recall 56/66, merchants 26 / 2. That line is the shipped default. Experiment lines on the same date marked `not kept` are measurements of rejected changes, not the default and not a trend endpoint. Do not quote merchant names from the notes.

## What this command is not

There is no chat eval command. Do not invent `finance eval-chat` or point this command at the agent. The chat does not use jev. [Architecture](../../docs/architecture.md) links the missing chat evals as [#27](https://github.com/raulvazquez7/personal-finance-agent/issues/27). That issue is not built.

The spike scripts under `docs/superpowers/spikes/2026-09-23-jev-categorization/` are history. Measure a production change with this command, not with `run.py` / `report.py` there.

Langfuse Datasets and Experiments are not built. The trace above is the observability that exists.

`finance labels export` and `finance labels import` are how the golden set survives `supabase db reset`. Export defaults to `data/labels/labels-YYYYMMDD.csv` and refuses to overwrite unless `--force` is passed. Import loads by `dedup_key` and does not restore merchant defaults. The CSV and `data/` are not documentation. Do not describe their contents. The restore rule is in [CLAUDE.md](../../CLAUDE.md). Scoring after a reset still requires the statements to be imported again, because the eval joins labels to `transactions`.

## When to run it, and what else to run

Run the paid command when the change can move a scored decision: category criteria, a system rule, the taxonomy order jev sees, `category_threshold`, `subscription_threshold`, `brand_threshold`, `merge_threshold`, `merge_suggestion_floor`, pairing window or pattern, or a jev upgrade. Put that in `--note`. A threshold experiment that the note marks `not kept` is not the shipped default.

Do not run it to verify a refactor that the unit tests already lock, and do not run it against a scratch database that has no user labels. A scratch copy has no golden set unless you imported one. Importing the real labels into a scratch database is a labels write. Name recipe R2 and follow [CLAUDE.md](../../CLAUDE.md). Do not invent the recipe.

| Change | Check first | Paid eval |
| --- | --- | --- |
| Metric math, history-line shape, fingerprint | `cd apps/api && uv run task test` on `tests/test_eval_metrics.py` | No |
| Dry run writes nothing, failed rows stay out, one `eval` span | `uv run task test-integration` on `tests/test_eval_run.py` | No. The test replaces `TypesafeJev` and fails if a real client is constructed. |
| CLI flags and the exit codes | `tests/test_cli.py` under `task test` | No |
| Criteria, rules, thresholds, taxonomy order, jev version | The unit or integration test for that piece, then this command on the labelled database | Yes, full set, with a note |
| Chat prompt or semantic layer | There is no eval. See the known gap in [Architecture](../../docs/architecture.md). | No |

`tests/test_eval_run.py` is marked `integration` for the whole file, so `uv run task test` never runs it. `tests/test_eval_metrics.py` is a unit test and does run in CI. Neither is a substitute for a line in `HISTORY.md`.
