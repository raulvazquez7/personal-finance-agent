---
type: workflow
title: Import to dashboard
description: How a BBVA or CaixaBank PDF becomes ledger rows, a background categorization run, and the overview and spending pages the web reads.
tags: [import, ingestion, dashboard, workflow, pdf]
verified:
  - by: openwiki/0.7.2
    at: 2026-10-17T19:58:49.962Z
sources:
  - id: openwiki-source-14bf78647b1830347bba54f7
    resource: repo://apps/api/finance/api/dashboard.py
  - id: openwiki-source-d4a379c23eebd0854d290dee
    resource: repo://apps/api/finance/api/deps.py
  - id: openwiki-source-40546be375b33e38583ad241
    resource: repo://apps/api/finance/api/imports.py
  - id: openwiki-source-93a650e15d829c7b5182b732
    resource: repo://apps/api/finance/api/main.py
  - id: openwiki-source-653c3f05b0dbfa67e28dd464
    resource: repo://apps/api/finance/api/periods.py
  - id: openwiki-source-2d458057d34ae33b8c6c9a37
    resource: repo://apps/api/finance/api/spending.py
  - id: openwiki-source-be202f0a191b0f5bedaec28d
    resource: repo://apps/api/finance/categorization/store.py
  - id: openwiki-source-83c03eca02f158255cf5b496
    resource: repo://apps/api/finance/cli.py
  - id: openwiki-source-96d9c417b9c763b4264b37fd
    resource: repo://apps/api/finance/dashboard/filters.py
  - id: openwiki-source-ce1615e8a9891cbec8c2a438
    resource: repo://apps/api/finance/dashboard/periods.py
  - id: openwiki-source-38be2e651acb6602bdc04d5a
    resource: repo://apps/api/finance/dashboard/totals.py
  - id: openwiki-source-2c7ad9ddc445f9183e19ce6a
    resource: repo://apps/api/finance/dashboard/transactions.py
  - id: openwiki-source-88763fc8b13bd378d91f8944
    resource: repo://apps/api/finance/ingestion/adapters/__init__.py
  - id: openwiki-source-60eb844834cd48ea76830648
    resource: repo://apps/api/finance/ingestion/adapters/base.py
  - id: openwiki-source-47e7eee47f85861f4df11fa1
    resource: repo://apps/api/finance/ingestion/adapters/bbva_pdf.py
  - id: openwiki-source-9218102a2ea2310a96a9fb56
    resource: repo://apps/api/finance/ingestion/adapters/caixabank_pdf.py
  - id: openwiki-source-0ea04da0263858331cae6747
    resource: repo://apps/api/finance/ingestion/balance_chain.py
  - id: openwiki-source-a23570ab06319771ad50a085
    resource: repo://apps/api/finance/ingestion/dedup.py
  - id: openwiki-source-20c9abe7182d471408c896aa
    resource: repo://apps/api/finance/ingestion/importer.py
  - id: openwiki-source-18c7950d8df5f6f0e6d447e8
    resource: repo://apps/api/finance/ingestion/structure.py
  - id: openwiki-source-ebacbce0ac9f7bcd4dedfcb5
    resource: repo://apps/api/tests/test_api.py
  - id: openwiki-source-0e19220a2f442ad3d5abcc10
    resource: repo://apps/api/tests/test_dedup.py
  - id: openwiki-source-9c046f0fe4126ef833ee77fe
    resource: repo://apps/web/src/app/imports/page.tsx
  - id: openwiki-source-b1a1bb6fe170c10c5ba87699
    resource: repo://apps/web/src/app/imports/upload-form.tsx
  - id: openwiki-source-4f290fdb91f0fdcd1d167183
    resource: repo://apps/web/src/app/income/page.tsx
  - id: openwiki-source-deba80bf5b4e6fbdad344120
    resource: repo://apps/web/src/app/page.tsx
  - id: openwiki-source-9bf231d59177afaf121c8f39
    resource: repo://apps/web/src/app/spending/%5Bgroup%5D/page.tsx
  - id: openwiki-source-ac9b852a2fa621958d429bb8
    resource: repo://apps/web/src/lib/api.ts
  - id: openwiki-source-9aa52b496223af6ebbb398ec
    resource: repo://supabase/migrations/20260922000000_init.sql
  - id: openwiki-source-221f6bc5f36164e5008b6ffb
    resource: repo://supabase/migrations/20260925110000_slice3_views.sql
