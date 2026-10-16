# Quality of life — closing the first phase

Date: 2026-10-14
Status: design, ready for the two plans
Owner: Raul Vazquez
Inputs: `docs/superpowers/specs/2026-10-14-quality-of-life-inputs.md` (the 2026-10-11 /
2026-10-12 brainstorm). Code checked against `main` at `20a3c79` (slice 4b merged).

This closes the first usable phase: subscriptions tell the truth, folded rows open, every
transaction list can be corrected, and the merchant page and the review inbox become places
where a decision sticks. The chat agent reads the same rules. It does not add chat features.
The accepted gaps of plan 4b stay accepted.

## 1. Delivery

One spec, two plans, two PRs. Each plan runs in a clean session with subagent-driven
development.

| Plan | Blocks | PR |
|---|---|---|
| `docs/superpowers/plans/2026-10-14-qol-1-baseline.md` | A, B, C, D | first |
| `docs/superpowers/plans/2026-10-14-qol-2-merchant-review.md` | E, F, G | second, after the first is merged |

The merchant page (E) reuses the cadence control (A) and the default category (C). Plan 2
does not rebuild them.

## 2. Decisions taken while writing this spec

Raul approved the scope, the Postgres home for the rules, the subscription rule, the
subscriptions page, and the folded-row behaviour. The rest of this spec records the calls
made so the plans can be written without another design round. A change to one of them is a
change to this spec.

| Topic | Call |
|---|---|
| Where a cadence lives | `merchants.cadence`, null means auto |
| Stored cadence values | `monthly`, `quarterly`, `yearly`. The UI says "Every 3 months" for `quarterly` |
| Amount column | `latest_amount`. `typical_amount` goes away in the view, the API and the agent |
| Who wins a merge | The survivor's cadence, category and subscription flag. The source fills only a null |
| Ended subscriptions | The view already has `active`. The API returns them separately. Totals ignore them |
| Active window, quarterly | 120 days, not "about 120" |
| Same-day charges | The largest charge that day is the latest amount |
| Folded children | On `BreakdownRow.rows`, only for `_other`. Shares stay shares of the period total |
| Children's deltas vs the subtotal | They may disagree. A key that disappeared is inside the subtotal and is not a row |
| No merchant | URL and API value `merchant_id=none`. The label picker does not offer it |
| Panel | One component, used by `/transactions` and every detail page's latest list |
| Unsaved close | Ask. Dirty means the category, the merchant, the subscription flag or the note changed |
| Search | 300 ms, `router.replace`, so typing does not fill history. Enter flushes at once |
| Group subtitle | Top 3 categories by spend in the period, slug as the tiebreak, on overview group rows only |
| Several categories on one merchant | `category_count` from the breakdown query. Hint names no single category |
| Delta cap | A percent change above +999 shows `>999%`. A change from 0 stays "new". Negatives are not capped |
| Mobile nav | Below `sm`, a Menu button opens a sheet. From `sm` up, the row stays |
| Cash-flow line | Keep in and out. Add the transfer sum and an info button |
| Merchant page period | A URL with none of `period`, `month` or `start` redirects to `last_12_months`, keeping the other params. The period picker always writes the `period` it picked, `period=month` included, so "Latest month" stays a month on a merchant page |
| Rename without a category | A rename or merge does not require a default category. Extract the existing name logic |
| Default change count | `rows_a_default_would_change` counts the rows the relabel can touch (`category_source` `jev`, `merchant` or `none`). The card says "up to", because money out never becomes income |
| Subscription switch | Goes through the existing review endpoint, so it relabels like a default change and those rows join the golden set. The card says so |
| Display names | `name` on each category and `_name` on each group in the seed YAML. `finance seed` writes them. jev criteria stay `what` / `not_for`, and the eval fingerprint ignores the names |
| Missing name | The readable slug, at read time |
| Where names show | Every category and group label in the web goes through `categoryName(slug, categories)` or `groupName(level1, categories)`. `label(slug)` stays the slug fallback only |
| Colours | Slots 1–8 are stable hues. Later ranks are distinct greys. `uncategorized` is ranked like any group. The folded row is a hatch, not a group grey |
| Light mode | The app is light. Dark chart tokens are updated so a forced dark class does not collapse the palette. No theme toggle |
| Review cards | A merge suggestion is its own card. A category card holds only rows with `needs_review` |
| Review count | `ReviewCount` gains `categories` and `merges` and keeps `uncategorized` |
| Merge Yes | Calls the merge, which coalesces the default. It does not relabel every row as a user label. The source's own category card leaves the list with it |
| Review filter, sort, skip | Client state on the loaded list. Skip is `sessionStorage`. Help open/closed is `localStorage` |
| Nav highlight on a merchant | Stays Overview. The shell comment already says merchant pages sit under it |
| Breadcrumb | Stays "Overview › merchant" |
| Chat gaps from plan 4b | Out of this spec |

