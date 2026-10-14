# Quality of life — brainstorm inputs

The design that took these inputs is
`docs/superpowers/specs/2026-10-14-quality-of-life-design.md`. This file stays the record of
the 2026-10-11 / 2026-10-12 brainstorm. It is not a design.

Inputs for the next design round, not a design. They record what Raul asked for, what a QA
pass found, and what Raul decided while brainstorming on 2026-10-11 and 2026-10-12.

How to use this file:

- **Decided** items are Raul's calls. Keep them unless the code has changed in a way that makes
  one wrong; if so, raise it with Raul instead of dropping it.
- **Ideas** came up in the discussion. They are suggestions, not commitments. The agent that
  takes this over owns the integration: architecture, API shape, file layout, migrations,
  plan split. Raul has changed the code since (slice 4, the chat), so read the current code
  before trusting any file or function named here.
- Code references are as of `main` at `a556e07` (2026-10-11).

## Sources

- Raul's feedback (2026-10-11):
  1. Set a subscription's cadence by hand (monthly, every 3 months, yearly). Once set, it
     sticks, and the totals use it.
  2. From a transaction, change its level-2 category and have it apply to the same merchant.
     Raul thought this already existed and asked for a check.
  3. A button to expand rows that a list folds together (groups, categories, merchants), in
     every list that folds.
  4. A full pass with agent-browser to check that everything adds up, makes sense, works, and is
     a solid first functional base for daily use.
- Two read-only agent-browser QA passes (2026-10-11): dashboards and numbers, and flows and
  quality of life. The full reports, with SQL and screenshots, are local and git-ignored:
  `dogfood-output/2026-10-11-qa-dashboards/report.md` and
  `dogfood-output/2026-10-11-qa-flows/report.md`. They contain real bank data: never copy them
  into the repo.

## What the QA confirmed works

The numbers add up. The UI matched SQL on the views to the cent for KPIs, savings, deltas, and
group, category and merchant breakdowns. That held across months, quarters, YTD, 12 months,
custom ranges, and one account versus all. The folded rows equal the total minus the shown rows.
Empty periods read "No data". There were no console errors or failed requests, and no horizontal
scroll at 375 px. Filters survive reload and Back, and "See all" links land on matching counts.
The problems found are about subscriptions, about what the dashboards hide, and about
quality of life.

## Decided: scope and delivery