generated: { by: "openwiki/0.7.2", at: "2026-10-17T19:58:49.962Z" }
---

# Import to dashboard

A statement becomes a number only after four owners finish their part. Ingestion parses a BBVA or CaixaBank PDF and inserts new movements. Categorization classifies those rows later, in the background. The dashboard package only reads `v_transactions_enriched`. The browser never opens Postgres.

Who owns each package is [System map](../architecture/system-map.md). What the numbers mean is [Money rules](../concepts/money-rules.md). How a pending row gets a category is [Categorization cascade](../concepts/categorization-cascade.md). How to check a change is [Verify a change](../operations/verify-a-change.md).

## Who owns each step

| Piece | Owns |
| --- | --- |
| `/imports` upload form | One `POST /imports` per selected PDF, then a refresh of the history |
| `POST /imports` | Content type, the insert, and the background task. It does not wait for categories |
| `import_statement` | Adapter, account, import record, deduped insert |
| `run_categorization_logged` | One cascade at a time. A failure here is logged, not returned |
| `GET /dashboard/overview`, `GET /spending/detail` | Period, totals, breakdowns, and the latest rows |
| `/`, `/spending/*`, `/income` | Display of those responses. They do not recompute spend |

`finance import` uses the same `import_statement`. It categorizes in the same process after every file, and prints a categorization exception instead of scheduling it. A bad file there is a line on stderr and exit code 1; the other files in the same command still import.

## From the PDF to the ledger

`/imports` is a server page. It lists `GET /imports` (the last 100 rows, newest first, joined to the account name) and renders `UploadForm`. The form accepts `application/pdf`, one or many files, and posts each file alone as multipart field `file`. A success line is the filename plus `rows_new` and `rows_duplicate`. A 415 or 422 shows FastAPI's `detail`. After the batch, `router.refresh()` reloads the history. The form does not wait for categories. The page copy says each import starts a run in the background.

`create_import` rejects any other content type with 415 before reading the body. A PDF is passed to `import_statement`. `UnsupportedStatement` and `ValueError` become 422 and schedule nothing. Only a returned summary schedules `run_categorization_logged` with no arguments, so the run is pending rows only. The response is 201 with that summary: import id, account id, bank, last four of the IBAN, filename, and the three row counts. The full IBAN is not in the response.

```mermaid
sequenceDiagram
    participant Browser
    participant Imports as Imports API
    participant Ingest as import_statement
    participant Ledger as Postgres
    participant Cascade as Categorize
    participant Dash as Dashboard API

    Browser->>Imports: POST /imports one PDF
    alt not a PDF
        Imports-->>Browser: 415
    else unreadable or unknown bank
        Imports-->>Browser: 422
    else parsed and committed
        Imports->>Ingest: bytes and filename
        Ingest->>Ingest: sniff then parse
        Ingest->>Ledger: resolve account, insert import, insert new rows
        Ingest-->>Imports: ImportSummary
        Imports->>Cascade: queue pending run
        Imports-->>Browser: 201 counts
    end
    Note over Cascade,Ledger: later, same process, one run at a time
    Cascade->>Ledger: pair, categorize, save
    Browser->>Dash: GET overview or spending detail
    Dash->>Ledger: sum v_transactions_enriched
    Dash-->>Browser: period, totals, breakdowns
```

One upload: reject, or commit then queue. The overview reads whatever the ledger holds when the page loads, including rows still waiting for a category.

### Detect and parse

`detect_adapter` extracts page text with `x_tolerance=1` and asks each adapter in `ADAPTERS` to sniff the first page. The list is BBVA, then CaixaBank. An empty page list, or a file pdfplumber cannot read, raises `UnsupportedStatement`. A readable PDF that neither adapter claims raises the same error and names the supported banks.

