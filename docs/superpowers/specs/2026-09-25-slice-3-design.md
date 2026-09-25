# Slice 3 — money rules, dashboards and the transactions explorer

Date: 2026-09-25
Status: draft for Raul's review
Owner: Raul Vazquez
Amends: `2026-09-22-personal-finance-agent-v1-design.md` (sections listed in 13)
Inputs: `2026-09-25-slice-3-brainstorm-inputs.md` (topics 1-10)
Mockups: `2026-09-25-slice-3-mockups/` (`index.html` plus one PNG per section; fake data)

Slice 3 turns the categorized ledger into something a person reads at a
glance. It first fixes what counts as income, spending and savings (section
2), then builds the overview, the detail pages and the transactions explorer
on views that the slice 4 agent will reuse. Every decision below was taken
with Raul in the brainstorm of 2026-09-25, one topic at a time; Monarch Money
served as the product reference for both the money rules and the look.

## 1. Goals and success criteria

1. **One set of money rules**, written once in SQL views and explained in
   `docs/money-rules.md`, so the dashboards and the slice 4 agent can never
   disagree.
2. **An overview that answers "how am I doing?" in one look**, and detail
   pages one click away for each group, category and merchant.
3. **A transactions explorer** where any row can be found, understood and
   corrected, including a free-text note.
4. **A visual system** (tokens, charts, layout) that later pages reuse.

Slice 3 is done when:

- the view tests pass on synthetic fixtures that cover every rule in section 2;
- `finance eval-categorization` has been run on the new taxonomy (Raul
  approves the paid run first), and its report states the known misses;
- each page in section 7 has passed an `agent-browser` core check, and one
  dogfood pass covers the whole app (report in `dogfood-output/`);
- `docs/money-rules.md` exists and is linked from the README and `CLAUDE.md`;
- the plan's checks for lint, types, build and unit tests are green.

## 2. Money rules

### 2.1 The contract

| Number | Definition |
|---|---|
| Income | Sum of the amounts of income-type rows |
| Expenses | Minus the sum of the amounts of expense-type rows. A refund (money in with an expense category) subtracts |
| Savings | Income − expenses. Money moved to your own savings or investment accounts counts as saved |
| Savings rate | Savings ÷ income. It can be negative, and it is empty when the period has no income. It is never clamped to 0 |
| Out of every total | Transfer-type rows: between own accounts (paired or not), loan money received, and a card settlement once card statements are imported |

**The row type (`transactions.tx_type`)** follows the category, not the sign:
a transfer slug makes a transfer, an income slug makes income, and an expense
slug makes an expense whatever the sign. A row that has not been categorized
yet takes its type from the sign (money in = income, money out = expense).
That keeps the totals complete while rows wait for review; those rows show as
"Uncategorized".

**Spend of a group, category or merchant** is the sum of the spend of its
expense rows, net of refunds. It can be negative in a month when a refund
lands after the purchase month. It is then shown as a negative number in
tables; donut slices only draw positive values.

### 2.2 Refunds take the purchase's category (model B)

This is how Monarch, YNAB and Copilot treat refunds. Example: a person buys
€200 of clothes and returns €80 in the same month. Fashion then shows €120,
and income is unchanged.

1. A refund keeps the category of what it refunds. A money-in row labelled
   `fashion` is a negative expense.
2. A merchant default applies in both directions. The direction checks go
   away: `Taxonomy.fits` in `categorizer.decide`, the direction filter in
   `labels._RELABEL_MERCHANT`, and `review_queue._joins_its_merchant`. The
   review bug that averaged income and expense probabilities for a merchant
   with mixed signs goes with them.
3. **A refund of a card purchase is money in whose bank concept is a card
   purchase** (in BBVA, `PAGO CON TARJETA ...`). For these rows, jev is still
   called, because it resolves the merchant in the same call, but it is shown
   the **expense** options instead of the income ones. After that, the usual
   path applies: the merchant default wins, otherwise the confidence gate
   decides. The list of card-purchase concepts is data in `rules.yaml`.
   - This refines what the brainstorm said ("jev is not asked"): jev has to be
     called anyway for the merchant, and with expense options its suggestion
     is the purchase category, which is also what makes these golden labels
     predictable in the eval.
4. `refunds` stays, for money back with no known purchase, such as cashback
   or a bank bonus. It is income. Its jev criterion is rewritten to say so.
5. Migration. The few existing purchase refunds labelled `refunds` go back to
   review with the new picker, and Raul relabels them. The bank-bonus rows
   keep `refunds`. `tx_type` is recomputed for every categorized row.