## 3. Subscriptions (A)

### 3.1 Rule

`v_subscriptions` is the only place the rule is computed. `docs/money-rules.md`, the overview
card and `/subscriptions` describe this rule and no older one.

A row counts when it is flagged, money out, an expense, and has a merchant. Refunds and
transfers do not. Card-paid subscriptions stay absent, because card statements are not imported.

Detection uses the median gap between charges of that merchant. A single charge has no gap
and is monthly. Up to 60 days is monthly. From 61 to 200 is every 3 months. Over 200 is
yearly. `merchants.cadence` wins whenever it is set. Clearing it returns to detection.

The amount is the charge on the latest `booked_at`. Two charges that day: the larger one.
The monthly equivalent is that amount divided by 1, 3 or 12, rounded to the cent. The yearly
total is twelve times the monthly total of the active rows, so an every-3-months plan counts
as four charges a year.

Active is measured from the latest imported transaction, not from today. The windows are 45,
120 and 400 days.

### 3.2 Storage and merge

```sql
alter table merchants
  add column cadence text check (cadence in ('monthly', 'quarterly', 'yearly'));
```

Null means auto. `merge_merchants` sets
`cadence = coalesce(i.cadence, s.cadence)` in the same update that already coalesces
`category_slug` and `is_subscription`.

### 3.3 View and agent

`v_subscriptions` exposes `merchant_id`, `merchant_name`, `charges`, `last_charge`,
`latest_amount`, `cadence`, `cadence_source` (`user` or `auto`), `monthly_equivalent`,
`active`. `agent.subscriptions` is the same projection without `merchant_id`, and its YAML
describes the new rule, including that a user-set cadence wins. The example query that
selects `typical_amount` selects `latest_amount` and `cadence_source`.

### 3.4 API

`GET /dashboard/subscriptions` returns `items` (active, largest monthly equivalent first),
`ended` (the rest, same order) and `monthly_total` / `yearly_total` from `items` only. The
overview summary keeps using the active totals.

`PATCH /merchants/{id}/cadence` with `{ "cadence": "monthly" | "quarterly" | "yearly" | null }`.
404 if the merchant does not exist. 422 if the value is anything else. Saving a cadence does
not flag or unflag the subscription.

### 3.5 Page

Desktop columns: merchant, cadence, latest amount, per month, last charge. Below `sm` the
row shows the merchant, the cadence select, per month and the last charge.

The select has Auto, Monthly, Every 3 months, Yearly. Auto shows "Auto · Monthly" (or the
detected cadence), and plain "Auto" when nothing is detected yet (a merchant page without
flagged charges). A user-set value shows only that value. Auto sends null. The control is
named "Cadence for {merchant}". It disables while the request runs, restores the previous
value on failure, and keeps focus. A success refreshes the page, so a row can move between
the active list and Ended.

Ended is a collapsed block, "Ended (N)", under the active list. It is absent when N is 0.
The text says these left the list because the last charge falls outside the cadence window,
and that changing the cadence can bring one back. The same select is on each row.

The merchant name links to `/merchants/{id}?period=last_12_months` with no account filter.

