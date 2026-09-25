# Slice 3 — brainstorm inputs

Date: 2026-09-25
Status: input for brainstorming, not a design. Nothing here is decided unless
it says so.

Raul reviewed the first real month in `/review` after slice 2 and raised the
points below. The small fixes went into the review-fix PR before slice 3
(v1 spec, "Review fixes before slice 3"). What is left needs its own
brainstorm, ideally one topic per session, before the slice 3 spec amendment
and plan. Each topic says what exists today, what was asked, the open
questions and, where there is one, a recommendation to start from.

Suggested order: topics 2 (refunds), 8 (loans) and 9 (credit card
settlements) answer one question, what counts as income and as spending, so
brainstorm them first, perhaps together; they decide how the dashboards
(topic 4) add up. Topic 7 follows topic 2. Topic 1 can go in parallel, but its
"type" filter depends on the tx_type rule topic 2 picks. Topic 10 is probably
v2.

## 1. Transactions list with categorization and filters

**Today.** `/transactions` shows date, account, description (or merchant
text), `tx_type` and amount, with a month filter. `GET /transactions` filters
by month and account; spec section 10 also lists category and
`needs_review`, which were never implemented. The page caps at 1,000 rows.

**Asked (Raul: "imprescindible").** Every row shows the merchant, level 1,
level 2, whether it is a subscription and how it was categorized (system
rule, jev, merchant default, the user, or still pending review). Filters for
each of those, plus type (expense, income, transfer), month and account.

**Starting point.** Build the list on `v_transactions_enriched` (spec 3.2),
which is already planned for the chat agent in slice 4: one view shared by
the list, the dashboards and the agent.

**Open questions.**

- Can a row be corrected from `/transactions`? Today `/review` is the only
  place that edits, and it only shows pending rows: a row accepted
  automatically (jev at 0.95 or more, or a merchant default) cannot be fixed
  from the UI, and neither can a merchant default. Clearing a default (for a
  mixed merchant, topic 3) is SQL only. The label endpoint
  (`POST /transactions/{id}/label`) already exists.
- Pagination or a higher cap, once several years are imported.
- Useful saved filters: transfers the user marked `own_accounts` that never
  paired, refunds (topic 2).

## 2. Refunds: how they are categorized and counted

**Today.**

| Situation | What happens |
|---|---|
| jev categorizes a money-in row | its options are the income slugs plus transfers, so a refund can only be `refunds`, `other_income`, ... |
| the merchant has a default (a clothes shop = `fashion`) | a default only applies in its own direction (`taxonomy.fits` in `categorizer.decide`): it never labels a refund |
| `/review`, merchant with a default | the refund is a one-off item (`review_queue._joins_its_merchant`) |
| `/review`, merchant without a default | the refund is grouped with the purchases: the item total mixes signs and the suggestion averages income and expense probabilities (a bug) |
| confirming that merchant item | `_RELABEL_MERCHANT` relabels only rows whose direction fits, so the refund silently stays pending while the row disappears from the page |
| the user labels a refund with an expense category | accepted; `tx_type` follows the sign, so it counts as income (follow-up M14) |
| dashboards | not designed yet; `refunds` sits under level 1 `income`, so refunds would inflate income |

**Evidence.** In the author's ledger every money-in row whose bank concept is
a card purchase ("PAGO CON TARJETA ...") was a refund (4 of 4). jev scored one
of them as `other_income` at 0.26. The user labelled one with the purchase's
category, without noticing it was money in, which is why review rows now show
the direction.

**Model A: a refund is income (`refunds`), as today.** Simple and in place.
Returning a purchase does not lower that category's spend, the income total
must exclude `refunds` by hand, and a merchant default never helps, so every
refund goes through jev or review.

**Model B: a refund takes the purchase's category and offsets it
(recommended).** This is how budgeting apps such as YNAB and Monarch treat
refunds.

- `tx_type` follows the category, not the sign: a money-in row labelled
  `fashion` is a negative expense.
- A merchant default applies in both directions, so a shop's refunds take its
  category without review.
- `refunds` stays for money back whose purchase category is unknown (no
  merchant, cashback).
- The direction checks go away: `taxonomy.fits` in the categorizer, the
  direction filter in `_RELABEL_MERCHANT`, the one-off rule in the review
  queue, and the mixed-sign grouping bug with them.