### 2.3 Loans

Principle: **loan money received is a liability, never income.**

- New slug `transfer > loan_received`, transfer type, so it is out of every
  total.
- Repayments stay `financial > loan_payment`, an expense. This is the
  cash-flow view, the Monarch default, and what the ledger already does. The
  principal/interest split is not on the bank line, so it is not modelled.
- Known distortion, accepted: when a loan arrives and is spent in the same
  month, that month shows negative savings, which is true (borrowed money was
  spent). Over the loan's life the principal counts once when spent and again
  as repayments. The alternative (repayments as transfers) would overstate
  savings in every repayment month.
- System rules label the fixed BBVA concepts: `ABONO POR DISPOSICION DE
  PRESTAMO` → `loan_received`, `CARGO POR AMORTIZACION DE PRESTAMO` →
  `loan_payment`.
- **Loan identity: one loan = one merchant.** The BBVA lines of a loan carry
  its contract number. A deterministic step after the rules names the
  merchant `Loan ····<last 4 digits>`, so the disbursement and every
  instalment of a contract share one merchant. The user can rename it through
  the existing merchant rename. There is no `loans` table; outstanding
  balance, rate and end date need user input and are v2.

### 2.4 Credit cards without card statements

Card statements are not imported, so the monthly card settlement is the only
trace of what was bought with the card. In the author's ledger it is a
noticeable share of monthly outflow, and it currently vanishes from every
total.

- New slug `credit_card > credit_card_spending`: an expense in its own
  level-1 group, not under `financial`, which would make fees and taxes look
  large. It is the same idea as `cash > atm_withdrawal`: money spent whose
  detail is unknown.
- The settlement rules (`card_settlement_concept`, `card_settlement_text`)
  point to it. So does a new rule for `CARGO POR OPERACION FINANCIADA CON
  TARJETA` (a card purchase paid in instalments).
- When card statements are imported (slice 5 or v2), the rules switch back to
  `credit_card_payment`, which then pairs with the card account as a
  transfer. A per-card setting is not needed until then.
- Accepted loss: there is no category detail inside card spending, and
  subscriptions paid by credit card do not reach `/subscriptions`. Debit card
  purchases are itemized in the account and are unaffected.

### 2.5 Transfers and Bizum

- Own-account transfers are neutral, and both legs are `own_accounts`. That
  holds whether or not the other account is imported. The explorer has a
  saved filter for own-account rows without a pair, because a wrong "own
  account" label hides spending.
- Bizum received is income (`payments_from_people`) and Bizum sent is an
  expense. When a received Bizum repays a shared bill, the user can label it
  with that bill's expense category (for example `restaurants_bars`), and it
  then offsets, exactly like a refund. No new code is needed.

### 2.6 Periods and comparisons

- Periods: a month (default: **the latest month with data**, because
  statements are imported in batches), previous month, last 3 months, year to
  date, last 12 months, custom range.
- Every delta compares with **the previous period of the same length**
  (August vs July, a quarter vs the quarter before). When the previous period
  has no data, the delta is hidden. When the previous value is 0, it reads
  "new".
- A month "has data" when at least one transaction of the selected accounts
  is booked in it. Months without data are drawn as "no data", never as 0.
  Per-account import coverage is v2.
- Delta colour: less spending, more income, more savings and a higher rate
  are good (green); the opposite is red. The arrow and the sign always carry
  the meaning, so it never depends on colour alone.

## 3. Taxonomy and rules (data)

Categories are data (v1 spec section 7): each new slug is a row in
`supabase/seed/categories.yaml` with its `what` / `not_for` criterion.

| Change | Type | Level 1 | Note |
|---|---|---|---|
| add `loan_received` | transfer | transfer | "money a bank or lender pays into the account as a loan or credit line; not income" |
| add `credit_card_spending` | expense | credit_card (new) | "the monthly settlement or instalment of a credit card whose purchases are not itemized" |
| reword `refunds` | income | income | money back with no known purchase: cashback, bonuses. A refund of a purchase takes the purchase's category |
| reword `credit_card_payment` | transfer | transfer | only when the card's own statement is imported |

- New slugs are appended at the end of their type, so the order jev sees
  keeps its meaning. The eval fingerprint changes, so the next eval run
  starts a new baseline line in `docs/evals/HISTORY.md`.
- `rules.yaml`: the settlement rules point to `credit_card_spending`. New
  rules: the financed card operation, the loan disbursement, the loan
  amortization, and the list of card-purchase concepts for section 2.2 rule 3.