## 4. Folded rows (B)

These lists fold today: overview Categories and Merchants (top 5), top merchants on a group
page (top 5), merchants on a category page (top 10), top merchants on Income (top 5). The
overview Groups view does not fold. `BreakdownTable` grows the button, so any later folded
row gets it too.

`BreakdownRow` gains `rows`, empty except on `_other`, where it holds the folded rows. Each
child keeps the share, amount and previous amount it had before folding. Share is of the
period total. The `_other` row stays the subtotal, with the delta the server already
computes, which includes keys that disappeared. Those keys are not listed. The donut keeps
drawing the top-level slices only.

The folded row has a button "Show N merchants" or "Show N categories", `aria-expanded`. A
second click hides them. Children render under it, indented, and link the way a visible row
links. The open state is component state. A reload folds again. It is not in the URL.

A merchant row whose key is `category:{slug}` links to Transactions for that category with
`merchant_id=none`, keeping the period, the accounts and the type. The merchant filter on
`/transactions` offers "No merchant" at the top, and only there. The label picker still uses
an empty id to create a merchant.

`GET /transactions` accepts `merchant_id` as a UUID or the literal `none`
(`merchant_id is null`). Anything else is 422. The shared `WHERE` fragment learns this, so
every dashboard read can express it. Only the explorer sends it.

## 5. Transaction panel (C)

`TransactionPanel` and the table that opens it move to one component used by
`/transactions` and by the latest-transactions card on group, category, merchant and income
pages. Saving already calls `router.refresh()`, so the page totals reload.

The category field's description leads with "Group › Category" when one is selected, then
the sentence it already has. Plan 1 builds that line with the slug labels. Plan 2's names
flow through the same `label` helper, so the line updates without a second layout change.

When the row has a merchant, a line under the category reads "Saving can apply this category
to every transaction of {name}." It is visible before Save. The confirm dialog stays as it
is: user labels and rule labels are kept, and money out never becomes income.

Closing with unsaved edits asks "Discard unsaved changes?" with Keep editing and Discard.
Dirty is a change to the category, the merchant, the subscription flag or the note. Escape,
the backdrop and Cancel all go through that question. A clean panel still closes at once.

## 6. Small fixes (D)

**Search.** The transactions box waits 300 ms and then writes `q` with `router.replace`.
Enter writes it at once. Clearing the box still clears `q` at once. Back no longer walks
each keystroke.

**Merchant filter hint.** Under the filter, when more than 50 merchants match,
"Showing 50 of N · type to search". N is the number of matches, which is the full list
before any typing. The hint is the field's description. The label picker does not show it.

**Group subtitles.** Each overview group row carries `top_categories`, at most three slugs,
ordered by spend in the period (slug as the tiebreak). The line under the group uses those,
not the first categories in the taxonomy. Other pages keep the current hint.

**Several categories.** The merchant breakdown counts distinct categories. When the count is
greater than one, the hint is "2 categories · N transactions" and does not name one of them.

**Deltas.** In `delta`, a percent change greater than 999 becomes the text `>999%` and keeps
its up direction and tone. A previous amount of 0 still reads "new".

**Mobile navigation.** Below `sm`, the scrolling row is replaced by a Menu button that opens
a sheet with every link. Review keeps its badge. The active link is `aria-current="page"`.
Closing the sheet returns focus to the button. From `sm` up, nothing about the row changes.

**Transactions header.** In and out stay. The totals query also returns `transfers`, the sum
of `abs(amount)` for `tx_type = 'transfer'` in the filtered set. When that sum is above zero
the header adds "incl. €X transfers". An info button, always there, explains that in and out
are cash flow, transfers and refunds included, while Overview income and expenses leave
transfers out and net a refund against its purchase.

## 7. Merchant page (E)

Opening `/merchants/{id}` with none of `period`, `month` or `start` redirects to the same URL
with `period=last_12_months`, preserving `type`, accounts and anything else. The period
picker then matches the numbers. A link that already sets a period or a month, including the
one from `/subscriptions`, does not redirect.

