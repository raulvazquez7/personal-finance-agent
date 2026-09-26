# Slice 3b — Interface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the slice 3a API into the tally ai web interface: the overview, the group, category, merchant and income pages, the transactions explorer with its side panel, subscriptions, settings, and the restyled review and imports pages.

**Architecture:** Server components read the period, the accounts and the filters from `searchParams` through one helper (`src/lib/params.ts`) and fetch the 3a endpoints. Small client components draw the Recharts charts and run the interactive controls. Pure helpers in `src/lib` hold every rule the pages share: formatting, deltas, colours, labels and picker grouping. The design tokens are shadcn CSS variables in `globals.css`.

**Tech Stack:** Next.js 16.3 App Router, React 19.2, TypeScript, Tailwind v4, shadcn/ui `base-nova` (Base UI primitives), Recharts 3.8 through the shadcn `chart` component, `openapi-typescript` types, Vitest for pure helpers (Decision A), `agent-browser` for UI checks.

**Spec:** `docs/superpowers/specs/2026-09-25-slice-3-design.md`, sections 2.6, 7, 8, 9, 11 and 14. The mockups are in `docs/superpowers/specs/2026-09-25-slice-3-mockups/`: `index.html` holds the exact tokens and copy, and `01-page-map.png`, `02-overview.png`, `03-group-page.png` and `04-tokens.png` are the visual contract (layout, hierarchy, tokens and chart forms; pixel values are indicative). The API contract is plan 3a, `docs/superpowers/plans/2026-09-25-slice-3a-money-rules-and-data.md`: Task 7 (note, clear default, label 422), Task 10 (`finance/dashboard/models.py`), Task 11 (`GET /dashboard/overview`, `GET /dashboard/subscriptions`), Task 12 (`GET /transactions`) and Task 13 (`GET /spending/detail`). Where plan 3a's code blocks and the shipped code differ, the code and the regenerated `apps/web/src/lib/api-types.ts` are the contract (plan 3a, "In-flight decisions").

## Decisions (taken by Raul on 2026-09-25)

The tasks below are written for these decisions.

- **A. Vitest for pure helpers: yes.** Add `vitest` as a dev dependency, configured as the Next.js Vitest guide recommends, minus `jsdom` and React Testing Library, which only component tests need, and with Vite 8's built-in `resolve: { tsconfigPaths: true }` in place of the guide's `vite-tsconfig-paths` plugin. Only `src/lib/*.test.ts` exists; CI does not run it.
- **B. Text contrast: darker text tokens for WCAG AA.** The mockup's muted `#8A8A94` is 3.4:1 on white and 3.2:1 on `#F7F7F9`, and its income/good `#16A34A` is 3.3:1 and 3.1:1, below AA (4.5:1) for small text. The text tokens are `--muted-foreground: #6b6b75` (4.9:1) and `--good`/`--income: #15803d` (4.7:1). Chart marks keep the mockup colours: the palette, ramp and chart chrome tokens are unchanged (Task 3 Step 2). Raul's contrast decision in the Task 14 triage (B.2) sets two more tokens a shade darker for the same reason: `--bad: #DC1A45` (4.59:1 on the surface) and the segmented-control track `--muted: #EFEFF3` (muted text on it 4.59:1).
- **C. Active nav item: the mockup (resolved; spec 7.2 corrected).** `index.html:24` draws the active pill near-black (`.nav.on{background:var(--text)}`), while spec 7.2 (lines 270-271) names the accent for "the active nav item". A near-black pill, with the accent for links, the current series and the logo dot.
- **D. Settings in the navigation: the last nav item.** The mockup nav has no Settings entry, and `/settings` needs a way in.
- **E. Resolved in plan 3a Task 7:** confirming a merchant never writes an income category on its money-out rows (they keep their labels), so "Apply to all" cannot turn money out into income. The API returns no 422 for it; only labelling one money-out row with an income category is a 422.
- **F. The period pill follows the account filter.** `period.latest_day` is the latest day of the selected accounts, and the root layout does not re-render on client navigation, so the server's `latestDay` is right only without an account filter. With one, `FilterBar` fetches `/transactions?limit=1&account_id=…` in the browser and passes that `latest_day` to the pill label and the presets, so the pill and the page always show the same month (Task 3 Step 7).
- **G. No data in the period: KPI tiles read "—".** When no month of the period has data (`MonthPoint.has_data` false, `periodHasData`), the four tiles show "—" and hide their deltas (spec 2.6: "no data, never 0"). The donut centre repeats the Expenses number, so it follows the same rule (Tasks 2, 4 and 5).
- **H. /review drops a jev suggestion that does not fit the item's direction** (an income suggestion on a money-out or mixed item). The category field then starts empty (`fitsDirection`, Task 8).
- **I. Copy.** The uncategorized group's hint reads "Not categorized yet", because those rows never reach /review (Task 2). The overview's subscriptions line says that "active" is measured from the latest import (Task 5). The /review "jev skipped" hint, the "Apply to all" income note and the "No data in <month>" title stay as written.

## Amendments during execution (2026-09-26)

What shipped differs from the tasks below in these points. The code blocks stay as planned; where one differs from the shipped file, the shipped file is the record.

- Vitest (Decision A): no `vite-tsconfig-paths`; `apps/web/vitest.config.mts` resolves the `@/` paths with Vite 8's `resolve: { tsconfigPaths: true }` (Task 1 Steps 1-2 updated).
- Range labels: a range of days across two years also shows the start's year ("10 Dec 2025 – 19 Jan 2026"); `periodLabel` and `rangeLabel` share one helper, `dayRange` in `apps/web/src/lib/format.ts` (Task 1 updated).
- Example values: Task 1's signed-money example and Task 2's breakdown example use the values of `apps/web/src/lib/format.test.ts` and `apps/web/src/lib/breakdown.test.ts`.
- Links styled as buttons: a plain Next `<Link>` with `className={buttonVariants(...)}`, never a `Button` rendered as a `Link` (`apps/web/src/app/page.tsx`, `apps/web/src/app/transactions/explorer-filters.tsx`; Global Constraint updated; the Task 4 and Task 9 code blocks show the first version).
- Money-in pickers: income first, then one "Refund of a purchase · <Group>" group per expense group, then transfers (`apps/web/src/lib/pickers.ts`; Global Constraint and Review Focus 5 updated; Task 8's `pickerGroups` and the picker checks in Tasks 8 and 10 show the single group planned first).
- Groups view: the API's overview `by_group` returns every group (`apps/api/finance/api/dashboard.py`), and the view lists every group with spend in the period as its own row, the five slotted groups in their colours and the rest in the "other" grey; `foldBySlot` and its test were removed (`apps/web/src/lib/colors.ts`). A folded `_other` row reads "Other groups" or "Other categories", and merchants keep "Other N merchants" (`rowName` in `apps/web/src/lib/labels.ts`); the Groups view has no folded row (Task 5's check and the known gaps note updated).
- Previous period (Task 14 finding D2): when the selected accounts' data ends inside the period, the API cuts the previous period after as many days (`apps/api/finance/api/periods.py`); the KPI tiles, the change columns and the same-day card compare those days, whether the previous period has data is judged on the whole of it, and the cumulative chart's previous line keeps running past the cut day, up to the current period's length (`apps/web/src/components/charts/cumulative-chart.tsx`). A custom range's `previousLabel` still counts the whole range before (`format.ts`). Spec 2.6 describes it.
- Same-day label (final review M1): when that cut applies, the "vs …" label of the KPI tiles and the change columns ends with " by the same day" ("vs Jul by the same day", "vs the 3 months before by the same day"); a whole period keeps the plain label, and the same-day card never says it twice (`previousLabel` and `endsInside` in `apps/web/src/lib/format.ts`).
- ⓘ definitions: `InfoTip` is a Popover that also opens on hover (`openOnHover`), not a Tooltip: Base UI tooltips are unreachable on touch and with a screen reader (`apps/web/src/components/money/info-tip.tsx`; Global Constraint updated; Task 4 Step 5 shows the Tooltip planned first).
- `ConfirmMerchant.is_subscription` is required and nullable: null (a confirm from money in, which has no subscription switch) keeps the merchant's flag and each row's mark where the row can still be a subscription (money out with an expense category) (`apps/api/finance/api/merchants.py`).
- `AccountUpdate.name` is trimmed before its 1-80 check, so a name of only spaces is a 422, never a blank account (`apps/api/finance/api/accounts.py`).
- Task 14 Step 3 ran as four fix waves after the dogfood and guidelines passes: data and copy, accessibility, interaction and layout, then tests, code quality, API validation and D2 (commits `b191cd6..e21b652`).

## Before Task 1

- [ ] **Step 1: Branch from main after 3a is merged**

```bash
git switch main && git pull
git switch -c feat/slice-3b-interface
```

- [ ] **Step 2: Regenerate the web types from the 3a API**

Start the API as a background process (`cd apps/api && uv run task api`), then:

```bash
cd apps/web && npm run gen:api
grep -cE '^        (Overview|PeriodOut|Totals|Cumulative|CumulativePoint|MonthPoint|BreakdownRow|SubscriptionsSummary|Subscriptions|SubscriptionOut|SpendingDetail|ScopeMonth|TransactionPage|NoteUpdate): \{' src/lib/api-types.ts
```

Expected: `14`. If `git status` shows `src/lib/api-types.ts` changed, commit it on its own:

```bash
git add apps/web/src/lib/api-types.ts
git commit -m "chore: regenerate the web API types"
```

- [ ] **Step 3: Check the starting point builds**

Run: `cd apps/web && npm run lint && npx tsc --noEmit && npm run build`
Expected: no errors.

## Global Constraints

- 3b starts after 3a is merged. Web types come from `npm run gen:api` (API on :8000) into `apps/web/src/lib/api-types.ts`, and code uses them as `Schemas["<Name>"]` from `@/lib/api`. The names used are: `Overview`, `PeriodOut`, `Totals`, `Cumulative`, `CumulativePoint`, `MonthPoint`, `BreakdownRow`, `SubscriptionsSummary`, `Subscriptions`, `SubscriptionOut`, `SpendingDetail`, `ScopeMonth`, `Transaction`, `TransactionPage`, `Account`, `CategoryOut`, `MerchantOut`, `ReviewItem`, `ReviewTransaction`, `ReviewCount`, `ImportRecord`, `ImportSummary`. Decimals arrive as strings.
- The folded row's key is "_other" (never a slug); plan 3a Task 10.
- This is Next.js 16.3.6, not the Next.js of training data. Read the guide in `apps/web/node_modules/next/dist/docs/` before using any API (`apps/web/AGENTS.md`). `params` and `searchParams` are Promises. `PageProps<"/route">` and `LayoutProps<"/route">` are global types. `error.tsx` receives `retry` (stable since 16.3). A client component that calls `useSearchParams` inside the root layout needs a `<Suspense>` boundary, or `next build` fails on the prerendered 404 page.
- Every page that fetches exports `export const dynamic = "force-dynamic"` (the existing convention), so `next build` in CI never calls the API.
- shadcn `base-nova` runs on Base UI, not Radix. Use `render={<Button />}`, never `asChild`. A link styled as a button is a plain Next `<Link>` with `className={buttonVariants(...)}`, never a `Button` rendered as a `Link`: Base UI gives that one `role="button"`, so screen readers announce the link as a button. `ToggleGroup` values are arrays. `Select` takes an `items` prop. Follow `.claude/skills/shadcn/rules/*.md`. Add components with `npx shadcn@latest add <name> --dry-run`, then without `--dry-run`, and read every added file. Icons come from `lucide-react`, and `cn` from `@/lib/utils`.
- Charts use Recharts 3 through the shadcn `chart` component. It installs `recharts@3.8.0`: keep that version and upgrade only on purpose, in its own change. Run `npm install react-is@19.2.8` to match React 19.2.8 (spec 8, gotcha 1). Every `ChartContainer` gets a height or `aspect-*` class. Colours are written as `var(--…)`, never `hsl(var(--…))`. Months without data arrive as `null` and are drawn as dashed "no data" boxes, never as 0. Legend isolation is a hidden-series state, plus `hide` on the series, plus legend items rendered as `<button aria-pressed>`. Use the Recharts v3 docs only.
- No other libraries: no nuqs, no TanStack Table, no date library. `Intl` formats money and dates, and period maths stays in the API; the web only shifts a month for the "Previous month" preset.
- The URL is the state. The period (`period`, `month`, `start`, `end`), `account_id` (repeatable) and the explorer filters live in `searchParams`, and they are parsed and written only through `src/lib/params.ts`. Every link carries them (`withFilters`).
- Server components fetch through `apiGet`. Client components exist only for charts and interactive controls. The browser fetches only "Load more" pages and writes.
- The API answers only the hosts in its `TRUSTED_HOSTS` setting (default `localhost`, `127.0.0.1`, `testserver`; plan 3a Task 14) and returns 400 for any other `Host`, so `NEXT_PUBLIC_API_URL` stays on `localhost` (`:8000`, and `:8001` in R2).
- Visual system (spec 7.2, mockup tokens): white page `#FFFFFF`; surfaces `#F7F7F9` without borders; text `#0B0B0F`; muted text `#6b6b75` (Decision B; the mockup's `#8A8A94` fails AA); one accent, indigo `#4F46E5`; income/good text `#15803d` (Decision B; the mockup's `#16A34A`); bad `#DC1A45` and the segmented-control track `#EFEFF3` (Decision B, Task 14 triage B.2); radius 16 for cards and 999 for pills; Geist with tabular numbers; the logo is lower-case "tally ai", in one colour and one weight, with the accent dot; a top navigation bar with a pill for the active item and the filters on the right.
- Group palette `#4F46E5 #EB6834 #1BAF7A #EDA100 #E87BA4`, other `#D4D4DC`, assigned by `Overview.group_slots`: colour follows the group, never its rank. One-hue ramp `#4F46E5 #6D66EE #8C86F2 #AAA6F5 #C4C0F8 #DAD8FB` (darkest = largest) for categories inside a group page. Green and red only for deltas, always with an arrow and a sign. Light mode only.
- The UI explains itself. Every edit field has a one-line `FieldDescription`, and every KPI has an ⓘ popover that quotes `docs/money-rules.md`. UI copy is in English, in sentence case.
- Direction-aware category pickers everywhere: money out offers expense and transfer categories; money in offers income first, then one "Refund of a purchase · <Group>" group per expense group, with that group's categories, then transfers.
- Simplicity: one responsibility per file, no abstraction for a single caller, 15 readable lines over 30 clever ones.
- Testing policy: CI stays lint + type-check + build (`npm run lint` and `npm run build`, which type-checks). Pure TypeScript helpers in `src/lib` get Vitest unit tests (Decision A). Components are verified in the browser with agent-browser, not with unit tests. The local gate for every task is `cd apps/web && npm run lint && npx tsc --noEmit && npm test && npm run build`.
- Browser checks follow "Browser checks" below. Real data is read-only; checks that write data run on the scratch database. Screenshots are saved only as absolute paths under `dogfood-output/slice-3b/`, which is git-ignored because the captures show real bank data; never commit them. Use a named session, stay on localhost, and `close` at the end.
- The repo is public. No real amounts, account digits, statement file names or merchant names in code, tests, commit messages or PR text. Test fixtures use `ZZTEST` names and fake UUIDs.
- jev is paid. The scratch API always runs with `TYPESAFE_API_KEY=` (empty), because an import starts a categorization run. No task runs `finance categorize`.
- Conventional commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`), ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **A hand-edited or stale URL** (`period=week`, `month=2026-13` or `month=2100-01`, a custom range that ends before it starts or on 30 February, a non-UUID `account_id`, a 150-character `q`): the page falls back to the defaults and renders; it never shows a 422 or a 500. Tests: Task 1 (`params.test.ts`).
2. **A browser west of UTC**: `2026-08-01` must read "Sat, 1 Aug", never 31 July. Day headers, axis labels and the period pill all format through `format.ts` in UTC. Tests: Task 1 (`format.test.ts`, run with `TZ=America/Los_Angeles`).
3. **A period whose previous period has no data, was zero, or was negative (refunds only), and a month without income**: the delta is hidden, reads "new", or keeps its real direction; the savings rate reads "—" and its delta is hidden. Tests: Task 2 (`delta.test.ts`).
4. **A day split across two "Load more" pages**: one header for the day, with the net of all its loaded rows. Tests: Task 6 (`transactions.test.ts`, `groupByDay`).
5. **Money in on a merchant with an expense default (a refund)**: its pickers list income first, then one "Refund of a purchase · <Group>" group per expense group, then transfers; it can never be saved as a subscription; and "Apply to all" never relabels rows the user or a rule labelled. Tests: Task 8 (`pickers.test.ts`) and Task 10 (`transactions.test.ts`, `applyChange`).

## Browser checks

Every task that changes a page ends with a check that follows one of these two recipes. Load the workflow once per session with `agent-browser skills get core`. The shell does not keep variables between commands, so each command below is self-contained.

### R1 — real data, read-only

1. Start the API and the web as background processes: `cd apps/api && uv run task api` (:8000, the real local database) and `cd apps/web && npm run dev` (:3000).
2. Use the session `slice3b` and only `http://localhost:3000`:

```bash
mkdir -p "$(git rev-parse --show-toplevel)/dogfood-output/slice-3b"
agent-browser --session slice3b open "http://localhost:3000/"
agent-browser --session slice3b snapshot -i
# act on @refs from the snapshot, then snapshot again to see the change
agent-browser --session slice3b screenshot "$(git rev-parse --show-toplevel)/dogfood-output/slice-3b/taskNN-page.png"
agent-browser --session slice3b errors        # expected: no page errors
agent-browser --session slice3b close
```

3. Read-only means navigating, switching toggles, changing filters, hovering, and opening the side panel and closing it with Cancel. Never press Save, Confirm, Apply, Import, Rename or Clear on real data.
4. Compare the screenshot with the task's mockup PNG (open both with the Read tool). Layout, hierarchy, tokens and chart forms must match; pixel values are indicative. List the differences in the task report, and fix the ones that break the contract.

### R2 — scratch database, for checks that write

1. Copy the local database into `scratch_review`:

```bash
PGPASSWORD=postgres dropdb --if-exists -h 127.0.0.1 -p 54322 -U postgres scratch_review
PGPASSWORD=postgres createdb -h 127.0.0.1 -p 54322 -U postgres scratch_review
PGPASSWORD=postgres pg_dump --schema=public --no-owner --no-privileges -h 127.0.0.1 -p 54322 -U postgres postgres | PGPASSWORD=postgres psql -q -h 127.0.0.1 -p 54322 -U postgres scratch_review
```

If `pg_dump` refuses because the server is newer, dump inside the container instead: `docker exec supabase_db_personal-finance-agent pg_dump -U postgres --schema=public --no-owner --no-privileges postgres | PGPASSWORD=postgres psql -q -h 127.0.0.1 -p 54322 -U postgres scratch_review`. The `CREATE SCHEMA public` error in the output is expected.

2. Start the API on :8001 against it, with no jev key, as a background process:

```bash
cd apps/api && SUPABASE_DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/scratch_review CORS_ORIGINS='["http://localhost:3001"]' TYPESAFE_API_KEY= uv run uvicorn finance.api.main:app --port 8001
```

3. Build and start the web on :3001 (Next 16 refuses a second `next dev` in the same folder), as a background process:

```bash
cd apps/web && NEXT_PUBLIC_API_URL=http://localhost:8001 npx next build && NEXT_PUBLIC_API_URL=http://localhost:8001 npx next start -p 3001
```

4. Use the session `slice3b-scratch` and only `http://localhost:3001`, with the same snapshot, screenshot, `errors` and `close` steps as R1.
5. Afterwards, stop both processes and drop the copy: `PGPASSWORD=postgres dropdb -h 127.0.0.1 -p 54322 -U postgres scratch_review`.

## File Structure

All paths are under `apps/web/`.

| File | Responsibility |
|---|---|
| `vitest.config.mts` (new) | Vitest for `src/lib/*.test.ts` only (Decision A) |
| `src/lib/params.ts` (new) | The URL state: parse and write the period, accounts and explorer filters |
| `src/lib/format.ts` (new) | Money, dates in UTC, period labels |
| `src/lib/delta.ts` (new) | Deltas against the previous period, and the same-day comparison |
| `src/lib/colors.ts` (new) | Group colour slots, the one-hue ramp, folding into "Other" |
| `src/lib/labels.ts` (new) | Slug labels, row names and hints, sources, accounts, known groups |
| `src/lib/definitions.ts` (new) | The KPI ⓘ texts, quoted from `docs/money-rules.md` |
| `src/lib/breakdown.ts` (new) | Breakdown rows as table and donut items: name, hint, link, colour, delta |
| `src/lib/pickers.ts` (new) | Direction-aware picker groups and explorer filter groups |
| `src/lib/transactions.ts` (new) | Rows grouped by day; a saved label applied to the loaded rows |
| `src/lib/api.ts` | Fetch helpers, `ApiError`, the top bar's context |
| `src/app/globals.css` | Design tokens |
| `src/components/ui/card.tsx`, `table.tsx`, `toggle.tsx`, `toggle-group.tsx` | Design edits to shadcn sources (surfaces, headers, segmented control) |
| `src/components/shell/top-bar.tsx` (new) | Logo, navigation and filters (server) |
| `src/components/shell/nav-links.tsx` (new) | Navigation with the active pill |
| `src/components/shell/filter-bar.tsx` (new) | The account and period pills, on the pages they filter |
| `src/components/shell/period-picker.tsx` (new) | Period presets, a month, a custom range |
| `src/components/shell/account-picker.tsx` (new) | Accounts, several at once |
| `src/app/error.tsx` (new) | A readable error with Try again |
| `src/components/money/delta-text.tsx`, `info-tip.tsx`, `kpi-tile.tsx` (new) | Deltas, ⓘ tooltips, KPI tiles |
| `src/components/charts/money-tooltip.tsx`, `legend-buttons.tsx`, `month-axis.tsx` (new) | Shared chart pieces |
| `src/components/charts/cumulative-chart.tsx`, `months-chart.tsx`, `breakdown-donut.tsx`, `scope-months-chart.tsx`, `category-treemap.tsx` (new) | One file per chart |
| `src/components/breakdown/breakdown-table.tsx` (new) | Name, share, amount, change |
| `src/components/overview/where-money-went.tsx` (new) | Groups, Categories and Merchants switch |
| `src/components/detail/detail-page.tsx`, `spending-card.tsx` (new) | The group, category, merchant and income template |
| `src/components/transactions/transaction-row.tsx`, `transaction-table.tsx` (new) | Rows grouped by day |
| `src/components/pickers/category-picker.tsx`, `merchant-picker.tsx` (moved from `src/app/review/`), `category-filter.tsx` (new) | Pickers shared by review, the panel and the filters |
| `src/app/page.tsx` | Overview |
| `src/app/spending/[group]/page.tsx`, `src/app/spending/[group]/[category]/page.tsx`, `src/app/income/page.tsx`, `src/app/income/[category]/page.tsx`, `src/app/merchants/[id]/page.tsx` (new) | Detail pages |
| `src/app/transactions/page.tsx`, `explorer-filters.tsx`, `transaction-list.tsx`, `transaction-panel.tsx` | The explorer |
| `src/app/subscriptions/page.tsx` (new) | Subscriptions |
| `src/app/settings/page.tsx`, `account-name-form.tsx` (new) | Settings |
| `src/app/review/*`, `src/app/imports/*` | Fixes and restyle |

---

### Task 1: URL state and formatting helpers

**Files:**
- Create: `apps/web/vitest.config.mts`, `apps/web/src/lib/params.ts`, `apps/web/src/lib/format.ts`
- Modify: `apps/web/package.json` (dev dependencies, `test` script)
- Test: `apps/web/src/lib/params.test.ts`, `apps/web/src/lib/format.test.ts`

**Interfaces:**
- Produces, `params.ts`:
  - `PERIODS`, `PeriodName = "month" | "last_3_months" | "ytd" | "last_12_months" | "custom"`; `TX_TYPES`, `TxType`; `SOURCES`, `Source`; `SAVED`, `Saved`; `EXPLORER_KEYS`.
  - `SearchParams = Record<string, string | string[] | undefined>`.
  - `Filters = { period: PeriodName; month?: string; start?: string; end?: string; accounts: string[] }`.
  - `ExplorerFilters = { q?; tx_type?: TxType; level1?; category?; merchant_id?; is_subscription?: "true" | "false"; category_source?: Source; needs_review?: "true" | "false"; saved?: Saved }`.
  - `isUuid(value)`, `isSlug(value)`, `isDay(value)`: type guards.
  - `parseFilters(params: SearchParams): Filters`; `filterParams(filters): URLSearchParams`; `withFilters(path: string, filters: Filters, extra?: Record<string, string | undefined>): string`.
  - `parseExplorer(params): ExplorerFilters`; `explorerParams(filters, explorer): URLSearchParams`; `clearedExplorer(query: string): string`.
  - `toSearchParams(search: URLSearchParams): SearchParams`; `replaceParams(query: string, changes: Record<string, string | string[] | undefined>): string`; `periodChanges(choice: Omit<Filters, "accounts">): Record<string, string | undefined>`; `shiftMonth(month: string, months: number): string`; `detailType(params): "expense" | "income"`.
- Produces, `format.ts`: `toNumber`, `money`, `moneyWhole`, `signedMoney`, `signedMoneyWhole`, `compactMoney`, `percent`, `rate`, `monthLabel`, `monthShort`, `dayHeader`, `dayShort`, `dayLong`, `dateTime`, `dayAt(start, offset)`, `daysIn(start, end)`, `dayRange(start, end)`, `PeriodLike`, `periodLabel(filters, latestDay)`, `rangeLabel(period)`, `previousLabel(period, style?)`, `periodNames(period)`.

- [ ] **Step 1: Install Vitest (Decision A)**

```bash
cd apps/web && npm install -D vitest
```

- [ ] **Step 2: Configure it**

Create `apps/web/vitest.config.mts`:

```ts
import { defineConfig } from "vitest/config";

// Pure helpers only (src/lib). Components are checked in the browser with agent-browser, so
// jsdom and React Testing Library from the Next.js guide are left out.
export default defineConfig({
  resolve: { tsconfigPaths: true },
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});
```

In `apps/web/package.json`, add to `"scripts"`: `"test": "vitest run"`.

- [ ] **Step 3: Write the failing tests**

Create `apps/web/src/lib/params.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import {
  clearedExplorer,
  detailType,
  explorerParams,
  filterParams,
  isDay,
  parseExplorer,
  parseFilters,
  replaceParams,
  shiftMonth,
  toSearchParams,
  withFilters,
} from "./params";

const A = "11111111-1111-4111-8111-111111111111";
const B = "22222222-2222-4222-8222-222222222222";

describe("parseFilters", () => {
  it("defaults to the latest month and all accounts", () => {
    expect(parseFilters({})).toEqual({ period: "month", accounts: [] });
  });

  it("keeps valid values and repeated accounts", () => {
    expect(parseFilters({ period: "last_3_months", month: "2026-08", account_id: [A, B] })).toEqual({
      period: "last_3_months",
      month: "2026-08",
      accounts: [A, B],
    });
  });

  it("drops what the API would refuse", () => {
    expect(parseFilters({ period: "week", month: "2026-13", account_id: ["1; drop", A] })).toEqual({
      period: "month",
      accounts: [A],
    });
    // GET /dashboard/overview and friends take months 1900-01..2099-12 only.
    expect(parseFilters({ month: "2100-01" })).toEqual({ period: "month", accounts: [] });
  });

  it("keeps a custom range only when it is two real days in order", () => {
    expect(parseFilters({ period: "custom", start: "2026-08-10", end: "2026-08-19" })).toEqual({
      period: "custom",
      start: "2026-08-10",
      end: "2026-08-19",
      accounts: [],
    });
    expect(parseFilters({ period: "custom", start: "2026-08-19", end: "2026-08-10" }).period).toBe("month");
    expect(parseFilters({ period: "custom", start: "2026-02-01", end: "2026-02-30" }).period).toBe("month");
    expect(parseFilters({ period: "custom", start: "1899-12-31", end: "2026-08-10" }).period).toBe("month");
  });
});

describe("links carry the filters", () => {
  const august = { period: "month" as const, month: "2026-08", accounts: [A] };

  it("writes the period and accounts in a fixed order and leaves the default out", () => {
    expect(withFilters("/spending/shopping", august)).toBe(`/spending/shopping?month=2026-08&account_id=${A}`);
    expect(withFilters("/", { period: "month", accounts: [] })).toBe("/");
    expect(withFilters("/transactions", august, { level1: "shopping", q: undefined })).toBe(
      `/transactions?month=2026-08&account_id=${A}&level1=shopping`,
    );
  });

  it("round-trips through a URL", () => {
    const custom = { period: "custom" as const, start: "2026-08-10", end: "2026-08-19", accounts: [A, B] };
    expect(parseFilters(toSearchParams(filterParams(custom)))).toEqual(custom);
  });
});

describe("explorer filters", () => {
  it("keeps known values, trims the search and cuts it to the API limit", () => {
    const explorer = parseExplorer({
      q: `  ${"x".repeat(150)} `,
      tx_type: "expense",
      level1: "shopping",
      category_source: "jev",
      saved: "refunds",
      needs_review: "true",
    });
    expect(explorer.q).toHaveLength(100);
    expect(explorer).toMatchObject({
      tx_type: "expense",
      level1: "shopping",
      category_source: "jev",
      saved: "refunds",
      needs_review: "true",
    });
  });

  it("drops unknown values", () => {
    expect(
      parseExplorer({ tx_type: "loan", category: "Robert'); DROP", merchant_id: "42", is_subscription: "maybe", q: "  " }),
    ).toEqual({});
  });

  it("adds the explorer filters after the period and clears them again", () => {
    const query = explorerParams({ period: "ytd", accounts: [] }, { q: "zztest", tx_type: "expense" }).toString();
    expect(query).toBe("period=ytd&q=zztest&tx_type=expense");
    expect(clearedExplorer(query)).toBe("period=ytd");
  });
});

describe("query helpers", () => {
  it("replaces and removes params", () => {
    expect(replaceParams(`period=ytd&account_id=${A}&q=zztest`, { period: undefined, month: "2026-07", q: undefined })).toBe(
      `account_id=${A}&month=2026-07`,
    );
    expect(replaceParams("", { account_id: [A, B] })).toBe(`account_id=${A}&account_id=${B}`);
  });

  it("shifts months across a year", () => {
    expect(shiftMonth("2026-01", -1)).toBe("2025-12");
    expect(shiftMonth("2025-12", 1)).toBe("2026-01");
  });

  it("knows a real day and the detail page type", () => {
    expect(isDay("2028-02-29")).toBe(true);
    expect(isDay("2026-02-29")).toBe(false);
    expect(isDay("2101-01-01")).toBe(false);
    expect(detailType({ type: "income" })).toBe("income");
    expect(detailType({ type: "loan" })).toBe("expense");
  });
});
```