- The seed stops only upserting. A rule removed from `rules.yaml` is disabled
  (`enabled = false`), not left running, and `Rule.pattern` is validated with
  `re.compile` when it is loaded. Files are read with `encoding="utf-8"`.
- After the migration, `finance categorize` re-applies the rules to non-user
  rows, so settlements and loan rows move without a paid jev run.

## 4. Data model

One new migration in `supabase/migrations/` (`<timestamp>_slice3.sql`):

- `transactions.note text null`, checked with `char_length(note) <= 500`. A
  note is the user's own account of what a row was ("AirPods Pro" on an
  electronics shop charge). jev never sees it. It reaches the LLM only in
  slice 4, through `v_transactions_enriched`.
- A one-off recompute of `tx_type` from the category, following section 2.1.
- Views (section 5), each with `COMMENT ON VIEW` pointing to
  `docs/money-rules.md`.
- `finance labels export/import` carry `note` (an optional column, so old
  CSVs still import). Without that, a `supabase db reset` would lose notes.
  A bad CSV row prints a readable error instead of a traceback.

Privacy (amends v1 section 2): the LLM receives descriptions, aggregates
**and the user's notes**. jev still sees bank text only.

## 5. Views

All money logic lives here. The API only filters and sums rows these views
already classify.

| View | Grain | Purpose |
|---|---|---|
| `v_transactions_enriched` | one row per transaction | account name, merchant name, `category_slug`, `level1`, `tx_type`, `amount`, `spend` (−amount for expense rows, else 0), `income` (amount for income rows, else 0), `direction`, `is_subscription`, `category_source`, `needs_review`, `note`, `transfer_pair_id`, `month`. The agent's main relation in slice 4 |
| `v_monthly_summary` | month × account | income, expenses, savings, row count. The API sums the selected accounts and then derives the savings rate, because rates are never summed. The rate's formula lives in `docs/money-rules.md` and in one API helper; slice 4 exposes it as a named metric |
| `v_spend_by_category` | month × account × level1 × category × merchant | spend, row count. Group, category and merchant breakdowns aggregate this |
| `v_subscriptions` | merchant | flagged expenses: last charge, typical amount (median), cadence (monthly or yearly from the median gap), monthly equivalent, and whether it is active (charged within 45 days for monthly or 400 days for yearly **of the latest imported transaction**, not of today) |

Daily cumulative series are computed in the API from
`v_transactions_enriched`. `v_review_queue` (deferred in slice 2) is dropped:
the review inbox is served by Python, and slice 4 decides whether the agent
needs one.

## 6. API

Pydantic models at every boundary, and `npm run gen:api` after each change.
Every read takes the same filter parameters: `from`, `to` (or `period`) and
`account_id` (repeatable).

| Method and path | Returns |
|---|---|
| `GET /dashboard/overview` | 4 KPIs for the period and the previous one (with `has_previous`); cumulative daily spend for both; a 12-month series of income, expenses and savings with `has_data`; breakdowns by group, category and merchant (top 5 + other, each with its previous value); a subscriptions summary |
| `GET /spending/detail?type=expense\|income&level1=&category=&merchant_id=` | the scope's total and previous total; monthly series (total and by child); cumulative daily series; the next-level breakdown; top merchants; the 5 latest rows |
| `GET /transactions` | filters: period, `q` (merchant, description, note), `tx_type`, `level1`, `category`, `merchant_id`, `account_id`, `is_subscription`, `category_source`, `needs_review`, `saved=unpaired_own\|refunds`. Pages of 100 with a cursor; totals for the whole filtered set |
| `PATCH /transactions/{id}` | the note (no label history: a note is not a label) |
| `POST /transactions/{id}/label` | as today, plus a direction check: money out rejects an income category (422). Closes M14 |
| `DELETE /merchants/{id}/default` | clears a merchant's default category (for mixed merchants) |
| `GET /dashboard/subscriptions` | active subscriptions and their monthly and yearly totals |
| `GET /categories` | as today, with `tx_type` and `level1`; the web builds the direction-aware pickers |

Removed: `POST /merchants/{id}/merge`, which the web no longer calls. Added:
`TrustedHostMiddleware` (localhost and the configured web host), against
DNS-rebinding reads.

## 7. Web application

### 7.1 Pages

See `2026-09-25-slice-3-mockups/01-page-map.png`. The URL holds the state
(period, accounts, filters as search params), and every link carries it.