The default period is written by leaving `period` out, so without a change "Latest month"
on a merchant page would redirect back to 12 months. `periodChanges` therefore always writes
the period it picked, `period=month` included. Every page already reads `period=month` as
the default, and links built by `filterParams` still leave it out.

`GET /merchants/{id}` returns the profile:

| Field | Meaning |
|---|---|
| `id`, `name` | The merchant |
| `category_slug` | The default, or null |
| `is_subscription` | The stored flag, or null when jev decides per row |
| `cadence` | The override, or null for auto |
| `cadence_effective`, `cadence_source` | From `v_subscriptions` when the merchant has flagged charges, otherwise null |
| `rows_a_default_would_change` | Rows of this merchant whose `category_source` is `jev`, `merchant` or `none`: the rows `_RELABEL_MERCHANT` can touch |

404 when the id is unknown. The page shows a controls card above the numbers.

**Default category.** The current one reads "Group › Category", or "No default" when null.
Changing it calls the existing `POST /merchants/{id}/review` with that category and the
current subscription flag. The card says "Would change up to N transactions. Ones you or a
rule labelled stay, and money out never becomes income." Clear calls the existing
`DELETE /merchants/{id}/default`, which also clears the subscription flag, and the card says
so.

**Subscription and cadence.** The switch calls the same review endpoint when a default
category exists, so it relabels the same rows as a default change and they join the golden
set. The line under the switch says "Applies to the transactions you or a rule did not
label." Without a default, the switch is disabled and the card says "Set a default category
first." The cadence select is the control from section 3.5, fed with the stored `cadence`
when set (source `user`), otherwise `cadence_effective` (source `auto`, plain "Auto" when
null).

**Rename and merge.** `PATCH /merchants/{id}` accepts `{ "name": "..." }` or
`{ "merge_into_id": "..." }`, not both. The name path is the block already inside
`confirm_merchant`: a `match_key` that belongs to another merchant merges into it, otherwise
the merchant is renamed. `merge_into_id` merges directly. Neither path sets a category or
writes user labels. `confirm_merchant` calls the same function and then sets the category,
so review keeps today's behaviour. The response is `{ "id": "<survivor>" }`. When it differs
from the page's id, the page navigates to the survivor, keeping the period. A stale URL of a
merged-away merchant stays a 404: nothing records where it went. 422 for a name with no
letter or digit, or for a body with both fields or neither. 404 for an unknown id, on both
paths.

The transaction list on this page opens the panel from section 5.

The nav item for a merchant stays Overview. The breadcrumb stays "Overview › merchant".

## 8. Names and colours (F)

### 8.1 Names

Names live in `supabase/seed/categories.yaml`, next to the criteria. Each group has `_name`.
Each category has `name`. The parser treats a key starting with `_` as group metadata and
does not turn it into a category. jev still receives `what` and `not_for` only.

```sql
alter table categories add column name text;
create table category_groups (
  level1 text primary key,
  name text not null
);
```

`finance seed` upserts both. A category or group with no stored name is shown as the
readable slug (`software_ai` → "Software ai"), in the web and in SQL via `coalesce`.