- Dashboards: spend per category is the sum over expense rows, refunds
  subtract; income is real income only.

Costs and questions for B:

- Spec sections 3.2 (`tx_type`), 5 and 5.3 (defaults), 7 (the meaning of
  `refunds`), 11.1 (the one-off rule from the slice 2 amendments).
- Eval: the dry run ignores merchant defaults and jev only sees income
  options for money-in rows, so a golden label with an expense category on a
  refund cannot be predicted. Options: give jev the expense options for
  money-in rows with a card-purchase concept, add a rule, or accept a few
  misses and say so in the report.
- A deterministic rule "money in + card-purchase concept = refund" fits spec
  section 5, but system rules today skip jev and leave the merchant empty; a
  refund should keep its merchant.
- Existing labels: the few `refunds` labels and the one refund labelled with
  its purchase category are migrated under the chosen model.
- Related follow-ups from PR #5: M13 (labelling one side of a pair) and M14
  (labels whose category does not fit the direction).

## 3. Mixed merchants whose category depends on the price

**Today (decided in the review-fix PR).** A merchant whose charges differ in
category only by price, for example a device insurance plan and a storage
plan billed under the same bank text, keeps no default and is labelled line
by line. jev usually scores such charges below the 0.95 gate, so each new one
reaches `/review`; a confident wrong guess is the residual risk.

**Candidate.** Remember a user label by merchant and exact amount: a new
charge of the same merchant and amount takes that label; a price change goes
to review. Questions: is it worth a cascade step now (after merchant
defaults, before the gate)? Which `category_source` does it write? How does it
relate to the recurrence detector left for v2 (spec 12) and to
`/subscriptions`? Measure it with `finance eval-categorization`.

## 4. Dashboards, as planned in the spec

Views (`v_monthly_summary`, `v_spend_by_category`, `v_subscriptions`,
`v_transactions_enriched`, and `v_review_queue`, deferred from slice 2), the
`/` overview, `/subscriptions` and a minimal `/settings` (spec 11, 14).
Decide with topics 2, 8 and 9 how refunds, loans, credit card settlements and
transfers enter income, expenses and the savings rate. Transfers the user marked `own_accounts` but that never paired
still count as transfers, so they stay out of both totals.

## 5. Follow-ups from PR #5 (slice 2 final review)

Data or product decisions:

- Orphan merchants (nothing references them) keep winning exact-key matches;
  clean them up (M7).
- `match_key` / `tokens_of` drop accented letters instead of folding them;
  folding changes stored keys for non-ASCII names (M8).
- Confirming a merchant item with another merchant picked overwrites that
  merchant's default (M10). Since the review-fix PR, Merge always goes
  through the confirm, so the survivor's default is the confirmed category by
  design (spec 5.3); check whether M10 is closed.
- A merge does not apply the survivor's default to the moved rows (M11).
- The brand gate still drops low-brand new names before the shortlist;
  measure with the eval first (M12).
- Labelling one side of a transfer pair leaves the counterpart as
  `own_accounts` (M13); labels whose category does not fit the direction are
  accepted (M14). Both depend on topic 2.
- CLI exit-code policy for `finance categorize` when skipped or when every
  row fails.

Hardening and tests:

- Seed only upserts (a removed rule stays enabled); validate `Rule.pattern`
  with `re.compile` at load; `read_text(encoding="utf-8")`.
- `save()` guards only `category_source = 'user'`; a merchant confirm during
  an `--all` run can be overwritten.
- Tests: card-regex edge cases (11, 12 and 19 digits, glued digits,
  CaixaBank), criteria order pinned, label and merge writes, merge-suggestion
  SQL and the confirm happy path, labels round-trip fields.
- `labels import` prints a raw traceback on a bad row; an empty CSV merchant
  keeps jev's merchant as the user's.
- `/review` polish: combobox accessible names, row fade-out, dogfood issues
  001–003 (clipped Duplicate column on `/imports`, expanded lines without a
  description, descriptions on phones).
- Reword the `/review` "not categorized yet — run `finance categorize`" line
  so it does not invite a parallel paid run while a background run is in
  progress; Swagger `/docs` writes get 403 (its origin is not in
  `cors_origins`); `*` in `CORS_ORIGINS` would block the web app's writes;
  add `TrustedHostMiddleware` against DNS-rebinding reads; document that
  merchant-confirm relabels come back as `user` after a restore.