| Route | Content |
|---|---|
| `/` | filters row; 4 KPI tiles with delta and an ⓘ definition; "spent this period vs previous" cumulative line; 12 months of income vs expenses bars with a savings line; "Where your money went" (donut + table, with a Groups \| Categories \| Merchants switch, default Groups); one subscriptions line |
| `/spending/[group]` | breadcrumb; total + delta; monthly bars (Total \| By category, Monthly \| Cumulative); categories as a treemap + table; top merchants; 5 latest rows + "See all in Transactions" |
| `/spending/[group]/[category]` | same template; merchants table instead of categories |
| `/merchants/[id]` | total + delta; cumulative vs previous period (default) and monthly bars; transactions |
| `/income`, `/income/[category]` | the same template over income categories |
| `/transactions` | the explorer (7.3) |
| `/subscriptions` | each subscription with amount, cadence, monthly equivalent and last charge; monthly and yearly totals |
| `/review`, `/imports` | existing pages, restyled |
| `/settings` | rename accounts (the existing `PATCH /accounts/{id}`); categories read-only |

### 7.2 Visual system

Direction "Mono" (Revolut-like), with Monarch's structure. The reference is
`2026-09-25-slice-3-mockups/index.html`: layout, hierarchy, tokens and chart forms are the
contract, and the pixel values are indicative.

- **Surfaces and type.** Pure white page; soft grey surfaces (`#F7F7F9`)
  without borders; radius 16 for cards and 999 for pills. Geist with tabular
  numbers; big headline numbers; small uppercase grey labels.
- **Accent.** One accent, indigo `#4F46E5`: links, the current series and the logo dot.
  The active nav item is a near-black pill, as in the mockup. The logo is lower-case "tally ai",
  in one colour and one weight.
- **Money colours.** Income is green with a "+"; expenses are neutral near
  black. Green and red are reserved for deltas and never used for a series.
- **Group palette** (validated with the dataviz validator, light surface):
  `#4F46E5`, `#EB6834`, `#1BAF7A`, `#EDA100`, `#E87BA4`, other `#D4D4DC`.
  Five groups get a colour and the rest fold into "Other". Colour follows the
  group, never the rank. Slots are assigned by all-time spend, so a period
  filter never repaints them, and the Categories and Merchants views paint
  each slice with its group's colour.
- **One-hue ramp** for categories inside a group page: `#4F46E5` → `#DAD8FB`
  (darkest = largest). It is used by the "By category" stacked bars and the
  treemap. Hover shows the name and amount, and clicking a legend item
  isolates it.
- **Charts.** Horizontal grid lines, recessive axes, a legend for 2 or more
  series, tooltips on hover, and months without data drawn as dashed "no
  data" boxes. There are no dual axes; the savings line shares the € axis.
- **Tokens** live in `globals.css` as the shadcn CSS variables (`--primary` =
  accent, `--chart-1..5` = group palette, plus a `--ramp-1..6` set). Light
  mode only in slice 3.
- **Layout.** Top navigation bar with a pill for the active item, and the
  filters on the right. On phones the nav scrolls horizontally; a bottom tab
  bar is later.
- **The UI explains itself.** Every edit field has a one-line
  `FieldDescription`, and every KPI has an ⓘ tooltip whose text comes from
  `docs/money-rules.md`. For example, the note field says: "What did you buy
  or what was it for? For example 'AirPods Pro'. The AI uses it to answer
  your questions." UI copy is in English.
- Empty state: with no imported data, the overview links to `/imports`.

### 7.3 Transactions explorer

- **Rows.** Rows are grouped by day, and each day header shows that day's
  net. Each row has the merchant (the note as a muted second line), group ·
  category, account, amount, a subscription mark, and a small source dot with
  text: Rule / Merchant / AI (jev) / You / Pending.
- **Filters.** Visible: period, search, type, group or category, merchant,
  account. Under "More filters": subscription, source and needs review. Two
  saved filters: "Own-account transfers without a pair" and "Refunds" (money
  in with an expense category). Pages of 100 with "Load more".
- **Side panel** (shadcn `Sheet`), opened by clicking a row. It edits the
  category, merchant, subscription flag and note. On save it asks "Apply to
  all transactions of this merchant?" (yes sets the merchant default). It
  also has a "Clear merchant default" action.
- **Direction-aware pickers** everywhere (`/review`, the panel, the filters):
  - money out offers expense and transfer categories;
  - money in offers income first, then a "Refund of a purchase" group with
    the expense categories, then transfers.