Create `apps/web/src/lib/format.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import {
  compactMoney,
  dayAt,
  dayHeader,
  dayRange,
  dayLong,
  dayShort,
  daysIn,
  money,
  moneyWhole,
  monthLabel,
  monthShort,
  percent,
  periodLabel,
  periodNames,
  previousLabel,
  rangeLabel,
  rate,
  signedMoney,
  signedMoneyWhole,
} from "./format";

// West of Greenwich, `new Date("2026-08-01")` is still 31 July: the helpers must not care.
process.env.TZ = "America/Los_Angeles";

describe("money", () => {
  it("formats euros the way the tables and tiles show them", () => {
    expect(money("2184")).toBe("€2,184.00");
    expect(moneyWhole("3250.40")).toBe("€3,250");
    expect(signedMoney("-42.10")).toBe("-€42.10");
    expect(signedMoney("12.34")).toBe("+€12.34");
    expect(signedMoneyWhole(3250)).toBe("+€3,250");
    expect(compactMoney(2400)).toBe("€2.4K");
    expect(money(null)).toBe("€0.00");
  });

  it("formats shares and rates", () => {
    expect(percent(0.3799)).toBe("38%");
    // A refund after its purchase month makes an entry's net negative: shares leave 0-100%.
    expect(percent(1.25)).toBe("125%");
    expect(percent(-0.1)).toBe("-10%");
    expect(rate(0.328)).toBe("32.8%");
    expect(rate(null)).toBe("—");
  });
});

describe("dates are formatted in UTC", () => {
  it("never shows the day before", () => {
    expect(dayHeader("2026-08-01")).toBe("Sat, 1 Aug");
    expect(dayShort("2026-08-31")).toBe("31 Aug");
    expect(dayLong("2026-01-01")).toBe("1 Jan 2026");
    expect(monthLabel("2026-08")).toBe("August 2026");
    expect(monthShort("2026-02")).toBe("Feb");
  });

  it("names a range of days, with the start's year only across two years", () => {
    expect(dayRange("2026-08-01", "2026-08-31")).toBe("1 Aug – 31 Aug 2026");
    expect(dayRange("2025-12-10", "2026-01-19")).toBe("10 Dec 2025 – 19 Jan 2026");
  });

  it("counts the days of a period", () => {
    expect(dayAt("2026-08-01", 30)).toBe("2026-08-31");
    expect(daysIn("2026-02-01", "2026-02-28")).toBe(28);
  });
});

describe("period labels", () => {
  const august = {
    name: "month",
    start: "2026-08-01",
    end: "2026-08-31",
    previous_start: "2026-07-01",
    previous_end: "2026-07-31",
  };

  it("names the filter pill", () => {
    expect(periodLabel({ period: "month", accounts: [] }, "2026-08-20")).toBe("August 2026");
    expect(periodLabel({ period: "month", month: "2026-01", accounts: [] }, "2026-08-20")).toBe("January 2026");
    expect(periodLabel({ period: "month", accounts: [] }, null)).toBe("Latest month");
    expect(periodLabel({ period: "custom", start: "2026-08-10", end: "2026-08-19", accounts: [] }, null)).toBe(
      "10 Aug – 19 Aug 2026",
    );
    expect(periodLabel({ period: "custom", start: "2025-12-10", end: "2026-01-19", accounts: [] }, null)).toBe(
      "10 Dec 2025 – 19 Jan 2026",
    );
  });

  it("names the resolved range and what it is compared with", () => {
    expect(rangeLabel(august)).toBe("August 2026");
    expect(previousLabel(august)).toBe("vs Jul");
    expect(previousLabel(august, "long")).toBe("vs July");
    expect(periodNames(august)).toEqual({ current: "August", previous: "July" });
    expect(rangeLabel({ ...august, name: "last_3_months", start: "2026-06-01" })).toBe("1 Jun – 31 Aug 2026");
    expect(previousLabel({ ...august, name: "last_3_months" })).toBe("vs the 3 months before");
    expect(previousLabel({ ...august, name: "ytd" })).toBe("vs the same dates last year");
    expect(previousLabel({ ...august, name: "custom", previous_start: "2026-07-31", previous_end: "2026-08-09" })).toBe(
      "vs the 10 days before",
    );
    expect(periodNames({ ...august, name: "ytd" })).toEqual({ current: "This period", previous: "Previous period" });
  });
});
```

- [ ] **Step 4: Run them to verify they fail**

Run: `cd apps/web && npm test`
Expected: FAIL, `Failed to resolve import "./params"` and `"./format"`.

- [ ] **Step 5: Implement `params.ts`**

Create `apps/web/src/lib/params.ts`:

```ts
/** The URL is the state (spec 7.1): every page reads its period, accounts and explorer filters
 * from searchParams through these helpers, and every link writes them back the same way.
 * Invalid values fall back to the defaults, so a hand-edited URL never reaches the API as a 422. */

export const PERIODS = ["month", "last_3_months", "ytd", "last_12_months", "custom"] as const;
export type PeriodName = (typeof PERIODS)[number];
export const TX_TYPES = ["expense", "income", "transfer"] as const;
export type TxType = (typeof TX_TYPES)[number];
export const SOURCES = ["rule", "merchant", "jev", "user", "none"] as const;
export type Source = (typeof SOURCES)[number];
export const SAVED = ["unpaired_own", "refunds"] as const;
export type Saved = (typeof SAVED)[number];
export const EXPLORER_KEYS = [
  "q",
  "tx_type",
  "level1",
  "category",
  "merchant_id",
  "is_subscription",
  "category_source",
  "needs_review",
  "saved",
] as const;

export type SearchParams = Record<string, string | string[] | undefined>;

export type Filters = {
  period: PeriodName;
  month?: string; // YYYY-MM; absent = the latest month with data (the API decides)
  start?: string; // YYYY-MM-DD, custom periods only
  end?: string;
  accounts: string[];
};

export type ExplorerFilters = {
  q?: string;
  tx_type?: TxType;
  level1?: string;
  category?: string;
  merchant_id?: string;
  is_subscription?: "true" | "false";
  category_source?: Source;
  needs_review?: "true" | "false";
  saved?: Saved;
};

// The API's bounds: `month` is 1900-01..2099-12, `start` and `end` are 1900-01-01..2100-12-31.
const MONTH = /^(19|20)\d{2}-(0[1-9]|1[0-2])$/;
const FIRST_DAY = "1900-01-01";
const LAST_DAY = "2100-12-31";
const SLUG = /^[a-z0-9_]{1,64}$/;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const BOOLEANS = ["true", "false"] as const;
const Q_MAX = 100; // GET /transactions: q max_length

const first = (value: string | string[] | undefined) => (Array.isArray(value) ? value[0] : value);
const all = (value: string | string[] | undefined) => (value === undefined ? [] : [value].flat());

function oneOf<T extends string>(values: readonly T[], value: string | undefined): T | undefined {
  return values.find((item) => item === value);
}

export const isUuid = (value: string | undefined): value is string => value !== undefined && UUID.test(value);
export const isSlug = (value: string | undefined): value is string => value !== undefined && SLUG.test(value);

/** A real calendar day as YYYY-MM-DD within the API's bounds: it refuses 2026-02-30 and 2101-01-01
 * with a 422. */
export function isDay(value: string | undefined): value is string {
  if (value === undefined || !/^\d{4}-\d{2}-\d{2}$/.test(value) || value < FIRST_DAY || value > LAST_DAY) return false;
  const date = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(date.getTime()) && date.toISOString().startsWith(value);
}

export function parseFilters(params: SearchParams): Filters {
  const period = oneOf(PERIODS, first(params.period)) ?? "month";
  const accounts = all(params.account_id).filter(isUuid);
  if (period === "custom") {
    const start = first(params.start);
    const end = first(params.end);
    return isDay(start) && isDay(end) && start <= end
      ? { period, start, end, accounts }
      : { period: "month", accounts };
  }
  const month = first(params.month);
  return month !== undefined && MONTH.test(month) ? { period, month, accounts } : { period, accounts };
}

/** The period and account params in a fixed order; the default period is left out. */
export function filterParams(filters: Filters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.period !== "month") params.set("period", filters.period);
  if (filters.month) params.set("month", filters.month);
  if (filters.start) params.set("start", filters.start);
  if (filters.end) params.set("end", filters.end);
  for (const id of filters.accounts) params.append("account_id", id);
  return params;
}

/** A link that keeps the period and accounts, plus page params (undefined leaves one out). */
export function withFilters(path: string, filters: Filters, extra: Record<string, string | undefined> = {}): string {
  const params = filterParams(filters);
  for (const [key, value] of Object.entries(extra)) if (value !== undefined) params.set(key, value);
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

export function parseExplorer(params: SearchParams): ExplorerFilters {
  const q = first(params.q)?.trim().slice(0, Q_MAX);
  const level1 = first(params.level1);
  const category = first(params.category);
  const merchantId = first(params.merchant_id);
  return {
    q: q || undefined,
    tx_type: oneOf(TX_TYPES, first(params.tx_type)),
    level1: isSlug(level1) ? level1 : undefined,
    category: isSlug(category) ? category : undefined,
    merchant_id: isUuid(merchantId) ? merchantId : undefined,
    is_subscription: oneOf(BOOLEANS, first(params.is_subscription)),
    category_source: oneOf(SOURCES, first(params.category_source)),
    needs_review: oneOf(BOOLEANS, first(params.needs_review)),
    saved: oneOf(SAVED, first(params.saved)),
  };
}

/** The explorer's query: the period and accounts, then its filters. The page URL and the API
 * use the same names, so this string serves both. */
export function explorerParams(filters: Filters, explorer: ExplorerFilters): URLSearchParams {
  const params = filterParams(filters);
  for (const [key, value] of Object.entries(explorer)) if (value) params.set(key, value);
  return params;
}

export function toSearchParams(search: URLSearchParams): SearchParams {
  const out: SearchParams = {};
  for (const key of new Set(search.keys())) {
    const values = search.getAll(key);
    out[key] = values.length > 1 ? values : values[0];
  }
  return out;
}

/** The query string with some params replaced; undefined or [] removes a param. */
export function replaceParams(query: string, changes: Record<string, string | string[] | undefined>): string {
  const params = new URLSearchParams(query);
  for (const [key, value] of Object.entries(changes)) {
    params.delete(key);
    for (const item of value === undefined ? [] : [value].flat()) params.append(key, item);
  }
  return params.toString();
}

/** The param changes that select a period; the others (explorer filters, accounts) stay. */
export function periodChanges(choice: Omit<Filters, "accounts">): Record<string, string | undefined> {
  return {
    period: choice.period === "month" ? undefined : choice.period,
    month: choice.month,
    start: choice.start,
    end: choice.end,
  };
}

export function clearedExplorer(query: string): string {
  return replaceParams(query, Object.fromEntries(EXPLORER_KEYS.map((key) => [key, undefined])));
}

/** "2026-01" shifted by -1 is "2025-12" (the "Previous month" preset). */
export function shiftMonth(month: string, months: number): string {
  const [year, index] = month.split("-").map(Number);
  const total = year * 12 + (index - 1) + months;
  return `${Math.floor(total / 12)}-${String((total % 12) + 1).padStart(2, "0")}`;
}

/** A merchant page shows spending unless its link asks for income (an employer, say). */
export function detailType(params: SearchParams): "expense" | "income" {
  return first(params.type) === "income" ? "income" : "expense";
}
```

- [ ] **Step 6: Implement `format.ts`**

Create `apps/web/src/lib/format.ts`:

```ts
/** Money and dates for display (spec 8: Intl, no date library). Amounts arrive as decimal
 * strings. Days arrive as YYYY-MM-DD and are formatted in UTC, so a browser west of Greenwich
 * never shows the day before. */

import type { Filters } from "./params";

const LOCALE = "en-IE";
const EUR = { style: "currency", currency: "EUR" } as const;
const NO_CENTS = { minimumFractionDigits: 0, maximumFractionDigits: 0 } as const;
const DAY_MS = 86_400_000;

const cents = new Intl.NumberFormat(LOCALE, EUR);
const whole = new Intl.NumberFormat(LOCALE, { ...EUR, ...NO_CENTS });
const signedCents = new Intl.NumberFormat(LOCALE, { ...EUR, signDisplay: "exceptZero" });
const signedWhole = new Intl.NumberFormat(LOCALE, { ...EUR, ...NO_CENTS, signDisplay: "exceptZero" });
const compact = new Intl.NumberFormat(LOCALE, { ...EUR, notation: "compact", maximumFractionDigits: 1 });

type Amount = string | number | null | undefined;

export const toNumber = (value: Amount): number => (value === null || value === undefined ? 0 : Number(value));
export const money = (value: Amount) => cents.format(toNumber(value)); // €2,184.00
export const moneyWhole = (value: Amount) => whole.format(toNumber(value)); // €2,184
/** With an explicit sign, so money in (+€12.34) never reads as money out (-€12.34). */
export const signedMoney = (value: Amount) => signedCents.format(toNumber(value));
export const signedMoneyWhole = (value: Amount) => signedWhole.format(toNumber(value));
export const compactMoney = (value: number) => compact.format(value); // €2.4K, for axis ticks
export const percent = (share: number) => `${Math.round(share * 100)}%`;
/** The savings rate; empty without income (docs/money-rules.md). */
export const rate = (value: number | null) => (value === null ? "—" : `${(value * 100).toFixed(1)}%`);

const utc = (day: string) => new Date(`${day.slice(0, 10)}T00:00:00Z`);
const dates = (options: Intl.DateTimeFormatOptions) =>
  new Intl.DateTimeFormat(LOCALE, { timeZone: "UTC", ...options });
const monthYear = dates({ month: "long", year: "numeric" });
const monthLong = dates({ month: "long" });
const monthAbbr = dates({ month: "short" });
const weekdayDay = dates({ weekday: "short", day: "numeric", month: "short" });
const dayMonth = dates({ day: "numeric", month: "short" });
const dayMonthYear = dates({ day: "numeric", month: "short", year: "numeric" });
const stamp = new Intl.DateTimeFormat(LOCALE, { dateStyle: "medium", timeStyle: "short" });

export const monthLabel = (month: string) => monthYear.format(utc(`${month}-01`)); // August 2026
export const monthShort = (month: string) => monthAbbr.format(utc(`${month}-01`)); // Aug
export const dayHeader = (day: string) => weekdayDay.format(utc(day)); // Sat, 1 Aug
export const dayShort = (day: string) => dayMonth.format(utc(day)); // 1 Aug
export const dayLong = (day: string) => dayMonthYear.format(utc(day)); // 1 Aug 2026
/** An import's timestamp, in the reader's own time zone. */
export const dateTime = (iso: string) => stamp.format(new Date(iso));

/** The day `offset` days after `start`: the cumulative charts label day N of a period. */
export const dayAt = (start: string, offset: number) =>
  new Date(utc(start).getTime() + offset * DAY_MS).toISOString().slice(0, 10);
export const daysIn = (start: string, end: string) =>
  Math.round((utc(end).getTime() - utc(start).getTime()) / DAY_MS) + 1;

/** A range of days, with the start's year only when it spans two years: "10 Aug – 19 Aug 2026",
 * "10 Dec 2025 – 19 Jan 2026". */
export const dayRange = (start: string, end: string) =>
  `${start.slice(0, 4) === end.slice(0, 4) ? dayShort(start) : dayLong(start)} – ${dayLong(end)}`;

/** The fields of Schemas["PeriodOut"] these labels need. */
export type PeriodLike = { name: string; start: string; end: string; previous_start: string; previous_end: string };

/** The period pill: "August 2026", "Last 3 months", "10 Aug – 19 Aug 2026". */
export function periodLabel(filters: Filters, latestDay: string | null): string {
  switch (filters.period) {
    case "month": {
      const month = filters.month ?? latestDay?.slice(0, 7);
      return month ? monthLabel(month) : "Latest month";
    }
    case "last_3_months":
      return "Last 3 months";
    case "last_12_months":
      return "Last 12 months";
    case "ytd":
      return "Year to date";
    case "custom":
      return dayRange(filters.start!, filters.end!);
  }
}

/** A page's resolved period: "August 2026" or "1 Jun – 31 Aug 2026". */
export function rangeLabel(period: PeriodLike): string {
  return period.name === "month" ? monthLabel(period.start.slice(0, 7)) : dayRange(period.start, period.end);
}

/** What a delta compares with (spec 2.6: the previous period of the same length). */
export function previousLabel(period: PeriodLike, style: "short" | "long" = "short"): string {
  if (period.name === "month") return `vs ${(style === "short" ? monthAbbr : monthLong).format(utc(period.previous_start))}`;
  if (period.name === "last_3_months") return "vs the 3 months before";
  if (period.name === "last_12_months") return "vs the 12 months before";
  if (period.name === "ytd") return "vs the same dates last year";
  return `vs the ${daysIn(period.previous_start, period.previous_end)} days before`;
}

/** The two series of a cumulative chart: "August" and "July", or this and the previous period. */
export function periodNames(period: PeriodLike): { current: string; previous: string } {
  if (period.name !== "month") return { current: "This period", previous: "Previous period" };
  return { current: monthLong.format(utc(period.start)), previous: monthLong.format(utc(period.previous_start)) };
}
```

- [ ] **Step 7: Run the tests**

Run: `cd apps/web && npm test`
Expected: PASS, both files. If an `Intl` string differs only in a character the runtime's ICU chooses (for example a narrow no-break space), fix the expectation to what `node -e` prints for the same call, not the helper.

- [ ] **Step 8: Run the gate**

Run: `cd apps/web && npm run lint && npx tsc --noEmit && npm run build`
Expected: no errors.

- [ ] **Step 9: Commit**

```bash
git add apps/web/package.json apps/web/package-lock.json apps/web/vitest.config.mts apps/web/src/lib/params.ts apps/web/src/lib/params.test.ts apps/web/src/lib/format.ts apps/web/src/lib/format.test.ts
git commit -m "feat: add URL state and formatting helpers for the web app"
```

---

### Task 2: Money helpers — deltas, colours, labels, breakdown items

**Files:**
- Create: `apps/web/src/lib/delta.ts`, `apps/web/src/lib/colors.ts`, `apps/web/src/lib/labels.ts`, `apps/web/src/lib/definitions.ts`, `apps/web/src/lib/breakdown.ts`
- Test: `apps/web/src/lib/delta.test.ts`, `apps/web/src/lib/colors.test.ts`, `apps/web/src/lib/labels.test.ts`, `apps/web/src/lib/breakdown.test.ts`

**Interfaces:**
- Consumes: `Filters`, `TxType`, `withFilters` (Task 1).
- Produces:
  - `delta.ts`: `Good = "up" | "down"`, `Unit = "percent" | "euro" | "points"`, `Tone = "good" | "bad" | "neutral"`, `Delta = { kind: "hidden" } | { kind: "new" } | { kind: "change"; direction: "up" | "down" | "flat"; tone: Tone; text: string }`, `delta(current: number | null, previous: number | null | undefined, good: Good, unit: Unit): Delta`, `atSameDay(cumulative): { current: number | null; previous: number | null }` (`current` is null when the current series is empty), `periodHasData(months: { month: string; has_data: boolean }[], period: { start: string; end: string }): boolean` (Decision G).
  - `colors.ts`: `OTHER_COLOR`, `groupColor(level1: string | null | undefined, slots: Record<string, number>): string`, `rampColor(index: number): string`, `foldBySlot(rows: BreakdownRow[], slots): BreakdownRow[]`.
  - `labels.ts`: `Dimension = "group" | "category" | "merchant"`, `label(slug)`, `plural(count, one, many)`, `groupHint(level1, categories)`, `rowName(row, dimension)`, `rowHint(row, dimension, categories)`, `sourceLabel(source)`, `accountsLabel(ids, accounts)`, `knownGroup(level1, categories)`, `knownCategory(slug, categories, where: { type: TxType; level1?: string })`.
  - `definitions.ts`: `DEFINITIONS = { income, expenses, savings, savingsRate }`.
  - `breakdown.ts`: `BreakdownItem = { key; name; hint; href: string | null; color?: string; share: number; amount: string; delta: Delta }`, `BreakdownContext = { categories; slots: Record<string, number> | null; filters: Filters; good: Good; type: "expense" | "income" }`, `breakdownItems(rows, dimension, context): BreakdownItem[]`.

- [ ] **Step 1: Write the failing tests**

Create `apps/web/src/lib/delta.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import { atSameDay, delta, periodHasData } from "./delta";

describe("delta", () => {
  it("reads spending that went down as good", () => {
    expect(delta(2184, 2374, "down", "percent")).toEqual({ kind: "change", direction: "down", tone: "good", text: "−8%" });
  });

  it("reads income, savings and the rate that went up as good", () => {
    expect(delta(3250, 3186, "up", "percent")).toMatchObject({ tone: "good", text: "+2%" });
    expect(delta(1066, 811, "up", "euro")).toMatchObject({ direction: "up", tone: "good", text: "+€255" });
    expect(delta(0.328, 0.258, "up", "points")).toMatchObject({ tone: "good", text: "+7 pts" });
  });

  it("reads more spending as bad", () => {
    expect(delta(306.4, 273.6, "down", "percent")).toMatchObject({ direction: "up", tone: "bad", text: "+12%" });
  });

  it("hides the delta without previous data and says new after a zero", () => {
    expect(delta(100, null, "down", "percent")).toEqual({ kind: "hidden" });
    expect(delta(100, undefined, "down", "percent")).toEqual({ kind: "hidden" });
    expect(delta(null, 0.2, "up", "points")).toEqual({ kind: "hidden" });
    expect(delta(51, 0, "down", "percent")).toEqual({ kind: "new" });
    expect(delta(0, 0, "down", "percent")).toEqual({ kind: "change", direction: "flat", tone: "neutral", text: "0%" });
  });

  it("compares with a negative month (refunds only) by its size", () => {
    expect(delta(120, -30, "down", "percent")).toMatchObject({ direction: "up", tone: "bad", text: "+500%" });
  });
});

describe("atSameDay", () => {
  const points = (...totals: string[]) => totals.map((total) => ({ total }));

  it("reads the previous period at the current period's latest day", () => {
    expect(atSameDay({ current: points("10", "30"), previous: points("5", "20", "60") })).toEqual({ current: 30, previous: 20 });
  });

  it("uses the end of a shorter previous period, and nothing without one", () => {
    expect(atSameDay({ current: points("1", "2", "3"), previous: points("7", "9") })).toEqual({ current: 3, previous: 9 });
    expect(atSameDay({ current: points("4"), previous: null })).toEqual({ current: 4, previous: null });
  });

  it("reads no data, never 0, when the current series is empty", () => {
    // The API sends [] when the period starts after the latest imported day, or there is no data.
    expect(atSameDay({ current: [], previous: points("5", "20") })).toEqual({ current: null, previous: null });
  });
});

describe("periodHasData", () => {
  const months = [
    { month: "2026-06", has_data: true },
    { month: "2026-07", has_data: false },
    { month: "2026-08", has_data: false },
  ];

  it("reads only the months of the period (Decision G: no data, never 0)", () => {
    expect(periodHasData(months, { start: "2026-08-01", end: "2026-08-31" })).toBe(false);
    expect(periodHasData(months, { start: "2026-07-10", end: "2026-08-19" })).toBe(false);
    expect(periodHasData(months, { start: "2026-06-01", end: "2026-08-31" })).toBe(true);
  });

  it("trusts the API's numbers for a range that starts before the 12-month series", () => {
    expect(periodHasData(months, { start: "2025-01-01", end: "2026-08-31" })).toBe(true);
    expect(periodHasData([], { start: "2026-08-01", end: "2026-08-31" })).toBe(true);
  });
});
```

Create `apps/web/src/lib/colors.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import type { Schemas } from "./api";
import { foldBySlot, groupColor, rampColor } from "./colors";

type Row = Schemas["BreakdownRow"];

const slots = { home: 1, shopping: 2, leisure: 3, transport: 4, credit_card: 5 };
const row = (key: string, amount: string, share: number, previous: string | null, folded = 0): Row => ({
  key,
  label: null,
  level1: key === "_other" ? null : key,
  category_slug: null,
  merchant_id: null,
  amount,
  share,
  previous,
  count: 1,
  folded,
});

describe("colours", () => {
  it("paints a group by its slot, never by its rank", () => {
    expect(groupColor("shopping", slots)).toBe("var(--chart-2)");
    expect(groupColor("health", slots)).toBe("var(--chart-other)");
    expect(groupColor(null, slots)).toBe("var(--chart-other)");
  });

  it("steps the ramp and keeps its last step for the rest", () => {
    expect([0, 1, 5, 9].map(rampColor)).toEqual(["var(--ramp-1)", "var(--ramp-2)", "var(--ramp-6)", "var(--ramp-6)"]);
  });

  it("folds the groups without a colour into Other", () => {
    const folded = foldBySlot(
      [
        row("home", "830.00", 0.38, "800.00"),
        row("health", "100.00", 0.05, "90.00"),
        row("shopping", "480.00", 0.22, "500.00"),
        row("_other", "90.00", 0.04, "100.00", 3),
      ],
      slots,
    );
    expect(folded.map((r) => r.key)).toEqual(["home", "shopping", "_other"]);
    expect(folded[2]).toMatchObject({ amount: "190.00", share: 0.09, previous: "190.00", folded: 4, count: 2 });
  });

  it("leaves the rows alone when every group has a colour", () => {
    const rows = [row("home", "10.00", 1, null)];
    expect(foldBySlot(rows, slots)).toBe(rows);
  });
});
```

Create `apps/web/src/lib/labels.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import type { Schemas } from "./api";
import {
  accountsLabel,
  groupHint,
  knownCategory,
  knownGroup,
  label,
  plural,
  rowHint,
  rowName,
  sourceLabel,
} from "./labels";

type Row = Schemas["BreakdownRow"];

const categories: Schemas["CategoryOut"][] = [
  { slug: "groceries", tx_type: "expense", level1: "shopping" },
  { slug: "fashion", tx_type: "expense", level1: "shopping" },
  { slug: "electronics", tx_type: "expense", level1: "shopping" },
  { slug: "home_goods", tx_type: "expense", level1: "shopping" },
  { slug: "credit_card_spending", tx_type: "expense", level1: "credit_card" },
  { slug: "salary", tx_type: "income", level1: "income" },
];
const row = (fields: Partial<Row> & { key: string }): Row => ({
  label: null,
  level1: null,
  category_slug: null,
  merchant_id: null,
  amount: "0.00",
  share: 0,
  previous: null,
  count: 1,
  folded: 0,
  ...fields,
});

describe("labels", () => {
  it("reads slugs as words", () => {
    expect(label("restaurants_bars")).toBe("Restaurants bars");
    expect(label(null)).toBe("Uncategorized");
    expect(plural(1, "transaction", "transactions")).toBe("1 transaction");
    expect(plural(31, "transaction", "transactions")).toBe("31 transactions");
  });

  it("describes a group by its first categories", () => {
    expect(groupHint("shopping", categories)).toBe("Groceries, fashion, electronics…");
    expect(groupHint("credit_card", categories)).toBe("Not itemized: card statements are not imported");
    // Decision I: uncategorized rows never reach /review, so the hint does not send the user there.
    expect(groupHint("uncategorized", categories)).toBe("Not categorized yet");
    expect(groupHint("unknown", categories)).toBe("");
  });

  it("names rows, including the folded ones and merchants without a merchant", () => {
    expect(rowName(row({ key: "_other", folded: 12 }), "merchant")).toBe("Other 12 merchants");
    expect(rowName(row({ key: "_other", folded: 3 }), "group")).toBe("Other");
    expect(rowName(row({ key: "category:credit_card_spending", category_slug: "credit_card_spending" }), "merchant")).toBe(
      "Credit card spending",
    );
    expect(rowHint(row({ key: "_other", folded: 3 }), "group", categories)).toBe("3 groups");
    expect(rowHint(row({ key: "fashion", level1: "shopping" }), "category", categories)).toBe("Shopping");
    expect(rowHint(row({ key: "m", category_slug: "groceries", count: 12 }), "merchant", categories)).toBe(
      "Groceries · 12 transactions",
    );
  });

  it("labels sources and account selections", () => {
    expect(sourceLabel("jev")).toBe("AI (jev)");
    expect(sourceLabel("none")).toBe("Pending");
    const accounts = [{ id: "a", name: "Main" }, { id: "b", name: "Savings" }];
    expect(accountsLabel([], accounts)).toBe("All accounts");
    expect(accountsLabel(["b"], accounts)).toBe("Savings");
    expect(accountsLabel(["a", "b"], accounts)).toBe("2 accounts");
  });

  it("knows which groups and categories exist", () => {
    expect(knownGroup("shopping", categories)).toBe(true);
    expect(knownGroup("uncategorized", categories)).toBe(true);
    expect(knownGroup("income", categories)).toBe(false);
    expect(knownCategory("fashion", categories, { type: "expense", level1: "shopping" })).toBe(true);
    expect(knownCategory("fashion", categories, { type: "expense", level1: "home" })).toBe(false);
    expect(knownCategory("uncategorized", categories, { type: "expense", level1: "uncategorized" })).toBe(true);
    // Uncategorized money in counts as income: /income lists it under the key "uncategorized".
    expect(knownCategory("uncategorized", categories, { type: "income" })).toBe(true);
    expect(knownCategory("salary", categories, { type: "income" })).toBe(true);
  });
});
```

Create `apps/web/src/lib/breakdown.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import type { Schemas } from "./api";
import { breakdownItems } from "./breakdown";

type Row = Schemas["BreakdownRow"];

const M = "33333333-3333-4333-8333-333333333333";
const categories: Schemas["CategoryOut"][] = [
  { slug: "groceries", tx_type: "expense", level1: "shopping" },
  { slug: "salary", tx_type: "income", level1: "income" },
];
const august = { period: "month" as const, month: "2026-08", accounts: [] };
const row = (fields: Partial<Row> & { key: string }): Row => ({
  label: null,
  level1: null,
  category_slug: null,
  merchant_id: null,
  amount: "0.00",
  share: 0,
  previous: null,
  count: 1,
  folded: 0,
  ...fields,
});

describe("breakdownItems", () => {
  it("links a category one level deeper and paints it with its group", () => {
    const [groceries, other] = breakdownItems(
      [
        row({ key: "groceries", level1: "shopping", category_slug: "groceries", amount: "268.40", share: 0.56, previous: "280.00" }),
        row({ key: "_other", amount: "10.00", previous: "20.00", folded: 2 }),
      ],
      "category",
      { categories, slots: { shopping: 2 }, filters: august, good: "down", type: "expense" },
    );
    expect(groceries).toMatchObject({
      name: "Groceries",
      hint: "Shopping",
      href: "/spending/shopping/groceries?month=2026-08",
      color: "var(--chart-2)",
      share: 0.56,
      amount: "268.40",
    });
    expect(groceries.delta).toMatchObject({ tone: "good", text: "−4%" });
    expect(other).toMatchObject({ name: "Other", hint: "2 categories", href: null, color: "var(--chart-other)" });
  });

  it("opens a merchant with its type and leaves a row without a merchant unlinked", () => {
    const [employer, card] = breakdownItems(
      [
        row({ key: M, label: "ZZTEST EMPLOYER", merchant_id: M, category_slug: "salary", level1: "income", count: 2 }),
        row({ key: "category:credit_card_spending", category_slug: "credit_card_spending", level1: "credit_card" }),
      ],
      "merchant",
      { categories, slots: null, filters: august, good: "up", type: "income" },
    );
    expect(employer).toMatchObject({
      name: "ZZTEST EMPLOYER",
      hint: "Salary · 2 transactions",
      href: `/merchants/${M}?month=2026-08&type=income`,
    });
    expect(employer.color).toBeUndefined();
    expect(card).toMatchObject({ name: "Credit card spending", href: null });
  });

  it("links a group to its page and an income category to the income pages", () => {
    const [home] = breakdownItems([row({ key: "home", level1: "home" })], "group", {
      categories,
      slots: { home: 1 },
      filters: { period: "ytd", accounts: [] },
      good: "down",
      type: "expense",
    });
    expect(home).toMatchObject({ href: "/spending/home?period=ytd", color: "var(--chart-1)" });
    const [salary] = breakdownItems([row({ key: "salary", level1: "income" })], "category", {
      categories,
      slots: null,
      filters: august,
      good: "up",
      type: "income",
    });
    expect(salary.href).toBe("/income/salary?month=2026-08");
  });
});
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd apps/web && npm test`
Expected: FAIL, `Failed to resolve import "./delta"` (and the other three modules).

- [ ] **Step 3: Implement `delta.ts`**

Create `apps/web/src/lib/delta.ts`:

```ts
/** Changes against the previous period (spec 2.6): hidden when the previous period has no data,
 * "new" when the previous value was 0, and a tone that says whether the change is good. The
 * arrow and the sign carry the meaning, so it never depends on colour alone. */

export type Good = "up" | "down";
export type Unit = "percent" | "euro" | "points";
export type Tone = "good" | "bad" | "neutral";
export type Delta =
  | { kind: "hidden" }
  | { kind: "new" }
  | { kind: "change"; direction: "up" | "down" | "flat"; tone: Tone; text: string };

const MINUS = "−";
const euro = new Intl.NumberFormat("en-IE", {
  style: "currency",
  currency: "EUR",
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

const flat = (text: string): Delta => ({ kind: "change", direction: "flat", tone: "neutral", text });

/** `good` says which way is good: less spending, more income, more savings, a higher rate.
 * Rates are fractions (0.328), so "points" moves them by 100. */
export function delta(current: number | null, previous: number | null | undefined, good: Good, unit: Unit): Delta {
  if (current === null || previous === null || previous === undefined) return { kind: "hidden" };
  let change: number;
  let text: string;
  if (unit === "percent") {
    if (previous === 0) return current === 0 ? flat("0%") : { kind: "new" };
    change = Math.round(((current - previous) / Math.abs(previous)) * 100);
    text = `${Math.abs(change)}%`;
  } else if (unit === "euro") {
    change = Math.round(current - previous);
    text = euro.format(Math.abs(change));
  } else {
    change = Math.round((current - previous) * 100);
    text = `${Math.abs(change)} pts`;
  }
  if (change === 0) return flat(text);
  const direction = change > 0 ? "up" : "down";
  return { kind: "change", direction, tone: direction === good ? "good" : "bad", text: `${change > 0 ? "+" : MINUS}${text}` };
}

type Cumulative = { current: { total: string }[]; previous: { total: string }[] | null };

/** "Spent so far against the previous period at the same day" (spec 7.1). The current series
 * stops at the latest imported day, and is empty when the period has no data yet: that reads as
 * no data, never 0 (spec 2.6). The previous one is read at the same day, or at its end when it
 * is shorter (February against January). */
export function atSameDay(cumulative: Cumulative): { current: number | null; previous: number | null } {
  const index = cumulative.current.length - 1;
  if (index < 0) return { current: null, previous: null };
  const current = Number(cumulative.current[index].total);
  const before = cumulative.previous;
  if (!before || before.length === 0) return { current, previous: null };
  return { current, previous: Number(before[Math.min(index, before.length - 1)].total) };
}

type MonthFlag = { month: string; has_data: boolean };

/** Whether any month of the period has data (spec 2.6: a month has data when at least one
 * transaction of the selected accounts is booked in it). Without data, the KPI tiles read "—",
 * never 0 (Decision G). The series holds the 12 months that end with the period, so a longer
 * custom range cannot be judged from it: the API's numbers stand. */
export function periodHasData(months: MonthFlag[], period: { start: string; end: string }): boolean {
  const from = period.start.slice(0, 7);
  const to = period.end.slice(0, 7);
  if (months.length === 0 || from < months[0].month) return true;
  return months.some((point) => point.has_data && point.month >= from && point.month <= to);
}
```

- [ ] **Step 4: Implement `colors.ts`**

Create `apps/web/src/lib/colors.ts`:

```ts
/** Colour follows the group, never its rank (spec 7.2). Slots 1-5 come from the API
 * (Overview.group_slots, by all-time spend), so a period filter never repaints a group. */

import type { Schemas } from "./api";

type Row = Schemas["BreakdownRow"];

export const OTHER_COLOR = "var(--chart-other)";

export function groupColor(level1: string | null | undefined, slots: Record<string, number>): string {
  const slot = level1 ? slots[level1] : undefined;
  return slot ? `var(--chart-${slot})` : OTHER_COLOR;
}

/** The one-hue ramp inside a group page, darkest = largest; the 6th step also paints "_other". */
export const rampColor = (index: number) => `var(--ramp-${Math.min(index, 5) + 1})`;

const sum = (values: number[]) => values.reduce((total, value) => total + value, 0);

/** The Groups view shows the five coloured groups and folds the rest into one "Other" row
 * (spec 7.2). The API ranks its top five by the period's spend, so a group without a slot can
 * be among them: it is folded here, with the API's own "_other" row. */
export function foldBySlot(rows: Row[], slots: Record<string, number>): Row[] {
  const kept = rows.filter((row) => row.key !== "_other" && slots[row.key] !== undefined);
  const rest = rows.filter((row) => !kept.includes(row));
  if (rest.length === 0) return rows;
  const other: Row = {
    key: "_other",
    label: null,
    level1: null,
    category_slug: null,
    merchant_id: null,
    amount: sum(rest.map((row) => Number(row.amount))).toFixed(2),
    share: Math.round(sum(rest.map((row) => row.share)) * 10_000) / 10_000,
    previous: rest.every((row) => row.previous !== null) ? sum(rest.map((row) => Number(row.previous))).toFixed(2) : null,
    count: sum(rest.map((row) => row.count)),
    folded: sum(rest.map((row) => (row.key === "_other" ? (row.folded ?? 0) : 1))),
  };
  return [...kept, other];
}
```

- [ ] **Step 5: Implement `labels.ts` and `definitions.ts`**

Create `apps/web/src/lib/labels.ts`:

```ts
/** Names shown for slugs, breakdown rows, sources and account selections. Categories are data
 * (supabase/seed/categories.yaml), so their names come from their slugs. */

import type { Schemas } from "./api";
import type { TxType } from "./params";

type Category = Schemas["CategoryOut"];
type Row = Schemas["BreakdownRow"];

export type Dimension = "group" | "category" | "merchant";

const capitalize = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

/** "restaurants_bars" reads "Restaurants bars"; a row without a category is "Uncategorized". */
export function label(slug: string | null | undefined): string {
  return slug ? capitalize(slug.replaceAll("_", " ")) : "Uncategorized";
}

export const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;

/** The line under a group's name: its first categories (mockup: "Rent, utilities, internet"). */
export function groupHint(level1: string, categories: Category[]): string {
  if (level1 === "credit_card") return "Not itemized: card statements are not imported";
  if (level1 === "uncategorized") return "Not categorized yet"; // these rows never reach /review
  const names = categories.filter((c) => c.level1 === level1).map((c) => c.slug.replaceAll("_", " "));
  if (names.length === 0) return "";
  const text = capitalize(names.slice(0, 3).join(", "));
  return names.length > 3 ? `${text}…` : text;
}

export function rowName(row: Row, dimension: Dimension): string {
  if (row.key === "_other") {
    return dimension === "merchant" ? `Other ${plural(row.folded ?? 0, "merchant", "merchants")}` : "Other";
  }
  // A merchant row without a merchant is keyed "category:<slug>" and reads as its category.
  return dimension === "merchant" ? (row.label ?? label(row.category_slug)) : label(row.key);
}

export function rowHint(row: Row, dimension: Dimension, categories: Category[]): string {
  if (row.key === "_other") {
    if (dimension === "merchant") return "";
    const folded = row.folded ?? 0;
    return dimension === "group" ? plural(folded, "group", "groups") : plural(folded, "category", "categories");
  }
  if (dimension === "group") return groupHint(row.key, categories);
  if (dimension === "category") return label(row.level1);
  return `${label(row.category_slug)} · ${plural(row.count, "transaction", "transactions")}`;
}

const SOURCES: Record<string, string> = { rule: "Rule", merchant: "Merchant", jev: "AI (jev)", user: "You", none: "Pending" };

/** Who categorized a row (spec 7.3). */
export const sourceLabel = (source: string) => SOURCES[source] ?? source;

export function accountsLabel(ids: string[], accounts: { id: string; name: string }[]): string {
  if (ids.length === 0) return "All accounts";
  if (ids.length === 1) return accounts.find((account) => account.id === ids[0])?.name ?? "1 account";
  return `${ids.length} accounts`;
}

/** A group in the URL must exist, or the page is a 404, never an empty page. */
export function knownGroup(level1: string, categories: Category[]): boolean {
  return level1 === "uncategorized" || categories.some((c) => c.tx_type === "expense" && c.level1 === level1);
}

export function knownCategory(slug: string, categories: Category[], where: { type: TxType; level1?: string }): boolean {
  // Rows without a category: money out sits in the "uncategorized" group, money in in Income.
  if (slug === "uncategorized" && (where.level1 === "uncategorized" || where.type === "income")) return true;
  return categories.some(
    (c) => c.slug === slug && c.tx_type === where.type && (where.level1 === undefined || c.level1 === where.level1),
  );
}
```

Create `apps/web/src/lib/definitions.ts` (the texts are the "The numbers" table of `docs/money-rules.md`, word for word):

```ts
/** The ⓘ texts on the KPI tiles, quoted from docs/money-rules.md ("The numbers"). Change them
 * there first: the dashboards and the slice 4 agent must never disagree. */
export const DEFINITIONS = {
  income: "The sum of income-type rows: rows with an income category, and uncategorized money in.",
  expenses:
    "Minus the sum of expense-type rows: rows with an expense category, and uncategorized money out. A refund (money in with an expense category) subtracts.",
  savings: "Income − expenses. Money you move to your own savings or investment accounts counts as saved.",
  savingsRate:
    "Savings ÷ income. It can be negative (you spent more than you earned). It is empty when there is no income.",
} as const;
```

These are the words of the file shipped by 3a (its Income and Expenses rows were reworded in flight). If `docs/money-rules.md` on `main` words them differently, copy the merged file's words.

- [ ] **Step 6: Implement `breakdown.ts`**

Create `apps/web/src/lib/breakdown.ts`:

```ts
/** Breakdown rows as the tables and donuts show them: named, linked one level deeper, coloured
 * by group on the overview (spec 7.2), and compared with the previous period. */

import type { Schemas } from "./api";
import { groupColor } from "./colors";
import { delta, type Delta, type Good } from "./delta";
import { rowHint, rowName, type Dimension } from "./labels";
import { withFilters, type Filters } from "./params";

type Row = Schemas["BreakdownRow"];

export type BreakdownItem = {
  key: string;
  name: string;
  hint: string;
  href: string | null;
  color?: string;
  share: number;
  amount: string;
  delta: Delta;
};

export type BreakdownContext = {
  categories: Schemas["CategoryOut"][];
  slots: Record<string, number> | null; // null: no group colours (the detail pages use the ramp)
  filters: Filters;
  good: Good;
  type: "expense" | "income";
};

function hrefOf(row: Row, dimension: Dimension, { filters, type }: BreakdownContext): string | null {
  if (row.key === "_other") return null;
  if (dimension === "group") return withFilters(`/spending/${row.key}`, filters);
  if (dimension === "category") {
    return withFilters(type === "income" ? `/income/${row.key}` : `/spending/${row.level1 ?? "uncategorized"}/${row.key}`, filters);
  }
  if (!row.merchant_id) return null;
  return withFilters(`/merchants/${row.merchant_id}`, filters, { type: type === "income" ? "income" : undefined });
}

export function breakdownItems(rows: Row[], dimension: Dimension, context: BreakdownContext): BreakdownItem[] {
  return rows.map((row) => ({
    key: row.key,
    name: rowName(row, dimension),
    hint: rowHint(row, dimension, context.categories),
    href: hrefOf(row, dimension, context),
    color: context.slots
      ? groupColor(dimension === "group" && row.key !== "_other" ? row.key : row.level1, context.slots)
      : undefined,
    share: row.share,
    amount: row.amount,
    delta: delta(Number(row.amount), row.previous === null ? null : Number(row.previous), context.good, "percent"),
  }));
}
```

- [ ] **Step 7: Run the tests**

Run: `cd apps/web && npm test`
Expected: PASS, all six test files.

- [ ] **Step 8: Run the gate**

Run: `cd apps/web && npm run lint && npx tsc --noEmit && npm run build`
Expected: no errors. If `tsc` says `folded` is not optional on `BreakdownRow`, keep the `?? 0` anyway: it is harmless and survives either shape of the generated type.

- [ ] **Step 9: Commit**

```bash
git add apps/web/src/lib/delta.ts apps/web/src/lib/delta.test.ts apps/web/src/lib/colors.ts apps/web/src/lib/colors.test.ts apps/web/src/lib/labels.ts apps/web/src/lib/labels.test.ts apps/web/src/lib/definitions.ts apps/web/src/lib/breakdown.ts apps/web/src/lib/breakdown.test.ts
git commit -m "feat: add delta, colour and label helpers for the dashboards"
```

---

### Task 3: Tokens, layout shell and top bar

**Files:**
- Modify: `apps/web/src/app/globals.css`, `apps/web/src/components/ui/card.tsx`, `apps/web/src/components/ui/table.tsx`, `apps/web/src/app/layout.tsx`, `apps/web/src/lib/api.ts`
- Modify (outer `<main>` becomes a `<div>`): `apps/web/src/app/imports/page.tsx`, `apps/web/src/app/transactions/page.tsx`, `apps/web/src/app/review/page.tsx`
- Create: `apps/web/src/app/error.tsx`, `apps/web/src/components/shell/top-bar.tsx`, `nav-links.tsx`, `filter-bar.tsx`, `period-picker.tsx`, `account-picker.tsx`
- Add (shadcn): `tooltip`, `popover`, `separator`, `field` (brings `label`), `empty`