## 6. Left over from the review-fix PR

- After a merge and confirm, if the surviving merchant also has its own item
  in the queue, that item stays on the page until a reload.
- `POST /merchants/{id}/merge` is no longer called by the web app: keep it for
  API clients or remove it.
- Expanded review lines show date, amount and account but no description
  (dogfood issue 002); it matters most for mixed merchants.
- On phones, a single-transaction review row hides its account to keep the
  amount visible.

## 7. Category options follow the direction (UI)

**Today.** The taxonomy already keeps income and expense categories apart
(spec section 7): 45 expense slugs, 7 income slugs and 3 transfer slugs, and
jev only sees the slugs of the row's direction plus the transfers. The
category pickers in `/review` (merchant row and expanded lines) list all 55,
and the API accepts any category for any row (follow-up M14).

**Asked.** A money-in row should offer income categories, not expense ones.

**Open questions.**

- Filter strictly (money in: income and transfer slugs; money out: expense
  and transfer slugs), or list the row's direction first and the rest under
  an "Other" group?
- It depends on topic 2: with model B a refund (money in) takes an expense
  category, so a strict filter would hide the right answer; with model A a
  strict filter plus a server-side check (closing M14) is consistent.
- Whatever is chosen applies to every picker, including `/transactions` if
  topic 1 makes rows editable there.

## 8. Loans received and repaid

**Today.** `financial > loan_payment` (expense) covers repayments; nothing
covers money received from a loan. Observed in BBVA statements:

| Bank concept | Direction | What the categorizer did |
|---|---|---|
| `ABONO POR DISPOSICION DE PRESTAMO/CREDITO` (disbursement) | money in | jev: `other_income` at 0.83, sent to review |
| `CARGO POR OPERACION FINANCIADA CON TARJETA` (same day, a different amount) | money out | jev: `credit_card_payment` at 0.43, sent to review |
| `CARGO POR AMORTIZACION DE PRESTAMO/CREDITO` (monthly repayment) | money out | labelled `loan_payment` by the user |

The two review rows stay pending until this topic is decided.

**Open questions.**

- A slug for the disbursement. It is not income (it is paid back), so a
  transfer-type slug that stays out of both totals (for example
  `transfer > loan_received`) is the likely fit. Categories are data: a seed
  row with its `what` / `not_for` criterion, measured with
  `finance eval-categorization`.
- How repayments count: all of it as spending (the cash-flow view, today's
  behaviour and the simplest), or the principal as a transfer and only the
  interest as spending (the bank line does not split them). If what the loan
  paid for is also recorded as an expense, counting both it and the
  repayments counts the principal twice; decide which one the dashboards
  show.
- All three concepts are fixed by the bank and name no merchant, so system
  rules (spec 5) can label them deterministically once the slugs exist.
- The financed card operation depends on topic 9.

## 9. Credit card settlements when card statements are not imported

**Today.** The monthly settlement of a credit card (`ADEUDO MENSUAL DE
TARJETA`, `T. VISA ...`) is labelled `transfer > credit_card_payment` by a
system rule, so it stays out of income and spending. That is right when the
card's own statement is imported too: its purchases are the expenses and the
settlement only moves money between two accounts. But card statements are
not imported, so everything paid with the card would vanish from the
dashboards.

**Options.**

- **A. Import card statements.** One adapter per card statement format;
  purchases are categorized one by one, and the settlement pairs with the
  card account as a transfer. The complete fix, and the most work (slice 5 or
  v2).
- **B. Until then, a settlement is spending.** A new expense slug for card
  spending that is not itemized (for example
  `financial > credit_card_spending`), and the system rules point to it. When
  card statements arrive, the rules switch back to `credit_card_payment` and
  pairing takes over.
- **C. A setting per card** ("statements imported: yes or no") that decides
  the slug. More flexible, more configuration.

Recommendation to start from: B now, A later. The settlements already labelled
`credit_card_payment` move to the new slug.

## 10. User notes on a transaction (probably v2)

The bank text names the shop, not what was bought: a phone bought at an
electronics retailer shows only the retailer. Candidate: a free-text note (or
tags) per transaction, editable wherever rows are edited (topic 1), shown in
the list and searchable by the chat agent ("how much did the phone cost?").
Related v2 ideas: splitting one charge into several categories, and receipts
(spec section 12). Notes would reach the LLM through the semantic layer, as
descriptions already do.