## 8. Libraries

**Charts: Recharts 3, through the shadcn/ui `chart` component.** This
confirms the v1 spec's assumption, checked on 2026-09-25.

- **It fits our stack.** It is the only candidate with an official shadcn
  component for our `base-nova` style (`registry/base-nova/ui/chart.tsx`).
  That component provides ChartContainer, ChartTooltip(Content),
  ChartLegend(Content) and a `ChartConfig` that emits one CSS variable per
  series.
- **It draws every chart we need.** Pie with a centre label, stacked bars
  (`stackId`), area and line, bars + line (`ComposedChart`) and `Treemap`.
  It renders SVG, so our CSS variables apply directly.
- **It is widely used and actively maintained.** About 42M weekly downloads,
  and regular 3.x releases through 2026.
- **The alternatives lose on fit or maintenance:**

  | Library | Why not |
  |---|---|
  | Tremor | Maintenance mode since Vercel acquired it, React 18, Radix-based |
  | Nivo | One maintainer, no release in over a year |
  | visx | Low-level: axes, tooltips and legends are ours to build |
  | ECharts, Chart.js | Canvas; CSS variables have to be read in JS |
  | MUI X | A second design system |
  | AG Charts | Treemap is paid |
  | Unovis | Little adoption |

- **Risks:** no company backs Recharts, and it adds about 150 kB gzip to
  the dashboard routes.

Install, from `apps/web`:

```bash
npx shadcn@latest add chart --dry-run
npx shadcn@latest add chart
npm install react-is@<same version as react>
```

Keep the Recharts version that shadcn installs, and upgrade it on purpose,
in its own change.

Gotchas the plan must handle:

1. **`react-is`.** It must match the React version. Today a 16.x copy comes
   in through eslint-plugin-react, so install it explicitly.
2. **Chart height.** `ChartContainer` is a client component that measures
   itself, so it always needs a height, `min-h-*` or `aspect-*` class.
3. **Colour values.** Colours are written as `var(--chart-1)`, not
   `hsl(var(...))`. The current `--chart-*` tokens are greys and are replaced
   by the palette in 7.2.
4. **Treemap.** It needs its own `content` renderer (rectangle and text,
   with no label on small tiles), and its tooltip must be tested.
5. **Legend isolation.** It is ours to build: keep a hidden-series state,
   pass `hide` to the series, and render legend items as
   `<button aria-pressed>`.
6. **No-data months.** They are sent as `null`, never 0.
7. **Examples online.** Many are written for Recharts v2 and break on v3;
   use the v3 docs.

**No other UI libraries in slice 3:**

- Filters live in plain Next `searchParams` with one parse helper; nuqs only
  if client-side controls multiply.
- The explorer uses the plain shadcn `Table`, with server pagination;
  TanStack Table only for column toggles or row selection.
- `Intl` formats money and dates, and period maths lives in the API; no date
  library.

Sources:
- https://ui.shadcn.com/docs/components/base/chart
- https://recharts.github.io/api/Treemap
- https://recharts.github.io/guide/sizes
- https://vercel.com/blog/vercel-acquires-tremor

## 9. Slice-2 follow-ups and debt

Criterion: an item is in if it touches code this slice changes anyway, if it
falsifies the numbers, or if it is cheap.

**In slice 3.**
- The seed disables removed rules; patterns are validated at load (section 3).
- M11: a merge applies the survivor's default to the moved rows.
- M13: labelling one side of a transfer pair unpairs both, and the other side
  goes to review.
- M14 is closed by the direction check (section 6).
- M10: check it is closed; add a test if it is.
- `/review`: expanded lines show the description (dogfood issue 002), and a
  surviving merchant's own item leaves the page after a merge and confirm
  (inputs topic 6).
- Reword the `/review` "run `finance categorize`" hint so it does not invite
  a parallel paid run.
- `TrustedHostMiddleware`; remove `POST /merchants/{id}/merge`.
- `labels import`: a readable error on a bad row.

**Later.**

| Item | Target |
|---|---|
| Topic 3: remember a label by merchant + exact amount | after measuring with the eval, v2 |
| M8 accent folding in `match_key`; M12 brand gate | measure first, slice 5 |
| M7 orphan merchants; `save()` during an `--all` run; CLI exit codes | slice 5 hardening |
| Card statement import (`credit_card_payment` pairing) | slice 5 or v2 |
| Dark mode (its own validated steps) | v2 |
| Mobile bottom tab bar; `/review` phone layout | v2 |
| Loans table (balance, rate, end date); splits; CSV export | v2 |
| Semantic layer and agent | slice 4 (section 12) |