**Interfaces:**
- Consumes: `parseFilters`, `filterParams`, `toSearchParams`, `replaceParams`, `periodChanges`, `shiftMonth`, `isDay`, `Filters` (Task 1); `periodLabel` (Task 1); `accountsLabel` (Task 2).
- Produces:
  - Tailwind utilities from the tokens: `bg-card` (surface), `rounded-card` (16 px), `text-income`, `text-good`, `text-bad`, `bg-chart-other`, `bg-ramp-1` … `bg-ramp-6`, `stroke`/`fill` equivalents, and CSS variables `--chart-1..5`, `--chart-other`, `--ramp-1..6`, `--chart-previous`, `--chart-grid`.
  - The root layout renders `<TopBar />` and wraps pages in `<main className="… flex flex-col gap-4 …">`: pages return fragments or plain elements, never their own `<main>`.
  - `filterContext(): Promise<{ accounts: Schemas["Account"][]; latestDay: string | null }>` in `lib/api.ts`.
  - `TopBar` (server), `NavLinks({ pending })`, `FilterBar({ accounts, latestDay })` (with an account filter it fetches that selection's `latest_day` itself, Decision F), `PeriodPicker({ latestDay })`, `AccountPicker({ accounts })` (client).

- [ ] **Step 1: Add the shadcn components**

```bash
cd apps/web && npx shadcn@latest add tooltip popover separator field empty --dry-run
cd apps/web && npx shadcn@latest add tooltip popover separator field empty
```

Read each new file under `src/components/ui/`. If the CLI changed `globals.css`, keep its additions only where Step 3 does not replace them.

- [ ] **Step 2: Replace the colour tokens**

In `apps/web/src/app/globals.css`, replace the whole `:root { … }` block with:

```css
:root {
  /* Direction "Mono" (spec 7.2; mockups/index.html and 04-tokens.png). Light mode only in slice 3. */
  --background: #ffffff; /* page */
  --foreground: #0b0b0f; /* text */
  --card: #f7f7f9; /* surface: soft grey, no border */
  --card-foreground: #0b0b0f;
  --popover: #ffffff;
  --popover-foreground: #0b0b0f;
  --primary: #4f46e5; /* the one accent: links, the current series, the logo dot */
  --primary-foreground: #ffffff;
  --secondary: #f7f7f9; /* pills on the white page */
  --secondary-foreground: #0b0b0f;
  --muted: #ececf1; /* segmented-control track, avatars, hovers */
  --muted-foreground: #6b6b75; /* Decision B: the mockup's #8a8a94 fails WCAG AA for small text */
  --accent: #eef0ff;
  --accent-foreground: #0b0b0f;
  --destructive: #e11d48;
  --border: #efeff1;
  --input: #e6e6eb;
  --ring: #4f46e5;
  --radius: 0.625rem;
  /* Group palette, validated on the light surface. Colour = group (Overview.group_slots), never rank. */
  --chart-1: #4f46e5;
  --chart-2: #eb6834;
  --chart-3: #1baf7a;
  --chart-4: #eda100;
  --chart-5: #e87ba4;
  --chart-other: #d4d4dc;
  /* One-hue ramp for the categories inside a group page: darkest = largest. */
  --ramp-1: #4f46e5;
  --ramp-2: #6d66ee;
  --ramp-3: #8c86f2;
  --ramp-4: #aaa6f5;
  --ramp-5: #c4c0f8;
  --ramp-6: #dad8fb;
  /* Chart chrome: the previous period's line, the dashed no-data boxes, the hairline grid. */
  --chart-previous: #c9c9d1;
  --chart-grid: #e6e6eb;
  /* Money: income is green with a "+"; otherwise green and red are only for deltas. Text colours:
     Decision B darkens the mockup's #16a34a for WCAG AA. */
  --income: #15803d;
  --good: #15803d;
  --bad: #e11d48;
  --sidebar: oklch(0.985 0 0);
  --sidebar-foreground: oklch(0.145 0 0);
  --sidebar-primary: oklch(0.205 0 0);
  --sidebar-primary-foreground: oklch(0.985 0 0);
  --sidebar-accent: oklch(0.97 0 0);
  --sidebar-accent-foreground: oklch(0.205 0 0);
  --sidebar-border: oklch(0.922 0 0);
  --sidebar-ring: oklch(0.708 0 0);
}
```

The palette, ramp and chart chrome values are the mockup's; only the text tokens `--muted-foreground`, `--income` and `--good` are darker (Decision B). Leave the `.dark` block as it is: dark mode is v2, with its own validated steps.

- [ ] **Step 3: Register the new tokens with Tailwind and apply tabular numbers**

In the same file, add at the end of the `@theme inline { … }` block:

```css
  --color-chart-other: var(--chart-other);
  --color-chart-previous: var(--chart-previous);
  --color-chart-grid: var(--chart-grid);
  --color-ramp-1: var(--ramp-1);
  --color-ramp-2: var(--ramp-2);
  --color-ramp-3: var(--ramp-3);
  --color-ramp-4: var(--ramp-4);
  --color-ramp-5: var(--ramp-5);
  --color-ramp-6: var(--ramp-6);
  --color-income: var(--income);
  --color-good: var(--good);
  --color-bad: var(--bad);
  --radius-card: 1rem; /* cards: 16 px; pills use rounded-full */
```

In `@layer base`, change `body { @apply bg-background text-foreground; }` to:

```css
  body {
    @apply bg-background text-foreground tabular-nums;
  }
```

- [ ] **Step 4: Surfaces without borders, recessive table headers**

In `apps/web/src/components/ui/card.tsx`:
- in `Card`, replace `rounded-xl bg-card` with `rounded-card bg-card`, delete `ring-1 ring-foreground/10 `, and replace `*:[img:first-child]:rounded-t-xl *:[img:last-child]:rounded-b-xl` with `*:[img:first-child]:rounded-t-card *:[img:last-child]:rounded-b-card`;
- in `CardHeader`, replace `rounded-t-xl` with `rounded-t-card`;
- in `CardFooter`, replace `rounded-b-xl` with `rounded-b-card`.

In `apps/web/src/components/ui/table.tsx`, in `TableHead`, replace `font-medium whitespace-nowrap text-foreground` with `text-xs font-medium tracking-wide whitespace-nowrap text-muted-foreground uppercase` (mockup: small uppercase grey labels).

- [ ] **Step 5: The top bar's context in `lib/api.ts`**

Append to `apps/web/src/lib/api.ts`:

```ts
/** What the top bar's filters need: the accounts, and the latest imported day, which is the
 * default month (spec 2.6). Empty when the API is unreachable or slow, like reviewCount. */
export async function filterContext(): Promise<{ accounts: Schemas["Account"][]; latestDay: string | null }> {
  try {
    const signal = AbortSignal.timeout(2000);
    const [accounts, page] = await Promise.all([
      apiGet<Schemas["Account"][]>("/accounts", { signal }),
      // No endpoint returns the latest day alone; every period read carries it in `period`.
      apiGet<Schemas["TransactionPage"]>("/transactions?limit=1", { signal }),
    ]);
    return { accounts, latestDay: page.period.latest_day };
  } catch {
    return { accounts: [], latestDay: null };
  }
}
```

- [ ] **Step 6: The navigation**

Create `apps/web/src/components/shell/nav-links.tsx`:

```tsx
"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

import { filterParams, parseFilters, toSearchParams } from "@/lib/params";
import { cn } from "@/lib/utils";

type Item = { href: string; label: string; keepsFilters: boolean; active: (path: string) => boolean };

const ITEMS: Item[] = [
  {
    href: "/",
    label: "Overview",
    keepsFilters: true,
    // The group, category, merchant and income pages sit under the overview (mockup 03).
    active: (path) => path === "/" || ["/spending", "/income", "/merchants"].some((p) => path.startsWith(p)),
  },
  { href: "/transactions", label: "Transactions", keepsFilters: true, active: (path) => path.startsWith("/transactions") },
  { href: "/subscriptions", label: "Subscriptions", keepsFilters: false, active: (path) => path.startsWith("/subscriptions") },
  { href: "/review", label: "Review", keepsFilters: false, active: (path) => path.startsWith("/review") },
  { href: "/imports", label: "Imports", keepsFilters: false, active: (path) => path.startsWith("/imports") },
  { href: "/settings", label: "Settings", keepsFilters: false, active: (path) => path.startsWith("/settings") },
];

/** The top navigation with a pill for the active item (spec 7.2). The pages that the period and
 * account filters scope keep them in their links. On phones the row scrolls sideways. */
export function NavLinks({ pending }: { pending: number | null }) {
  const pathname = usePathname();
  const search = useSearchParams();
  const query = filterParams(parseFilters(toSearchParams(search))).toString();
  return (
    <nav
      aria-label="Main"
      className="order-last -mx-1 flex w-full items-center gap-1 overflow-x-auto px-1 text-sm sm:order-none sm:w-auto sm:flex-1"
    >
      {ITEMS.map((item) => {
        const active = item.active(pathname);
        return (
          <Link
            key={item.href}
            href={item.keepsFilters && query ? `${item.href}?${query}` : item.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "shrink-0 rounded-full px-3 py-1.5 text-muted-foreground transition-colors hover:text-foreground",
              active && "bg-foreground font-medium text-background hover:text-background",
            )}
          >
            {item.label}
            {item.href === "/review" && pending ? (
              <span className={cn("ml-1.5", !active && "text-primary")}>{pending}</span>
            ) : null}
          </Link>
        );
      })}
    </nav>
  );
}
```

- [ ] **Step 7: The period and account pickers**

Create `apps/web/src/components/shell/period-picker.tsx`:

```tsx
"use client";

import { Check, ChevronDown } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Separator } from "@/components/ui/separator";
import { periodLabel } from "@/lib/format";
import {
  isDay,
  parseFilters,
  periodChanges,
  replaceParams,
  shiftMonth,
  toSearchParams,
  type Filters,
} from "@/lib/params";

type Choice = Omit<Filters, "accounts">;

/** The period filter (spec 2.6): presets as rows, then one month, then a custom range. The
 * default month is the latest one with data, because statements arrive in batches. */
export function PeriodPicker({ latestDay }: { latestDay: string | null }) {
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams();
  const filters = parseFilters(toSearchParams(search));
  const [open, setOpen] = useState(false);
  const [start, setStart] = useState(filters.start ?? "");
  const [end, setEnd] = useState(filters.end ?? "");
  const latestMonth = latestDay?.slice(0, 7);
  const presets: { label: string; choice: Choice }[] = [
    { label: "Latest month", choice: { period: "month" } },
    ...(latestMonth ? [{ label: "Previous month", choice: { period: "month" as const, month: shiftMonth(latestMonth, -1) } }] : []),
    { label: "Last 3 months", choice: { period: "last_3_months" } },
    { label: "Year to date", choice: { period: "ytd" } },
    { label: "Last 12 months", choice: { period: "last_12_months" } },
  ];
  const selected = (choice: Choice) => choice.period === filters.period && choice.month === filters.month;

  function go(choice: Choice) {
    setOpen(false);
    router.push(`${pathname}?${replaceParams(search.toString(), periodChanges(choice))}`);
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger render={<Button variant="secondary" size="sm" className="rounded-full" />}>
        <span className="sr-only">Period: </span>
        {periodLabel(filters, latestDay)}
        <ChevronDown data-icon="inline-end" />
      </PopoverTrigger>
      <PopoverContent align="end" className="w-72 gap-1 p-1">
        <div className="flex flex-col">
          {presets.map(({ label, choice }) => (
            <Button key={label} variant="ghost" className="justify-between" onClick={() => go(choice)}>
              {label}
              {selected(choice) && <Check data-icon="inline-end" />}
            </Button>
          ))}
        </div>
        <Separator />
        <Field className="p-2">
          <FieldLabel htmlFor="period-month">One month</FieldLabel>
          <Input
            id="period-month"
            type="month"
            max={latestMonth}
            defaultValue={filters.month ?? latestMonth}
            onChange={(event) => event.target.value && go({ period: "month", month: event.target.value })}
          />
        </Field>
        <Separator />
        <form
          className="flex flex-col gap-2 p-2"
          onSubmit={(event) => {
            event.preventDefault();
            go({ period: "custom", start, end });
          }}
        >
          <FieldGroup className="grid grid-cols-2 gap-2">
            <Field>
              <FieldLabel htmlFor="period-start">From</FieldLabel>
              <Input id="period-start" type="date" value={start} max={end || (latestDay ?? undefined)} onChange={(event) => setStart(event.target.value)} />
            </Field>
            <Field>
              <FieldLabel htmlFor="period-end">To</FieldLabel>
              <Input id="period-end" type="date" value={end} min={start || undefined} max={latestDay ?? undefined} onChange={(event) => setEnd(event.target.value)} />
            </Field>
          </FieldGroup>
          <Button type="submit" size="sm" disabled={!isDay(start) || !isDay(end) || start > end}>
            Apply range
          </Button>
        </form>
      </PopoverContent>
    </Popover>
  );
}
```

Create `apps/web/src/components/shell/account-picker.tsx`:

```tsx
"use client";

import { Check, ChevronDown } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { Schemas } from "@/lib/api";
import { accountsLabel } from "@/lib/labels";
import { parseFilters, replaceParams, toSearchParams } from "@/lib/params";

/** The account filter: none selected means all accounts; several can be picked (spec 6). */
export function AccountPicker({ accounts }: { accounts: Schemas["Account"][] }) {
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams();
  const selected = parseFilters(toSearchParams(search)).accounts;
  const go = (ids: string[]) => router.push(`${pathname}?${replaceParams(search.toString(), { account_id: ids })}`);
  const toggle = (id: string) => go(selected.includes(id) ? selected.filter((other) => other !== id) : [...selected, id]);

  return (
    <Popover>
      <PopoverTrigger render={<Button variant="secondary" size="sm" className="rounded-full" />}>
        <span className="sr-only">Accounts: </span>
        {accountsLabel(selected, accounts)}
        <ChevronDown data-icon="inline-end" />
      </PopoverTrigger>
      <PopoverContent align="end" className="w-64 gap-0 p-1">
        <Button variant="ghost" className="justify-between" aria-pressed={selected.length === 0} onClick={() => go([])}>
          All accounts
          {selected.length === 0 && <Check data-icon="inline-end" />}
        </Button>
        {accounts.map((account) => (
          <Button
            key={account.id}
            variant="ghost"
            className="justify-between"
            aria-pressed={selected.includes(account.id)}
            onClick={() => toggle(account.id)}
          >
            <span className="truncate">
              {account.name} <span className="text-muted-foreground">··{account.iban_last4}</span>
            </span>
            {selected.includes(account.id) && <Check data-icon="inline-end" />}
          </Button>
        ))}
      </PopoverContent>
    </Popover>
  );
}
```

Create `apps/web/src/components/shell/filter-bar.tsx`:

```tsx
"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { apiGet, type Schemas } from "@/lib/api";
import { filterParams, parseFilters, toSearchParams } from "@/lib/params";

import { AccountPicker } from "./account-picker";
import { PeriodPicker } from "./period-picker";

const FILTERED = ["/transactions", "/spending", "/income", "/merchants"];

type Props = { accounts: Schemas["Account"][]; latestDay: string | null };

/** The filters on the right of the top bar (spec 7.2), only on the pages they scope. The default
 * month is the latest one with data for the selected accounts (spec 2.6). `latestDay` comes from
 * the root layout, which does not re-render on client navigation, so it is right only without an
 * account filter; with one, the latest day of those accounts is fetched here (Decision F), and the
 * pill and the page always show the same month. */
export function FilterBar({ accounts, latestDay }: Props) {
  const pathname = usePathname();
  const search = useSearchParams();
  const shown = pathname === "/" || FILTERED.some((path) => pathname.startsWith(path));
  // Only the account_id params: the period does not change the latest day.
  const accountQuery = filterParams({ period: "month", accounts: parseFilters(toSearchParams(search)).accounts }).toString();
  const [filtered, setFiltered] = useState<{ query: string; latestDay: string | null } | null>(null);

  useEffect(() => {
    if (!shown || !accountQuery) return;
    const controller = new AbortController();
    apiGet<Schemas["TransactionPage"]>(`/transactions?limit=1&${accountQuery}`, { signal: controller.signal }).then(
      (page) => setFiltered({ query: accountQuery, latestDay: page.period.latest_day }),
      () => {}, // aborted by a newer selection, or the API is down: the pill reads "Latest month"
    );
    return () => controller.abort();
  }, [shown, accountQuery]);

  if (!shown) return null;
  const day = !accountQuery ? latestDay : filtered?.query === accountQuery ? filtered.latestDay : null;
  return (
    <div className="ml-auto flex items-center gap-2">
      <AccountPicker accounts={accounts} />
      <PeriodPicker latestDay={day} />
    </div>
  );
}
```

While the fetch runs, the pill reads "Latest month" for a moment (a null `latestDay`): it never shows another account's month.

- [ ] **Step 8: The top bar and the layout**

Create `apps/web/src/components/shell/top-bar.tsx`:

```tsx
import Link from "next/link";
import { Suspense } from "react";

import { filterContext, reviewCount } from "@/lib/api";

import { FilterBar } from "./filter-bar";
import { NavLinks } from "./nav-links";

/** Logo, navigation and filters (spec 7.2; mockup 02). The logo is lower-case "tally ai" in one
 * colour and one weight, with the accent dot. */
export async function TopBar() {
  const [pending, { accounts, latestDay }] = await Promise.all([reviewCount(), filterContext()]);
  return (
    <header className="border-b">
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3 sm:px-6">
        <Link href="/" className="flex shrink-0 items-center gap-2 pr-2 font-semibold tracking-tight">
          <span aria-hidden className="size-2.5 rounded-full bg-primary" />
          tally ai
        </Link>
        {/* Both read the URL: without Suspense, `next build` fails on the prerendered 404 page. */}
        <Suspense fallback={null}>
          <NavLinks pending={pending} />
        </Suspense>
        <Suspense fallback={null}>
          <FilterBar accounts={accounts} latestDay={latestDay} />
        </Suspense>
      </div>
    </header>
  );
}
```

Replace `apps/web/src/app/layout.tsx` with:

```tsx
import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

import { TopBar } from "@/components/shell/top-bar";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "tally ai",
  description: "Local-first personal finance: import bank statements and see where your money goes.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <TooltipProvider>
          <TopBar />
          <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-4 px-4 py-5 sm:px-6">{children}</main>
        </TooltipProvider>
        {/* Light mode only in slice 3: the toaster must not follow a dark system theme. */}
        <Toaster position="bottom-center" theme="light" />
      </body>
    </html>
  );
}
```

In `apps/web/src/app/imports/page.tsx` and `apps/web/src/app/transactions/page.tsx`, replace the outer `<main className="mx-auto flex max-w-5xl flex-col gap-6 p-6">` with `<div className="flex flex-col gap-6">` and its closing `</main>` with `</div>`. In `apps/web/src/app/review/page.tsx`, replace `<main className="mx-auto flex w-full max-w-4xl flex-col gap-6 p-4 sm:p-6">` with `<div className="mx-auto flex w-full max-w-4xl flex-col gap-6">` and `</main>` with `</div>`.

- [ ] **Step 9: A readable error when the API is down**

Create `apps/web/src/app/error.tsx` (closes dogfood issue 004 of slice 2):

```tsx
"use client";

import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";

/** A page whose data could not load (usually: the API is not running). `retry` refetches. */
export default function Error({ retry }: { error: Error & { digest?: string }; retry: () => void }) {
  return (
    <Empty>
      <EmptyHeader>
        <EmptyTitle>This page could not load</EmptyTitle>
        <EmptyDescription>
          The API did not answer. Check that it is running (from apps/api: uv run task api), then try again.
        </EmptyDescription>
      </EmptyHeader>
      <EmptyContent>
        <Button onClick={() => retry()}>Try again</Button>
      </EmptyContent>
    </Empty>
  );
}
```

- [ ] **Step 10: Run the gate**

Run: `cd apps/web && npm run lint && npx tsc --noEmit && npm test && npm run build`
Expected: no errors. A build error "useSearchParams() should be wrapped in a suspense boundary" means a `<Suspense>` from Step 8 is missing.

- [ ] **Step 11: Check the shell in the browser (R1, read-only)**

`/` still redirects to `/imports` until Task 4, so check on `/transactions`, which already has the filters.
1. `open "http://localhost:3000/transactions"`, `snapshot -i`. Expect: the link "tally ai"; the nav links Overview, Transactions (with `aria-current="page"`), Subscriptions, Review (with a number when items are pending), Imports, Settings; on the right, the buttons "Accounts: All accounts" and "Period: <latest imported month>", for example "Period: August 2026".
2. Click the period button, `snapshot -i`. Expect the rows "Latest month" (with a check), "Previous month", "Last 3 months", "Year to date", "Last 12 months", the field "One month", the fields "From" and "To", and "Apply range" (disabled). Click "Previous month": `agent-browser --session slice3b get url` ends with `month=<one month before the latest>`, and the button reads that month.
3. Click the accounts button, then one account: the URL gains `account_id=`, and the button shows that account's name. The period pill reads that account's latest month (Decision F): it matches the month of `period.latest_day` in `curl -s "http://localhost:8000/transactions?limit=1&account_id=<id>"`; if the accounts end in different months, pick the one that ends earlier and check that the pill moves to its month. Click "All accounts": `account_id` is gone, and the pill returns to the latest month of all accounts.
4. With a month selected, `snapshot -i -u`: the "Overview" and "Transactions" links carry `month=…`; "Review" does not.
5. `open "http://localhost:3000/review"`: no filter buttons. `open "http://localhost:3000/does-not-exist"`: the 404 page renders inside the layout, with the navigation.
6. `set viewport 390 844`, `open "http://localhost:3000/transactions"`, screenshot `task03-phone.png`. The nav is on its own row and scrolls sideways; the page itself does not scroll sideways: `agent-browser --session slice3b eval "document.documentElement.scrollWidth <= window.innerWidth"` prints `true`. Set the viewport back with `set viewport 1280 900`.
7. Stop the API; `open "http://localhost:3000/imports"`: "This page could not load" and "Try again". Start the API again, click "Try again": the imports page returns.
8. Screenshot `task03-top-bar.png` at 1280 px, and compare the bar with the top of `02-overview.png`: logo on the left with the dot, a near-black pill on the active item (Decision C), the filter pills on the right. `errors`, `close`.

- [ ] **Step 12: Commit**

```bash
git add apps/web/components.json apps/web/package.json apps/web/package-lock.json apps/web/src/app/globals.css apps/web/src/app/layout.tsx apps/web/src/app/error.tsx apps/web/src/app/imports/page.tsx apps/web/src/app/transactions/page.tsx apps/web/src/app/review/page.tsx apps/web/src/components/ui apps/web/src/components/shell apps/web/src/lib/api.ts
git commit -m "feat: add the tally ai design tokens, top bar and period and account filters"
```

---

### Task 4: Charts foundation and the overview's numbers and trends

**Files:**
- Create: `apps/web/src/components/charts/money-tooltip.tsx`, `legend-buttons.tsx`, `month-axis.tsx`, `cumulative-chart.tsx`, `months-chart.tsx`
- Create: `apps/web/src/components/money/delta-text.tsx`, `info-tip.tsx`, `kpi-tile.tsx`
- Modify: `apps/web/src/app/page.tsx` (the redirect becomes the overview)
- Add (shadcn): `chart` (brings `recharts@3.8.0`); npm: `react-is@19.2.8`

**Interfaces:**
- Consumes: `delta`, `atSameDay`, `periodHasData`, `Delta` (Task 2); `DEFINITIONS` (Task 2); `money`, `moneyWhole`, `signedMoneyWhole`, `compactMoney`, `rate`, `monthLabel`, `monthShort`, `dayShort`, `dayAt`, `daysIn`, `periodNames`, `previousLabel`, `rangeLabel` (Task 1); `parseFilters`, `filterParams`, `withFilters` (Task 1).
- Produces:
  - `moneyRow(config: ChartConfig)`: a `ChartTooltipContent` formatter (line key, series name, value in euros, "no data" for `null`); `monthTooltipLabel(label, payload)`; `dayTooltipLabel(start)`.
  - `LegendItem = { key; label; color; shape?: "box" | "line" }`; `LegendButtons({ items, isolated: string | null, onIsolate: (key: string | null) => void })`.
  - `MonthRange = [string, string]` (first and last `YYYY-MM` of the period); `MonthTick` (an XAxis `tick` element); `monthBarShape(range)` (a Bar `shape`).
  - `CumulativeChart({ cumulative: Schemas["Cumulative"], period: Schemas["PeriodOut"] })`.
  - `MonthsChart({ months: Schemas["MonthPoint"][], range: MonthRange })`.
  - `DeltaText({ value: Delta, arrow?: boolean, parens?: boolean })`, `InfoTip({ label, text })`, `KpiTile({ label, definition, value, delta, versus, href?, income?, hasData? })` (`hasData` false: "—" and no delta, Decision G).

- [ ] **Step 1: Add the chart component and pin `react-is`**

```bash
cd apps/web && npx shadcn@latest add chart --dry-run
cd apps/web && npx shadcn@latest add chart
cd apps/web && npm install react-is@19.2.8
cd apps/web && npm ls recharts react-is
```

Expected: `recharts@3.8.0`, and `react-is@19.2.8` at the top level (spec 8, gotcha 1: a 16.x copy arrives through eslint-plugin-react). Read `src/components/ui/chart.tsx`: it exports `ChartContainer`, `ChartTooltip`, `ChartTooltipContent`, `ChartLegend`, `ChartLegendContent`, `ChartStyle` and the type `ChartConfig`.

- [ ] **Step 2: Shared chart pieces**

Create `apps/web/src/components/charts/money-tooltip.tsx`:

```tsx
import type { ReactNode } from "react";

import type { ChartConfig } from "@/components/ui/chart";
import { dayAt, dayShort, money, monthLabel } from "@/lib/format";

type Item = { color?: string; payload?: unknown };

/** Tooltip rows: a short line key in the series colour, the series name, and the value in euros
 * as the strong element (dataviz: values lead, labels follow). A month without data reads
 * "no data", never €0.00. */
export function moneyRow(config: ChartConfig) {
  return function MoneyRow(value: unknown, name: unknown, item: Item): ReactNode {
    const key = String(name);
    const fill = (item.payload as { fill?: string } | undefined)?.fill;
    return (
      <div className="flex w-full items-center gap-2">
        <span aria-hidden className="h-0.5 w-3 shrink-0 rounded-full" style={{ background: item.color ?? fill }} />
        <span className="text-muted-foreground">{config[key]?.label ?? key}</span>
        <span className="ml-auto pl-3 font-medium text-foreground">
          {value === null || value === undefined ? "no data" : money(Number(value))}
        </span>
      </div>
    );
  };
}

/** The tooltip title of a month column: "August 2026". */
export function monthTooltipLabel(_label: unknown, payload: readonly { payload?: unknown }[]): ReactNode {
  const month = (payload[0]?.payload as { month?: string } | undefined)?.month;
  return month ? monthLabel(month) : null;
}

/** The tooltip title of day N of a period: "15 Aug". */
export function dayTooltipLabel(start: string) {
  return function DayLabel(_label: unknown, payload: readonly { payload?: unknown }[]): ReactNode {
    const day = (payload[0]?.payload as { day?: number } | undefined)?.day;
    return day ? dayShort(dayAt(start, day - 1)) : null;
  };
}
```

Create `apps/web/src/components/charts/legend-buttons.tsx`:

```tsx
"use client";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type LegendItem = { key: string; label: string; color: string; shape?: "box" | "line" };

type Props = { items: LegendItem[]; isolated: string | null; onIsolate: (key: string | null) => void };

/** The legend of a chart with two or more series. Clicking an item shows that series alone and
 * dims the others; clicking it again shows them all. Recharts' own legend cannot do this, so the
 * chart keeps the state and passes `hide` to its series (spec 8, gotcha 5). */
export function LegendButtons({ items, isolated, onIsolate }: Props) {
  return (
    <div role="group" aria-label="Series" className="flex flex-wrap gap-1">
      {items.map((item) => (
        <Button
          key={item.key}
          type="button"
          variant="ghost"
          size="xs"
          aria-pressed={isolated === item.key}
          onClick={() => onIsolate(isolated === item.key ? null : item.key)}
          className={cn("text-muted-foreground", isolated !== null && isolated !== item.key && "opacity-50")}
        >
          <span
            aria-hidden
            className={cn("shrink-0", item.shape === "line" ? "h-0.5 w-3.5 rounded-full" : "size-2.5 rounded-[3px]")}
            style={{ background: item.color }}
          />
          {item.label}
        </Button>
      ))}
    </div>
  );
}
```

Create `apps/web/src/components/charts/month-axis.tsx`:

```tsx
import { Rectangle, type BarShapeProps } from "recharts";

import { monthShort } from "@/lib/format";

/** The first and last month (YYYY-MM) of the selected period. */
export type MonthRange = [string, string];

const inRange = (month: string, [from, to]: MonthRange) => month >= from && month <= to;

// Recharts puts the tick text below the axis; the "no data" box stands on the baseline above it.
// If the box floats above the €0 grid line or overlaps it, adjust `lift` (in px).
const BOX = { width: 32, height: 30, lift: 12 };

type TickProps = { x?: number | string; y?: number | string; payload?: { value?: string }; range: MonthRange; noData: Set<string> };

/** The month under each column, bold inside the selected period, with a dashed "no data" box for
 * a month without imported data (spec 2.6: such a month is never drawn as zero). */
export function MonthTick({ x = 0, y = 0, payload, range, noData }: TickProps) {
  const month = payload?.value ?? "";
  const cx = Number(x);
  const top = Number(y);
  const baseline = top - BOX.lift;
  return (
    <g>
      {noData.has(month) && (
        <>
          <rect
            x={cx - BOX.width / 2}
            y={baseline - BOX.height}
            width={BOX.width}
            height={BOX.height}
            rx={4}
            fill="none"
            stroke="var(--chart-previous)"
            strokeDasharray="3 3"
          />
          <text x={cx} y={baseline - BOX.height - 4} textAnchor="middle" fontSize={10} className="fill-muted-foreground">
            no data
          </text>
        </>
      )}
      <text
        x={cx}
        y={top}
        dy="0.9em"
        textAnchor="middle"
        fontSize={12}
        className={inRange(month, range) ? "fill-foreground font-semibold" : "fill-muted-foreground"}
      >
        {month ? monthShort(month) : ""}
      </text>
    </g>
  );
}

/** Columns outside the selected period are drawn lighter (mockup: the current month in full). */
export function monthBarShape(range: MonthRange) {
  return function MonthBar(props: BarShapeProps) {
    const month = (props.payload as { month?: string } | undefined)?.month ?? "";
    return <Rectangle {...props} fillOpacity={inRange(month, range) ? 1 : 0.55} />;
  };
}
```

If `tsc` reports that `BarShapeProps` has no `payload`, type the parameter with `BarRectangleItem` from `recharts` instead; both come from the Recharts 3 examples.

- [ ] **Step 3: The cumulative chart**

Create `apps/web/src/components/charts/cumulative-chart.tsx`:

```tsx
"use client";

import { useState } from "react";
import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from "recharts";

import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import type { Schemas } from "@/lib/api";
import { compactMoney, dayAt, dayShort, daysIn, periodNames } from "@/lib/format";

import { LegendButtons } from "./legend-buttons";
import { dayTooltipLabel, moneyRow } from "./money-tooltip";

type Props = { cumulative: Schemas["Cumulative"]; period: Schemas["PeriodOut"] };

/** Spent so far, day by day, against the previous period (spec 7.1). The current line stops at
 * the latest imported day; the x axis always spans the whole current period. */
export function CumulativeChart({ cumulative, period }: Props) {
  const [isolated, setIsolated] = useState<string | null>(null);
  const names = periodNames(period);
  const config = {
    current: { label: names.current, color: "var(--primary)" },
    previous: { label: names.previous, color: "var(--chart-previous)" },
  } satisfies ChartConfig;
  const length = daysIn(period.start, period.end);
  const data = Array.from({ length }, (_, index) => ({
    day: index + 1,
    current: cumulative.current[index] ? Number(cumulative.current[index].total) : null,
    previous: cumulative.previous?.[index] ? Number(cumulative.previous[index].total) : null,
  }));
  const dayLabel = (day: number) => dayShort(dayAt(period.start, day - 1));
  return (
    <div className="flex flex-col gap-3">
      {cumulative.previous && (
        <LegendButtons
          isolated={isolated}
          onIsolate={setIsolated}
          items={[
            { key: "current", label: names.current, color: config.current.color, shape: "line" },
            { key: "previous", label: names.previous, color: config.previous.color, shape: "line" },
          ]}
        />
      )}
      <ChartContainer config={config} className="aspect-auto h-56 w-full">
        <AreaChart accessibilityLayer data={data} margin={{ top: 8, right: 12, left: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
          <XAxis
            dataKey="day"
            type="number"
            domain={[1, length]}
            ticks={[1, Math.ceil(length / 2), length]}
            tickFormatter={dayLabel}
            tickLine={false}
            axisLine={false}
            tickMargin={8}
          />
          <YAxis width={48} tickLine={false} axisLine={false} tickFormatter={(tick: number) => compactMoney(tick)} />
          <ChartTooltip
            content={<ChartTooltipContent labelFormatter={dayTooltipLabel(period.start)} formatter={moneyRow(config)} />}
          />
          <Area
            dataKey="previous"
            type="monotone"
            stroke="var(--color-previous)"
            strokeWidth={2}
            fill="transparent"
            dot={false}
            activeDot={false}
            hide={isolated === "current"}
          />
          <Area
            dataKey="current"
            type="monotone"
            stroke="var(--color-current)"
            strokeWidth={2}
            fill="var(--color-current)"
            fillOpacity={0.1}
            dot={false}
            activeDot={{ r: 4 }}
            hide={isolated === "previous"}
          />
        </AreaChart>
      </ChartContainer>
    </div>
  );
}
```

- [ ] **Step 4: The 12-month chart**

Create `apps/web/src/components/charts/months-chart.tsx`:

```tsx
"use client";

import { useState } from "react";
import { Bar, CartesianGrid, ComposedChart, Line, XAxis, YAxis } from "recharts";

import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import type { Schemas } from "@/lib/api";
import { compactMoney } from "@/lib/format";

import { LegendButtons } from "./legend-buttons";
import { MonthTick, monthBarShape, type MonthRange } from "./month-axis";
import { moneyRow, monthTooltipLabel } from "./money-tooltip";

const config = {
  income: { label: "Income", color: "var(--ramp-1)" },
  expenses: { label: "Expenses", color: "var(--ramp-4)" },
  savings: { label: "Savings", color: "var(--foreground)" },
} satisfies ChartConfig;

const amount = (value: string | null) => (value === null ? null : Number(value));

/** Twelve months of income and expenses as bars and savings as a line, on one € axis (spec 7.2:
 * no dual axes). Months without imported data are dashed boxes, not zeros. */
export function MonthsChart({ months, range }: { months: Schemas["MonthPoint"][]; range: MonthRange }) {
  const [isolated, setIsolated] = useState<string | null>(null);
  const hidden = (key: string) => isolated !== null && isolated !== key;
  const noData = new Set(months.filter((month) => !month.has_data).map((month) => month.month));
  const data = months.map((month) => ({
    month: month.month,
    income: amount(month.income),
    expenses: amount(month.expenses),
    savings: amount(month.savings),
  }));
  const shape = monthBarShape(range);
  return (
    <div className="flex flex-col gap-3">
      <LegendButtons
        isolated={isolated}
        onIsolate={setIsolated}
        items={[
          { key: "income", label: "Income", color: config.income.color },
          { key: "expenses", label: "Expenses", color: config.expenses.color },
          { key: "savings", label: "Savings", color: config.savings.color, shape: "line" },
        ]}
      />
      <ChartContainer config={config} className="aspect-auto h-64 w-full">
        <ComposedChart accessibilityLayer data={data} barGap={2} margin={{ top: 28, right: 8, left: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
          <XAxis
            dataKey="month"
            interval={0}
            tickLine={false}
            axisLine={false}
            tickMargin={6}
            height={28}
            tick={<MonthTick range={range} noData={noData} />}
          />
          <YAxis width={48} tickLine={false} axisLine={false} tickFormatter={(tick: number) => compactMoney(tick)} />
          <ChartTooltip content={<ChartTooltipContent labelFormatter={monthTooltipLabel} formatter={moneyRow(config)} />} />
          <Bar dataKey="income" fill="var(--color-income)" radius={[4, 4, 0, 0]} maxBarSize={24} hide={hidden("income")} shape={shape} />
          <Bar dataKey="expenses" fill="var(--color-expenses)" radius={[4, 4, 0, 0]} maxBarSize={24} hide={hidden("expenses")} shape={shape} />
          <Line
            dataKey="savings"
            type="linear"
            stroke="var(--color-savings)"
            strokeWidth={2}
            dot={{ r: 3, fill: "var(--color-savings)" }}
            connectNulls={false}
            hide={hidden("savings")}
          />
        </ComposedChart>
      </ChartContainer>
    </div>
  );
}
```

- [ ] **Step 5: Deltas, ⓘ tooltips and KPI tiles**

Create `apps/web/src/components/money/delta-text.tsx`:

```tsx
import type { Delta } from "@/lib/delta";
import { cn } from "@/lib/utils";

const ARROWS = { up: "↗", down: "↘", flat: "—" } as const;
const WORDS = { up: "up", down: "down", flat: "no change" } as const;
const TONES = { good: "text-good", bad: "text-bad", neutral: "text-muted-foreground" } as const;

type Props = { value: Delta; arrow?: boolean; parens?: boolean };

/** A change against the previous period (spec 2.6): the arrow and the sign always carry the
 * meaning; green or red only add to it. Nothing when the previous period has no data. */
export function DeltaText({ value, arrow = true, parens = false }: Props) {
  if (value.kind === "hidden") return null;
  if (value.kind === "new") return <span className="text-muted-foreground">new</span>;
  return (
    <span className={cn(TONES[value.tone])}>
      {arrow && (
        <>
          <span aria-hidden>{ARROWS[value.direction]} </span>
          <span className="sr-only">{WORDS[value.direction]} </span>
        </>
      )}
      {parens ? `(${value.text})` : value.text}
    </span>
  );
}
```

Create `apps/web/src/components/money/info-tip.tsx`:

```tsx
import { Info } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

/** The ⓘ next to a number: its definition, word for word from docs/money-rules.md (spec 7.2). */
export function InfoTip({ label, text }: { label: string; text: string }) {
  return (
    <Tooltip>
      <TooltipTrigger render={<Button variant="ghost" size="icon-xs" aria-label={`About ${label}`} />}>
        <Info />
      </TooltipTrigger>
      <TooltipContent className="max-w-64 text-pretty">{text}</TooltipContent>
    </Tooltip>
  );
}
```

Create `apps/web/src/components/money/kpi-tile.tsx`:

```tsx
import Link from "next/link";

import { Card, CardAction, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import type { Delta } from "@/lib/delta";
import { cn } from "@/lib/utils";

import { DeltaText } from "./delta-text";
import { InfoTip } from "./info-tip";

type Props = {
  label: string;
  definition: string;
  value: string;
  delta: Delta;
  versus: string;
  href?: string;
  income?: boolean;
  hasData?: boolean;
};

/** One of the four overview numbers (spec 7.1): the value, its change against the previous period
 * and an ⓘ with its definition. Income is green with a "+" (spec 7.2). A period without data
 * reads "—" with no delta, never 0 (spec 2.6, Decision G). */
export function KpiTile({ label, definition, value, delta, versus, href, income = false, hasData = true }: Props) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardDescription className="text-xs tracking-wide uppercase">
          {href ? (
            <Link href={href} className="hover:text-foreground">
              {label}
            </Link>
          ) : (
            label
          )}
        </CardDescription>
        <CardAction>
          <InfoTip label={label} text={definition} />
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-1">
        <p className={cn("text-2xl font-semibold tracking-tight", income && hasData && "text-income")}>
          {hasData ? value : "—"}
        </p>
        <p className="min-h-4 text-xs text-muted-foreground">
          {hasData && delta.kind !== "hidden" && (
            <>
              <DeltaText value={delta} /> {versus}
            </>
          )}
        </p>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 6: The overview, first half**

Replace `apps/web/src/app/page.tsx` with:

```tsx
import { FileUp } from "lucide-react";
import Link from "next/link";

import { CumulativeChart } from "@/components/charts/cumulative-chart";
import { MonthsChart } from "@/components/charts/months-chart";
import { DeltaText } from "@/components/money/delta-text";
import { KpiTile } from "@/components/money/kpi-tile";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { apiGet, type Schemas } from "@/lib/api";
import { DEFINITIONS } from "@/lib/definitions";
import { atSameDay, delta, periodHasData } from "@/lib/delta";
import { moneyWhole, periodNames, previousLabel, rangeLabel, rate, signedMoneyWhole } from "@/lib/format";
import { filterParams, parseFilters, withFilters } from "@/lib/params";

export const dynamic = "force-dynamic";

const amount = (value: string | null | undefined) => (value === null || value === undefined ? null : Number(value));

/** "How am I doing?" in one look (spec 7.1; mockup 02). */
export default async function OverviewPage({ searchParams }: PageProps<"/">) {
  const filters = parseFilters(await searchParams);
  const overview = await apiGet<Schemas["Overview"]>(`/dashboard/overview?${filterParams(filters)}`);
  if (overview.period.latest_day === null) return <NoTransactions filtered={filters.accounts.length > 0} />;

  const { period, kpis, previous_kpis: before } = overview;
  const versus = previousLabel(period);
  const spent = atSameDay(overview.cumulative);
  // Decision G: a period without data shows "—" in the tiles, never €0.
  const hasData = periodHasData(overview.months, period);
  return (
    <>
      <h1 className="sr-only">Overview, {rangeLabel(period)}</h1>
      <section aria-label="Key numbers" className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiTile
          label="Income"
          definition={DEFINITIONS.income}
          value={signedMoneyWhole(kpis.income)}
          income
          hasData={hasData}
          delta={delta(amount(kpis.income), amount(before?.income), "up", "percent")}
          versus={versus}
          href={withFilters("/income", filters)}
        />
        <KpiTile
          label="Expenses"
          definition={DEFINITIONS.expenses}
          value={moneyWhole(kpis.expenses)}
          hasData={hasData}
          delta={delta(amount(kpis.expenses), amount(before?.expenses), "down", "percent")}
          versus={versus}
        />
        <KpiTile
          label="Savings"
          definition={DEFINITIONS.savings}
          value={moneyWhole(kpis.savings)}
          hasData={hasData}
          delta={delta(amount(kpis.savings), amount(before?.savings), "up", "euro")}
          versus={versus}
        />
        <KpiTile
          label="Savings rate"
          definition={DEFINITIONS.savingsRate}
          value={rate(kpis.savings_rate)}
          hasData={hasData}
          delta={delta(kpis.savings_rate, before?.savings_rate, "up", "points")}
          versus={versus}
        />
      </section>
      <Card>
        <CardHeader>
          <CardTitle>
            {/* An empty current series (the period starts after the latest imported day) is no data, never €0. */}
            {spent.current === null ? "No data" : `${moneyWhole(spent.current)} spent`}{" "}
            {period.name === "month" ? `in ${periodNames(period).current}` : "in this period"}
          </CardTitle>
          <CardDescription>
            <DeltaText value={delta(spent.current, spent.previous, "down", "euro")} />{" "}
            <DeltaText value={delta(spent.current, spent.previous, "down", "percent")} arrow={false} parens />{" "}
            {spent.previous !== null && `${previousLabel(period, "long")} at the same day`}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <CumulativeChart cumulative={overview.cumulative} period={period} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Last 12 months</CardTitle>
          <CardDescription>Income, expenses and savings per month · months without imported data are marked</CardDescription>
        </CardHeader>
        <CardContent>
          <MonthsChart months={overview.months} range={[period.start.slice(0, 7), period.end.slice(0, 7)]} />
        </CardContent>
      </Card>
    </>
  );
}

/** Spec 7.2: with no imported data, the overview links to /imports. */
function NoTransactions({ filtered }: { filtered: boolean }) {
  return (
    <Empty>
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <FileUp />
        </EmptyMedia>
        <EmptyTitle>{filtered ? "No transactions in these accounts" : "No statements yet"}</EmptyTitle>
        <EmptyDescription>Import a bank statement PDF to see your income, spending and savings here.</EmptyDescription>
      </EmptyHeader>
      <EmptyContent>
        <Button render={<Link href="/imports" />} nativeButton={false}>
          Import statements
        </Button>
      </EmptyContent>
    </Empty>
  );
}
```

The mockup's "12 months | Year to date | All" switch is left out: `GET /dashboard/overview` always returns the 12 months that end with the period (3a `month_series`).

- [ ] **Step 7: Run the gate**

Run: `cd apps/web && npm run lint && npx tsc --noEmit && npm test && npm run build`
Expected: no errors. Fix prop-type mismatches against the generated `chart.tsx` if `tsc` reports them.

- [ ] **Step 8: Check the overview in the browser (R1, read-only)**

1. `open "http://localhost:3000/"`, `snapshot -i`. Expect: the nav "Overview" with `aria-current="page"`; four tiles labelled Income, Expenses, Savings and Savings rate, each with a button "About <label>"; the Income value starts with "+€"; each delta line reads like "up +2% vs Jul" in the snapshot (the arrow is `aria-hidden`; the screenshot shows "↗ +2% vs Jul"), or is empty when the previous month has no data.
2. `hover` the "About Savings" button, `snapshot`: the tooltip reads exactly "Income − expenses. Money you move to your own savings or investment accounts counts as saved."
3. The cumulative card: title "€… spent in <month>", legend buttons "<month>" and "<previous month>". Hover the middle of the chart: `agent-browser --session slice3b eval "JSON.stringify(document.querySelectorAll('[data-slot=chart]')[0].getBoundingClientRect())"`, then `mouse move <x + width/2> <y + height/2>`, `snapshot`: a tooltip with a day ("15 Aug") and one or two rows in euros.
4. The 12-month chart: 12 month labels. For a month without data, "no data" appears above a dashed box that sits on the €0 line (adjust `BOX.lift` if not). `find nth 1 ".recharts-bar-rectangle" hover`, `snapshot`: a tooltip "<Month YYYY>" with Income, Expenses and Savings in euros (or "no data").
5. Legend isolation: `eval "document.querySelectorAll('.recharts-bar-rectangle').length"`; click the "Expenses" legend button: it has `aria-pressed="true"`, the others are dimmed, and the count halves; click it again: the count returns.
6. Choose "Last 3 months" in the period picker: the URL has `period=last_3_months`, the deltas read "vs the 3 months before", the cumulative title reads "spent in this period", and `eval "document.querySelectorAll('[data-slot=chart] text.font-semibold').length"` prints `3`.
7. `open "http://localhost:3000/?account_id=00000000-0000-4000-8000-000000000000"`: "No transactions in these accounts" and an "Import statements" link to `/imports`. `open "http://localhost:3000/?month=2099-12"` (after the latest imported day): the four tiles read "—" with empty delta lines, and the Income "—" is not green (Decision G); the cumulative title reads "No data in December", no current line is drawn (never a line at €0), and `errors` is empty.
8. Screenshot `task04-overview.png` at 1280 px and compare with the top half of `02-overview.png`: four tiles in a row, the cumulative line in the accent with a soft fill over the grey previous line, the 12-month bars with the savings line and the dashed boxes. `errors`, `close`.

- [ ] **Step 9: Commit**

```bash
git add apps/web/package.json apps/web/package-lock.json apps/web/src/components/ui/chart.tsx apps/web/src/components/charts apps/web/src/components/money apps/web/src/app/page.tsx
git commit -m "feat: add the overview KPIs, the cumulative spend chart and the 12-month chart"
```

---

### Task 5: "Where your money went" and the subscriptions line

**Files:**
- Create: `apps/web/src/components/breakdown/breakdown-table.tsx`, `apps/web/src/components/charts/breakdown-donut.tsx`, `apps/web/src/components/overview/where-money-went.tsx`
- Modify: `apps/web/src/components/ui/toggle.tsx`, `apps/web/src/components/ui/toggle-group.tsx` (a `segment` variant), `apps/web/src/app/page.tsx`
- Add (shadcn): `toggle-group` (brings `toggle`)

**Interfaces:**
- Consumes: `breakdownItems`, `BreakdownItem`, `BreakdownContext` (Task 2); `foldBySlot` (Task 2); `plural` (Task 2); `money`, `moneyWhole`, `percent` (Task 1); `DeltaText` (Task 4); `moneyRow` (Task 4).
- Produces:
  - `ToggleGroup variant="segment"`: the mockup's segmented control (grey track, white pill on the pressed item).
  - `BreakdownTable({ items: BreakdownItem[], nameHeader: string, versus: string, showShare?: boolean })`.
  - `Slice = { name: string; value: number; fill: string }`; `BreakdownDonut({ slices, total: string | null, change: Delta, versus: string })` (`total` null: no data, "—", Decision G).
  - `WhereMoneyWent({ views: Record<Dimension, BreakdownItem[]>, total: string | null, change: Delta, versus: string, subtitle: string })`.

- [ ] **Step 1: Add the toggle group and its segment variant**

```bash
cd apps/web && npx shadcn@latest add toggle-group --dry-run
cd apps/web && npx shadcn@latest add toggle-group
```

In `apps/web/src/components/ui/toggle.tsx`, add a variant after `outline:` inside `variants.variant`:

```ts
        segment:
          "bg-transparent px-3 text-muted-foreground hover:bg-transparent hover:text-foreground aria-pressed:bg-background aria-pressed:text-foreground aria-pressed:shadow-xs",
```

and, after `defaultVariants`, a compound variant so the size variants' radius cannot win:

```ts
    compoundVariants: [
      // A segment stays a pill (radius 999, spec 7.2) whatever its size.
      { variant: "segment", className: "rounded-full" },
    ],
```

In `apps/web/src/components/ui/toggle-group.tsx`, in `ToggleGroup`'s `className`, append ` data-[variant=segment]:gap-0.5 data-[variant=segment]:rounded-full data-[variant=segment]:bg-muted data-[variant=segment]:p-0.5` to the first string (the mockup's grey track).

- [ ] **Step 2: The breakdown table**

Create `apps/web/src/components/breakdown/breakdown-table.tsx`:

```tsx
import Link from "next/link";

import { DeltaText } from "@/components/money/delta-text";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { BreakdownItem } from "@/lib/breakdown";
import { money, percent } from "@/lib/format";

type Props = { items: BreakdownItem[]; nameHeader: string; versus: string; showShare?: boolean };

/** Name (with its colour and a hint), share, amount and the change against the previous period.
 * Each name opens the next level (mockup: every click goes one level deeper). A negative amount
 * (refunds only) is shown as it is (spec 2.1). */
export function BreakdownTable({ items, nameHeader, versus, showShare = true }: Props) {
  if (items.length === 0) return <p className="text-sm text-muted-foreground">Nothing in this period.</p>;
  const compared = items.some((item) => item.delta.kind !== "hidden");
  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead>{nameHeader}</TableHead>
          {showShare && <TableHead className="text-right">Share</TableHead>}
          <TableHead className="text-right">Amount</TableHead>
          {compared && <TableHead className="text-right">{versus}</TableHead>}
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => (
          <TableRow key={item.key}>
            <TableCell className="max-w-72 whitespace-normal">
              <div className="flex items-center gap-2.5">
                {item.color && (
                  <span
                    aria-hidden
                    data-slot="series-dot"
                    className="size-2.5 shrink-0 rounded-[3px]"
                    style={{ background: item.color }}
                  />
                )}
                <div className="min-w-0">
                  {item.href ? (
                    <Link href={item.href} className="font-medium hover:underline">
                      {item.name}
                    </Link>
                  ) : (
                    <span className="font-medium">{item.name}</span>
                  )}
                  {item.hint && <p className="truncate text-xs text-muted-foreground">{item.hint}</p>}
                </div>
              </div>
            </TableCell>
            {showShare && <TableCell className="text-right text-muted-foreground">{percent(item.share)}</TableCell>}
            <TableCell className="text-right font-semibold">{money(item.amount)}</TableCell>
            {compared && (
              <TableCell className="text-right">
                <DeltaText value={item.delta} />
              </TableCell>
            )}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
```

- [ ] **Step 3: The donut**

Create `apps/web/src/components/charts/breakdown-donut.tsx`:

```tsx
"use client";

import { Pie, PieChart } from "recharts";

import { DeltaText } from "@/components/money/delta-text";
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import type { Delta } from "@/lib/delta";
import { moneyWhole } from "@/lib/format";

import { moneyRow } from "./money-tooltip";

export type Slice = { name: string; value: number; fill: string };

type Props = { slices: Slice[]; total: string | null; change: Delta; versus: string };

/** Part-to-whole at a glance, with the total in the centre (mockup 02). Only positive amounts
 * draw a slice (spec 2.1); the table next to it lists every row. A period without data (`total`
 * null) reads "—" with no change, like the Expenses tile (Decision G). */
export function BreakdownDonut({ slices, total, change, versus }: Props) {
  return (
    <div className="relative mx-auto size-52">
      <ChartContainer config={{}} className="aspect-square size-full">
        <PieChart>
          <ChartTooltip content={<ChartTooltipContent hideLabel formatter={moneyRow({})} />} />
          <Pie
            data={slices}
            dataKey="value"
            nameKey="name"
            innerRadius="72%"
            outerRadius="100%"
            startAngle={90}
            endAngle={-270}
            stroke="var(--card)"
            strokeWidth={2}
            isAnimationActive={false}
          />
        </PieChart>
      </ChartContainer>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
        <span className="text-xs text-muted-foreground">Spent</span>
        <span className="text-2xl font-semibold tracking-tight">{total === null ? "—" : moneyWhole(total)}</span>
        {total !== null && (
          <span className="text-xs">
            <DeltaText value={change} /> {change.kind === "change" && <span className="text-muted-foreground">{versus}</span>}
          </span>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: The switchable card**

Create `apps/web/src/components/overview/where-money-went.tsx`:

```tsx
"use client";

import { useState } from "react";

import { BreakdownTable } from "@/components/breakdown/breakdown-table";
import { BreakdownDonut } from "@/components/charts/breakdown-donut";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { BreakdownItem } from "@/lib/breakdown";
import { OTHER_COLOR } from "@/lib/colors";
import type { Delta } from "@/lib/delta";
import type { Dimension } from "@/lib/labels";

const HEADERS: Record<Dimension, string> = { group: "Group", category: "Category", merchant: "Merchant" };

type Props = { views: Record<Dimension, BreakdownItem[]>; total: string | null; change: Delta; versus: string; subtitle: string };

/** "Where your money went" (spec 7.1): donut + table, Groups by default. The Categories and
 * Merchants views paint each slice and row with its group's colour (spec 7.2). */
export function WhereMoneyWent({ views, total, change, versus, subtitle }: Props) {
  const [dimension, setDimension] = useState<Dimension>("group");
  const items = views[dimension];
  const slices = items
    .filter((item) => Number(item.amount) > 0)
    .map((item) => ({ name: item.name, value: Number(item.amount), fill: item.color ?? OTHER_COLOR }));
  return (
    <Card>
      <CardHeader>
        <CardTitle>Where your money went</CardTitle>
        <CardDescription>{subtitle}</CardDescription>
        <CardAction>
          <ToggleGroup
            variant="segment"
            size="sm"
            aria-label="Break down by"
            value={[dimension]}
            onValueChange={(value: string[]) => value[0] && setDimension(value[0] as Dimension)}
          >
            <ToggleGroupItem value="group">Groups</ToggleGroupItem>
            <ToggleGroupItem value="category">Categories</ToggleGroupItem>
            <ToggleGroupItem value="merchant">Merchants</ToggleGroupItem>
          </ToggleGroup>
        </CardAction>
      </CardHeader>
      <CardContent className="grid items-center gap-6 md:grid-cols-[13rem_minmax(0,1fr)]">
        <BreakdownDonut slices={slices} total={total} change={change} versus={versus} />
        <BreakdownTable items={items} nameHeader={HEADERS[dimension]} versus={versus} />
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 5: Add both to the overview**

In `apps/web/src/app/page.tsx`:

Add the imports:

```tsx
import { WhereMoneyWent } from "@/components/overview/where-money-went";
import { breakdownItems, type BreakdownContext } from "@/lib/breakdown";
import { foldBySlot } from "@/lib/colors";
import { plural } from "@/lib/labels";
```

and add `money` to the `@/lib/format` import and `CardAction` to the `@/components/ui/card` import.

Replace the fetch line with a parallel fetch of the categories (the group hints):

```tsx
  const [overview, categories] = await Promise.all([
    apiGet<Schemas["Overview"]>(`/dashboard/overview?${filterParams(filters)}`),
    apiGet<Schemas["CategoryOut"][]>("/categories"),
  ]);
```

After `const spent = atSameDay(overview.cumulative);`, add:

```tsx
  const context: BreakdownContext = { categories, slots: overview.group_slots, filters, good: "down", type: "expense" };
  const views = {
    group: breakdownItems(foldBySlot(overview.by_group, overview.group_slots), "group", context),
    category: breakdownItems(overview.by_category, "category", context),
    merchant: breakdownItems(overview.by_merchant, "merchant", context),
  };
  const subscriptions = overview.subscriptions;
```

After the "Last 12 months" card, before the closing `</>`, add:

```tsx
      <WhereMoneyWent
        views={views}
        total={hasData ? kpis.expenses : null}
        change={delta(amount(kpis.expenses), amount(before?.expenses), "down", "percent")}
        versus={versus}
        subtitle={`${rangeLabel(period)} · ${previousLabel(period, "long")} · colour = group`}
      />
      <Card size="sm">
        <CardHeader>
          <CardTitle>
            {plural(subscriptions.count, "active subscription", "active subscriptions")}
            {/* v_subscriptions is per merchant: the account filter does not apply, so say so. */}
            <span className="font-normal text-muted-foreground">
              {" "}
              · {money(subscriptions.monthly_total)} per month · {money(subscriptions.yearly_total)} per year · all
              accounts
            </span>
          </CardTitle>
          {/* Decision I: "active" is relative to the latest import (spec 5, v_subscriptions). */}
          <CardDescription>
            Active means charged within 45 days (monthly) or 400 days (yearly) of your latest imported transaction, not
            of today.
          </CardDescription>
          <CardAction>
            <Link href="/subscriptions" className="text-sm font-medium text-primary">
              Subscriptions →
            </Link>
          </CardAction>
        </CardHeader>
      </Card>
```

- [ ] **Step 6: Run the gate**

Run: `cd apps/web && npm run lint && npx tsc --noEmit && npm test && npm run build`
Expected: no errors.

- [ ] **Step 7: Check the card in the browser (R1, read-only)**

1. `open "http://localhost:3000/"`, `snapshot -i`. Expect the card "Where your money went" with a group of three toggle buttons, "Groups" pressed; a table with the headers GROUP, SHARE, AMOUNT and "VS <PREVIOUS MONTH>" (the last one only when the previous month has data); one row per group with spend in the period and no folded row, each with a hint under its name ("Not itemized: card statements are not imported" for Credit card).
2. Colour = group: `eval "[...document.querySelectorAll('[data-slot=series-dot]')].map(e => e.style.background)"` lists `var(--chart-N)` for the slotted groups and `var(--chart-other)` for the rest. Note each group's value; choose "Last 12 months" in the period picker and read them again: every group that is still listed keeps the same colour.
3. Click "Categories": category rows with their group's name as the hint, dots in their group's colour, the last row "Other categories" when categories were folded. Click "Merchants": the last row reads "Other N merchants" when merchants were folded.
4. Hover a donut slice (`find first ".recharts-pie-sector" hover`), `snapshot`: the tooltip shows its name and an amount in euros.
5. `snapshot -i -u`: a group's link is `/spending/<group>?<the same period params>`; a category's link is `/spending/<group>/<category>?…`; a merchant's link is `/merchants/<id>?…`. (These pages come in Tasks 6 and 7.)
6. The subscriptions line reads "N active subscriptions · €… per month · €… per year · all accounts", with the line "Active means charged within 45 days (monthly) or 400 days (yearly) of your latest imported transaction, not of today." under it (Decision I) and a link to `/subscriptions`; picking one account in the top bar leaves it unchanged (`/dashboard/overview` ignores `account_id` for subscriptions). `open "http://localhost:3000/?month=2099-12"`: the donut centre reads "Spent —" with no delta (Decision G).
7. Screenshot `task05-overview.png` and compare with the bottom half of `02-overview.png`: donut left, table right, the segmented control at the top right, the subscriptions line as its own low card. `errors`, `close`.

- [ ] **Step 8: Commit**

```bash
git add apps/web/src/components/ui/toggle.tsx apps/web/src/components/ui/toggle-group.tsx apps/web/src/components/breakdown apps/web/src/components/charts/breakdown-donut.tsx apps/web/src/components/overview apps/web/src/app/page.tsx
git commit -m "feat: show where the money went by group, category and merchant on the overview"
```

---

### Task 6: The detail template and the group page

**Files:**
- Create: `apps/web/src/lib/transactions.ts`, `apps/web/src/components/transactions/transaction-row.tsx`, `apps/web/src/components/transactions/transaction-table.tsx`
- Create: `apps/web/src/components/charts/scope-months-chart.tsx`, `apps/web/src/components/charts/category-treemap.tsx`
- Create: `apps/web/src/components/detail/spending-card.tsx`, `apps/web/src/components/detail/detail-page.tsx`, `apps/web/src/app/spending/[group]/page.tsx`
- Add (shadcn): `breadcrumb`
- Test: `apps/web/src/lib/transactions.test.ts`

**Interfaces:**
- Consumes: Tasks 1, 2, 4 and 5 (`BreakdownTable`, `DeltaText`, `CumulativeChart`, `LegendButtons`, `MonthTick`, `monthBarShape`, `MonthRange`, `moneyRow`, `monthTooltipLabel`, `breakdownItems`, `rampColor`, `delta`, `knownGroup`, `label`, `plural`, `isSlug`, `parseFilters`, `withFilters`).
- Produces:
  - `transactions.ts`: `Day = { day: string; net: number; items: Schemas["Transaction"][] }`; `groupByDay(items): Day[]`.
  - `TransactionRow({ tx, onOpen?: () => void, showSource?: boolean })`; `TransactionTable({ items, onOpen?: (tx) => void, showSource?: boolean })`: rows grouped by day, each day header a `TableRow` with `data-day="YYYY-MM-DD"` and the day's net.
  - `Series = { key: string; label: string; color: string }`; `ScopeMonthsChart({ months: Schemas["ScopeMonth"][], series: Series[], range: MonthRange })`: one bar per month when `series` is empty, stacked by child otherwise.
  - `Tile = { name; value: number; share: number; fill: string; href: string | null }`; `CategoryTreemap({ tiles })`.
  - `SpendingCard({ title, months, series, cumulative, period, split: boolean, defaultView: "monthly" | "cumulative" })`.
  - `Crumb = { label: string; href?: string }`; `DetailPage({ detail: Schemas["SpendingDetail"], categories, filters, title, crumbs, childDimension: "category" | "merchant" | null, seeAllHref, defaultView? })`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/lib/transactions.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import type { Schemas } from "./api";
import { groupByDay } from "./transactions";

type Tx = Schemas["Transaction"];

const tx = (id: string, day: string, amount: string, fields: Partial<Tx> = {}): Tx => ({
  id,
  booked_at: day,
  account_id: "a",
  account_name: "ZZTEST ACCOUNT",
  amount,
  description_raw: "ZZTEST",
  bank_merchant_text: null,
  merchant_id: null,
  merchant_name: null,
  tx_type: "expense",
  category_slug: null,
  level1: null,
  category_source: "none",
  is_subscription: false,
  needs_review: false,
  note: null,
  transfer_pair_id: null,
  ...fields,
});

describe("groupByDay", () => {
  it("groups rows by day with the day's net", () => {
    const days = groupByDay([tx("1", "2026-08-26", "-42.10"), tx("2", "2026-08-26", "-16.30"), tx("3", "2026-08-25", "51.00")]);
    expect(days.map((d) => [d.day, d.net.toFixed(2), d.items.length])).toEqual([
      ["2026-08-26", "-58.40", 2],
      ["2026-08-25", "51.00", 1],
    ]);
  });

  it("keeps one header for a day split across two pages", () => {
    const firstPage = [tx("1", "2026-08-26", "-10.00")];
    const secondPage = [tx("2", "2026-08-26", "-5.00"), tx("3", "2026-08-24", "-1.00")];
    const days = groupByDay([...firstPage, ...secondPage]);
    expect(days.map((d) => [d.day, d.net, d.items.length])).toEqual([
      ["2026-08-26", -15, 2],
      ["2026-08-24", -1, 1],
    ]);
  });
});
```

Run: `cd apps/web && npm test`
Expected: FAIL, `Failed to resolve import "./transactions"`.

- [ ] **Step 2: Implement `transactions.ts`**

Create `apps/web/src/lib/transactions.ts`:

```ts
/** The explorer's rows: grouped by day (spec 7.3). */

import type { Schemas } from "./api";

type Tx = Schemas["Transaction"];

export type Day = { day: string; net: number; items: Tx[] };

/** Rows arrive newest first (booked_at desc). A day split across two "Load more" pages still gets
 * one header, because the pages are grouped together after they are merged. */
export function groupByDay(items: Tx[]): Day[] {
  const days: Day[] = [];
  for (const tx of items) {
    const last = days.at(-1);
    if (last && last.day === tx.booked_at) {
      last.items.push(tx);
      last.net += Number(tx.amount);
    } else {
      days.push({ day: tx.booked_at, net: Number(tx.amount), items: [tx] });
    }
  }
  return days;
}
```

Run: `cd apps/web && npm test`
Expected: PASS.

- [ ] **Step 3: Transaction rows**

Create `apps/web/src/components/transactions/transaction-row.tsx`:

```tsx
import { Repeat, StickyNote } from "lucide-react";

import { TableCell, TableRow } from "@/components/ui/table";
import type { Schemas } from "@/lib/api";
import { signedMoney } from "@/lib/format";
import { label, sourceLabel } from "@/lib/labels";
import { cn } from "@/lib/utils";

type Tx = Schemas["Transaction"];

// A small dot beside the source's name (spec 7.3); the text carries the meaning.
const SOURCE_DOT: Record<string, string> = {
  rule: "bg-muted-foreground",
  merchant: "bg-ramp-3",
  jev: "bg-primary",
  user: "bg-foreground",
  none: "bg-chart-other",
};

type Props = { tx: Tx; onOpen?: () => void; showSource?: boolean };

/** One transaction (mockup 03): the merchant with the note as a muted second line, group ·
 * category, account, amount, a subscription mark and, in the explorer, who categorized it. */
export function TransactionRow({ tx, onOpen, showSource = false }: Props) {
  const name = tx.merchant_name ?? tx.bank_merchant_text ?? tx.description_raw;
  const amount = Number(tx.amount);
  return (
    <TableRow onClick={onOpen} className={cn(onOpen && "cursor-pointer")}>
      <TableCell className="max-w-72 whitespace-normal">
        <div className="flex items-center gap-3">
          <span
            aria-hidden
            className="flex size-7 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold text-muted-foreground"
          >
            {name.charAt(0).toUpperCase()}
          </span>
          <div className="min-w-0">
            {onOpen ? (
              <button
                type="button"
                className="max-w-full truncate text-left font-medium"
                onClick={(event) => {
                  event.stopPropagation();
                  onOpen();
                }}
              >
                {name}
              </button>
            ) : (
              <p className="truncate font-medium">{name}</p>
            )}
            {tx.note && (
              <p className="flex items-center gap-1 truncate text-xs text-muted-foreground">
                <StickyNote aria-hidden className="size-3 shrink-0" />
                {tx.note}
              </p>
            )}
          </div>
        </div>
      </TableCell>
      <TableCell className="hidden text-muted-foreground sm:table-cell">
        {tx.level1 ? `${label(tx.level1)} · ${label(tx.category_slug)}` : "Uncategorized"}
      </TableCell>
      <TableCell className="hidden text-xs text-muted-foreground md:table-cell">{tx.account_name}</TableCell>
      {showSource && (
        <TableCell className="hidden text-xs text-muted-foreground lg:table-cell">
          <span className="flex items-center gap-1.5">
            <span aria-hidden className={cn("size-1.5 rounded-full", SOURCE_DOT[tx.category_source] ?? "bg-chart-other")} />
            {sourceLabel(tx.category_source)}
          </span>
        </TableCell>
      )}
      <TableCell className={cn("text-right font-medium", amount > 0 && "text-income")}>
        <span className="inline-flex items-center gap-1.5">
          {tx.is_subscription && <Repeat aria-label="Subscription" className="size-3.5 text-muted-foreground" />}
          {signedMoney(amount)}
        </span>
      </TableCell>
    </TableRow>
  );
}
```

Create `apps/web/src/components/transactions/transaction-table.tsx`:

```tsx
import { Fragment } from "react";

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { Schemas } from "@/lib/api";
import { dayHeader, signedMoney } from "@/lib/format";
import { groupByDay } from "@/lib/transactions";

import { TransactionRow } from "./transaction-row";

type Tx = Schemas["Transaction"];

type Props = { items: Tx[]; onOpen?: (tx: Tx) => void; showSource?: boolean };

/** Rows grouped by day; each day header shows that day's net (spec 7.3). */
export function TransactionTable({ items, onOpen, showSource = false }: Props) {
  const columns = showSource ? 5 : 4;
  return (
    <Table>
      <TableHeader className="sr-only">
        <TableRow>
          <TableHead>Merchant</TableHead>
          <TableHead>Category</TableHead>
          <TableHead>Account</TableHead>
          {showSource && <TableHead>Categorized by</TableHead>}
          <TableHead>Amount</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {groupByDay(items).map((day) => (
          <Fragment key={day.day}>
            <TableRow data-day={day.day} className="hover:bg-transparent">
              <TableCell colSpan={columns} className="pt-4 pb-1 text-xs text-muted-foreground">
                <div className="flex justify-between">
                  <span>{dayHeader(day.day)}</span>
                  <span>{signedMoney(day.net)}</span>
                </div>
              </TableCell>
            </TableRow>
            {day.items.map((tx) => (
              <TransactionRow key={tx.id} tx={tx} showSource={showSource} onOpen={onOpen && (() => onOpen(tx))} />
            ))}
          </Fragment>
        ))}
      </TableBody>
    </Table>
  );
}
```

- [ ] **Step 4: The per-month chart and the treemap**

Create `apps/web/src/components/charts/scope-months-chart.tsx`:

```tsx
"use client";

import { useState } from "react";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";

import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import type { Schemas } from "@/lib/api";
import { compactMoney } from "@/lib/format";

import { LegendButtons } from "./legend-buttons";
import { MonthTick, monthBarShape, type MonthRange } from "./month-axis";
import { moneyRow, monthTooltipLabel } from "./money-tooltip";

/** One stacked series: a child of the scope (a category, or "_other"), in a ramp shade. */
export type Series = { key: string; label: string; color: string };

type Props = { months: Schemas["ScopeMonth"][]; series: Series[]; range: MonthRange };

/** A scope's 12 months (spec 7.1): one bar per month, or each month stacked by child in the
 * one-hue ramp (spec 7.2). Series keys are s0..s5 because child keys (slugs, "category:…") are not
 * valid CSS variable names. Refund-only months stack below zero (`stackOffset="sign"`). */
export function ScopeMonthsChart({ months, series, range }: Props) {
  const [isolated, setIsolated] = useState<string | null>(null);
  const keys = series.map((_, index) => `s${index}`);
  const visible = keys.filter((key) => isolated === null || key === isolated);
  const noData = new Set(months.filter((month) => !month.has_data).map((month) => month.month));
  const data = months.map((month) => ({
    month: month.month,
    total: month.has_data ? Number(month.total) : null,
    ...Object.fromEntries(series.map((s, index) => [`s${index}`, month.has_data ? Number(month.by_child[s.key] ?? 0) : null])),
  }));
  const config: ChartConfig = series.length
    ? Object.fromEntries(series.map((s, index) => [`s${index}`, { label: s.label, color: s.color }]))
    : { total: { label: "Total", color: "var(--primary)" } };
  const shape = monthBarShape(range);
  return (
    <div className="flex flex-col gap-3">
      {series.length > 1 && (
        <LegendButtons
          isolated={isolated}
          onIsolate={setIsolated}
          items={series.map((s, index) => ({ key: `s${index}`, label: s.label, color: s.color }))}
        />
      )}
      <ChartContainer config={config} className="aspect-auto h-60 w-full">
        <BarChart accessibilityLayer data={data} stackOffset="sign" margin={{ top: 28, right: 8, left: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
          <XAxis
            dataKey="month"
            interval={0}
            tickLine={false}
            axisLine={false}
            tickMargin={6}
            height={28}
            tick={<MonthTick range={range} noData={noData} />}
          />
          <YAxis width={48} tickLine={false} axisLine={false} tickFormatter={(tick: number) => compactMoney(tick)} />
          <ChartTooltip content={<ChartTooltipContent labelFormatter={monthTooltipLabel} formatter={moneyRow(config)} />} />
          {series.length === 0 ? (
            <Bar dataKey="total" fill="var(--color-total)" radius={[4, 4, 0, 0]} maxBarSize={32} shape={shape} />
          ) : (
            keys.map((key) => (
              <Bar
                key={key}
                dataKey={key}
                stackId="months"
                fill={`var(--color-${key})`}
                stroke="var(--card)"
                strokeWidth={1}
                maxBarSize={32}
                radius={key === visible.at(-1) ? [4, 4, 0, 0] : 0}
                hide={!visible.includes(key)}
                shape={shape}
              />
            ))
          )}
        </BarChart>
      </ChartContainer>
    </div>
  );
}
```

Create `apps/web/src/components/charts/category-treemap.tsx`:

```tsx
"use client";

import { useRouter } from "next/navigation";
import { Treemap } from "recharts";

import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import { moneyWhole, percent } from "@/lib/format";

import { moneyRow } from "./money-tooltip";

export type Tile = { name: string; value: number; share: number; fill: string; href: string | null };

type TileProps = Partial<Tile> & {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  depth?: number;
  onOpen: (href: string) => void;
};

// The two lightest ramp steps take dark ink, the others white (dataviz: a label inside a fill).
const LIGHT = new Set(["var(--ramp-5)", "var(--ramp-6)"]);

/** Recharts calls this for the root (depth 0) and for each tile (depth 1). A tile's label is left
 * out when it would not fit, instead of being clipped (spec 8, gotcha 4). */
function TreemapTile({ x = 0, y = 0, width = 0, height = 0, depth, name = "", value = 0, share = 0, fill, href, onOpen }: TileProps) {
  if (depth !== 1) return <g />;
  const fits = width > 20 + name.length * 7 && height > 40;
  return (
    <g className={href ? "cursor-pointer" : undefined} onClick={() => href && onOpen(href)}>
      <rect x={x} y={y} width={width} height={height} rx={6} fill={fill} stroke="var(--card)" strokeWidth={3} />
      {fits && (
        <text x={x + 9} y={y + 18} fontSize={12} className={LIGHT.has(fill ?? "") ? "fill-foreground" : "fill-primary-foreground"}>
          <tspan fontWeight={600}>{name}</tspan>
          <tspan x={x + 9} dy={16}>
            {moneyWhole(value)} · {percent(share)}
          </tspan>
        </text>
      )}
    </g>
  );
}

/** Categories in a group, area = money (mockup 03), in the same ramp shades as the stacked bars.
 * The table next to it is the accessible twin: tiles are for the mouse. */
export function CategoryTreemap({ tiles }: { tiles: Tile[] }) {
  const router = useRouter();
  if (tiles.length === 0) return null;
  return (
    <ChartContainer config={{}} className="aspect-auto h-52 w-full">
      <Treemap
        data={tiles}
        dataKey="value"
        nameKey="name"
        isAnimationActive={false}
        content={<TreemapTile onOpen={(href) => router.push(href)} />}
      >
        <ChartTooltip content={<ChartTooltipContent hideLabel formatter={moneyRow({})} />} />
      </Treemap>
    </ChartContainer>
  );
}
```

- [ ] **Step 5: The per-month card and the template**

```bash
cd apps/web && npx shadcn@latest add breadcrumb --dry-run
cd apps/web && npx shadcn@latest add breadcrumb
```

Create `apps/web/src/components/detail/spending-card.tsx`:

```tsx
"use client";

import { useState } from "react";

import { CumulativeChart } from "@/components/charts/cumulative-chart";
import { ScopeMonthsChart, type Series } from "@/components/charts/scope-months-chart";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { Schemas } from "@/lib/api";

type View = "monthly" | "cumulative";

type Props = {
  title: string;
  months: Schemas["ScopeMonth"][];
  series: Series[];
  cumulative: Schemas["Cumulative"];
  period: Schemas["PeriodOut"];
  split: boolean;
  defaultView: View;
};

/** "<Scope> per month" (mockup 03): Total | By category, and Monthly | Cumulative. */
export function SpendingCard({ title, months, series, cumulative, period, split, defaultView }: Props) {
  const [view, setView] = useState<View>(defaultView);
  const [stacked, setStacked] = useState(false);
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardAction className="flex flex-wrap justify-end gap-2">
          {split && view === "monthly" && (
            <ToggleGroup
              variant="segment"
              size="sm"
              aria-label="Split"
              value={[stacked ? "split" : "total"]}
              onValueChange={(value: string[]) => value[0] && setStacked(value[0] === "split")}
            >
              <ToggleGroupItem value="total">Total</ToggleGroupItem>
              <ToggleGroupItem value="split">By category</ToggleGroupItem>
            </ToggleGroup>
          )}
          <ToggleGroup
            variant="segment"
            size="sm"
            aria-label="View"
            value={[view]}
            onValueChange={(value: string[]) => value[0] && setView(value[0] as View)}
          >
            <ToggleGroupItem value="monthly">Monthly</ToggleGroupItem>
            <ToggleGroupItem value="cumulative">Cumulative</ToggleGroupItem>
          </ToggleGroup>
        </CardAction>
      </CardHeader>
      <CardContent>
        {view === "cumulative" ? (
          <CumulativeChart cumulative={cumulative} period={period} />
        ) : (
          <ScopeMonthsChart
            months={months}
            series={split && stacked ? series : []}
            range={[period.start.slice(0, 7), period.end.slice(0, 7)]}
          />
        )}
      </CardContent>
    </Card>
  );
}
```

Create `apps/web/src/components/detail/detail-page.tsx`:

```tsx
import Link from "next/link";
import { Fragment } from "react";

import { BreakdownTable } from "@/components/breakdown/breakdown-table";
import { CategoryTreemap } from "@/components/charts/category-treemap";
import { DeltaText } from "@/components/money/delta-text";
import { TransactionTable } from "@/components/transactions/transaction-table";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { Schemas } from "@/lib/api";
import { breakdownItems, type BreakdownContext } from "@/lib/breakdown";
import { rampColor } from "@/lib/colors";
import { delta, type Good } from "@/lib/delta";
import { money, previousLabel, rangeLabel } from "@/lib/format";
import { plural } from "@/lib/labels";
import type { Filters } from "@/lib/params";
import { cn } from "@/lib/utils";

import { SpendingCard } from "./spending-card";

export type Crumb = { label: string; href?: string };

type Props = {
  detail: Schemas["SpendingDetail"];
  categories: Schemas["CategoryOut"][];
  filters: Filters;
  title: string;
  crumbs: Crumb[];
  childDimension: "category" | "merchant" | null;
  seeAllHref: string;
  defaultView?: "monthly" | "cumulative";
};

/** One template for every level (mockup page map): the total and its delta, a per-month chart,
 * the next level as chart + table, top merchants, and the latest transactions with "See all". */
export function DetailPage({ detail, categories, filters, title, crumbs, childDimension, seeAllHref, defaultView = "monthly" }: Props) {
  const good: Good = detail.type === "expense" ? "down" : "up";
  const context: BreakdownContext = { categories, slots: null, filters, good, type: detail.type };
  const children = childDimension ? breakdownItems(detail.children, childDimension, context) : [];
  const merchants = breakdownItems(detail.top_merchants, "merchant", context);
  const names = new Map(children.map((item) => [item.key, item.name]));
  const series = detail.child_keys.map((key, index) => ({
    key,
    label: key === "_other" ? "Other" : (names.get(key) ?? key),
    color: rampColor(key === "_other" ? 5 : index),
  }));
  const tiles = children
    .filter((item) => Number(item.amount) > 0)
    .map((item, index) => ({ name: item.name, value: Number(item.amount), share: item.share, fill: rampColor(index), href: item.href }));
  const total = Number(detail.total);
  const previous = detail.previous_total === null ? null : Number(detail.previous_total);
  const change = delta(total, previous, good, "euro");
  const versus = previousLabel(detail.period, "long");
  return (
    <>
      <Breadcrumb>
        <BreadcrumbList>
          {crumbs.map((crumb, index) => (
            <Fragment key={index}>
              {index > 0 && <BreadcrumbSeparator />}
              <BreadcrumbItem>
                {crumb.href ? (
                  <BreadcrumbLink render={<Link href={crumb.href} />}>{crumb.label}</BreadcrumbLink>
                ) : (
                  <BreadcrumbPage>{crumb.label}</BreadcrumbPage>
                )}
              </BreadcrumbItem>
            </Fragment>
          ))}
        </BreadcrumbList>
      </Breadcrumb>
      <header className="flex flex-col gap-0.5">
        <h1 className="text-sm text-muted-foreground">
          {title} · {rangeLabel(detail.period)}
        </h1>
        <p className="text-4xl font-semibold tracking-tight">{money(total)}</p>
        <p className="text-sm text-muted-foreground">
          <DeltaText value={change} /> <DeltaText value={delta(total, previous, good, "percent")} arrow={false} parens />{" "}
          {change.kind !== "hidden" && `${versus} · `}
          {plural(detail.count, "transaction", "transactions")}
        </p>
      </header>
      <SpendingCard
        title={`${title} per month`}
        months={detail.months}
        series={series}
        cumulative={detail.cumulative}
        period={detail.period}
        split={childDimension === "category"}
        defaultView={defaultView}
      />
      {childDimension && (
        <Card>
          <CardHeader>
            <CardTitle>{childDimension === "category" ? `Categories in ${title}` : `Merchants in ${title}`}</CardTitle>
            <CardDescription>
              {childDimension === "category"
                ? `Area = money ${detail.type === "expense" ? "spent" : "received"} · click a category to open it`
                : "Click a merchant to open it"}
            </CardDescription>
          </CardHeader>
          <CardContent className={cn("grid items-start gap-6", childDimension === "category" && "lg:grid-cols-2")}>
            {childDimension === "category" && <CategoryTreemap tiles={tiles} />}
            <BreakdownTable items={children} nameHeader={childDimension === "category" ? "Category" : "Merchant"} versus={versus} />
          </CardContent>
        </Card>
      )}
      <div className={cn("grid items-start gap-4", merchants.length > 0 && "lg:grid-cols-[minmax(0,1fr)_minmax(0,1.25fr)]")}>
        {merchants.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Top merchants</CardTitle>
              <CardAction>
                <Link href={seeAllHref} className="text-sm font-medium text-primary">
                  All →
                </Link>
              </CardAction>
            </CardHeader>
            <CardContent>
              <BreakdownTable items={merchants} nameHeader="Merchant" versus={versus} showShare={false} />
            </CardContent>
          </Card>
        )}
        <Card>
          <CardHeader>
            <CardTitle>Transactions</CardTitle>
            <CardAction>
              <Link href={seeAllHref} className="text-sm font-medium text-primary">
                See all {detail.count} in Transactions →
              </Link>
            </CardAction>
          </CardHeader>
          <CardContent>
            {detail.latest.length > 0 ? (
              <TransactionTable items={detail.latest} />
            ) : (
              <p className="text-sm text-muted-foreground">No transactions in this period.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
```

- [ ] **Step 6: The group page**

Create `apps/web/src/app/spending/[group]/page.tsx`:

```tsx
import { notFound } from "next/navigation";

import { DetailPage } from "@/components/detail/detail-page";
import { apiGet, type Schemas } from "@/lib/api";
import { knownGroup, label } from "@/lib/labels";
import { isSlug, parseFilters, withFilters } from "@/lib/params";

export const dynamic = "force-dynamic";

/** A spending group (spec 7.1): its categories as a treemap + table, top merchants, rows. */
export default async function GroupPage({ params, searchParams }: PageProps<"/spending/[group]">) {
  const [{ group }, query] = await Promise.all([params, searchParams]);
  if (!isSlug(group)) notFound();
  const filters = parseFilters(query);
  const [categories, detail] = await Promise.all([
    apiGet<Schemas["CategoryOut"][]>("/categories"),
    apiGet<Schemas["SpendingDetail"]>(withFilters("/spending/detail", filters, { type: "expense", level1: group })),
  ]);
  if (!knownGroup(group, categories)) notFound();
  return (
    <DetailPage
      detail={detail}
      categories={categories}
      filters={filters}
      title={label(group)}
      crumbs={[{ label: "Overview", href: withFilters("/", filters) }, { label: label(group) }]}
      childDimension="category"
      seeAllHref={withFilters("/transactions", filters, { tx_type: "expense", level1: group })}
    />
  );
}
```

- [ ] **Step 7: Run the gate**

Run: `cd apps/web && npm run lint && npx tsc --noEmit && npm test && npm run build`
Expected: no errors.

- [ ] **Step 8: Check the group page in the browser (R1, read-only)**

Take the largest group from the overview's "Where your money went" table (its link), for example `/spending/shopping`.
1. `open` it, `snapshot -i`. Expect: a breadcrumb "Overview › <Group>" (Overview is a link that keeps the period params); the h1 "<Group> · <period>"; the total in large type; a delta line such as "down −€38 (−7%) vs July · 31 transactions" (the screenshot shows "↘ −€38 (−7%) vs July · 31 transactions").
2. "<Group> per month": the toggles "Total"/"By category" (Total pressed) and "Monthly"/"Cumulative" (Monthly pressed); 12 columns, the selected month in full colour, the rest lighter; "no data" boxes where a month has no data.
3. Click "By category": a legend of up to six items appears and each column stacks in the ramp shades, darkest at the bottom. `eval "document.querySelectorAll('.recharts-bar-rectangle').length"`, click the first legend item: it is `aria-pressed="true"`, the others are dimmed, and the count drops to one bar per month; click it again: the count returns. `find nth 1 ".recharts-bar-rectangle" hover`: the tooltip lists the categories in euros.
4. Click "Cumulative": the two-line chart replaces the bars and the Total/By category toggle hides.
5. "Categories in <Group>": the treemap and the table. `find first ".recharts-treemap-depth-1" hover`, `snapshot`: the tooltip shows a category name and an amount in euros. A tile too small for its label shows no text (no clipped letters). Click the largest tile: the URL becomes `/spending/<group>/<category>?…` (the page comes in Task 7).
6. "Top merchants" rows link to `/merchants/<id>?…`. "Transactions" shows up to five rows grouped by day, each day header with its net; "See all N in Transactions →" links to `/transactions?…&tx_type=expense&level1=<group>`.
7. `open "http://localhost:3000/spending/not-a-group"`: the 404 page.
8. Screenshot `task06-group.png` (use "By category") and compare with `03-group-page.png`: breadcrumb, headline number, the per-month card with both segmented controls, the treemap next to its table, top merchants and transactions side by side. `errors`, `close`.

- [ ] **Step 9: Commit**

```bash
git add apps/web/src/lib/transactions.ts apps/web/src/lib/transactions.test.ts apps/web/src/components/transactions apps/web/src/components/charts/scope-months-chart.tsx apps/web/src/components/charts/category-treemap.tsx apps/web/src/components/detail apps/web/src/components/ui/breadcrumb.tsx apps/web/src/app/spending
git commit -m "feat: add the detail page template and the spending group page"
```

---

### Task 7: Category, income and merchant pages

**Files:**
- Create: `apps/web/src/app/spending/[group]/[category]/page.tsx`, `apps/web/src/app/income/page.tsx`, `apps/web/src/app/income/[category]/page.tsx`, `apps/web/src/app/merchants/[id]/page.tsx`

**Interfaces:**
- Consumes: `DetailPage` (Task 6); `knownCategory`, `label` (Task 2); `isSlug`, `isUuid`, `detailType`, `parseFilters`, `withFilters` (Task 1).
- Produces: the routes `/spending/[group]/[category]`, `/income`, `/income/[category]` and `/merchants/[id]` (with `?type=income` for money received from a merchant, such as an employer).

- [ ] **Step 1: The category page**

Create `apps/web/src/app/spending/[group]/[category]/page.tsx`:

```tsx
import { notFound } from "next/navigation";

import { DetailPage } from "@/components/detail/detail-page";
import { apiGet, type Schemas } from "@/lib/api";
import { knownCategory, label } from "@/lib/labels";
import { isSlug, parseFilters, withFilters } from "@/lib/params";

export const dynamic = "force-dynamic";

/** A category inside a group (spec 7.1): the same template, with merchants instead of categories. */
export default async function CategoryPage({ params, searchParams }: PageProps<"/spending/[group]/[category]">) {
  const [{ group, category }, query] = await Promise.all([params, searchParams]);
  if (!isSlug(group) || !isSlug(category)) notFound();
  const filters = parseFilters(query);
  const [categories, detail] = await Promise.all([
    apiGet<Schemas["CategoryOut"][]>("/categories"),
    apiGet<Schemas["SpendingDetail"]>(withFilters("/spending/detail", filters, { type: "expense", level1: group, category })),
  ]);
  if (!knownCategory(category, categories, { type: "expense", level1: group })) notFound();
  return (
    <DetailPage
      detail={detail}
      categories={categories}
      filters={filters}
      title={label(category)}
      crumbs={[
        { label: "Overview", href: withFilters("/", filters) },
        { label: label(group), href: withFilters(`/spending/${group}`, filters) },
        { label: label(category) },
      ]}
      childDimension="merchant"
      seeAllHref={withFilters("/transactions", filters, { tx_type: "expense", level1: group, category })}
    />
  );
}
```

- [ ] **Step 2: The income pages**

Create `apps/web/src/app/income/page.tsx`:

```tsx
import { DetailPage } from "@/components/detail/detail-page";
import { apiGet, type Schemas } from "@/lib/api";
import { parseFilters, withFilters } from "@/lib/params";

export const dynamic = "force-dynamic";

/** Income (spec 7.1): the group template over the income categories. More is good here. */
export default async function IncomePage({ searchParams }: PageProps<"/income">) {
  const filters = parseFilters(await searchParams);
  const [categories, detail] = await Promise.all([
    apiGet<Schemas["CategoryOut"][]>("/categories"),
    apiGet<Schemas["SpendingDetail"]>(withFilters("/spending/detail", filters, { type: "income" })),
  ]);
  return (
    <DetailPage
      detail={detail}
      categories={categories}
      filters={filters}
      title="Income"
      crumbs={[{ label: "Overview", href: withFilters("/", filters) }, { label: "Income" }]}
      childDimension="category"
      seeAllHref={withFilters("/transactions", filters, { tx_type: "income" })}
    />
  );
}
```

Create `apps/web/src/app/income/[category]/page.tsx`:

```tsx
import { notFound } from "next/navigation";

import { DetailPage } from "@/components/detail/detail-page";
import { apiGet, type Schemas } from "@/lib/api";
import { knownCategory, label } from "@/lib/labels";
import { isSlug, parseFilters, withFilters } from "@/lib/params";

export const dynamic = "force-dynamic";

/** One income category, with the merchants that paid it. */
export default async function IncomeCategoryPage({ params, searchParams }: PageProps<"/income/[category]">) {
  const [{ category }, query] = await Promise.all([params, searchParams]);
  if (!isSlug(category)) notFound();
  const filters = parseFilters(query);
  const [categories, detail] = await Promise.all([
    apiGet<Schemas["CategoryOut"][]>("/categories"),
    apiGet<Schemas["SpendingDetail"]>(withFilters("/spending/detail", filters, { type: "income", category })),
  ]);
  if (!knownCategory(category, categories, { type: "income" })) notFound();
  return (
    <DetailPage
      detail={detail}
      categories={categories}
      filters={filters}
      title={label(category)}
      crumbs={[
        { label: "Overview", href: withFilters("/", filters) },
        { label: "Income", href: withFilters("/income", filters) },
        { label: label(category) },
      ]}
      childDimension="merchant"
      seeAllHref={withFilters("/transactions", filters, { tx_type: "income", category })}
    />
  );
}
```

- [ ] **Step 3: The merchant page**

Create `apps/web/src/app/merchants/[id]/page.tsx`:

```tsx
import { notFound } from "next/navigation";

import { DetailPage } from "@/components/detail/detail-page";
import { apiGet, type Schemas } from "@/lib/api";
import { detailType, isUuid, parseFilters, withFilters } from "@/lib/params";

export const dynamic = "force-dynamic";

/** A merchant (spec 7.1): the total and its delta, the cumulative line against the previous
 * period by default, and its transactions. Links from the income pages add `?type=income`. */
export default async function MerchantPage({ params, searchParams }: PageProps<"/merchants/[id]">) {
  const [{ id }, query] = await Promise.all([params, searchParams]);
  if (!isUuid(id)) notFound();
  const filters = parseFilters(query);
  const type = detailType(query);
  const [categories, detail] = await Promise.all([
    apiGet<Schemas["CategoryOut"][]>("/categories"),
    apiGet<Schemas["SpendingDetail"]>(withFilters("/spending/detail", filters, { type, merchant_id: id })),
  ]);
  if (detail.merchant_name === null) notFound();
  return (
    <DetailPage
      detail={detail}
      categories={categories}
      filters={filters}
      title={detail.merchant_name}
      crumbs={[{ label: "Overview", href: withFilters("/", filters) }, { label: detail.merchant_name }]}
      childDimension={null}
      seeAllHref={withFilters("/transactions", filters, { tx_type: type, merchant_id: id })}
      defaultView="cumulative"
    />
  );
}
```

- [ ] **Step 4: Run the gate**

Run: `cd apps/web && npm run lint && npx tsc --noEmit && npm test && npm run build`
Expected: no errors.

- [ ] **Step 5: Check the pages in the browser (R1, read-only)**

1. From the group page of Task 6, click the largest tile. Expect: the breadcrumb "Overview › <Group> › <Category>" with two links; the per-month card with only "Monthly"/"Cumulative" (no "By category"); the card "Merchants in <Category>" with a table (no treemap) whose rows link to `/merchants/<id>?…`; no "Top merchants" card; transactions grouped by day.
2. Click a merchant. Expect: "Overview › <Merchant>"; the per-month card opens on "Cumulative" (pressed) with the current and previous lines; switching to "Monthly" shows the 12 columns; "See all N in Transactions →" links to `/transactions?…&tx_type=expense&merchant_id=<id>`.
3. `open "http://localhost:3000/income"` (or click the Income tile on the overview). Expect: "Overview › Income"; "Categories in Income" with a treemap of the income categories and "Area = money received"; a delta that is green when income went up.
4. Click an income category, then a merchant in it: the merchant URL carries `type=income`, and the page shows that merchant's income.
5. 404s: `open "http://localhost:3000/merchants/not-a-uuid"`, `open "http://localhost:3000/merchants/00000000-0000-4000-8000-000000000000"`, `open "http://localhost:3000/spending/shopping/salary"` (salary is not a shopping category): each shows the 404 page.
6. Change the period in the top bar on a category page: the URL keeps the path, the numbers change, and the breadcrumb links carry the new period.
7. Screenshots `task07-category.png`, `task07-merchant.png`, `task07-income.png`; compare them with the page map (`01-page-map.png`): each level uses the same template. `errors`, `close`.

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/app/spending apps/web/src/app/income apps/web/src/app/merchants
git commit -m "feat: add the category, merchant and income detail pages"
```

---

### Task 8: Direction-aware pickers and the /review fixes

**Files:**
- Create: `apps/web/src/lib/pickers.ts`
- Move and modify: `apps/web/src/app/review/category-picker.tsx` → `apps/web/src/components/pickers/category-picker.tsx`; `apps/web/src/app/review/merchant-picker.tsx` → `apps/web/src/components/pickers/merchant-picker.tsx`
- Modify: `apps/web/src/app/review/review-row.tsx`, `apps/web/src/app/review/review-list.tsx`
- Test: `apps/web/src/lib/pickers.test.ts`

**Interfaces:**
- Consumes: `label`, `plural` (Task 2); `dayLong`, `signedMoney` (Task 1); `TxType` (Task 1).
- Produces:
  - `pickers.ts`: `Direction = "in" | "out"`; `PickerGroup = { value: string; label: string; items: CategoryOut[] }`; `directionOf(amounts: (string | number)[]): Direction`; `fitsDirection(slug, categories, direction): boolean` (Decision H); `byLevel1(categories): PickerGroup[]`; `pickerGroups(categories, direction, suggested?: string[]): PickerGroup[]`; `FilterOption = { kind: "group" | "category"; value: string; label: string }`; `FilterGroup = { value; label; items: FilterOption[] }`; `filterGroups(categories, txType?: TxType): FilterGroup[]`.
  - `CategoryPicker({ categories, direction, suggested?, value, onChange, id?, ariaLabel? })`.
  - `MerchantChoice = { id: string | null; name: string }`; `MerchantPicker({ merchants, value, onChange, allowCreate? = true, showClear? = false, id?, ariaLabel? = "Merchant" })`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/lib/pickers.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import type { Schemas } from "./api";
import { directionOf, filterGroups, fitsDirection, pickerGroups } from "./pickers";

const categories: Schemas["CategoryOut"][] = [
  { slug: "groceries", tx_type: "expense", level1: "shopping" },
  { slug: "fashion", tx_type: "expense", level1: "shopping" },
  { slug: "rent", tx_type: "expense", level1: "home" },
  { slug: "salary", tx_type: "income", level1: "income" },
  { slug: "refunds", tx_type: "income", level1: "income" },
  { slug: "own_accounts", tx_type: "transfer", level1: "transfer" },
];
const slugs = (groups: { items: { slug: string }[] }[]) => groups.map((group) => group.items.map((item) => item.slug));

describe("pickerGroups", () => {
  it("offers expense and transfer categories for money out", () => {
    const groups = pickerGroups(categories, "out");
    expect(groups.map((group) => group.label)).toEqual(["Shopping", "Home", "Transfer"]);
    expect(slugs(groups)).toEqual([["groceries", "fashion"], ["rent"], ["own_accounts"]]);
  });

  it("offers income first, then refunds of a purchase, then transfers for money in", () => {
    const groups = pickerGroups(categories, "in");
    expect(groups.map((group) => group.label)).toEqual(["Income", "Refund of a purchase", "Transfer"]);
    expect(slugs(groups)[1]).toEqual(["groceries", "fashion", "rent"]);
  });

  it("keeps only the suggestions that fit the direction", () => {
    const [suggested] = pickerGroups(categories, "out", ["salary", "fashion"]);
    expect(suggested.label).toBe("Suggested");
    expect(suggested.items.map((item) => item.slug)).toEqual(["fashion"]);
    expect(pickerGroups(categories, "out", ["salary"])[0].label).toBe("Shopping");
  });

  it("reads a merchant with purchases and refunds as money out", () => {
    expect(directionOf(["15.00", "-20.00"])).toBe("out");
    expect(directionOf(["2000.00"])).toBe("in");
  });
});

describe("fitsDirection", () => {
  it("tells whether a category fits the direction (Decision H)", () => {
    expect(fitsDirection("salary", categories, "out")).toBe(false);
    expect(fitsDirection("fashion", categories, "out")).toBe(true);
    // A refund keeps its purchase's category, so money in takes any category.
    expect(fitsDirection("fashion", categories, "in")).toBe(true);
    expect(fitsDirection("unknown", categories, "in")).toBe(false);
  });
});

describe("filterGroups", () => {
  it("follows the type filter and starts each group with the whole group", () => {
    expect(filterGroups(categories, "income")).toEqual([
      {
        value: "income",
        label: "Income",
        items: [
          { kind: "group", value: "income", label: "All of Income" },
          { kind: "category", value: "salary", label: "Salary" },
          { kind: "category", value: "refunds", label: "Refunds" },
        ],
      },
    ]);
    expect(filterGroups(categories).map((group) => group.value)).toEqual(["shopping", "home", "income", "transfer"]);
  });
});
```

Run: `cd apps/web && npm test`
Expected: FAIL, `Failed to resolve import "./pickers"`.

- [ ] **Step 2: Implement `pickers.ts`**

Create `apps/web/src/lib/pickers.ts`:

```ts
/** Category pickers follow the money's direction (spec 7.3). A refund is money in with the
 * purchase's expense category (spec 2.2), so money in must still offer the expense categories. */

import type { Schemas } from "./api";
import { label } from "./labels";
import type { TxType } from "./params";

type Category = Schemas["CategoryOut"];

export type Direction = "in" | "out";
export type PickerGroup = { value: string; label: string; items: Category[] };

/** Money out when any row goes out: a merchant item with purchases and refunds is labelled as a
 * purchase, and its refunds take the same category. */
export const directionOf = (amounts: (string | number)[]): Direction =>
  amounts.some((amount) => Number(amount) < 0) ? "out" : "in";

/** Money out never takes an income category (the API answers 422); money in takes any, because
 * a refund keeps its purchase's category. /review drops a jev suggestion that does not fit. */
export function fitsDirection(slug: string, categories: Category[], direction: Direction): boolean {
  const category = categories.find((c) => c.slug === slug);
  return category !== undefined && (direction === "in" || category.tx_type !== "income");
}

export function byLevel1(categories: Category[]): PickerGroup[] {
  const groups = new Map<string, Category[]>();
  for (const category of categories) groups.set(category.level1, [...(groups.get(category.level1) ?? []), category]);
  return [...groups].map(([value, items]) => ({ value, label: label(value), items }));
}

/** Money out: expense groups, then transfers. Money in: income first, then every expense category
 * as "Refund of a purchase", then transfers. Suggestions (jev's top scores) come first when they
 * fit the direction. */
export function pickerGroups(categories: Category[], direction: Direction, suggested: string[] = []): PickerGroup[] {
  const of = (type: string) => categories.filter((category) => category.tx_type === type);
  const main =
    direction === "out"
      ? [...byLevel1(of("expense")), ...byLevel1(of("transfer"))]
      : [
          ...byLevel1(of("income")),
          { value: "refund", label: "Refund of a purchase", items: of("expense") },
          ...byLevel1(of("transfer")),
        ];
  const allowed = new Map(main.flatMap((group) => group.items).map((category) => [category.slug, category]));
  const top = suggested.flatMap((slug) => allowed.get(slug) ?? []);
  return top.length ? [{ value: "suggested", label: "Suggested", items: top }, ...main] : main;
}

export type FilterOption = { kind: "group" | "category"; value: string; label: string };
export type FilterGroup = { value: string; label: string; items: FilterOption[] };

/** The explorer's "group or category" filter follows its type filter; each group starts with
 * "All of <group>". */
export function filterGroups(categories: Category[], txType?: TxType): FilterGroup[] {
  const shown = txType ? categories.filter((category) => category.tx_type === txType) : categories;
  return byLevel1(shown).map((group) => ({
    value: group.value,
    label: group.label,
    items: [
      { kind: "group", value: group.value, label: `All of ${group.label}` },
      ...group.items.map((category): FilterOption => ({ kind: "category", value: category.slug, label: label(category.slug) })),
    ],
  }));
}
```

Run: `cd apps/web && npm test`
Expected: PASS.

- [ ] **Step 3: Move the pickers and make them direction-aware**

```bash
mkdir -p apps/web/src/components/pickers
git mv apps/web/src/app/review/category-picker.tsx apps/web/src/components/pickers/category-picker.tsx
git mv apps/web/src/app/review/merchant-picker.tsx apps/web/src/components/pickers/merchant-picker.tsx
```

Replace `apps/web/src/components/pickers/category-picker.tsx` with:

```tsx
"use client";

import {
  Combobox,
  ComboboxCollection,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxGroup,
  ComboboxInput,
  ComboboxItem,
  ComboboxLabel,
  ComboboxList,
} from "@/components/ui/combobox";
import type { Schemas } from "@/lib/api";
import { label } from "@/lib/labels";
import { pickerGroups, type Direction, type PickerGroup } from "@/lib/pickers";

type Category = Schemas["CategoryOut"];

type Props = {
  categories: Category[];
  direction: Direction;
  suggested?: string[];
  value: string;
  onChange: (slug: string) => void;
  id?: string;
  ariaLabel?: string;
};

/** A category picker that follows the money's direction (spec 7.3), used by /review, the
 * explorer's side panel and nothing else: the explorer's filter has its own (CategoryFilter). */
export function CategoryPicker({ categories, direction, suggested = [], value, onChange, id, ariaLabel = "Category" }: Props) {
  const bySlug = new Map(categories.map((category) => [category.slug, category]));
  return (
    <Combobox
      items={pickerGroups(categories, direction, suggested)}
      value={bySlug.get(value) ?? null}
      onValueChange={(category: Category | null) => category && onChange(category.slug)}
      itemToStringLabel={(category: Category) => label(category.slug)}
    >
      <ComboboxInput id={id} placeholder="Category" aria-label={ariaLabel} className="w-full" />
      <ComboboxContent>
        <ComboboxEmpty>No category found.</ComboboxEmpty>
        <ComboboxList>
          {(group: PickerGroup) => (
            <ComboboxGroup key={group.value} items={group.items}>
              <ComboboxLabel>{group.label}</ComboboxLabel>
              <ComboboxCollection>
                {(category: Category) => (
                  <ComboboxItem key={`${group.value}-${category.slug}`} value={category}>
                    {label(category.slug)}
                  </ComboboxItem>
                )}
              </ComboboxCollection>
            </ComboboxGroup>
          )}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  );
}
```

Replace `apps/web/src/components/pickers/merchant-picker.tsx` with:

```tsx
"use client";

import { useState } from "react";

import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxInput,
  ComboboxItem,
  ComboboxList,
} from "@/components/ui/combobox";
import type { Schemas } from "@/lib/api";

/** An existing merchant (id) or a new name typed by the user (id null). */
export type MerchantChoice = { id: string | null; name: string };

type Props = {
  merchants: Schemas["MerchantOut"][];
  value: MerchantChoice | null;
  onChange: (merchant: MerchantChoice | null) => void;
  /** A label may create a merchant from a typed name; a filter only picks existing ones. */
  allowCreate?: boolean;
  showClear?: boolean;
  id?: string;
  ariaLabel?: string;
};

export function MerchantPicker({
  merchants,
  value,
  onChange,
  allowCreate = true,
  showClear = false,
  id,
  ariaLabel = "Merchant",
}: Props) {
  const [query, setQuery] = useState(value?.name ?? "");
  // The value can change from outside (Merge picks the suggested merchant): show its name.
  const [shownName, setShownName] = useState(value?.name);
  if (value?.name !== shownName) {
    setShownName(value?.name);
    setQuery(value?.name ?? "");
  }
  const typed = query.trim();
  const exists = merchants.some((m) => m.name.toLowerCase() === typed.toLowerCase());
  const items: MerchantChoice[] = [
    ...merchants.map((m) => ({ id: m.id, name: m.name })),
    ...(allowCreate && typed && !exists ? [{ id: null, name: typed }] : []),
  ];

  return (
    <Combobox
      items={items}
      value={value}
      onValueChange={(merchant: MerchantChoice | null) => onChange(merchant)}
      inputValue={query}
      onInputValueChange={setQuery}
      itemToStringLabel={(merchant: MerchantChoice) => merchant.name}
      isItemEqualToValue={(a: MerchantChoice, b: MerchantChoice) => a.id === b.id && a.name === b.name}
    >
      <ComboboxInput id={id} placeholder="Merchant" aria-label={ariaLabel} showClear={showClear} className="w-full" />
      <ComboboxContent>
        <ComboboxEmpty>No merchant found.</ComboboxEmpty>
        <ComboboxList>
          {(merchant: MerchantChoice) => (
            <ComboboxItem key={merchant.id ?? `new-${merchant.name}`} value={merchant}>
              {merchant.id ? merchant.name : `Create "${merchant.name}"`}
            </ComboboxItem>
          )}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  );
}
```

- [ ] **Step 4: The review row — pickers, descriptions and the restyle**

Replace `apps/web/src/app/review/review-row.tsx` with:

```tsx
"use client";

import { ArrowDownLeft, ArrowUpRight, Check, ChevronRight } from "lucide-react";
import { useState } from "react";

import { CategoryPicker } from "@/components/pickers/category-picker";
import { MerchantPicker, type MerchantChoice } from "@/components/pickers/merchant-picker";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import type { Schemas } from "@/lib/api";
import { dayLong, signedMoney } from "@/lib/format";
import { label } from "@/lib/labels";
import { directionOf, fitsDirection } from "@/lib/pickers";
import { cn } from "@/lib/utils";

type Item = Schemas["ReviewItem"];
type Transaction = Schemas["ReviewTransaction"];

export type Decision = { categorySlug: string; isSubscription: boolean; merchant: MerchantChoice | null };

type Props = {
  item: Item;
  categories: Schemas["CategoryOut"][];
  merchants: Schemas["MerchantOut"][];
  onConfirm: (decision: Decision) => void;
  onLabelOne: (tx: Transaction, decision: Decision) => void;
  onDismissMerge: () => void;
};

export function ReviewRow({ item, categories, merchants, onConfirm, onLabelOne, onDismissMerge }: Props) {
  const { suggestion, merge } = item;
  const direction = directionOf(item.transactions.map((t) => t.amount));
  // Decision H: a jev suggestion that does not fit the direction (income on money out) is dropped.
  const suggested = suggestion.category_slug ?? "";
  const [categorySlug, setCategorySlug] = useState(fitsDirection(suggested, categories, direction) ? suggested : "");
  const [isSubscription, setIsSubscription] = useState(suggestion.is_subscription);
  const [merchant, setMerchant] = useState<MerchantChoice | null>(item.merchant ?? null);
  const [open, setOpen] = useState(false);
  const level1 = categories.find((c) => c.slug === categorySlug)?.level1;
  const showConfidence = categorySlug === suggestion.category_slug && suggestion.confidence != null;
  const single = item.count < 2 ? item.transactions[0] : null;
  // Merge only picks the suggested merchant: confirming then merges and sets the category in one request.
  const mergePicked = merge != null && merchant?.id === merge.merchant_id;
  const incoming = item.transactions.some((t) => Number(t.amount) > 0);
  const outgoing = item.transactions.some((t) => Number(t.amount) < 0);
  const description = item.transactions[0].description_raw;

  return (
    <li className="flex flex-col gap-3 rounded-card bg-card p-4">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        disabled={item.count < 2}
        className="flex min-w-0 items-center gap-2 text-left text-sm text-muted-foreground"
      >
        <ChevronRight className={cn("size-4 shrink-0 transition-transform", open && "rotate-90", item.count < 2 && "invisible")} />
        <Direction incoming={incoming} outgoing={outgoing} />
        {single && (
          <span className="shrink-0">
            {dayLong(single.booked_at)}
            {/* On phones the account would push the amount off the row. */}
            <span className="hidden sm:inline"> · {single.account_name}</span>
          </span>
        )}
        {/* Two lines and a title, so the bank text can always be read on a phone (dogfood issue 003). */}
        <span className="line-clamp-2 min-w-0 break-words" title={description}>
          {description}
        </span>
        {item.count > 1 && <span className="shrink-0">×{item.count}</span>}
        <Amount value={Number(item.total)} className="ml-auto shrink-0 font-medium" />
      </button>

      <div className="grid gap-3 md:grid-cols-[1fr_1fr_7rem_auto_auto] md:items-center">
        <MerchantPicker merchants={merchants} value={merchant} onChange={setMerchant} />
        <div className="flex items-center gap-2">
          <CategoryPicker
            categories={categories}
            direction={direction}
            suggested={suggestion.top.map((score) => score.slug)}
            value={categorySlug}
            onChange={setCategorySlug}
          />
          {showConfidence && (
            <span className="text-xs text-muted-foreground" title="jev confidence">
              ·{Math.round((suggestion.confidence ?? 0) * 100)}
            </span>
          )}
        </div>
        <span className="truncate text-sm text-muted-foreground">{level1 ? label(level1) : "—"}</span>
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <Switch checked={isSubscription} onCheckedChange={(checked) => setIsSubscription(checked)} />
          Subscription
        </label>
        {/* With several transactions, say that the answer covers all of them, not the first line. */}
        <Button
          size={single ? "icon" : "default"}
          aria-label={single ? "Confirm" : undefined}
          disabled={!categorySlug}
          onClick={() => onConfirm({ categorySlug, isSubscription, merchant })}
        >
          <Check />
          {!single && `Apply to all ${item.count}`}
        </Button>
      </div>

      {merge && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg bg-muted px-3 py-2 text-sm">
          {mergePicked ? (
            <span>
              Confirm to merge into <strong>{merge.name}</strong>.
            </span>
          ) : (
            <>
              <span>
                Same merchant as <strong>{merge.name}</strong>?
              </span>
              <Button size="sm" variant="outline" className="ml-auto" onClick={() => setMerchant({ id: merge.merchant_id, name: merge.name })}>
                Merge
              </Button>
              <Button size="sm" variant="ghost" onClick={onDismissMerge}>
                No
              </Button>
            </>
          )}
        </div>
      )}

      {open && (
        <ul className="flex flex-col divide-y border-t">
          {item.transactions.map((tx) => (
            <TransactionLine
              key={tx.id}
              tx={tx}
              categories={categories}
              initial={categorySlug}
              initialSubscription={isSubscription}
              onLabel={(decision) => onLabelOne(tx, decision)}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

function TransactionLine({
  tx,
  categories,
  initial,
  initialSubscription,
  onLabel,
}: {
  tx: Transaction;
  categories: Schemas["CategoryOut"][];
  initial: string;
  initialSubscription: boolean;
  onLabel: (decision: Decision) => void;
}) {
  const [slug, setSlug] = useState(initial);
  const [subscription, setSubscription] = useState(initialSubscription);
  return (
    <li className="grid gap-2 py-2 text-sm md:grid-cols-[6.5rem_minmax(0,1fr)_minmax(0,1fr)_auto_auto] md:items-center">
      <span className="text-muted-foreground">{dayLong(tx.booked_at)}</span>
      {/* Each line shows its own bank text: one merchant can carry different charges (dogfood issue 002). */}
      <span className="flex min-w-0 flex-col">
        <span className="line-clamp-2 break-words" title={tx.description_raw}>
          {tx.description_raw}
        </span>
        <span className="text-muted-foreground">
          <Amount value={Number(tx.amount)} /> · {tx.account_name}
        </span>
      </span>
      <CategoryPicker
        categories={categories}
        direction={directionOf([tx.amount])}
        value={slug}
        onChange={setSlug}
        ariaLabel="Category for this transaction"
      />
      <Switch
        checked={subscription && Number(tx.amount) < 0}
        disabled={Number(tx.amount) > 0}
        onCheckedChange={(checked) => setSubscription(checked)}
        aria-label="Subscription"
      />
      <Button
        size="sm"
        variant="outline"
        disabled={!slug}
        onClick={() => onLabel({ categorySlug: slug, isSubscription: subscription, merchant: null })}
      >
        <Check data-icon="inline-start" />
        Only this one
      </Button>
    </li>
  );
}

/** Money in or out at a glance, beyond the sign: a refund must not read as a purchase. */
function Direction({ incoming, outgoing }: { incoming: boolean; outgoing: boolean }) {
  if (incoming && outgoing) return <Badge variant="outline">Money in and out</Badge>;
  return incoming ? (
    <Badge variant="outline" className="text-income">
      <ArrowDownLeft />
      Money in
    </Badge>
  ) : (
    <Badge variant="outline">
      <ArrowUpRight />
      Money out
    </Badge>
  );
}

function Amount({ value, className }: { value: number; className?: string }) {
  return <span className={cn("text-foreground", value > 0 && "text-income", className)}>{signedMoney(value)}</span>;
}
```

- [ ] **Step 5: The review list — the survivor's item and the hint**

In `apps/web/src/app/review/review-list.tsx`:

Add `import { plural } from "@/lib/labels";` after the `@/lib/api` import.

Replace the whole `schedule` function with:

```tsx
  function schedule(
    original: Item,
    next: Item | null,
    message: string,
    send: (keepalive: boolean) => Promise<void>,
    settled: Item | null = null,
  ) {
    // A new change on the same row sends the earlier one first, so Undo never restores a stale row.
    const earlier = pending.current.get(original.key);
    if (earlier) {
      clearTimeout(earlier.timer);
      earlier.commit(false);
    }
    // A merge and confirm also settles the surviving merchant's own item (inputs topic 6):
    // it leaves the page with the merged one, and Undo brings both back.
    const restore = () => {
      replace(original.key, original);
      if (settled) replace(settled.key, settled);
    };
    replace(original.key, next);
    if (settled) replace(settled.key, null);
    const id = `${original.key}:${++seq}`;
    const commit = (keepalive: boolean) => {
      pending.current.delete(original.key);
      // The toast can outlive the timer (sonner pauses on hover): no Undo once the change is sent.
      toast.dismiss(id);
      send(keepalive).then(
        // The root layout does not re-render on client navigation: refresh its badge count.
        () => router.refresh(),
        () => {
          toast.error("Could not save that change.");
          restore();
        },
      );
    };
    const timer = setTimeout(() => commit(false), UNDO_MS);
    pending.current.set(original.key, { id, timer, commit });
    toast(message, {
      id,
      duration: UNDO_MS,
      action: {
        label: "Undo",
        onClick: () => {
          if (pending.current.get(original.key)?.id !== id) return;
          clearTimeout(timer);
          pending.current.delete(original.key);
          restore();
        },
      },
    });
  }
```

Replace the merchant branch of `confirm` with:

```tsx
    if (item.kind === "merchant" && item.merchant) {
      const merchantId = item.merchant.id;
      const mergeInto = d.merchant?.id && d.merchant.id !== merchantId ? d.merchant.id : null;
      const body = {
        category_slug: d.categorySlug,
        is_subscription: d.isSubscription,
        name: d.merchant && d.merchant.id === null ? d.merchant.name : null,
        merge_into_id: mergeInto,
      };
      // Review keys merchant items "m:<merchant id>" (review_queue.build_review_items).
      const survivor = mergeInto ? (items.find((other) => other.key === `m:${mergeInto}`) ?? null) : null;
      schedule(item, null, "Confirmed", (keepalive) => apiPost(`/merchants/${merchantId}/review`, body, { keepalive }), survivor);
    } else {
```

Replace the `uncategorized > 0` paragraph with (it must not invite a second, parallel paid run):

```tsx
        {uncategorized > 0 && (
          <p className="text-sm text-muted-foreground">
            {plural(uncategorized, "transaction is", "transactions are")} not categorized yet. Each import starts a
            categorization run in the background: give it a minute and reload this page before starting another run.
            If they stay, the API console says why (&quot;jev skipped&quot; when no jev key is set).
          </p>
        )}
```

- [ ] **Step 6: Run the gate**

Run: `cd apps/web && npm run lint && npx tsc --noEmit && npm test && npm run build`
Expected: no errors, and `grep -rn "review/category-picker\|review/merchant-picker" apps/web/src` prints nothing.

- [ ] **Step 7: Check /review in the browser (R2, scratch database: confirming writes)**

1. `open "http://localhost:3001/review"`, `snapshot -i`. Expect: rows as grey cards without borders; each row's header shows the direction badge, the date for a single row, the bank text (two lines at most) and the amount, green with "+" for money in.
2. On a "Money out" row, and on a "Money in and out" merchant row (its answer covers every row), open the category picker: groups of expense categories, then "Transfer"; no "Income" group. On a "Money in" row: "Income" first, then "Refund of a purchase" (the expense categories), then "Transfer". A "Suggested" group comes first when jev scored the row. Decision H: find an item whose jev suggestion is an income category on money out or on a mixed merchant (`curl -s http://localhost:8001/review` lists each item's `suggestion.category_slug` and amounts; slugs with `tx_type` "income" come from `curl -s http://localhost:8001/categories`): its category field starts empty and its Confirm button is disabled. If the data has no such item, write "Decision H case not exercised: no such item in the data" in the task report.
3. Expand a merchant with ×2 or more: each line shows its own bank text, its amount and account, and a category picker for its own direction.
4. If a row shows "Same merchant as X?" and X also has its own row on the page: click "Merge", then confirm. Both rows leave the page; click "Undo" in the toast: both come back. Confirm again, wait 6 s, reload: both stay gone. If the data has no such pair, write "survivor case not exercised: no pair in the data" in the task report.
5. Confirm any other row: it leaves the page, the nav's Review count drops after the toast closes, and after a reload it stays gone.
6. If the page says "N transactions are not categorized yet", the text reads "Each import starts a categorization run in the background: give it a minute and reload this page before starting another run. If they stay, the API console says why ("jev skipped" when no jev key is set)." and names no CLI command.
7. `set viewport 390 844`, screenshot `task08-review-phone.png`: the bank text wraps to two lines; `get attr` of that span's `title` is the full text.
8. Screenshot `task08-review.png` at 1280 px; the surfaces and type match `04-tokens.png`. `errors`, `close`, then drop the scratch database (R2 step 5).

- [ ] **Step 8: Commit**

```bash
git add apps/web/src/lib/pickers.ts apps/web/src/lib/pickers.test.ts apps/web/src/components/pickers apps/web/src/app/review
git commit -m "feat: make the category pickers follow the money's direction and fix the review leftovers"
```

---

### Task 9: The transactions explorer — rows and filters

**Files:**
- Create: `apps/web/src/components/pickers/category-filter.tsx`, `apps/web/src/app/transactions/explorer-filters.tsx`, `apps/web/src/app/transactions/transaction-list.tsx`
- Modify: `apps/web/src/app/transactions/page.tsx` (replaced), `apps/web/src/lib/api.ts` (drop `euro` and `signedEuro`)
- Add (shadcn): `select`, `spinner`

**Interfaces:**
- Consumes: `parseFilters`, `parseExplorer`, `explorerParams`, `replaceParams`, `clearedExplorer`, `ExplorerFilters`, `TxType` (Task 1); `rangeLabel`, `signedMoney` (Task 1); `plural` (Task 2); `filterGroups`, `FilterGroup`, `FilterOption` (Task 8); `MerchantPicker` (Task 8); `TransactionTable` (Task 6).
- Produces:
  - `CategoryFilter({ categories, txType?, level1?, category?, onChange: (level1?: string, category?: string) => void })`.
  - `ExplorerFilters({ search: string, explorer: ExplorerFilters, categories, merchants })`: every change rewrites the URL (`router.push`, no scroll).
  - `TransactionList({ initial: Schemas["TransactionPage"], search: string })`: keyed by `search` in the page, so a filter change starts again from the first page. Task 10 adds `categories`, `merchants` and the side panel.

- [ ] **Step 1: Add the components**

```bash
cd apps/web && npx shadcn@latest add select spinner --dry-run
cd apps/web && npx shadcn@latest add select spinner
```

- [ ] **Step 2: The "group or category" filter**

Create `apps/web/src/components/pickers/category-filter.tsx`:

```tsx
"use client";

import {
  Combobox,
  ComboboxCollection,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxGroup,
  ComboboxInput,
  ComboboxItem,
  ComboboxLabel,
  ComboboxList,
} from "@/components/ui/combobox";
import type { Schemas } from "@/lib/api";
import type { TxType } from "@/lib/params";
import { filterGroups, type FilterGroup, type FilterOption } from "@/lib/pickers";

type Props = {
  categories: Schemas["CategoryOut"][];
  txType?: TxType;
  level1?: string;
  category?: string;
  onChange: (level1: string | undefined, category: string | undefined) => void;
};

/** "Group or category" in one picker (spec 7.3), following the type filter. */
export function CategoryFilter({ categories, txType, level1, category, onChange }: Props) {
  const groups = filterGroups(categories, txType);
  const value =
    groups
      .flatMap((group) => group.items)
      .find((option) =>
        category ? option.kind === "category" && option.value === category : option.kind === "group" && option.value === level1,
      ) ?? null;
  return (
    <Combobox
      items={groups}
      value={value}
      onValueChange={(option: FilterOption | null) =>
        onChange(option?.kind === "group" ? option.value : undefined, option?.kind === "category" ? option.value : undefined)
      }
      itemToStringLabel={(option: FilterOption) => option.label}
      isItemEqualToValue={(a: FilterOption, b: FilterOption) => a.kind === b.kind && a.value === b.value}
    >
      <ComboboxInput placeholder="Group or category" aria-label="Group or category filter" showClear className="w-full sm:w-56" />
      <ComboboxContent>
        <ComboboxEmpty>No category found.</ComboboxEmpty>
        <ComboboxList>
          {(group: FilterGroup) => (
            <ComboboxGroup key={group.value} items={group.items}>
              <ComboboxLabel>{group.label}</ComboboxLabel>
              <ComboboxCollection>
                {(option: FilterOption) => (
                  <ComboboxItem key={`${option.kind}-${option.value}`} value={option}>
                    {option.label}
                  </ComboboxItem>
                )}
              </ComboboxCollection>
            </ComboboxGroup>
          )}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  );
}
```

- [ ] **Step 3: The filters row**

Create `apps/web/src/app/transactions/explorer-filters.tsx`:

```tsx
"use client";

import { Search, SlidersHorizontal } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { FormEvent } from "react";

import { CategoryFilter } from "@/components/pickers/category-filter";
import { MerchantPicker } from "@/components/pickers/merchant-picker";
import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { InputGroup, InputGroupAddon, InputGroupInput } from "@/components/ui/input-group";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { Schemas } from "@/lib/api";
import { clearedExplorer, replaceParams, type ExplorerFilters as Explorer } from "@/lib/params";

type Props = { search: string; explorer: Explorer; categories: Schemas["CategoryOut"][]; merchants: Schemas["MerchantOut"][] };

const SUBSCRIPTION = [
  { value: null, label: "Any" },
  { value: "true", label: "Subscriptions only" },
  { value: "false", label: "Not subscriptions" },
];
const SOURCE = [
  { value: null, label: "Any" },
  { value: "rule", label: "Rule" },
  { value: "merchant", label: "Merchant" },
  { value: "jev", label: "AI (jev)" },
  { value: "user", label: "You" },
  { value: "none", label: "Pending" },
];

/** The explorer's filters (spec 7.3): search, type, group or category, merchant visible; the
 * account and period are in the top bar; subscription, source and needs review under "More
 * filters"; two saved filters. Each change rewrites the URL and the page refetches. */
export function ExplorerFilters({ search, explorer, categories, merchants }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const go = (changes: Record<string, string | undefined>) =>
    router.push(`${pathname}?${replaceParams(search, changes)}`, { scroll: false });
  const more = [explorer.is_subscription, explorer.category_source, explorer.needs_review].filter(Boolean).length;
  const merchant = merchants.find((m) => m.id === explorer.merchant_id);
  const cleared = clearedExplorer(search);

  function onSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const q = String(new FormData(event.currentTarget).get("q") ?? "").trim();
    go({ q: q || undefined });
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        {/* Keyed by the search, so "Clear filters" also empties the box. */}
        <form key={explorer.q ?? ""} role="search" onSubmit={onSearch} className="w-full sm:w-72">
          <InputGroup>
            <InputGroupAddon>
              <Search />
            </InputGroupAddon>
            <InputGroupInput
              name="q"
              defaultValue={explorer.q}
              maxLength={100}
              placeholder="Merchant, description or note"
              aria-label="Search transactions"
            />
          </InputGroup>
        </form>
        <ToggleGroup
          variant="segment"
          size="sm"
          aria-label="Type"
          value={[explorer.tx_type ?? "all"]}
          onValueChange={(value: string[]) =>
            go({ tx_type: value[0] && value[0] !== "all" ? value[0] : undefined, level1: undefined, category: undefined })
          }
        >
          <ToggleGroupItem value="all">All</ToggleGroupItem>
          <ToggleGroupItem value="expense">Expenses</ToggleGroupItem>
          <ToggleGroupItem value="income">Income</ToggleGroupItem>
          <ToggleGroupItem value="transfer">Transfers</ToggleGroupItem>
        </ToggleGroup>
        <CategoryFilter
          categories={categories}
          txType={explorer.tx_type}
          level1={explorer.level1}
          category={explorer.category}
          onChange={(level1, category) => go({ level1, category })}
        />
        <div className="w-full sm:w-56">
          <MerchantPicker
            merchants={merchants}
            value={merchant ? { id: merchant.id, name: merchant.name } : null}
            onChange={(choice) => go({ merchant_id: choice?.id ?? undefined })}
            allowCreate={false}
            showClear
            ariaLabel="Merchant filter"
          />
        </div>
        <Popover>
          <PopoverTrigger render={<Button variant="secondary" size="sm" />}>
            <SlidersHorizontal data-icon="inline-start" />
            More filters{more > 0 ? ` · ${more}` : ""}
          </PopoverTrigger>
          <PopoverContent align="start" className="w-72">
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="filter-subscription">Subscription</FieldLabel>
                <Select
                  items={SUBSCRIPTION}
                  value={explorer.is_subscription ?? null}
                  onValueChange={(value: string | null) => go({ is_subscription: value ?? undefined })}
                >
                  <SelectTrigger id="filter-subscription" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {SUBSCRIPTION.map((item) => (
                        <SelectItem key={item.label} value={item.value}>
                          {item.label}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </Field>
              <Field>
                <FieldLabel htmlFor="filter-source">Categorized by</FieldLabel>
                <Select
                  items={SOURCE}
                  value={explorer.category_source ?? null}
                  onValueChange={(value: string | null) => go({ category_source: value ?? undefined })}
                >
                  <SelectTrigger id="filter-source" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {SOURCE.map((item) => (
                        <SelectItem key={item.label} value={item.value}>
                          {item.label}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </Field>
              <Field orientation="horizontal">
                <Switch
                  id="filter-review"
                  checked={explorer.needs_review === "true"}
                  onCheckedChange={(checked) => go({ needs_review: checked ? "true" : undefined })}
                />
                <FieldLabel htmlFor="filter-review">Needs review only</FieldLabel>
              </Field>
            </FieldGroup>
          </PopoverContent>
        </Popover>
        {cleared !== search && (
          <Button variant="ghost" size="sm" render={<Link href={`${pathname}?${cleared}`} />} nativeButton={false}>
            Clear filters
          </Button>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <span id="saved-filters">Saved filters</span>
        <ToggleGroup
          variant="segment"
          size="sm"
          aria-labelledby="saved-filters"
          value={explorer.saved ? [explorer.saved] : []}
          onValueChange={(value: string[]) => go({ saved: value[0] })}
        >
          <ToggleGroupItem value="unpaired_own">Own-account transfers without a pair</ToggleGroupItem>
          <ToggleGroupItem value="refunds">Refunds</ToggleGroupItem>
        </ToggleGroup>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: The list with "Load more"**

Create `apps/web/src/app/transactions/transaction-list.tsx`:

```tsx
"use client";

import { useState } from "react";
import { toast } from "sonner";

import { TransactionTable } from "@/components/transactions/transaction-table";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Spinner } from "@/components/ui/spinner";
import { apiGet, type Schemas } from "@/lib/api";

type Props = { initial: Schemas["TransactionPage"]; search: string };

/** The explorer's rows, grouped by day, 100 at a time (spec 7.3). The next pages are fetched
 * by the browser with the page's own query plus the cursor. */
export function TransactionList({ initial, search }: Props) {
  const [items, setItems] = useState(initial.items);
  const [cursor, setCursor] = useState(initial.next_cursor);
  const [loading, setLoading] = useState(false);

  async function loadMore() {
    if (!cursor) return;
    setLoading(true);
    try {
      const params = new URLSearchParams(search);
      params.set("cursor", cursor);
      const next = await apiGet<Schemas["TransactionPage"]>(`/transactions?${params}`);
      setItems((current) => [...current, ...next.items]);
      setCursor(next.next_cursor);
    } catch {
      toast.error("Could not load more transactions.");
    } finally {
      setLoading(false);
    }
  }

  if (items.length === 0) {
    return (
      <Empty>
        <EmptyHeader>
          <EmptyTitle>No transactions match these filters</EmptyTitle>
          <EmptyDescription>Try another period, or clear the filters.</EmptyDescription>
        </EmptyHeader>
      </Empty>
    );
  }
  return (
    <>
      <Card>
        <CardContent>
          <TransactionTable items={items} showSource />
        </CardContent>
      </Card>
      <div className="flex flex-col items-center gap-2 text-sm text-muted-foreground">
        <span>
          Showing {items.length} of {initial.count}
        </span>
        {cursor && (
          <Button variant="secondary" onClick={loadMore} disabled={loading}>
            {loading && <Spinner data-icon="inline-start" />}
            Load more
          </Button>
        )}
      </div>
    </>
  );
}
```

- [ ] **Step 5: The page**

Replace `apps/web/src/app/transactions/page.tsx` with:

```tsx
import { apiGet, type Schemas } from "@/lib/api";
import { rangeLabel, signedMoney } from "@/lib/format";
import { plural } from "@/lib/labels";
import { explorerParams, parseExplorer, parseFilters } from "@/lib/params";

import { ExplorerFilters } from "./explorer-filters";
import { TransactionList } from "./transaction-list";

export const dynamic = "force-dynamic";

/** The explorer (spec 7.3): any row can be found, understood and, in Task 10, corrected. The page
 * URL and the API take the same params, so one sanitized query string serves both. */
export default async function TransactionsPage({ searchParams }: PageProps<"/transactions">) {
  const query = await searchParams;
  const explorer = parseExplorer(query);
  const search = explorerParams(parseFilters(query), explorer).toString();
  const [page, categories, merchants] = await Promise.all([
    apiGet<Schemas["TransactionPage"]>(`/transactions?${search}`),
    apiGet<Schemas["CategoryOut"][]>("/categories"),
    apiGet<Schemas["MerchantOut"][]>("/merchants?limit=5000"),
  ]);
  return (
    <>
      <header className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h1 className="text-xl font-semibold tracking-tight">Transactions</h1>
        <p className="text-sm text-muted-foreground">
          {rangeLabel(page.period)} · {plural(page.count, "transaction", "transactions")} ·{" "}
          <span className="text-income">{signedMoney(page.money_in)}</span> in · {signedMoney(-Number(page.money_out))} out
        </p>
      </header>
      <ExplorerFilters search={search} explorer={explorer} categories={categories} merchants={merchants} />
      <TransactionList key={search} initial={page} search={search} />
    </>
  );
}
```

In `apps/web/src/lib/api.ts`, delete the `euro` and `signedEuro` constants (their comment included): `format.ts` replaces them. Check nothing imports them any more:

```bash
cd apps/web && grep -rnE "\b(signedEuro|euro)\b" src --include=*.tsx --include=*.ts
```

Expected: no output.

- [ ] **Step 6: Run the gate**

Run: `cd apps/web && npm run lint && npx tsc --noEmit && npm test && npm run build`
Expected: no errors.

- [ ] **Step 7: Check the explorer in the browser (R1, read-only)**

1. `open "http://localhost:3000/transactions"`, `snapshot -i`. Expect: the h1 "Transactions" and the line "<period> · N transactions · +€… in · -€… out"; the search box "Search transactions"; the type toggles All (pressed), Expenses, Income, Transfers; "Group or category filter"; "Merchant filter"; "More filters"; the saved filters "Own-account transfers without a pair" and "Refunds". Rows are grouped under day headers such as "Wed, 26 Aug" with the day's net; each row shows the merchant (the note as a second line when there is one), "Group · Category", the account, who categorized it (Rule, Merchant, AI (jev), You or Pending) and the amount.
2. Fill the search box with a word from the first row's merchant and press Enter: the URL gains `q=…`; every row contains it in its merchant, description or note.
3. Click "Income": the URL has `tx_type=income`; every amount is green with "+". Open the group or category filter: it lists only income groups, each starting with "All of …". Pick one: the URL gains `level1=` or `category=`.
4. Pick a merchant in the merchant filter: `merchant_id=` in the URL, every row is that merchant. Clear it with the × button.
5. "More filters" → "Categorized by" → "AI (jev)": `category_source=jev`, and every row reads "AI (jev)"; the trigger reads "More filters · 1".
6. Saved filter "Refunds": `saved=refunds`; every row is money in with an expense category. "Own-account transfers without a pair": `saved=unpaired_own`.
7. "Clear filters": every explorer param is gone, and the period and account params stay.
8. Paging: choose "Last 12 months". If the count is above 100, click "Load more": "Showing 200 of N", and `eval "(() => { const d = [...document.querySelectorAll('tr[data-day]')].map(r => r.dataset.day); return d.length === new Set(d).size })()"` prints `true` (no day header twice, Review Focus 4).
9. Bad URLs: `open "http://localhost:3000/transactions?tx_type=loan&q=$(printf 'x%.0s' {1..150})&account_id=42"`: the page renders without an error; the search box holds 100 characters.
10. Screenshot `task09-explorer.png` and compare the rows with the transaction card of `03-group-page.png`. `errors`, `close`.

- [ ] **Step 8: Commit**

```bash
git add apps/web/src/components/pickers/category-filter.tsx apps/web/src/components/ui apps/web/src/app/transactions apps/web/src/lib/api.ts apps/web/package.json apps/web/package-lock.json
git commit -m "feat: add the transactions explorer with search, filters, saved filters and paging"
```

---

### Task 10: The explorer's side panel

**Files:**
- Create: `apps/web/src/app/transactions/transaction-panel.tsx`
- Modify: `apps/web/src/lib/api.ts` (write helpers, `ApiError`), `apps/web/src/lib/transactions.ts` (`applyChange`), `apps/web/src/app/transactions/transaction-list.tsx`, `apps/web/src/app/transactions/page.tsx`
- Add (shadcn): `sheet`, `alert-dialog`
- Test: `apps/web/src/lib/transactions.test.ts`

**Interfaces:**
- Consumes: `CategoryPicker`, `MerchantPicker`, `MerchantChoice`, `Direction` (Task 8); `TransactionTable` (Task 6); `dayLong`, `signedMoney` (Task 1); `label` (Task 2); the 3a endpoints `PATCH /transactions/{id}` (`{ note }`, 204; `note` is required, a string or null, and `{}` is a 422), `POST /transactions/{id}/label` (`LabelTransaction`, 204; 422 when money out gets an income category), `POST /merchants/{id}/review` (`ConfirmMerchant`, 204; an income category relabels only the money-in rows, and the money-out rows keep theirs) and `DELETE /merchants/{id}/default` (204).
- Produces:
  - `api.ts`: `ApiError` (`status`, `detail: string | null`); `apiPost(path, body?, { keepalive? })` (unchanged signature); `apiPatch<T = void>(path, body): Promise<T>`; `apiDelete(path): Promise<void>`.
  - `transactions.ts`: `LabelChange = { id: string; categorySlug: string | null; isSubscription: boolean; merchant: MerchantChoice | null; note: string | null; defaultFor: string | null }`; `applyChange(rows, change, categories): Transaction[]`.
  - `TransactionPanel({ tx: Transaction | null, categories, merchants, onClose, onSaved: (change: LabelChange) => void })`.
  - `TransactionList({ initial, search, categories, merchants })`.

- [ ] **Step 1: Write the failing tests**

In `apps/web/src/lib/transactions.test.ts`, change the import to `import { applyChange, groupByDay } from "./transactions";` and append:

```ts
const categories: Schemas["CategoryOut"][] = [
  { slug: "fashion", tx_type: "expense", level1: "shopping" },
  { slug: "salary", tx_type: "income", level1: "income" },
];

describe("applyChange", () => {
  it("labels the edited row as the user's and keeps its note", () => {
    const [row] = applyChange(
      [tx("1", "2026-08-26", "-51.00", { merchant_id: "m", merchant_name: "ZZTEST ACME" })],
      { id: "1", categorySlug: "fashion", isSubscription: true, merchant: null, note: "AirPods case", defaultFor: null },
      categories,
    );
    expect(row).toMatchObject({
      category_slug: "fashion",
      level1: "shopping",
      tx_type: "expense",
      category_source: "user",
      is_subscription: true,
      needs_review: false,
      note: "AirPods case",
      merchant_id: "m",
    });
  });

  it("gives the merchant's other rows its new default, except the ones the user or a rule labelled", () => {
    const rows = [
      tx("1", "2026-08-26", "-1.00", { merchant_id: "m" }),
      tx("2", "2026-08-26", "-2.00", { merchant_id: "m", category_source: "jev" }),
      tx("3", "2026-08-26", "-3.00", { merchant_id: "m", category_source: "user", category_slug: "salary" }),
      tx("4", "2026-08-26", "-4.00", { merchant_id: "m", category_source: "rule" }),
      tx("5", "2026-08-26", "-5.00", { merchant_id: "x", category_source: "jev" }),
    ];
    const out = applyChange(
      rows,
      { id: "1", categorySlug: "fashion", isSubscription: false, merchant: null, note: null, defaultFor: "m" },
      categories,
    );
    expect(out.map((row) => [row.id, row.category_source, row.category_slug])).toEqual([
      ["1", "user", "fashion"],
      ["2", "merchant", "fashion"],
      ["3", "user", "salary"],
      ["4", "rule", null],
      ["5", "jev", null],
    ]);
  });

  it("leaves the merchant's money out alone when its new default is income", () => {
    const rows = [
      tx("1", "2026-08-26", "100.00", { merchant_id: "m" }),
      tx("2", "2026-08-26", "100.00", { merchant_id: "m", category_source: "jev" }),
      tx("3", "2026-08-26", "-10.00", { merchant_id: "m", category_source: "jev" }),
    ];
    const out = applyChange(
      rows,
      { id: "1", categorySlug: "salary", isSubscription: false, merchant: null, note: null, defaultFor: "m" },
      categories,
    );
    expect(out.map((row) => [row.id, row.category_source, row.category_slug])).toEqual([
      ["1", "user", "salary"],
      ["2", "merchant", "salary"],
      ["3", "jev", null],
    ]);
  });

  it("never makes money in a subscription, and a note-only change keeps the label", () => {
    const [refund] = applyChange(
      [tx("1", "2026-08-26", "80.00")],
      { id: "1", categorySlug: "fashion", isSubscription: true, merchant: null, note: null, defaultFor: null },
      categories,
    );
    expect(refund).toMatchObject({ tx_type: "expense", is_subscription: false });
    const [noted] = applyChange(
      [tx("1", "2026-08-26", "-5.00", { category_slug: "fashion", level1: "shopping", category_source: "jev" })],
      { id: "1", categorySlug: null, isSubscription: false, merchant: null, note: "gift", defaultFor: null },
      categories,
    );
    expect(noted).toMatchObject({ category_slug: "fashion", category_source: "jev", note: "gift" });
  });

  it("moves the row to a newly named merchant without inventing its id", () => {
    const [row] = applyChange(
      [tx("1", "2026-08-26", "-9.00", { merchant_id: "old" })],
      { id: "1", categorySlug: "fashion", isSubscription: false, merchant: { id: null, name: "ZZTEST NEW" }, note: null, defaultFor: null },
      categories,
    );
    expect(row).toMatchObject({ merchant_id: null, merchant_name: "ZZTEST NEW" });
  });
});
```

Run: `cd apps/web && npm test`
Expected: FAIL, `applyChange` is not exported.

- [ ] **Step 2: Implement `applyChange`**

Append to `apps/web/src/lib/transactions.ts` (and add `Category` next to `Tx` at the top: `type Category = Schemas["CategoryOut"];`):

```ts
/** What the side panel saved (spec 7.3). `categorySlug` is null when only the note changed;
 * `merchant` is set when the merchant changed; `defaultFor` is the merchant whose default the
 * change became ("Apply to all transactions of this merchant?" → yes). */
export type LabelChange = {
  id: string;
  categorySlug: string | null;
  isSubscription: boolean;
  merchant: { id: string | null; name: string } | null;
  note: string | null;
  defaultFor: string | null;
};

// labels._RELABEL_MERCHANT in the API: a merchant default relabels these sources only, so the
// user's own labels and the system rules keep theirs, and it never gives money going out an
// income category (those rows keep theirs too).
const FOLLOW_THE_MERCHANT = ["jev", "merchant", "none"];

/** The loaded rows after a save, patched in place so "Load more" pages are not lost. */
export function applyChange(rows: Tx[], change: LabelChange, categories: Category[]): Tx[] {
  const category = categories.find((c) => c.slug === change.categorySlug);
  const labelled = (row: Tx, source: Tx["category_source"]): Tx =>
    category
      ? {
          ...row,
          category_slug: category.slug,
          level1: category.level1,
          // CategoryOut.tx_type is a plain string; Transaction.tx_type is typed.
          tx_type: category.tx_type as Tx["tx_type"],
          category_source: source,
          needs_review: false,
          // Only money going out is a subscription (spec 6).
          is_subscription: change.isSubscription && category.tx_type === "expense" && Number(row.amount) < 0,
        }
      : row;
  return rows.map((row) => {
    if (row.id === change.id) {
      // A new merchant's id comes back only on reload, so it stays null here.
      const merchant = change.merchant ? { merchant_id: change.merchant.id, merchant_name: change.merchant.name } : {};
      return { ...labelled(row, "user"), ...merchant, note: change.note };
    }
    const fits = !(Number(row.amount) < 0 && category?.tx_type === "income");
    if (change.defaultFor && row.merchant_id === change.defaultFor && FOLLOW_THE_MERCHANT.includes(row.category_source) && fits) {
      return labelled(row, "merchant");
    }
    return row;
  });
}
```

Run: `cd apps/web && npm test`
Expected: PASS.

- [ ] **Step 3: The write helpers**

In `apps/web/src/lib/api.ts`, replace the `apiPost` function with:

```ts
/** A failed write: the HTTP status, and FastAPI's `detail` when it is a sentence (for example
 * the 422 for an income category on money going out). */
export class ApiError extends Error {
  status: number;
  detail: string | null;

  constructor(status: number, detail: string | null, message: string) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function send<T>(method: "POST" | "PATCH" | "DELETE", path: string, body?: unknown, keepalive?: boolean): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    keepalive,
  });
  if (!response.ok) {
    const detail = await response.json().then(
      (json: { detail?: unknown }) => (typeof json.detail === "string" ? json.detail : null),
      () => null,
    );
    throw new ApiError(response.status, detail, `${method} ${path} failed with ${response.status}`);
  }
  return (response.status === 204 ? undefined : await response.json()) as T;
}

export const apiPost = (path: string, body?: unknown, init: { keepalive?: boolean } = {}) =>
  send<void>("POST", path, body, init.keepalive);
export const apiPatch = <T = void>(path: string, body: unknown) => send<T>("PATCH", path, body);
export const apiDelete = (path: string) => send<void>("DELETE", path);
```

- [ ] **Step 4: The panel**

```bash
cd apps/web && npx shadcn@latest add sheet alert-dialog --dry-run
cd apps/web && npx shadcn@latest add sheet alert-dialog
```

Create `apps/web/src/app/transactions/transaction-panel.tsx`:

```tsx
"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { CategoryPicker } from "@/components/pickers/category-picker";
import { MerchantPicker, type MerchantChoice } from "@/components/pickers/merchant-picker";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Field, FieldContent, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, apiDelete, apiPatch, apiPost, type Schemas } from "@/lib/api";
import { dayLong, signedMoney } from "@/lib/format";
import { label } from "@/lib/labels";
import type { Direction } from "@/lib/pickers";
import type { LabelChange } from "@/lib/transactions";
import { cn } from "@/lib/utils";

type Tx = Schemas["Transaction"];

type Props = {
  tx: Tx | null;
  categories: Schemas["CategoryOut"][];
  merchants: Schemas["MerchantOut"][];
  onClose: () => void;
  onSaved: (change: LabelChange) => void;
};

const NOTE_MAX = 500; // transactions.note: char_length(note) <= 500

/** The side panel (spec 7.3): the category, merchant, subscription flag and note of one row. */
export function TransactionPanel({ tx, categories, merchants, onClose, onSaved }: Props) {
  return (
    <Sheet
      open={tx !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <SheetContent className="data-[side=right]:w-full data-[side=right]:sm:max-w-md">
        {tx && <PanelForm key={tx.id} tx={tx} categories={categories} merchants={merchants} onClose={onClose} onSaved={onSaved} />}
      </SheetContent>
    </Sheet>
  );
}

function PanelForm({ tx, categories, merchants, onClose, onSaved }: Omit<Props, "tx"> & { tx: Tx }) {
  const router = useRouter();
  const amount = Number(tx.amount);
  const direction: Direction = amount < 0 ? "out" : "in";
  const [categorySlug, setCategorySlug] = useState(tx.category_slug ?? "");
  const [merchant, setMerchant] = useState<MerchantChoice | null>(
    tx.merchant_id ? { id: tx.merchant_id, name: tx.merchant_name ?? "" } : null,
  );
  const [isSubscription, setIsSubscription] = useState(tx.is_subscription);
  const [note, setNote] = useState(tx.note ?? "");
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);

  const category = categories.find((c) => c.slug === categorySlug);
  const canSubscribe = direction === "out" && category?.tx_type === "expense";
  const merchantChanged = merchant !== null && (merchant.id === null || merchant.id !== tx.merchant_id);
  const labelChanged = categorySlug !== (tx.category_slug ?? "") || isSubscription !== tx.is_subscription || merchantChanged;
  const noteChanged = note.trim() !== (tx.note ?? "");
  const name = tx.merchant_name ?? tx.bank_merchant_text ?? tx.description_raw;

  function onSave() {
    // Only an existing merchant can take a default; a new name is created by this label alone.
    if (labelChanged && merchant?.id) setAsking(true);
    else void save(false);
  }

  async function save(toMerchant: boolean) {
    setBusy(true);
    try {
      const finalNote = note.trim() || null;
      const subscription = isSubscription && canSubscribe;
      if (noteChanged) await apiPatch(`/transactions/${tx.id}`, { note: finalNote });
      if (labelChanged) {
        await apiPost(`/transactions/${tx.id}/label`, {
          category_slug: categorySlug,
          is_subscription: subscription,
          merchant_id: merchant?.id ?? null,
          new_merchant_name: merchant && merchant.id === null ? merchant.name : null,
        });
      }
      if (toMerchant && merchant?.id) {
        // The merchant's default: its other rows (not the user's own labels) and future imports.
        await apiPost(`/merchants/${merchant.id}/review`, { category_slug: categorySlug, is_subscription: subscription });
      }
      onSaved({
        id: tx.id,
        categorySlug: labelChanged ? categorySlug : null,
        isSubscription: subscription,
        merchant: merchantChanged ? merchant : null,
        note: finalNote,
        defaultFor: toMerchant && merchant?.id ? merchant.id : null,
      });
      toast.success(toMerchant && merchant ? `Saved for every ${merchant.name} transaction` : "Saved");
      router.refresh();
      onClose();
    } catch (error) {
      toast.error(error instanceof ApiError && error.detail ? error.detail : "Could not save this transaction.");
    } finally {
      setBusy(false);
      setAsking(false);
    }
  }

  async function clearDefault() {
    if (!tx.merchant_id) return;
    try {
      await apiDelete(`/merchants/${tx.merchant_id}/default`);
      toast.success(`${tx.merchant_name ?? "This merchant"} has no default category now.`);
    } catch {
      toast.error("Could not clear the merchant default.");
    }
  }

  return (
    <>
      <SheetHeader>
        <SheetTitle>{name}</SheetTitle>
        <SheetDescription>
          {dayLong(tx.booked_at)} · {tx.account_name}
        </SheetDescription>
        <p className={cn("text-2xl font-semibold tracking-tight", amount > 0 && "text-income")}>{signedMoney(amount)}</p>
        <p className="text-xs break-words text-muted-foreground">{tx.description_raw}</p>
      </SheetHeader>
      <div className="flex-1 overflow-y-auto px-4">
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="panel-category">Category</FieldLabel>
            <CategoryPicker id="panel-category" categories={categories} direction={direction} value={categorySlug} onChange={setCategorySlug} />
            <FieldDescription>
              {direction === "out" ? "What this money went on." : "Income, or the category of the purchase this money refunds."}
            </FieldDescription>
          </Field>
          <Field>
            <FieldLabel htmlFor="panel-merchant">Merchant</FieldLabel>
            <MerchantPicker id="panel-merchant" merchants={merchants} value={merchant} onChange={(choice) => choice && setMerchant(choice)} />
            <FieldDescription>Who you paid or who paid you. Type a new name to create a merchant.</FieldDescription>
          </Field>
          <Field orientation="horizontal" data-disabled={!canSubscribe || undefined}>
            <Switch
              id="panel-subscription"
              checked={isSubscription && canSubscribe}
              disabled={!canSubscribe}
              onCheckedChange={(checked) => setIsSubscription(checked)}
            />
            <FieldContent>
              <FieldLabel htmlFor="panel-subscription">Subscription</FieldLabel>
              <FieldDescription>A charge that repeats, like a streaming plan. Only money going out can be one.</FieldDescription>
            </FieldContent>
          </Field>
          <Field>
            <FieldLabel htmlFor="panel-note">
              Note
              <span className="ml-auto font-normal text-muted-foreground">
                {note.length}/{NOTE_MAX}
              </span>
            </FieldLabel>
            <Textarea id="panel-note" value={note} maxLength={NOTE_MAX} onChange={(event) => setNote(event.target.value)} />
            <FieldDescription>
              What did you buy or what was it for? For example &apos;AirPods Pro&apos;. The AI uses it to answer your questions.
            </FieldDescription>
          </Field>
          {tx.merchant_id && (
            <Field>
              <Button variant="outline" size="sm" className="self-start" onClick={clearDefault} disabled={busy}>
                Clear merchant default
              </Button>
              <FieldDescription>
                For a merchant whose purchases need different categories: its transactions keep theirs, and new ones are
                categorized one by one.
              </FieldDescription>
            </Field>
          )}
        </FieldGroup>
      </div>
      <SheetFooter className="flex-row justify-end">
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
        <Button onClick={onSave} disabled={busy || (!labelChanged && !noteChanged) || (labelChanged && !categorySlug)}>
          {busy && <Spinner data-icon="inline-start" />}
          Save
        </Button>
      </SheetFooter>
      <AlertDialog open={asking} onOpenChange={setAsking}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Apply to all transactions of this merchant?</AlertDialogTitle>
            <AlertDialogDescription>
              {merchant?.name} then uses {label(categorySlug)} for its other transactions and for new imports. Transactions you
              labelled yourself keep their category.
              {category?.tx_type === "income" && " Money going out keeps its category too: it is never income."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>Back</AlertDialogCancel>
            <AlertDialogAction variant="outline" disabled={busy} onClick={() => save(false)}>
              Only this one
            </AlertDialogAction>
            <AlertDialogAction disabled={busy} onClick={() => save(true)}>
              Apply to all
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
```

- [ ] **Step 5: Open the panel from a row**

Replace `apps/web/src/app/transactions/transaction-list.tsx` with:

```tsx
"use client";

import { useState } from "react";
import { toast } from "sonner";

import { TransactionTable } from "@/components/transactions/transaction-table";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Spinner } from "@/components/ui/spinner";
import { apiGet, type Schemas } from "@/lib/api";
import { applyChange } from "@/lib/transactions";

import { TransactionPanel } from "./transaction-panel";

type Tx = Schemas["Transaction"];

type Props = {
  initial: Schemas["TransactionPage"];
  search: string;
  categories: Schemas["CategoryOut"][];
  merchants: Schemas["MerchantOut"][];
};

/** The explorer's rows, grouped by day, 100 at a time (spec 7.3); clicking a row opens the side
 * panel. The next pages are fetched by the browser with the page's own query plus the cursor. */
export function TransactionList({ initial, search, categories, merchants }: Props) {
  const [items, setItems] = useState(initial.items);
  const [cursor, setCursor] = useState(initial.next_cursor);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<Tx | null>(null);

  async function loadMore() {
    if (!cursor) return;
    setLoading(true);
    try {
      const params = new URLSearchParams(search);
      params.set("cursor", cursor);
      const next = await apiGet<Schemas["TransactionPage"]>(`/transactions?${params}`);
      setItems((current) => [...current, ...next.items]);
      setCursor(next.next_cursor);
    } catch {
      toast.error("Could not load more transactions.");
    } finally {
      setLoading(false);
    }
  }

  if (items.length === 0) {
    return (
      <Empty>
        <EmptyHeader>
          <EmptyTitle>No transactions match these filters</EmptyTitle>
          <EmptyDescription>Try another period, or clear the filters.</EmptyDescription>
        </EmptyHeader>
      </Empty>
    );
  }
  return (
    <>
      <Card>
        <CardContent>
          <TransactionTable items={items} showSource onOpen={setSelected} />
        </CardContent>
      </Card>
      <div className="flex flex-col items-center gap-2 text-sm text-muted-foreground">
        <span>
          Showing {items.length} of {initial.count}
        </span>
        {cursor && (
          <Button variant="secondary" onClick={loadMore} disabled={loading}>
            {loading && <Spinner data-icon="inline-start" />}
            Load more
          </Button>
        )}
      </div>
      <TransactionPanel
        tx={selected}
        categories={categories}
        merchants={merchants}
        onClose={() => setSelected(null)}
        onSaved={(change) => setItems((rows) => applyChange(rows, change, categories))}
      />
    </>
  );
}
```

In `apps/web/src/app/transactions/page.tsx`, pass the lists to the list:

```tsx
      <TransactionList key={search} initial={page} search={search} categories={categories} merchants={merchants} />
```

- [ ] **Step 6: Run the gate**

Run: `cd apps/web && npm run lint && npx tsc --noEmit && npm test && npm run build`
Expected: no errors.

- [ ] **Step 7: Check the panel in the browser (R2, scratch database: saving writes)**

1. `open "http://localhost:3001/transactions"`, click a money-out row with a merchant, `snapshot -i`. Expect a dialog titled with the merchant, the date and account, the signed amount, the bank text, and the fields Category, Merchant, Subscription, Note (with "0/500" or its length) and "Clear merchant default", each with its one-line description. The note field reads exactly: "What did you buy or what was it for? For example 'AirPods Pro'. The AI uses it to answer your questions."
2. The category picker of that money-out row has no "Income" group. Close with Cancel, open a money-in row: its picker starts with "Income", then "Refund of a purchase", then "Transfer"; its Subscription switch is disabled.
3. Note only: type "ZZTEST note" on a row and press Save. No dialog appears; the toast says "Saved"; the row shows the note as its second line; reload: the note is still there. Press Escape on a reopened panel: it closes and nothing changes.
4. Only this one: on a row of a merchant with several rows in the list, change the category and press Save. The dialog "Apply to all transactions of this merchant?" appears; press "Only this one". That row's source reads "You"; the merchant's other rows keep theirs.
5. Apply to all: on another row of the same merchant, change the category and choose "Apply to all". The toast says "Saved for every <merchant> transaction"; the merchant's rows whose source was AI (jev), Merchant or Pending now show the new category with the source "Merchant"; rows marked "You" keep theirs. Reload: the same.
6. "Clear merchant default": the toast says "<merchant> has no default category now."
7. Screenshot `task10-panel.png`. `errors`, `close`, then drop the scratch database (R2 step 5).

- [ ] **Step 8: Commit**

```bash
git add apps/web/src/lib/api.ts apps/web/src/lib/transactions.ts apps/web/src/lib/transactions.test.ts apps/web/src/components/ui apps/web/src/app/transactions
git commit -m "feat: edit a transaction's category, merchant, subscription and note in a side panel"
```

---

### Task 11: Subscriptions

**Files:**
- Create: `apps/web/src/app/subscriptions/page.tsx`

**Interfaces:**
- Consumes: `GET /dashboard/subscriptions` → `Schemas["Subscriptions"]` (`items: SubscriptionOut[]`, `monthly_total`, `yearly_total`); `money`, `dayLong` (Task 1).
- Produces: the route `/subscriptions`.

- [ ] **Step 1: The page**

Create `apps/web/src/app/subscriptions/page.tsx`:

```tsx
import { Repeat } from "lucide-react";
import Link from "next/link";

import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiGet, type Schemas } from "@/lib/api";
import { dayLong, money } from "@/lib/format";

export const dynamic = "force-dynamic";

const CADENCE: Record<string, string> = { monthly: "Monthly", yearly: "Yearly" };

/** Every active subscription with its amount, cadence, monthly equivalent and last charge, and
 * the monthly and yearly totals (spec 7.1). "Active" is relative to the latest import. */
export default async function SubscriptionsPage() {
  const { items, monthly_total, yearly_total } = await apiGet<Schemas["Subscriptions"]>("/dashboard/subscriptions");
  return (
    <>
      <header className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold tracking-tight">Subscriptions</h1>
        <p className="max-w-prose text-sm text-muted-foreground">
          Charges you marked as subscriptions that are still running: charged within 45 days (monthly) or 400 days
          (yearly) of your latest imported transaction. A subscription charged only once counts as monthly until its
          second charge. Subscriptions paid by credit card do not appear, because card statements are not imported.
        </p>
      </header>
      <section aria-label="Totals" className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Total label="Active" value={String(items.length)} />
        <Total label="Per month" value={money(monthly_total)} />
        <Total label="Per year" value={money(yearly_total)} />
      </section>
      {items.length === 0 ? (
        <Empty>
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <Repeat />
            </EmptyMedia>
            <EmptyTitle>No active subscriptions</EmptyTitle>
            <EmptyDescription>
              Mark a charge as a subscription in Transactions or Review, and it shows here with its cadence and cost.
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : (
        <Card>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>Merchant</TableHead>
                  <TableHead>Cadence</TableHead>
                  <TableHead className="text-right">Amount</TableHead>
                  <TableHead className="text-right">Per month</TableHead>
                  <TableHead className="text-right">Last charge</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item) => (
                  <TableRow key={item.merchant_id}>
                    <TableCell className="font-medium">
                      <Link href={`/merchants/${item.merchant_id}`} className="hover:underline">
                        {item.merchant_name}
                      </Link>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{CADENCE[item.cadence] ?? item.cadence}</TableCell>
                    <TableCell className="text-right">{money(item.typical_amount)}</TableCell>
                    <TableCell className="text-right font-semibold">{money(item.monthly_equivalent)}</TableCell>
                    <TableCell className="text-right text-muted-foreground">{dayLong(item.last_charge)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </>
  );
}

function Total({ label, value }: { label: string; value: string }) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardDescription className="text-xs tracking-wide uppercase">{label}</CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-2xl font-semibold tracking-tight">{value}</p>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: Run the gate**

Run: `cd apps/web && npm run lint && npx tsc --noEmit && npm test && npm run build`
Expected: no errors.

- [ ] **Step 3: Check the page in the browser (R1, read-only)**

1. `open "http://localhost:3000/subscriptions"`, `snapshot -i`. Expect: the nav "Subscriptions" with `aria-current="page"` and no filter pills; the explanation paragraph; three tiles Active, Per month, Per year; a table with Merchant (links to `/merchants/<id>`), Cadence (Monthly or Yearly), Amount, Per month and Last charge; or the empty state "No active subscriptions".
2. The numbers agree with the overview: `open "http://localhost:3000/"` and compare its subscriptions line (count, per month, per year) with the three tiles. The explanation says that a subscription charged only once counts as monthly until its second charge (`docs/money-rules.md`, "Subscriptions").
3. Click a merchant: its page opens.
4. Screenshot `task11-subscriptions.png`; check the tokens against `04-tokens.png` (surfaces, type, one accent). `errors`, `close`.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/app/subscriptions
git commit -m "feat: add the subscriptions page"
```

---

### Task 12: Settings

**Files:**
- Create: `apps/web/src/app/settings/page.tsx`, `apps/web/src/app/settings/account-name-form.tsx`

**Interfaces:**
- Consumes: `GET /accounts` → `Schemas["Account"][]`; `PATCH /accounts/{id}` (`AccountUpdate { name }`, 1-80 characters) → `Schemas["Account"]`; `GET /categories`; `apiPatch` (Task 10); `byLevel1` (Task 8); `label` (Task 2).
- Produces: the route `/settings`.

- [ ] **Step 1: The rename form**

Create `apps/web/src/app/settings/account-name-form.tsx`:

```tsx
"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { apiPatch, type Schemas } from "@/lib/api";

const NAME_MAX = 80; // AccountUpdate.name: 1-80 characters

/** Rename one account (the existing PATCH /accounts/{id}, spec 7.1). */
export function AccountNameForm({ account }: { account: Schemas["Account"] }) {
  const router = useRouter();
  const [name, setName] = useState(account.name);
  const [saved, setSaved] = useState(account.name);
  const [busy, setBusy] = useState(false);
  const trimmed = name.trim();
  const id = `account-${account.id}`;

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    try {
      const updated = await apiPatch<Schemas["Account"]>(`/accounts/${account.id}`, { name: trimmed });
      setSaved(updated.name);
      setName(updated.name);
      toast.success("Account renamed");
      // The top bar's account picker reads the names in the root layout.
      router.refresh();
    } catch {
      toast.error("Could not rename the account.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit}>
      <Field>
        <FieldLabel htmlFor={id}>
          {account.bank.toUpperCase()} ··{account.iban_last4}
        </FieldLabel>
        <div className="flex gap-2">
          <Input id={id} value={name} maxLength={NAME_MAX} onChange={(event) => setName(event.target.value)} />
          <Button type="submit" variant="outline" disabled={busy || !trimmed || trimmed === saved}>
            {busy && <Spinner data-icon="inline-start" />}
            Save
          </Button>
        </div>
        <FieldDescription>The name shown in lists and in the account filter, for example &quot;Joint account&quot;.</FieldDescription>
      </Field>
    </form>
  );
}
```

- [ ] **Step 2: The page**

Create `apps/web/src/app/settings/page.tsx`:

```tsx
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FieldGroup } from "@/components/ui/field";
import { apiGet, type Schemas } from "@/lib/api";
import { label } from "@/lib/labels";
import { byLevel1 } from "@/lib/pickers";

import { AccountNameForm } from "./account-name-form";

export const dynamic = "force-dynamic";

const TYPES = [
  { type: "expense", title: "Expenses" },
  { type: "income", title: "Income" },
  { type: "transfer", title: "Transfers (out of every total)" },
] as const;

/** Rename accounts; the categories are read-only in slice 3 (spec 7.1). */
export default async function SettingsPage() {
  const [accounts, categories] = await Promise.all([
    apiGet<Schemas["Account"][]>("/accounts"),
    apiGet<Schemas["CategoryOut"][]>("/categories"),
  ]);
  return (
    <>
      <h1 className="text-xl font-semibold tracking-tight">Settings</h1>
      <Card>
        <CardHeader>
          <CardTitle>Accounts</CardTitle>
          <CardDescription>Give each account a name you recognize.</CardDescription>
        </CardHeader>
        <CardContent>
          {accounts.length === 0 ? (
            <p className="text-sm text-muted-foreground">No accounts yet: import a statement first.</p>
          ) : (
            <FieldGroup>
              {accounts.map((account) => (
                <AccountNameForm key={account.id} account={account} />
              ))}
            </FieldGroup>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Categories</CardTitle>
          <CardDescription>
            Read-only in this version. A refund takes the category of its purchase; transfers never count as income or
            spending.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          {TYPES.map(({ type, title }) => (
            <section key={type} className="flex flex-col gap-3">
              <h2 className="text-sm font-medium">{title}</h2>
              <dl className="grid gap-4 sm:grid-cols-2">
                {byLevel1(categories.filter((category) => category.tx_type === type)).map((group) => (
                  <div key={group.value} className="flex flex-col gap-1.5">
                    <dt className="text-xs tracking-wide text-muted-foreground uppercase">{group.label}</dt>
                    <dd className="flex flex-wrap gap-1">
                      {group.items.map((category) => (
                        <Badge key={category.slug} variant="outline">
                          {label(category.slug)}
                        </Badge>
                      ))}
                    </dd>
                  </div>
                ))}
              </dl>
            </section>
          ))}
        </CardContent>
      </Card>
    </>
  );
}
```

- [ ] **Step 3: Run the gate**

Run: `cd apps/web && npm run lint && npx tsc --noEmit && npm test && npm run build`
Expected: no errors.

- [ ] **Step 4: Check the page in the browser (R2, scratch database: renaming writes)**

1. `open "http://localhost:3001/settings"`, `snapshot -i`. Expect: the nav "Settings" active; one field per account, labelled "<BANK> ··<last 4>", with its name, a disabled "Save" and the description; the categories grouped under Expenses, Income and "Transfers (out of every total)", each group with its categories as badges; no edit control for categories.
2. Fill one account's field with "ZZTEST Main": "Save" enables; press it. The toast says "Account renamed"; open `/transactions`: the account picker lists "ZZTEST Main". Reload `/settings`: the new name stays.
3. Empty the field: "Save" is disabled.
4. Screenshot `task12-settings.png`. `errors`, `close`, then drop the scratch database (R2 step 5).

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/app/settings
git commit -m "feat: add the settings page to rename accounts and list the categories"
```

---

### Task 13: Imports restyle

**Files:**
- Modify: `apps/web/src/app/imports/page.tsx`, `apps/web/src/app/imports/upload-form.tsx`

**Interfaces:**
- Consumes: `GET /imports` → `Schemas["ImportRecord"][]`; `POST /imports` → `Schemas["ImportSummary"]`; `dateTime` (Task 1).
- Produces: the restyled `/imports`, with all seven history columns visible at desktop width (slice 2 dogfood issue 001).

- [ ] **Step 1: The page**

Replace `apps/web/src/app/imports/page.tsx` with:

```tsx
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiGet, type Schemas } from "@/lib/api";
import { dateTime } from "@/lib/format";

import { UploadForm } from "./upload-form";

export const dynamic = "force-dynamic";

export default async function ImportsPage() {
  const imports = await apiGet<Schemas["ImportRecord"][]>("/imports");

  return (
    <>
      <h1 className="text-xl font-semibold tracking-tight">Imports</h1>
      <Card>
        <CardHeader>
          <CardTitle>Import statements</CardTitle>
          <CardDescription>
            PDF statements from BBVA or CaixaBank. Each import starts a categorization run in the background.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <UploadForm />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Import history</CardTitle>
        </CardHeader>
        <CardContent>
          {imports.length === 0 ? (
            <p className="text-sm text-muted-foreground">No statements imported yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead>When</TableHead>
                  <TableHead>Account</TableHead>
                  <TableHead>File</TableHead>
                  <TableHead className="hidden md:table-cell">Period</TableHead>
                  <TableHead className="text-right">Rows</TableHead>
                  <TableHead className="text-right">New</TableHead>
                  <TableHead className="text-right">Duplicate</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {imports.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell>{dateTime(row.imported_at)}</TableCell>
                    <TableCell>{row.account_name}</TableCell>
                    {/* A long file name used to push the Duplicate column out of the card (issue 001). */}
                    <TableCell className="max-w-48 truncate" title={row.filename}>
                      {row.filename}
                    </TableCell>
                    <TableCell className="hidden md:table-cell">
                      {row.period_start ?? "—"} → {row.period_end ?? "—"}
                    </TableCell>
                    <TableCell className="text-right">{row.rows_total}</TableCell>
                    <TableCell className="text-right">{row.rows_new}</TableCell>
                    <TableCell className="text-right">{row.rows_duplicate}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </>
  );
}
```

- [ ] **Step 2: The upload form as a described field**

In `apps/web/src/app/imports/upload-form.tsx`, add the imports:

```tsx
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Spinner } from "@/components/ui/spinner";
```

and replace the returned JSX with:

```tsx
  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3">
      <Field>
        <FieldLabel htmlFor="statements">Statement PDFs</FieldLabel>
        <div className="flex items-center gap-2">
          <Input id="statements" type="file" name="files" accept="application/pdf" multiple required />
          <Button type="submit" disabled={busy}>
            {busy && <Spinner data-icon="inline-start" />}
            Import
          </Button>
        </div>
        <FieldDescription>One or more PDF statements. A statement imported twice only adds its new rows.</FieldDescription>
      </Field>
      <div aria-live="polite">
        {messages.length > 0 && (
          <ul className="text-sm text-muted-foreground">
            {messages.map((message) => (
              <li key={message}>{message}</li>
            ))}
          </ul>
        )}
      </div>
    </form>
  );
```

- [ ] **Step 3: Run the gate**

Run: `cd apps/web && npm run lint && npx tsc --noEmit && npm test && npm run build`
Expected: no errors.

- [ ] **Step 4: Check the page in the browser (R2, scratch database: importing writes)**

The scratch API runs with `TYPESAFE_API_KEY=` empty, so the categorization run that an import starts does not call jev.
1. `open "http://localhost:3001/imports"`, `snapshot -i`. Expect the h1 "Imports", the field "Statement PDFs" with its description, "Import", and the history table.
2. At 1280 px, all seven columns fit: `eval "(() => { const t = document.querySelector('[data-slot=table-container]'); return t.scrollWidth <= t.clientWidth })()"` prints `true`.
3. Upload a statement that is already imported (absolute path; never write its name into the repo): `upload @<file input ref> "$(ls "$(git rev-parse --show-toplevel)"/data/raw/*.pdf | head -1)"`, then click "Import". Expect a message "<file>: 0 new, N duplicate" and a new history row after the refresh.
4. `set viewport 390 844`, screenshot `task13-imports-phone.png`: the Period column is hidden and nothing overflows the card.
5. Screenshot `task13-imports.png`. `errors`, `close`, then drop the scratch database (R2 step 5).

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/app/imports
git commit -m "feat: restyle the imports page and keep its history table inside the card"
```

---

### Task 14: Dogfood pass, guidelines review and docs

**Files:**
- Modify: `CLAUDE.md` ("Verifying the web app": the page list); whatever files the review below fixes
- Create (git-ignored, never committed): `dogfood-output/slice-3b/report.md`

- [ ] **Step 1: One dogfood pass over the whole app**

Load the workflow with `agent-browser skills get dogfood` and follow it with session `slice3b-dogfood`: real data on :3000 read-only (R1) for every page — `/`, a group, a category, a merchant, `/income`, an income category, `/transactions` (filters, saved filters, Load more, the panel opened and cancelled), `/subscriptions`, `/review`, `/imports`, `/settings` — at 1280 px and at 390 px; then the write flows on the scratch database (R2): a note, "Only this one", "Apply to all", "Clear merchant default", a review confirm with Undo, an account rename and a re-import. Write the report to `dogfood-output/slice-3b/report.md`, with screenshots beside it (absolute paths). Use generic descriptions in the report's issue titles; the report itself stays git-ignored.

- [ ] **Step 2: The web design guidelines review**

Load the `web-design-guidelines` skill and run it on the files this slice changed:

```bash
git diff --name-only main...HEAD -- apps/web/src | grep -E '\.tsx
```

Fix every finding that breaks accessibility (names, focus, contrast; see Decision B), layout at 390 px, or the spec's copy rules. Record the ones left as they are, with a reason, in the report.

- [ ] **Step 3: Fix what the two passes found**

One `fix:` commit per issue (or per group of issues in one file), each followed by the same page's check from its task. Re-run the gate after the last one:

Run: `cd apps/web && npm run lint && npx tsc --noEmit && npm test && npm run build`
Expected: no errors.

- [ ] **Step 4: Point the project instructions at the new pages**

In `CLAUDE.md`, section "Verifying the web app", replace the sentence that starts "Run the API and web first; pages live at" (it ends with "(`/imports`, `/transactions`).") with:

```markdown
Run the API and web first; pages live at `http://localhost:3000` (`/`, `/spending/<group>`,
`/income`, `/merchants/<id>`, `/transactions`, `/subscriptions`, `/review`, `/imports`, `/settings`).
```

and add, at the end of that section:

```markdown
- Checks that write data (labels, notes, merchant defaults, renames, imports) run on a scratch
  copy of the database, never on the real one: the recipe is "R2" in
  `docs/superpowers/plans/2026-09-25-slice-3b-interface.md`.
```

- [ ] **Step 5: Final checks and commit**

```bash
git status --short dogfood-output   # expected: nothing (the folder is git-ignored)
git add CLAUDE.md
git commit -m "docs: list the slice 3 pages and the scratch database recipe for UI checks"
```

Expected: the spec's slice 3 "done" list for the web holds: every page in section 7 passed its agent-browser check (Tasks 3-13), one dogfood pass covers the whole app, and lint, types, build and unit tests are green.

---

## Notes for the executor

- **Order:** Tasks 1 → 14. Tasks 1-2 are pure helpers; every later task consumes them. Task 8 must come before Tasks 9 and 10 (the pickers move), and Task 10 before Task 12 (`apiPatch`).
- **Known gaps in the contract, handled here:** the API has no endpoint for the latest imported day, so the top bar reads `period.latest_day` from `GET /transactions?limit=1`; the API's overview `by_group` returns every group, so the Groups view lists every group with spend in the period as its own row, the five slotted groups in their colours and the rest in the "other" grey (`foldBySlot` was removed); the mockup's "12 months | Year to date | All" switch is left out, because the API sends exactly 12 months; `Transaction` has no account bank or last digits, so rows show `account_name`; the panel always offers "Clear merchant default" for a row with a merchant, because the API does not say whether the merchant has a default.
- **Not in this plan:** Playwright tests (v2), dark mode (v2), a phone bottom tab bar (v2), editing categories (v2), and the Decision E check in the API.