`GET /categories` adds `name` and `group_name`, always strings. The web reads names through
two helpers in `labels.ts`: `categoryName(slug, categories)` and `groupName(level1,
categories)`. Both fall back to `label(slug)`, which stays the readable-slug function. Every
place that shows a category or group uses them: breakdown row names and hints, the group
subtitle, breadcrumbs and page titles, pickers and filter groups, transaction rows, the panel,
review cards, settings and the merchant card. The group subtitle then lists names ("Fuel,
Parking & tolls").

The eval fingerprint (`finance/evals/run.py`) dumps the categories without `name` and
`group_name`, so a name change does not read as a taxonomy change.

`v_transactions_enriched` gains `category_name` and `group_name` at the end.
`agent.transactions` projects them. The semantic layer tells the model to say those names
and to keep filtering on the slug columns `category` and `category_group`.

The names to seed:

| Group slug | Name | Category slug | Name |
|---|---|---|---|
| home | Home | rent | Rent |
| | | mortgage | Mortgage |
| | | utilities | Utilities |
| | | internet_phone | Internet & phone |
| | | home_insurance | Home insurance |
| | | maintenance | Maintenance |
| shopping | Shopping | groceries | Groceries |
| | | fashion | Fashion |
| | | electronics | Electronics |
| | | home_goods | Home goods |
| | | beauty_perfumery | Beauty & perfumery |
| | | hobbies | Hobbies |
| | | tobacco | Tobacco |
| | | other_shopping | Other shopping |
| leisure | Leisure | restaurants_bars | Restaurants & bars |
| | | entertainment | Entertainment |
| | | culture_events | Culture & events |
| | | sports_gym | Sports & gym |
| | | gambling_lottery | Gambling & lottery |
| transport | Transport | fuel | Fuel |
| | | public_transport | Public transport |
| | | taxi_rideshare | Taxi & rideshare |
| | | parking_tolls | Parking & tolls |
| | | car_costs | Car costs |
| travel | Travel | flights | Flights |
| | | lodging | Lodging |
| | | travel_other | Other travel |
| health | Health | pharmacy | Pharmacy |
| | | medical | Medical |
| | | health_insurance | Health insurance |
| | | personal_care | Personal care |
| technology | Technology | software_ai | Software & AI |
| education | Education | tuition | Tuition |
| | | courses | Courses |
| | | books_supplies | Books & supplies |
| family | Family | childcare_kids | Childcare & kids |
| | | pets | Pets |
| people | People | payments_to_people | Payments to people |
| giving | Giving | donations | Donations |
| financial | Financial | bank_fees | Bank fees |
| | | loan_payment | Loan payments |
| | | taxes | Taxes |
| | | other_insurance | Other insurance |
| cash | Cash | atm_withdrawal | ATM withdrawals |
| other | Other | uncategorized_expense | Uncategorized expense |
| credit_card | Credit card | credit_card_spending | Credit card bill |
| income | Income | salary | Salary |
| | | self_employment | Self-employment |
| | | pension_benefits | Pension & benefits |
| | | refunds | Refunds |
| | | investment_income | Investment income |
| | | payments_from_people | Payments from people |
| | | other_income | Other income |
| transfer | Transfers | own_accounts | Own accounts |
| | | savings_investment | Savings & investments |
| | | credit_card_payment | Credit card payment |
| | | loan_received | Loan received |

A wording tweak in the YAML is not a design change. Adding or renaming a slug is.

### 8.2 Colours

`group_slots` returns every expense group, ranked by all-time spend, slot 1 first, with
rows without a category ranked as the group `uncategorized`. A period filter does not change
the ranking. Slots 1–8 use hues. Slot 9 and later use the grey scale, in order, so two groups
never share a grey. There are 15 expense groups plus `uncategorized`, so eight greys are
enough. A row's colour reads its group as `level1 ?? "uncategorized"`. A group with no slot
(no expense rows ever) keeps `--chart-other`, which is none of the greys.

Hues, on the light surface. 1–5 stay the colours shipped in slice 3.

| Slot | Token | Hex |
|---|---|---|
| 1 | `--chart-1` | `#4f46e5` |
| 2 | `--chart-2` | `#eb6834` |
| 3 | `--chart-3` | `#1baf7a` |
| 4 | `--chart-4` | `#eda100` |
| 5 | `--chart-5` | `#e87ba4` |
| 6 | `--chart-6` | `#0891b2` |
| 7 | `--chart-7` | `#7c3aed` |
| 8 | `--chart-8` | `#b45309` |

Greys, darkest last, all different from the folded treatment: `#b9b9c2`, `#9a9aa6`,
`#7d7d8a`, `#62626e`, `#4a4a55`, `#3a3a44`, `#2c2c34`, `#1f1f26` as `--chart-grey-1` through
`--chart-grey-8`.

The folded row uses `--chart-folded` (`#ececf1`) with a 45-degree hatch in `#9a9aa6`, on the
donut (an SVG pattern) and on the table dot (the same stripe as a CSS gradient). It is not a
slot and not the group `other`.

These colours are fills and dots, never text. The `.dark` chart tokens get the same hues at
a higher lightness so they remain distinct. The product stays light mode.

## 9. Review inbox (G)

The inbox query stops pulling in every row of a merchant merely because a merge is pending.
Category and transaction cards are built from rows with `needs_review` only, still excluding
`category_source = 'user'`. A merge suggestion becomes a card of `kind: "merge"`, key
`merge:{merchant_id}`, with no transaction list.

`ReviewCount` keeps `pending` (all cards, the badge) and `uncategorized` (the review page's
"not categorized yet" note), and gains `categories` (every card that is not a merge) and
`merges`. The header reads "{pending} to review: {categories} categories ·
{merges} possible duplicates". The nav badge keeps showing `pending`. The transactions
switch "Needs review only" gains the description "Counts transactions that need a category,
not review cards."

A merge card asks "Is {name} the same merchant as {other}?" Yes calls `PATCH` from section 7
with `merge_into_id` and does not relabel rows. No calls the existing dismiss endpoint. Both
keep the undo toast the page already has, including its send-on-leave, so `apiPatch` takes
`keepalive` like `apiPost`. When the source also has a category card, Yes takes that card
off the list with it (Undo brings both back): its rows now belong to the survivor and reappear
under it on the next load.

The help block is a disclosure. It starts open. Closing it writes `review-help:v1=closed` in
`localStorage`, and that choice is read on the next visit.

The confirm button of a card with one transaction is a button labelled "Confirm", with the
check icon beside the word.

Above the list: a filter (All, Categories, Duplicates) and a sort (Amount, the default, or
Date of the latest transaction on the card). A Skip button moves that card to the end for
this tab, remembered in `sessionStorage` under `review-skip:v1`. A new tab starts unskipped.
No keyboard shortcuts.

## 10. Verification

Tests first, as the plans specify. A test is about the rule: a 91-day gap is every 3 months
at a third of the latest charge, a manual cadence beats detection, a folded delta still
contains a group that disappeared, `merchant_id=none` returns only rows without a merchant,
a merge keeps a cadence already set on the survivor.

Checks that write (cadence, defaults, renames, merges, labels) run on a scratch database,
recipe R2 in `docs/superpowers/plans/2026-09-25-slice-3b-interface.md`. Read-only checks may
use the real database. Chat checks, if a task touches the agent, use the scripted server,
recipe R3 in the slice 4b plan. No paid model calls.

Each plan ends with an `agent-browser` core check of the flows it changed, then one dogfood
pass before the PR. Re-run the four scenarios from the inputs and record them in the
git-ignored dogfood report:

1. A quarterly plan's monthly total is a third of its latest charge, and it stays listed past 45 days.
2. The largest "Other" row expands, and the donut does not change.
3. The panel opens from a merchant page, and closing it dirty asks first.
4. The review header's two counts add up to the badge, and the transactions filter counts rows.

Screenshots stay in `dogfood-output/`. They show real bank data and are never committed.

## 11. Out of scope

Partial period comparisons, income grouped by payer, subscriptions per account, chart polish
(step lines, a shared default view, the 12-month legend, the breakdown switch in the URL),
and the other QA ideas listed in the inputs (average month, fixed versus variable, bulk edit,
saved filters, CSV, deep links, undo after Save).

Several subscriptions under one merchant stay one row. One-off purchases flagged by mistake
are unflagged by hand. The data checks in `/review` from the inputs are data, not code.

"AI (jev)" stays visible. The Refunds saved filter stays as the money rules define it.

The accepted plan 4b gaps stay out: a stopped first turn's title, a chat continued
elsewhere, leaving `/chat` mid-answer, a query the limit refused, and the database-down
notice.