## 10. Documentation deliverables

- `docs/money-rules.md`: section 2 written for users and future agents, with
  the worked examples (refund, loan, card settlement, Bizum) and the reason
  behind each rule. It is linked from the README and `CLAUDE.md`, and the
  views reference it.
- The v1 spec gets a "Slice 3 amendments" pointer to this document in
  section 16.
- `docs/evals/HISTORY.md` gets the first line on the new taxonomy.
- The README showcases jev with its results, as before; screenshots use the
  fake-data mockups, never real data.

## 11. Testing and verification

- **Unit tests (no DB):** `Taxonomy.tx_type_of` by category; the refund
  option switch in the jev questions; the loan contract parser; the seed
  disabling removed rules; the pattern validation; delta and period helpers
  (previous period of equal length, has-data, "new").
- **Integration tests (local Supabase):**
  - one synthetic fixture month covering a purchase + refund, a
    cross-month refund, a loan disbursement + instalments, a card settlement,
    a paired and an unpaired own transfer, a Bizum repayment relabelled as an
    expense, and an uncategorized row;
  - the view totals asserted by hand;
  - `GET /dashboard/overview`, `GET /spending/detail` and `GET /transactions`
    (filters, cursor, totals) on that fixture.
- **Eval:** `finance eval-categorization --note "slice 3 taxonomy"` after
  Raul approves the paid run. The report lists the refund rows as known
  misses if any remain.
- **UI:**
  - an `agent-browser` core check per page (overview, group, category,
    merchant, income, transactions with an edit, subscriptions, settings);
  - one dogfood pass before merge;
  - mutating checks on the scratch database recipe, and real-data checks
    read-only.

## 12. Handoff to slice 4

Slice 4 opens with its own semantic-layer brainstorm. It starts from these
facts:

- the views in section 5 are the agent's relations;
- `docs/money-rules.md` is the source for their descriptions, including the
  "not for" parts (a received loan is a liability, never income; transfers
  are out of every total);
- `note` is the user's own account of a row, more reliable than the bank
  text, and searchable;
- a loan is a merchant named `Loan ····NNNN`, so the agent can list loans,
  the paying account, the instalment, the number paid and the total paid.

## 13. Changes to the v1 spec

| v1 section | Change |
|---|---|
| 2 Principles | the LLM also receives the user's notes |
| 3.2 Schema | `transactions.note`; `tx_type` follows the category; views as in section 5; `v_review_queue` dropped |
| 5 Cascade, 5.3 Defaults | defaults apply in both directions; the card-refund option switch; the loan merchant step |
| 6 Subscriptions | "active" is relative to the latest imported transaction |
| 7 Taxonomy | `loan_received`, `credit_card_spending` (new level 1 `credit_card`), `refunds` and `credit_card_payment` reworded |
| 10 API | section 6 of this document |
| 11 Web, 11.1 Review | section 7; the one-off refund rule from the slice 2 amendments is removed |
| 14 Slices | slice 3 is delivered as two plans (section 14) |

## 14. Delivery

Two plans, each ending merged and usable:

- **3a — money rules and data** (API). Taxonomy and rules, cascade changes,
  loan merchant step, migration (note, `tx_type`, views), labels
  export/import with notes, the API endpoints in section 6, the backend debt
  items, `docs/money-rules.md`, tests and the eval run.
- **3b — interface** (web). Tokens and layout, chart components, overview,
  detail pages, income, explorer with side panel and pickers, subscriptions,
  settings, `/review` fixes and restyle, `agent-browser` checks and dogfood.

3b starts after 3a is merged, because it consumes the generated API types.

## 15. References

- Monarch Money help center (read on 2026-09-25 through its public help-center
  API):
  - categories: https://help.monarch.com/hc/en-us/articles/360048883851
  - credit card payments and transfers: https://help.monarch.com/hc/en-us/articles/360048393292
  - refunds: https://help.monarch.com/hc/en-us/articles/46420712538260
  - debt payments: https://help.monarch.com/hc/en-us/articles/44373293932052
  - rules: https://help.monarch.com/hc/en-us/articles/360048393372
  - cash flow: https://help.monarch.com/hc/en-us/articles/20504904768020
- Monarch and Revolut screenshots were used during the brainstorm and are not
  stored in the repo (third-party images). The mockups in
  `2026-09-25-slice-3-mockups/` are original, with fake data.