| Adapter | Sniff | What a row is | Period | Balance order |
| --- | --- | --- | --- | --- |
| `BbvaPdfAdapter` | Compacted first page contains `EXTRACTODE` and `F.Oper.` | Dated operation line plus the next detail line, stopped at the footer | Calendar month of `EXTRACTO DE <month> <year>` | Ascending, oldest first |
| `CaixaBankPdfAdapter` | Compacted first page contains `ConceptoFechaImporteSaldo` and `Periodo` | One concept-date-amount-balance line | The printed `Periodo` range | Descending, newest first |

Both parse Spanish amounts and dates, store a space-stripped IBAN, and set `merchant` with `normalize_merchant` (leading reference numbers dropped, spaces collapsed, upper case). BBVA joins the concept and the detail with ` | `. CaixaBank has no separate concept. A January value date on a December BBVA statement rolls into the next year, and the reverse rolls back. A header that does not match raises `ValueError` before any insert.

After the rows are built, `check_balance_chain` requires each printed balance to equal the previous balance plus this amount. BBVA walks the file as printed. CaixaBank reverses it first. Fewer than two rows, or any row with no printed balance, skips the check. A break raises `ValueError` that names the bank, the printed index, and both balances, and says nothing was imported. That is the guard against a regex silently dropping a line.

### Account, import record, dedup

`import_statement` does the write in one transaction.

1. Resolve the account by the parsed IBAN. An existing row is reused. A new row is inserted with bank, IBAN, and a display name of the bank plus the last four. The IBAN stays in `accounts` and is not returned by the list routes.
2. Insert `imports`: filename, SHA-256 of the PDF bytes, period, and `rows_total`. The hash is stored. It is not the duplicate check. The same file uploaded again still parses and still tries every row.
3. Build insert tuples in `transaction_rows`, then insert each with `on conflict (dedup_key) do nothing`. `rows_new` is the sum of `rowcount`. `rows_duplicate` is the rest. Both are written back onto the import record.

A new row starts as `income` when `amount > 0`, otherwise `expense`. `category_source` stays the column default `none`. Categorization may later change `tx_type`. Until it does, the dashboard still counts the sign-based type through the money view.

`structure` splits what the cascade reads. For BBVA, `bank_concept` is the text before ` | `. CaixaBank has none. A 12-to-19 digit token is removed from concept and merchant text and kept as `card_last4`. The raw description keeps the digits. The explorer masks them on the way out with `mask_card_numbers`.

The dedup key is a SHA-256 hex digest. Its input is the IBAN, the booking date, the amount to two decimals, the raw description with collapsed spaces and upper case, the printed balance (empty when missing), and the occurrence index of that fingerprint in this file. Two identical movements in one statement get indexes 0 and 1, so both insert. The same movement in a later overlapping statement gets index 0 again and conflicts. A different IBAN is a different key. Spacing and case in the description do not change the key.

## Background categorization

The 201 is already committed when the task runs. FastAPI runs the sync function in its threadpool. `run_categorization_logged` takes a process-wide lock, calls `run_categorization` for pending rows, and logs the summary. Any exception is logged and swallowed. The upload does not roll back, and a later `POST /categorize/run` can queue the same function again. `?all=true` on that route re-runs non-user rows. The import route never passes that flag.

Pending means `category_source = 'none'`. The cascade pairs own-account transfers, applies system rules, and calls jev only when `TYPESAFE_API_KEY` is set. A missing key still pairs and applies rules. Rows jev cannot answer stay pending. User labels are not overwritten. Two uploads cannot categorize at once in this process. A second API process would not share the lock.

Until that run finishes, new rows are visible to the dashboard as uncategorized income or expense. An overview refresh after the upload can therefore change again when the run writes categories, transfer types, and merchants.

## What the web reads

Dashboard SQL does not read `transactions` for money. It sums `v_transactions_enriched`, whose `spend` and `income` follow `tx_type`. Transfers are zero in both. A month with no imported row is `has_data = false`, not a zero. Do not recompute those columns in a page.

Every dashboard read takes the period query: `period` (default `month`), optional `month`, `start` and `end` for `custom`, and repeated `account_id`. `resolve_request` anchors a relative period on the latest `booked_at` of the selected accounts, or today when there is no row. The previous period is the same length. When the latest imported day falls inside the current period, deltas use a cut of that previous period. `has_previous` looks at the whole previous period. The cumulative chart's previous line is the whole previous period, not the cut.