- **In scope:** the seven blocks below.
  - First delivery: A, B, C, D (Raul's feedback and the QA fixes).
  - Second delivery: E, F, G. Raul pulled these in from the backlog.
- **Delivery:** one spec with two plans and two PRs, each run in a clean session with
  subagent-driven development. The blocks share design: the merchant page (E) hosts the
  cadence (A) and the default category (C).

## A. Subscriptions

**Problem.**

- **No quarterly cadence.** The cadence is inferred from the median gap between charges: yearly
  above 200 days, otherwise monthly. A plan charged every 91 days shows as monthly at its full
  price, so the monthly and yearly totals overstate it about 3×.
- **It drops in and out of the list.** "Active" means charged within 45 days, so a quarterly plan
  leaves the list and comes back each quarter.
- **Stale amounts.** The typical amount is the median of the whole history. It lags price rises,
  and with an even count it can be a price never charged.
- **Hidden ended plans.** `/subscriptions` lists only active subscriptions. There is no way to
  see or fix one that dropped off.
- **Empty merchant page.** A subscription links to its merchant page for the latest month, which
  is often empty for a non-monthly plan (€0, −100 %).
- **Cadence hidden on phones.** At phone width the cadence column is hidden.

**Decided.**

- **Three cadences:** monthly, every 3 months, yearly.
- **Auto-detected or set by the user.** When the user sets one, it always wins. "Auto" stays
  available to go back to detection.
- **Monthly equivalent:** amount ÷ 1, ÷ 3, ÷ 12.
- **Amount = the latest charge**, not the median (Raul chose this over "median of the last 3"
  and "keep the median").
- **Active window per cadence**, measured from the latest imported transaction (as today):
  45 days monthly, about 120 days every 3 months, 400 days yearly.
- **Cadence editable** from `/subscriptions`, on desktop and phone.
- **A collapsed "Ended" section** on `/subscriptions`, where the cadence can also be fixed.
  Fixing it can bring a subscription back to active.
- **The subscription link opens the merchant over the last 12 months.**
- **Docs and copy.** `docs/money-rules.md` and the copy on `/` and `/subscriptions` describe the
  new rule.

**Ideas.**

- **Storage.** The cadence override lives on the merchant: subscriptions are grouped per merchant
  today. A null value means auto.
- **Detection bands** from the median gap: up to 60 days monthly, 61–200 every 3 months, over
  200 yearly. A single charge stays monthly.
- **Merging merchants** keeps a cadence, as merging already keeps the default category.
- **API.** One endpoint sets or clears the cadence. The subscriptions endpoint also returns the
  ended ones, outside the totals.

**Known limit (not in scope).** Several different subscriptions under one merchant, such as
several bills from one app store under one bank text, are grouped into one row. The workaround
is to move each one to its own merchant from the transaction panel.

**Data hygiene (not code).** One-off purchases flagged as subscriptions at a merchant that also
has a real plan. The user unflags those rows.

## B. Expand folded rows

**Problem.** Breakdowns show the top N (5 or 10) and fold the rest into "Other N merchants" or
"Other N categories". That row is plain text, and it is often the largest one: in one month it
held more than half of the spending on the overview's Merchants view. "No merchant" rows are
not links either.

The lists that fold:

- the overview, Categories and Merchants views;
- top merchants on group pages;
- merchants on category pages;
- top merchants on the income page.

The overview's Groups view does not fold. The "latest transactions" lists already have a
"See all" link.

**Decided.** Every folded row can be expanded in place with a button, in every list that folds.

**Ideas.**

- **Shape.** The folded row stays as a subtotal, keeping its delta against the previous period.
  Its rows appear under it, indented, each with its own share, amount and delta. A second click
  folds them again. The donut does not change.
- **Data.** The API sends the folded rows inside the `_other` row. Only the server computes the
  `_other` delta correctly, since it includes keys that disappeared since the previous period.
- **"No merchant" rows** link to Transactions filtered to that category with no merchant. This
  needs a "no merchant" filter value, and that option in the merchant filter.
- **Reuse.** The same expand/collapse pattern serves the "Ended" subscriptions (A) and the review
  help (G).

## C. Transaction panel everywhere

**Finding.** Point 2 of the feedback already works, but only on `/transactions`. The side panel
changes the level-2 category. When the row has a merchant, Save asks "Apply to all transactions
of this merchant?". "Apply to all" sets the merchant's default category. That relabels the
merchant's rows that the AI or an earlier default categorized, and future imports. Rows the user
or a rule labelled keep their category, and money out never becomes income.

The gaps:

- The "latest transactions" lists on group, category, merchant and income pages are read-only.
  The panel cannot be opened there.
- Nothing says before saving that the change can apply to the whole merchant.
- The category field shows only the category, not its group.
- Escape or a click outside discards unsaved edits without asking.

**Decided.**

- The panel opens from every transaction list.
- The category reads "Group › Category".
- A line under the category says, before saving, that the change can apply to every transaction
  of the merchant.
- Closing with unsaved changes asks first.

**Ideas.** Extract the list-plus-panel part of the transactions explorer into one component, and
reuse it on the detail pages. After a save, the page's totals refresh.

## D. Small fixes from the QA

**Decided.**

1. **Search as you type** in Transactions: debounced, without filling the browser history.
   Enter still works.
2. **Merchant filter search hint.** The merchant filter renders 50 of all merchants and narrows as
   you type, but says neither. Show "Showing 50 of N · type to search".
3. **Group subtitles by spend.** The line under each group on the overview lists the group's top
   categories by spend in the period, not the first ones alphabetically. Today the category that
   drives a group can be hidden.
4. **Merchants with several categories.** A merchant row whose spend spans several categories says
   "2 categories · N transactions", instead of naming one category while summing all of them.
   The category page then disagreed with the group page.
5. **Cap extreme deltas.** Above +999 %, show ">999%". Changes from 0 keep reading "new".
6. **Mobile navigation.** Below `sm`, a menu button opens a sheet with every link and the review
   badge. Today the nav strip is cut mid-word with no hint that it scrolls.
7. **Transactions in/out header.** It sums transfers and refunds, so it disagrees with the
   overview's income and expenses, with no explanation. Keep the cash-flow numbers, and say
   what they include, for example "incl. €X transfers", with an ⓘ that explains the difference.

## E. Merchant page as a control centre

**Problem.** A merchant page shows numbers only. The QA found it a dead end, especially when
reached from `/subscriptions`.

**Decided.** All four controls Raul was offered:

1. **Default category.** See it and change it, with how many rows it would change. Clear it for a
   mixed merchant. The API for this already exists.
2. **Subscription and cadence.** Flag or unflag the merchant as a subscription, and set the
   cadence, the same control as in A.
3. **Rename and merge.** A rename that matches another merchant merges into it; or pick a
   merchant to merge into. The API for this already exists.
4. **Full history.** The merchant page defaults to the last 12 months when the URL has no period.
   Its transaction list opens the panel (C).

**Ideas.** Two smaller QA points, not decided:

- The nav always highlights Overview on a merchant page.
- The breadcrumb is always "Overview › merchant", which loses the way back to the group or to
  Subscriptions.

## F. Category names and group colours

**Problem.**

- **Raw names.** Category and group names are slugs made readable ("Software ai", "Restaurants
  bars", "Atm withdrawal"). The taxonomy has no display names.
- **Too few colours.** Only the 5 groups with the most all-time spend get a colour. Every other
  group shares one grey with the folded "Other" row, so the largest group of a month can be grey.
  In the Categories view, half the donut became one grey arc.

**Decided.**

- **Readable English names** for every category and group, e.g. "Software & AI",
  "Restaurants & bars", "ATM withdrawals".
- **Eight stable colours.** The 8 groups with the most all-time spend get a colour that no period
  filter repaints. Eight is about the most categorical colours people can tell apart, and the
  stability is the existing rule.
- **Distinct greys for the rest.** The remaining groups get a scale of greys that differ from
  each other, not one shared grey. Raul asked that they be told apart and look good.
- **A distinct "Other" row.** The folded row gets its own treatment, so it never reads as a group.

**Ideas.**

- **Where names live.** Names stored with the taxonomy, in the seed and the database rather than
  only in the web, because the chat agent should also answer with readable names. The jev
  criteria stay as they are.
- **Fallback.** A category without a name falls back to the readable slug.
- **The "Other" treatment:** a very light grey with a hatch in the donut and the table dot.
- **Palette.** Validated for contrast, colour blindness, and light and dark themes; the `dataviz`
  skill has a method and a validator.
- **Review.** Raul did not review a full name list. Draft one and put it in front of him.

## G. Review inbox

**Finding.** The QA saw that the counts do not reconcile: 68 cards, about 139 rows, and 71 rows
with "Needs review only" in Transactions. This is not a data bug:

- 71 rows have `needs_review`.
- The inbox also includes every row of the merchants that have a pending merge suggestion. That
  gives about 139 rows, grouped into 68 cards.
- The nav badge counts the cards.

So a merge suggestion arrives inside a categorization card. It reads as a card with 100 %
confidence and no rows needing review.

**Decided.** All four:

1. **Clear counts.** The badge and the page header say what they count, for example "68 to
   review: 54 categories · 14 possible duplicates". The Transactions filter says it counts rows.
2. **Merge suggestions as their own cards.** A merge suggestion reads as a question, "Is X the
   same merchant as Y?", with Yes and No, apart from the categorization cards.
3. **Collapsible help, labelled buttons.** The always-open help block can be collapsed and
   remembers it. The confirm button of a single card has a text label, not only an icon.
4. **Filter, sort and skip.** Filter cards by kind (category or merge), sort by amount or date,
   and a "Skip" that moves a card to the end for the session. No keyboard shortcuts yet.

**Ideas.** If merge cards are separate, categorization cards could hold only the rows that
need review. The counts would then reconcile with the Transactions filter.

## Out of scope (backlog)

- **Partial comparisons.** A comparison against a previous period that imports cover only
  partly inflates every delta, e.g. 43 days against 31 days of data. It needs import coverage
  (backlog idea 4): mark the comparison "partial" or hide it.
- **Income breakdown.** It is mostly "No merchant" rows. Group income by payer instead.
- **Subscriptions per account.** `/subscriptions` ignores the account filter, and the nav loses
  the period on the way back from it.
- **Chart polish:**
  - smoothed cumulative lines rise before the charge date (a step line would be exact);
  - the default views (monthly or cumulative) differ between pages;
  - the 12-month legend colour does not match most bars;
  - the Groups / Categories / Merchants switch is not in the URL.
- **Other QA ideas:** an average-month card for long periods; a fixed vs variable costs split; an
  "€X uncategorized → review" nudge; merchant stats (average ticket, visits per month); bulk edit;
  saved filters; CSV export; a `?tx=` deep link; an undo toast after Save.
- **Data to check in `/review`, not code:**
  - one incoming row categorized as a card payment, which makes it a transfer outside every
    total;
  - unpaired own-account transfers on one account;
  - a couple of income rows that look miscategorized.

## Kept as is

- **"AI (jev)" in the UI.** It stays visible on purpose.
- **The "Refunds" saved filter** leaves out the income category `refunds`. That follows the money
  rules: that category is money back with no known purchase.

## Verification expectations

As the project instructions say:

- tests first;
- an agent-browser `core` check of each changed flow;
- checks that write data (cadence, defaults, renames, merges, labels) run only on a scratch copy
  of the database (recipe R2);
- one `dogfood` pass per delivery before merge.

Re-run the two QA scenarios that found the problems, and confirm they are fixed:

- a quarterly plan's monthly total;
- expanding the largest "Other" row;
- opening the panel from a merchant page;
- the review counts.