`GET /dashboard/overview` is the home page. KPIs use `totals` with no type filter. Group, category, and merchant charts use `breakdown` on expenses. The current cumulative line is omitted when there is no latest day. `group_slots` ranks groups by all-time spend so a period change does not recolor them. The subscription card is `summary(active_subscriptions)`, which reads `v_subscriptions` and ignores the account filter. The page says so.

`GET /spending/detail` is one scope. The route sets `tx_type`, optional `level1`, `category`, and `merchant_id`. Child rows are categories under a group, merchants under a category (top 10 plus `_other`), and none under a merchant. It also returns five latest transactions, a 12-month series, and the same cumulative pair. The overview's category and merchant charts fold at five. A group chart does not fold.

| Page | Call | Empty state |
| --- | --- | --- |
| `/` | `GET /dashboard/overview` and `GET /categories` | `latest_day` null: "No statements yet", or "No transactions in these accounts" when an account filter is on. Both link to `/imports` |
| `/spending/[group]` | `GET /spending/detail?type=expense&level1=` | Unknown slug is not-found |
| `/spending/[group]/[category]` | same, plus `category` | Unknown category for that group is not-found |
| `/income` and `/income/[category]` | `GET /spending/detail?type=income` | Same detail template. More income is good |
| `/subscriptions` | `GET /dashboard/subscriptions` | Not period-scoped |
| `/transactions` | `GET /transactions` | The explorer. Card numbers in `description_raw` are masked |
| `/imports` | `GET /imports` | "No statements imported yet" |

Pages are `force-dynamic` and fetch with `cache: "no-store"`. Filters travel as search params and are appended by `filterParams` / `withFilters`. The shell's account list and default month come from `filterContext`, which times out at 2 seconds and returns an empty context if the API is down.

A page must not invent a total from `amount`. Income, expenses, savings, and savings rate are already on the overview payload. A spending page uses `total` from the detail payload. Formatting lives in `apps/web/src/lib`.

## Failures that must stay separate

- A non-PDF is 415. An empty, corrupt, or unrecognized PDF is 422. Neither writes an import row or a transaction, and neither queues categorization.
- A balance-chain break or a missing header is the same 422. The transaction rolls back. The error says nothing was imported.
- A second upload of the same movements returns 201 with `rows_new = 0`. It still inserts an `imports` row and still queues a run. The run finds no new pending rows from that file.
- Categorization failing after a good insert still returns 201. The rows stay pending until a later run.
- A foreign `Origin` on `POST /imports` is 403 before the insert. Requests with no `Origin` (CLI, curl, tests) pass. `TrustedHostMiddleware` refuses a request whose `Host` is not in `trusted_hosts`.
- Dashboard reads do not write. A missing custom range is 422 from `resolve_request`. An unknown spending slug is a Next.js not-found, not an empty chart of zeros.

## Adding a bank

A new bank is a new `BankAdapter` in `ADAPTERS`, a `bank` enum value, and a parser that returns `ParsedStatement`. Sniff the first page only. Call `check_balance_chain` with the order the statement prints. Do not put categorization in the adapter. `import_statement` already resolves the account, builds the dedup key, and inserts. Update the upload copy only if the product should name the new bank. The web does not branch on bank for the dashboard.

Do not use the file hash as the duplicate rule. Overlapping statements are deduped per movement. Do not include the occurrence index from a previous file. It is computed only inside the file being imported.

## Verify

From `apps/api`:

- Unit, no database: `tests/test_adapters.py`, `tests/test_bbva_pdf.py`, `tests/test_caixabank_pdf.py`, `tests/test_balance_chain.py`, `tests/test_dedup.py`, `tests/test_importer.py` (the pure `transaction_rows` cases), and `tests/test_api.py` for 415, 422, 403, and a 201 that still reports counts when categorization raises.
- Integration, local Supabase: `tests/test_importer.py` re-imports the sample PDFs and expects the second pass to add nothing. `tests/test_views.py` and `tests/test_dashboard_api.py` lock the read side. `uv run task test-integration` is not CI.

A UI import writes the ledger. Check it with agent-browser on scratch-database recipe R2, named in [CLAUDE.md](../../CLAUDE.md). Do not invent that recipe's steps. Do not describe `data/` or paste statement contents into a test or a page.
