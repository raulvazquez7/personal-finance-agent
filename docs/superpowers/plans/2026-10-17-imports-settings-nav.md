# Imports Coverage, Settings Taxonomy and the Secondary Menu — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Imports shows which months have a statement, per account, on a year board above a history grouped by month. Settings shows the taxonomy as cards in the app's visual language. Imports and Settings move from the top row into a menu.

**Architecture:** The API gains one small route (`GET /dashboard/group-slots`) and lists every import in statement order. Two pure helpers in `apps/web/src/lib` hold the rules: `coverage.ts` computes the board and `import-history.ts` groups the history. Both are tested with Vitest. Components are thin clients of those helpers, on the existing shadcn `base-nova` kit (Base UI). The only new UI file from shadcn is `dropdown-menu.tsx`, and no npm dependency is added.

**Tech Stack:** FastAPI + psycopg (Python 3.12, uv, pytest), Next.js 16.3.6 App Router, React 19.2.8, Tailwind v4, shadcn `base-nova` on `@base-ui/react` 1.8.0, lucide-react, Vitest, agent-browser.

**Spec:** `docs/superpowers/specs/2026-10-17-imports-settings-nav-design.md` (commits `0d6350f` and `63cd7d8`). The approved mockup, with made-up data, is `/Users/raulvazquez/Documents/AI Engineer/personal-finance-agent/.superpowers/brainstorm/66615-1792262926/content/proposal-v4.html`. It is git-ignored: open it in a browser from the main checkout. Where mockup and spec differ, the spec wins: there is no "Complete through" chip, and the drop zone has no Import button.

## Global Constraints

- No new npm or Python dependency. `npx shadcn@latest add dropdown-menu` adds one file and reports `cn`, which is already a dependency.
- Everything is in English: code, comments, UI copy and commits. UI copy is in sentence case, exactly as the spec quotes it.
- Category names render as `category.name`, never `label(slug)`.
- Copy the existing tokens. Use no hex colours in components: `bg-primary`, `bg-primary/35`, `border-chart-previous`, `text-muted-foreground`, `bg-card`, `var(--chart-other)` through `OTHER_COLOR`.
- Simplicity: one responsibility per file, no abstraction for a single caller, 15 readable lines over 30 clever ones.
- The repo is public. Tests use `ZZTEST` names, fake IBANs (`ES00…`) and 1999 dates for database rows. Never write real amounts, account digits or statement file names into code, tests, commits or the PR.
- Screenshots go only to `dogfood-output/imports-settings/` (git-ignored), as absolute paths. Never commit captures.
- Checks that write data (import, rename) run on a scratch database (recipe R2). The scratch API runs with `TYPESAFE_API_KEY=` (empty): an import starts a categorization run, and jev is paid.
- Web gate for every web task: `cd apps/web && npm run lint && npx tsc --noEmit && npm test && npm run build`.
- API gate for every API task: `cd apps/api && uv run task lint && uv run task test && uv run task test-integration`. Integration needs the local Supabase; `supabase status` must show it running.
- Conventional commits (`feat:`, `fix:`, `test:`, `chore:`, `docs:`), on the branch `feat/imports-settings-nav`.
- Before writing version-sensitive library code beyond what this plan shows, read the current docs through Context7. If a library behaves differently from this plan, stop and report instead of improvising.

## Review Focus

1. **A statement that crosses New Year** (1 Dec 2025 – 31 Jan 2026): both months are covered, each on its own year's board, and the history lists it under January 2026. Test: Task 2, `coverage.test.ts`, "draws a statement across New Year in both years".
2. **Today is a month's last day** (31 Oct): October is not a gap yet. On 1 Nov it is. Test: Task 2, `coverage.test.ts`, "waits for the month's last day to pass before calling it a gap".
3. **Two accounts with the same name** (a rename can do that): the board shows two rows, and the popover lists both. Keys are account ids, never names. Test: Task 2, `coverage.test.ts`, "lists missing accounts by id".
4. **A dropped file that is not a PDF, among PDFs**: its own message reads "Only PDF statements are supported", the PDFs still import, and the same file can be picked again right after. Test: Task 5, browser step 4.
5. **A 390 px phone and an 820 px tablet**: the board scrolls sideways inside its card, never the page. The sheet holds every page. The category toggle wraps under its heading. Test: Task 4 step 7, Task 3 step 6 and Task 6 step 5.

## Browser checks

Load the workflow once per session with `agent-browser skills get core`. Each command below is self-contained, because the shell does not keep variables.

**R1, real data, read-only.** Start the API (`cd apps/api && uv run task api`, :8000) and the web (`cd apps/web && npm run dev`, :3000) as background processes, unless they already answer: `curl -s -o /dev/null -w "%{http_code}" localhost:8000/imports` should print `200`. Use `agent-browser --session imports-settings` on `http://localhost:3000` only. Read-only means navigating, hovering, opening menus and popovers, and switching toggles. Never import, save or rename on real data. End with `agent-browser --session imports-settings errors` (expected: none) and `close`.

**R2, scratch database, for checks that write.** Follow recipe R2 in `docs/superpowers/plans/2026-09-25-slice-3b-interface.md` (section "R2 — scratch database, for checks that write"): copy the database into `scratch_review`, run the API on :8001 with `TYPESAFE_API_KEY=` and the web on :3001, use the session `imports-settings-scratch` on `http://localhost:3001` only, then stop both processes and drop `scratch_review`.

## File map

| File | Change | Responsibility |
|---|---|---|
| `apps/api/finance/api/imports.py` | modify | `LIST_IMPORTS_SQL`: every import, newest `period_end` first |
| `apps/api/finance/api/dashboard.py` | modify | `GET /dashboard/group-slots` |
| `apps/api/tests/test_api.py` | modify | unit: the list SQL has no `limit` |
| `apps/api/tests/test_imports_api.py` | create | integration: list order |
| `apps/api/tests/test_dashboard_api.py` | modify | integration: the slots route equals `group_slots()` |
| `apps/web/src/lib/api-types.ts` | regenerate | `npm run gen:api` |
| `apps/web/src/app/preview-ux/` | delete | the throwaway preview |
| `apps/web/src/lib/format.ts` (+ test) | modify | `monthName` ("August") |
| `apps/web/src/lib/coverage.ts` (+ test) | create | board states, popover lines, year bounds, missing summary |
| `apps/web/src/lib/import-history.ts` (+ test) | create | history groups by `period_end` month |
| `apps/web/src/components/ui/dropdown-menu.tsx` | create (shadcn CLI) | menu primitives |
| `apps/web/src/components/shell/nav-links.tsx` | modify | `MAIN_ITEMS`, `MORE_ITEMS`, row from `lg` |
| `apps/web/src/components/shell/more-menu.tsx` | create | the menu button and its two links |
| `apps/web/src/components/shell/mobile-nav.tsx` | modify | sheet below `lg`, separator, more items |
| `apps/web/src/components/shell/filter-bar.tsx` | modify | drop its own `ml-auto` |
| `apps/web/src/components/shell/top-bar.tsx` | modify | right-hand group: filters, then the menu |
| `apps/web/src/app/imports/swatch.tsx` | create | one coverage square, shared by board, legend and popover |
| `apps/web/src/app/imports/month-header.tsx` | create | a month's header button and its popover |
| `apps/web/src/app/imports/coverage-board.tsx` | create | the coverage card |
| `apps/web/src/app/imports/import-history.tsx` | create | the history card |
| `apps/web/src/app/imports/upload-form.tsx` | modify | the drop zone |
| `apps/web/src/app/imports/page.tsx` | modify | wires the three cards |
| `apps/web/src/app/settings/account-name-form.tsx` | modify | compact row |
| `apps/web/src/app/settings/category-browser.tsx` | create | toggle and group cards |
| `apps/web/src/app/settings/page.tsx` | modify | wires accounts and categories |

Order: Task 1 first (Tasks 4 and 6 read its types). Tasks 2 and 3 are independent of each other. Task 4 needs 1 and 2. Task 5 is independent of 4, but both live in `app/imports`: run them in sequence. Task 6 needs 1. Task 7 comes last.

---

### Task 1: API — every import in statement order, and the group slots route

**Files:**
- Modify: `apps/api/finance/api/imports.py:43-49`
- Modify: `apps/api/finance/api/dashboard.py` (add a route after `overview`)
- Modify: `apps/api/tests/test_api.py` (add one unit test)
- Create: `apps/api/tests/test_imports_api.py`
- Modify: `apps/api/tests/test_dashboard_api.py` (add one test)
- Regenerate: `apps/web/src/lib/api-types.ts`
- Delete: `apps/web/src/app/preview-ux/`

**Interfaces:**
- Produces: `GET /imports` returns `ImportRecord[]` (shape unchanged) ordered by `period_end desc nulls last, account name, imported_at desc`, with no cap. `GET /dashboard/group-slots` returns `{ [level1: string]: number }`. In the web, `apiGet<Record<string, number>>("/dashboard/group-slots")`.

- [ ] **Step 1: Write the failing unit test**

Append to `apps/api/tests/test_api.py`:

```python
def test_the_import_list_has_no_cap():
    # A handful of rows cannot prove a cap is gone, and the coverage board needs every import.
    assert "limit" not in imports.LIST_IMPORTS_SQL.lower()
```

- [ ] **Step 2: Write the failing integration tests**

Create `apps/api/tests/test_imports_api.py`:

```python
from datetime import date

import pytest
from fastapi.testclient import TestClient

from finance.api.deps import db
from finance.api.main import app

pytestmark = pytest.mark.integration


@pytest.fixture
def client(db_conn):
    previous = app.dependency_overrides.get(db)
    app.dependency_overrides[db] = lambda: db_conn
    yield TestClient(app)
    if previous is None:
        app.dependency_overrides.pop(db, None)
    else:
        app.dependency_overrides[db] = previous


def _account(conn, iban: str, name: str):
    return conn.execute(
        "insert into accounts (bank, iban, name) values ('bbva', %s, %s) returning id", (iban, name)
    ).fetchone()["id"]


def _import(conn, account, start: date | None, end: date | None, imported_at: str):
    return conn.execute(
        "insert into imports (account_id, filename, file_sha256, period_start, period_end, rows_total, imported_at)"
        " values (%s, 'zztest.pdf', 'x', %s, %s, 1, %s) returning id",
        (account, start, end, imported_at),
    ).fetchone()["id"]


def test_imports_list_newest_statement_first_then_account_then_null_periods(client, db_conn):
    savings = _account(db_conn, "ES0000000000000000000091", "ZZTEST savings")
    everyday = _account(db_conn, "ES0000000000000000000092", "ZZTEST everyday")
    january = _import(db_conn, everyday, date(1999, 1, 1), date(1999, 1, 31), "1999-03-01T10:00:00Z")
    february_savings = _import(db_conn, savings, date(1999, 2, 1), date(1999, 2, 28), "1999-03-01T10:00:00Z")
    february = _import(db_conn, everyday, date(1999, 2, 1), date(1999, 2, 28), "1999-03-01T09:00:00Z")
    february_again = _import(db_conn, everyday, date(1999, 2, 1), date(1999, 2, 28), "1999-03-02T09:00:00Z")
    undated = _import(db_conn, everyday, None, None, "1999-03-03T10:00:00Z")

    body = client.get("/imports").json()

    ours = [row["id"] for row in body if row["account_id"] in {str(savings), str(everyday)}]
    assert ours == [str(february_again), str(february), str(february_savings), str(january), str(undated)]
    # Null periods come after every dated import, ours or not.
    first_null = next(index for index, row in enumerate(body) if row["period_end"] is None)
    assert all(row["period_end"] is None for row in body[first_null:])
```

Append to `apps/api/tests/test_dashboard_api.py` (add `from finance.dashboard.breakdowns import group_slots` to its imports):

```python
def test_group_slots_route_returns_group_slots(client, db_conn, make_tx):
    money_month(db_conn, make_tx)
    assert client.get("/dashboard/group-slots").json() == group_slots(db_conn)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd apps/api && uv run pytest tests/test_api.py::test_the_import_list_has_no_cap -q`
Expected: FAIL with `AttributeError: module 'finance.api.imports' has no attribute 'LIST_IMPORTS_SQL'`.

Run: `cd apps/api && uv run pytest -m integration tests/test_imports_api.py tests/test_dashboard_api.py::test_group_slots_route_returns_group_slots -q`
Expected: FAIL. The order assertion fails (today's list is by `imported_at`), and the slots route returns 404.

- [ ] **Step 4: Implement the list query**

In `apps/api/finance/api/imports.py`, replace `list_imports` with:

```python
# Every import, newest statement first (spec 2026-10-17, section 7). No cap: the coverage board
# on /imports reads the whole list.
LIST_IMPORTS_SQL = (
    "select i.*, a.name as account_name from imports i join accounts a on a.id = i.account_id"
    " order by i.period_end desc nulls last, a.name, i.imported_at desc"
)


@router.get("")
def list_imports(conn: Db) -> list[ImportRecord]:
    rows = conn.execute(LIST_IMPORTS_SQL).fetchall()
    return [ImportRecord.model_validate(row) for row in rows]
```

- [ ] **Step 5: Implement the slots route**

In `apps/api/finance/api/dashboard.py`, after the `overview` route (`group_slots` is already imported):

```python
@router.get("/group-slots")
def slots(conn: Db) -> dict[str, int]:
    """Every expense group's colour slot (spec 8.2), for pages that colour groups without the
    overview. The overview calls the same function, so the two cannot drift."""
    return group_slots(conn)
```

- [ ] **Step 6: Run the API gate**

Run: `cd apps/api && uv run task lint && uv run task test && uv run task test-integration`
Expected: all pass. If `ruff format --check` fails, run `uv run ruff format` and run the gate again.

- [ ] **Step 7: Regenerate the web types and delete the preview**

The API on :8000 reloads on save. Start it if it is not running (`cd apps/api && uv run task api`, background).

```bash
cd apps/web && npm run gen:api && grep -n '"/dashboard/group-slots"' src/lib/api-types.ts
rm -r apps/web/src/app/preview-ux
```

Expected: one match for the route. `git diff --stat` shows `api-types.ts` and the deleted preview files.

- [ ] **Step 8: Run the web gate**

Run: `cd apps/web && npm run lint && npx tsc --noEmit && npm test && npm run build`
Expected: all pass. The build no longer lists `/preview-ux`.

- [ ] **Step 9: Commit**

```bash
git add apps/api/finance/api/imports.py apps/api/finance/api/dashboard.py apps/api/tests/test_api.py apps/api/tests/test_imports_api.py apps/api/tests/test_dashboard_api.py apps/web/src/lib/api-types.ts apps/web/src/app/preview-ux
git commit -m "feat: list every import in statement order and serve the group colour slots"
```

---

### Task 2: Pure helpers — coverage model, history groups, month name

**Files:**
- Modify: `apps/web/src/lib/format.ts` (add `monthName` after `monthShort`)
- Modify: `apps/web/src/lib/format.test.ts`
- Create: `apps/web/src/lib/coverage.ts`
- Create: `apps/web/src/lib/coverage.test.ts`
- Create: `apps/web/src/lib/import-history.ts`
- Create: `apps/web/src/lib/import-history.test.ts`

**Interfaces:**
- Produces, from `@/lib/format`: `monthName(month: "YYYY-MM"): string`, which returns "August".
- Produces, from `@/lib/coverage`:
  - `type Coverage = "covered" | "partial" | "gap" | "outside"`
  - `type Span = { start: string; end: string }`
  - `type AccountRef = { id: string; name: string; digits: string | null }`
  - `type ImportSpan = { accountId: string; start: string | null; end: string | null }`
  - `type CoverageLine = { id: string; name: string; count: number }`
  - `type PartialLine = CoverageLine & { spans: Span[] }`
  - `type MonthDetail = { covered: CoverageLine[]; partial: PartialLine[]; missing: { id: string; name: string }[] }`
  - `type BoardAccount = AccountRef & { states: Coverage[] }`
  - `type YearBoard = { months: string[]; accounts: BoardAccount[]; byMonth: MonthDetail[] }`
  - `type MissingEntry = { month: string; names: string[] }`
  - `monthSpan(month: string): Span`
  - `mergeSpans(spans: Span[]): Span[]`
  - `monthState(periods: Span[], month: Span, today: string): Coverage`
  - `buildYear(accounts: AccountRef[], imports: ImportSpan[], year: number, today: string): YearBoard`
  - `yearBounds(imports: ImportSpan[], today: string): { first: number; last: number; initial: number }`
  - `missingSummary(board: YearBoard): MissingEntry[]`
- Produces, from `@/lib/import-history`: `type HistoryGroup<T> = { month: string | null; rows: T[] }` and `groupByEndMonth<T extends { period_end: string | null }>(rows: T[]): HistoryGroup<T>[]`.

- [ ] **Step 1: Write the failing tests**

Add to `apps/web/src/lib/format.test.ts`. Add `monthName` to the import list, then append:

```ts
describe("monthName", () => {
  it("names the month alone, west of UTC too", () => {
    expect(monthName("2026-08")).toBe("August");
    expect(monthName("2026-01")).toBe("January");
  });
});
```

Create `apps/web/src/lib/coverage.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import {
  buildYear,
  mergeSpans,
  missingSummary,
  monthSpan,
  monthState,
  yearBounds,
  type AccountRef,
  type ImportSpan,
} from "./coverage";

const TODAY = "2026-10-17";
const span = (start: string, end: string) => ({ start, end });
const row = (accountId: string, start: string | null, end: string | null): ImportSpan => ({ accountId, start, end });
const august = monthSpan("2026-08");
const ACCOUNTS: AccountRef[] = [
  { id: "b", name: "ZZTEST Savings", digits: "····0002" },
  { id: "a", name: "ZZTEST Everyday", digits: null },
];

describe("monthSpan", () => {
  it("runs from the first to the last day, leap years included", () => {
    expect(monthSpan("2026-08")).toEqual(span("2026-08-01", "2026-08-31"));
    expect(monthSpan("2028-02")).toEqual(span("2028-02-01", "2028-02-29"));
    expect(monthSpan("2026-12")).toEqual(span("2026-12-01", "2026-12-31"));
  });
});

describe("mergeSpans", () => {
  it("joins spans that touch or overlap, and keeps a hole", () => {
    expect(
      mergeSpans([
        span("2026-08-06", "2026-08-08"),
        span("2026-08-01", "2026-08-05"),
        span("2026-08-20", "2026-08-25"),
        span("2026-08-21", "2026-08-22"),
      ]),
    ).toEqual([span("2026-08-01", "2026-08-08"), span("2026-08-20", "2026-08-25")]);
  });
});

describe("monthState", () => {
  it("is covered when one period contains the whole month", () => {
    expect(monthState([span("2026-07-15", "2026-09-02")], august, TODAY)).toBe("covered");
  });

  it("is partial when a period ends on the 5th", () => {
    expect(monthState([span("2026-06-01", "2026-08-05")], august, TODAY)).toBe("partial");
  });

  it("stays partial when two partials together fill the month", () => {
    const periods = [span("2026-08-01", "2026-08-15"), span("2026-08-16", "2026-08-31")];
    expect(monthState(periods, august, TODAY)).toBe("partial");
  });

  it("is a gap when an ended month falls between two periods", () => {
    const periods = [span("2026-07-01", "2026-07-31"), span("2026-09-01", "2026-09-30")];
    expect(monthState(periods, august, TODAY)).toBe("gap");
  });

  it("never calls the current month a gap", () => {
    expect(monthState([span("2026-09-01", "2026-09-30")], monthSpan("2026-10"), TODAY)).toBe("outside");
  });

  it("calls the current month partial when a statement reaches into it", () => {
    expect(monthState([span("2026-09-01", "2026-10-10")], monthSpan("2026-10"), TODAY)).toBe("partial");
  });

  it("waits for the month's last day to pass before calling it a gap", () => {
    const periods = [span("2026-09-01", "2026-09-30")];
    expect(monthState(periods, monthSpan("2026-10"), "2026-10-31")).toBe("outside");
    expect(monthState(periods, monthSpan("2026-10"), "2026-11-01")).toBe("gap");
  });

  it("is outside before the account's first period", () => {
    expect(monthState([span("2026-03-01", "2026-03-31")], monthSpan("2026-02"), TODAY)).toBe("outside");
  });
});

describe("buildYear", () => {
  it("orders accounts by name and puts January at index 0", () => {
    const board = buildYear(ACCOUNTS, [row("a", "2026-01-01", "2026-01-31")], 2026, TODAY);
    expect(board.months).toHaveLength(12);
    expect(board.months[0]).toBe("2026-01");
    expect(board.months[11]).toBe("2026-12");
    expect(board.accounts.map((account) => account.name)).toEqual(["ZZTEST Everyday", "ZZTEST Savings"]);
    expect(board.accounts[0].states[0]).toBe("covered");
    expect(board.accounts[0].digits).toBeNull();
    expect(board.accounts[1].states).toEqual(Array(12).fill("outside"));
  });

  it("lists a partial month with its clipped, merged days", () => {
    const imports = [row("a", "2026-06-01", "2026-08-03"), row("a", "2026-08-04", "2026-08-05")];
    expect(buildYear(ACCOUNTS, imports, 2026, TODAY).byMonth[7].partial).toEqual([
      { id: "a", name: "ZZTEST Everyday", count: 2, spans: [span("2026-08-01", "2026-08-05")] },
    ]);
  });

  it("counts two statements that each cover a month and draws one covered state", () => {
    const imports = [row("b", "2026-03-01", "2026-03-31"), row("b", "2026-03-01", "2026-03-31")];
    const board = buildYear(ACCOUNTS, imports, 2026, TODAY);
    expect(board.accounts[1].states[2]).toBe("covered");
    expect(board.byMonth[2].covered).toEqual([{ id: "b", name: "ZZTEST Savings", count: 2 }]);
  });

  it("ignores a period with a null end: it paints nothing and makes no later gap", () => {
    const board = buildYear(ACCOUNTS, [row("a", "2026-01-01", null)], 2026, TODAY);
    expect(board.accounts[0].states).toEqual(Array(12).fill("outside"));
    expect(board.byMonth.every((month) => month.missing.length === 0)).toBe(true);
  });

  it("lists missing accounts by id, so two accounts with one name both show", () => {
    const twins: AccountRef[] = [
      { id: "x", name: "ZZTEST Joint", digits: "····0003" },
      { id: "y", name: "ZZTEST Joint", digits: "····0004" },
    ];
    const imports = [row("x", "2026-01-01", "2026-01-31"), row("y", "2026-01-01", "2026-01-31")];
    const board = buildYear(twins, imports, 2026, TODAY);
    expect(board.accounts.map((account) => account.id)).toEqual(["x", "y"]);
    expect(board.byMonth[1].missing.map((line) => line.id)).toEqual(["x", "y"]);
  });

  it("draws a statement across New Year in both years", () => {
    const imports = [row("a", "2025-12-01", "2026-01-31")];
    expect(buildYear(ACCOUNTS, imports, 2025, TODAY).accounts[0].states[11]).toBe("covered");
    expect(buildYear(ACCOUNTS, imports, 2026, TODAY).accounts[0].states[0]).toBe("covered");
  });
});

describe("yearBounds", () => {
  it("opens on the latest statement's year and runs to the current year", () => {
    const imports = [row("a", "2024-12-01", "2025-01-31"), row("b", "2025-03-01", "2025-03-31"), row("a", null, null)];
    expect(yearBounds(imports, TODAY)).toEqual({ first: 2024, last: 2026, initial: 2025 });
  });

  it("falls back to the current year without any dated statement", () => {
    expect(yearBounds([row("a", null, null)], TODAY)).toEqual({ first: 2026, last: 2026, initial: 2026 });
  });
});

describe("missingSummary", () => {
  it("lists the newest month first, with every missing account", () => {
    const imports = [
      row("a", "2026-01-01", "2026-08-31"),
      row("b", "2026-01-01", "2026-03-31"),
      row("b", "2026-05-01", "2026-08-31"),
    ];
    expect(missingSummary(buildYear(ACCOUNTS, imports, 2026, TODAY))).toEqual([
      { month: "2026-09", names: ["ZZTEST Everyday", "ZZTEST Savings"] },
      { month: "2026-04", names: ["ZZTEST Savings"] },
    ]);
  });
});
```

Create `apps/web/src/lib/import-history.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import { groupByEndMonth } from "./import-history";

const record = (id: string, period_end: string | null) => ({ id, period_end });

describe("groupByEndMonth", () => {
  it("groups by the month a statement ends, keeping the API order", () => {
    // "2" is a statement from 1 June to 5 August: it belongs to August.
    const rows = [record("1", "2026-08-31"), record("2", "2026-08-05"), record("3", "2026-07-31")];
    expect(groupByEndMonth(rows)).toEqual([
      { month: "2026-08", rows: [rows[0], rows[1]] },
      { month: "2026-07", rows: [rows[2]] },
    ]);
  });

  it("puts statements without a period in a last group", () => {
    const rows = [record("1", "2026-08-31"), record("2", null)];
    expect(groupByEndMonth(rows)).toEqual([
      { month: "2026-08", rows: [rows[0]] },
      { month: null, rows: [rows[1]] },
    ]);
  });

  it("returns nothing for no imports", () => {
    expect(groupByEndMonth([])).toEqual([]);
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd apps/web && npx vitest run src/lib/coverage.test.ts src/lib/import-history.test.ts src/lib/format.test.ts`
Expected: FAIL. The two new modules cannot be resolved, and `monthName` is not exported.

- [ ] **Step 3: Implement `monthName`**

In `apps/web/src/lib/format.ts`, after `monthShort` (the `monthLong` formatter already exists):

```ts
export const monthName = (month: string) => monthLong.format(utc(`${month}-01`)); // August
```

- [ ] **Step 4: Implement `coverage.ts`**

Create `apps/web/src/lib/coverage.ts`:

```ts
/** Statement coverage for the year board on /imports (spec 2026-10-17, section 5). Pure: dates are
 * YYYY-MM-DD strings compared as text, and a month runs from its first to its last day, in UTC. */

export type Coverage = "covered" | "partial" | "gap" | "outside";
export type Span = { start: string; end: string };
export type AccountRef = { id: string; name: string; digits: string | null };
export type ImportSpan = { accountId: string; start: string | null; end: string | null };
export type CoverageLine = { id: string; name: string; count: number };
export type PartialLine = CoverageLine & { spans: Span[] };
export type MonthDetail = { covered: CoverageLine[]; partial: PartialLine[]; missing: { id: string; name: string }[] };
export type BoardAccount = AccountRef & { states: Coverage[] };
export type YearBoard = { months: string[]; accounts: BoardAccount[]; byMonth: MonthDetail[] };
export type MissingEntry = { month: string; names: string[] };

const DAY_MS = 86_400_000;
const iso = (time: number) => new Date(time).toISOString().slice(0, 10);
const nextDay = (day: string) => iso(Date.parse(`${day}T00:00:00Z`) + DAY_MS);

/** "2026-02" → 1 to 28 February. Day 0 of the next month is this month's last day. */
export function monthSpan(month: string): Span {
  const [year, index] = month.split("-").map(Number);
  return { start: `${month}-01`, end: iso(Date.UTC(year, index, 0)) };
}

const overlaps = (period: Span, month: Span) => period.start <= month.end && period.end >= month.start;
const covers = (period: Span, month: Span) => period.start <= month.start && period.end >= month.end;
const clip = (period: Span, month: Span): Span => ({
  start: period.start > month.start ? period.start : month.start,
  end: period.end < month.end ? period.end : month.end,
});

/** Spans that touch or overlap become one, so 1–5 and 6–8 read as 1–8. */
export function mergeSpans(spans: Span[]): Span[] {
  const merged: Span[] = [];
  for (const span of [...spans].sort((a, b) => a.start.localeCompare(b.start))) {
    const last = merged.at(-1);
    if (last && span.start <= nextDay(last.end)) {
      if (span.end > last.end) last.end = span.end;
    } else {
      merged.push({ ...span });
    }
  }
  return merged;
}

/** The four rules of spec section 5, in order. A month is expected only once it has ended. */
export function monthState(periods: Span[], month: Span, today: string): Coverage {
  if (periods.some((period) => covers(period, month))) return "covered";
  if (periods.some((period) => overlaps(period, month))) return "partial";
  if (month.end < today && periods.some((period) => period.end < month.start)) return "gap";
  return "outside";
}

const periodsOf = (imports: ImportSpan[], accountId: string): Span[] =>
  imports.flatMap((row) => (row.accountId === accountId && row.start && row.end ? [{ start: row.start, end: row.end }] : []));

export function buildYear(accounts: AccountRef[], imports: ImportSpan[], year: number, today: string): YearBoard {
  const months = Array.from({ length: 12 }, (_, index) => `${year}-${String(index + 1).padStart(2, "0")}`);
  const rows = [...accounts]
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((account) => {
      const periods = periodsOf(imports, account.id);
      return { account, periods, states: months.map((month) => monthState(periods, monthSpan(month), today)) };
    });
  const byMonth = months.map((month, index): MonthDetail => {
    const span = monthSpan(month);
    const detail: MonthDetail = { covered: [], partial: [], missing: [] };
    for (const { account, periods, states } of rows) {
      const hitting = periods.filter((period) => overlaps(period, span));
      const line = { id: account.id, name: account.name, count: hitting.length };
      if (states[index] === "covered") detail.covered.push(line);
      if (states[index] === "partial") detail.partial.push({ ...line, spans: mergeSpans(hitting.map((p) => clip(p, span))) });
      if (states[index] === "gap") detail.missing.push({ id: account.id, name: account.name });
    }
    return detail;
  });
  return { months, accounts: rows.map(({ account, states }) => ({ ...account, states })), byMonth };
}

/** The board opens on the latest statement's year; the arrows run from the earliest statement's
 * year to the later of that year and today's. */
export function yearBounds(imports: ImportSpan[], today: string): { first: number; last: number; initial: number } {
  const current = Number(today.slice(0, 4));
  const starts = imports.flatMap((row) => (row.start && row.end ? [row.start] : [])).sort();
  const ends = imports.flatMap((row) => (row.start && row.end ? [row.end] : [])).sort();
  if (ends.length === 0) return { first: current, last: current, initial: current };
  const initial = Number(ends[ends.length - 1].slice(0, 4));
  return { first: Number(starts[0].slice(0, 4)), last: Math.max(initial, current), initial };
}

/** The missing line above the board: each month with a gap, newest first. */
export function missingSummary(board: YearBoard): MissingEntry[] {
  return board.months
    .map((month, index) => ({ month, names: board.byMonth[index].missing.map((line) => line.name) }))
    .filter((entry) => entry.names.length > 0)
    .reverse();
}
```

- [ ] **Step 5: Implement `import-history.ts`**

Create `apps/web/src/lib/import-history.ts`:

```ts
/** The import history on /imports, one group per month in which a statement ends (spec section
 * 4.3). The API already sorts by `period_end` (newest first), so a month's rows are adjacent. */

export type HistoryGroup<T> = { month: string | null; rows: T[] };

export function groupByEndMonth<T extends { period_end: string | null }>(rows: T[]): HistoryGroup<T>[] {
  const groups: HistoryGroup<T>[] = [];
  const undated: T[] = [];
  for (const row of rows) {
    if (!row.period_end) {
      undated.push(row);
      continue;
    }
    const month = row.period_end.slice(0, 7);
    const last = groups.at(-1);
    if (last?.month === month) last.rows.push(row);
    else groups.push({ month, rows: [row] });
  }
  return undated.length > 0 ? [...groups, { month: null, rows: undated }] : groups;
}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd apps/web && npx vitest run src/lib/coverage.test.ts src/lib/import-history.test.ts src/lib/format.test.ts`
Expected: PASS.

- [ ] **Step 7: Run the web gate**

Run: `cd apps/web && npm run lint && npx tsc --noEmit && npm test && npm run build`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add apps/web/src/lib/format.ts apps/web/src/lib/format.test.ts apps/web/src/lib/coverage.ts apps/web/src/lib/coverage.test.ts apps/web/src/lib/import-history.ts apps/web/src/lib/import-history.test.ts
git commit -m "feat: coverage model and history groups for the imports page"
```

---

### Task 3: Navigation — the menu button, and the sheet below `lg`

**Files:**
- Create (CLI): `apps/web/src/components/ui/dropdown-menu.tsx`
- Modify: `apps/web/src/components/shell/nav-links.tsx`
- Create: `apps/web/src/components/shell/more-menu.tsx`
- Modify: `apps/web/src/components/shell/mobile-nav.tsx`
- Modify: `apps/web/src/components/shell/filter-bar.tsx` (root `className` only)
- Modify: `apps/web/src/components/shell/top-bar.tsx`

**Interfaces:**
- Produces: `MAIN_ITEMS: Item[]` and `MORE_ITEMS: (Item & { icon: LucideIcon; hint: string })[]` from `nav-links.tsx` (`ITEMS` is removed; `grep -rn "ITEMS" apps/web/src` shows its only users, `nav-links.tsx` and `mobile-nav.tsx`). `MoreMenu()` from `more-menu.tsx`.

- [ ] **Step 1: Add the shadcn dropdown menu**

Run: `cd apps/web && npx shadcn@latest add dropdown-menu`
Expected: one new file, `src/components/ui/dropdown-menu.tsx`, with lucide icons (the CLI resolves the registry's icon placeholder). `git status` shows no other changed file. If it shows `package.json` changes beyond `cn`, stop and report.

- [ ] **Step 2: Split the items**

In `apps/web/src/components/shell/nav-links.tsx`:

1. Import the icons. Add `import { type LucideIcon, SlidersHorizontal, Upload } from "lucide-react";` at the top of the imports.
2. Replace the `ITEMS` constant with:

```tsx
/** The pages used every day: the row from `lg`, the top of the sheet below it. */
export const MAIN_ITEMS: Item[] = [
  {
    href: "/",
    label: "Overview",
    keepsFilters: true,
    // The group, category, merchant and income pages sit under the overview (mockup 03).
    active: (path) => path === "/" || ["/spending", "/income", "/merchants"].some((p) => path.startsWith(p)),
  },
  { href: "/transactions", label: "Transactions", keepsFilters: true, active: (path) => path.startsWith("/transactions") },
  { href: "/subscriptions", label: "Subscriptions", keepsFilters: false, active: (path) => path.startsWith("/subscriptions") },
  { href: "/chat", label: "Chat", keepsFilters: false, active: (path) => path.startsWith("/chat") },
  { href: "/review", label: "Review", keepsFilters: false, active: (path) => path.startsWith("/review") },
];

/** Behind the menu button from `lg` (more-menu.tsx), after a separator in the sheet below it. */
export const MORE_ITEMS: (Item & { icon: LucideIcon; hint: string })[] = [
  {
    href: "/imports",
    label: "Imports",
    keepsFilters: false,
    active: (path) => path.startsWith("/imports"),
    icon: Upload,
    hint: "Upload statements, see coverage",
  },
  {
    href: "/settings",
    label: "Settings",
    keepsFilters: false,
    active: (path) => path.startsWith("/settings"),
    icon: SlidersHorizontal,
    hint: "Account names, categories",
  },
];
```

3. In `NavLinks`, map `MAIN_ITEMS` instead of `ITEMS`. Change the nav's `className` from `sm:` to `lg:`:
   `"order-last -m-1 hidden w-full items-center gap-1 overflow-x-auto p-1 text-sm lg:order-none lg:flex lg:w-auto lg:flex-1"`.
4. Update its doc comment so it says "Below `lg` a menu lists the same links" and "From `lg` the row scrolls sideways".

- [ ] **Step 3: Write the menu**

Create `apps/web/src/components/shell/more-menu.tsx`:

```tsx
"use client";

import { Menu } from "@base-ui/react/menu";
import { Settings } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

import { MORE_ITEMS } from "./nav-links";

/** Imports and Settings, behind one button at the end of the top bar (spec section 3). The items
 * are Base UI link items: real links, so they open in a new tab and announce as links. */
export function MoreMenu() {
  const pathname = usePathname();
  const active = MORE_ITEMS.some((item) => item.active(pathname));

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            variant="secondary"
            size="icon-sm"
            aria-label="Imports and settings"
            // Below lg the sheet lists these pages. On them, the button takes the active pill's colours.
            className={cn(
              "hidden rounded-full lg:inline-flex",
              active && "bg-foreground text-background hover:bg-foreground/90",
            )}
          />
        }
      >
        <Settings />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        {MORE_ITEMS.map((item) => {
          const current = item.active(pathname);
          return (
            <Menu.LinkItem
              key={item.href}
              closeOnClick
              render={<Link href={item.href} />}
              aria-current={current ? "page" : undefined}
              className="flex items-start gap-2.5 rounded-md px-2 py-1.5 text-sm outline-hidden select-none data-highlighted:bg-accent"
            >
              <item.icon aria-hidden className="mt-0.5 size-4 shrink-0" />
              <span className="flex flex-col">
                <span className={cn(current && "font-medium")}>{item.label}</span>
                <span className="text-xs text-muted-foreground">{item.hint}</span>
              </span>
            </Menu.LinkItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
```

- [ ] **Step 4: Put the button in the top bar**

In `apps/web/src/components/shell/filter-bar.tsx`, change the returned root `className` from `"ml-auto flex items-center gap-2"` to `"flex items-center gap-2"`. The top bar now owns the push to the right.

In `apps/web/src/components/shell/top-bar.tsx`, add `import { MoreMenu } from "./more-menu";` and replace the `FilterBar` `Suspense` block with:

```tsx
        {/* Filters (only on the pages they scope), then the menu, always last. */}
        <div className="ml-auto flex items-center gap-2">
          <Suspense fallback={null}>
            <FilterBar accounts={accounts} latestDay={latestDay} />
          </Suspense>
          <MoreMenu />
        </div>
```

- [ ] **Step 5: The sheet below `lg`**

Replace `apps/web/src/components/shell/mobile-nav.tsx` with:

```tsx
"use client";

import { Menu } from "lucide-react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { filterParams, parseFilters, toSearchParams } from "@/lib/params";
import { cn } from "@/lib/utils";

import { MAIN_ITEMS, MORE_ITEMS } from "./nav-links";

/** Every page, behind a menu that shows below `lg`: the daily pages, then Imports and Settings. */
export function MobileNav({ pending }: { pending: number | null }) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const search = useSearchParams();
  const query = filterParams(parseFilters(toSearchParams(search))).toString();

  const link = (item: (typeof MAIN_ITEMS)[number]) => {
    const active = item.active(pathname);
    return (
      <Link
        key={item.href}
        href={item.keepsFilters && query ? `${item.href}?${query}` : item.href}
        aria-current={active ? "page" : undefined}
        aria-label={item.href === "/review" && pending ? `${item.label}, ${pending} to review` : undefined}
        onClick={() => setOpen(false)}
        className={cn(
          // 44 px tall: a comfortable target for a finger.
          "flex min-h-11 items-center rounded-full px-3 text-muted-foreground hover:text-foreground",
          active && "bg-foreground font-medium text-background hover:text-background",
        )}
      >
        {item.label}
        {item.href === "/review" && pending ? (
          <span className={cn("ml-1.5", !active && "text-primary")}>{pending}</span>
        ) : null}
      </Link>
    );
  };

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger render={<Button variant="ghost" size="icon-sm" className="lg:hidden" aria-label="Menu" />}>
        <Menu />
      </SheetTrigger>
      <SheetContent side="left">
        <SheetHeader>
          <SheetTitle>Menu</SheetTitle>
        </SheetHeader>
        <nav aria-label="Main" className="flex flex-col gap-1 px-2">
          {MAIN_ITEMS.map(link)}
          <Separator className="my-2" />
          {MORE_ITEMS.map(link)}
        </nav>
      </SheetContent>
    </Sheet>
  );
}
```

- [ ] **Step 6: Check in the browser (R1)**

1. At 1280×900, `open http://localhost:3000/` and `snapshot -i`. The row shows Overview, Transactions, Subscriptions, Chat and Review. There is no Imports or Settings link in the row, and there is a button "Imports and settings" after the period pill.
2. Click the button and `snapshot -i`. A menu shows two links, Imports and Settings, with their hints. Click Imports: the URL is `/imports`, the menu is closed, and the button has the dark active fill (screenshot `task3-menu-active.png`). Open the menu again: Imports carries `aria-current="page"`. Press Escape: the menu closes and focus returns to the button.
3. Keyboard: Tab to the button, press Enter, then ArrowDown and Enter on Settings. You land on `/settings`.
4. At 1024×800 on `/`: the five links, both filter pills and the button fit. Check with `eval "(() => { const n=[...document.querySelectorAll('nav[aria-label=Main]')].find(e=>getComputedStyle(e).display!=='none'); return n.scrollWidth <= n.clientWidth })()"`, which should print `true`.
5. At 820×900 and at 390×844 (`set viewport`): the "Menu" button shows and the row and the "Imports and settings" button do not. Open the sheet: five links, a separator, then Imports and Settings. Tap Settings: the sheet closes on `/settings`. Screenshot `task3-sheet-820.png`.
6. On 390×844, `/` and `/imports`: the page does not scroll sideways (`eval "document.documentElement.scrollWidth <= innerWidth"` prints `true`).
7. `errors` reports none, then `close`.

- [ ] **Step 7: Run the web gate**

Run: `cd apps/web && npm run lint && npx tsc --noEmit && npm test && npm run build`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add apps/web/src/components/ui/dropdown-menu.tsx apps/web/src/components/shell
git commit -m "feat: move imports and settings into a menu, sheet below lg"
```

---

### Task 4: Imports — coverage board and grouped history

**Files:**
- Create: `apps/web/src/app/imports/swatch.tsx`
- Create: `apps/web/src/app/imports/month-header.tsx`
- Create: `apps/web/src/app/imports/coverage-board.tsx`
- Create: `apps/web/src/app/imports/import-history.tsx`
- Modify: `apps/web/src/app/imports/page.tsx`

**Interfaces:**
- Consumes: from Task 2, `buildYear`, `yearBounds`, `missingSummary`, `monthSpan` and the types `AccountRef`, `ImportSpan`, `Coverage` and `MonthDetail` (`@/lib/coverage`); `groupByEndMonth` (`@/lib/import-history`); `monthName` (`@/lib/format`). From Task 1, `GET /imports` in statement order.
- Produces: `Swatch({ state, className })`, `MonthHeader({ month, detail, today, onOpenChange })`, `CoverageBoard({ accounts, imports, today })`, `ImportHistory({ imports })`.

- [ ] **Step 1: The swatch**

Create `apps/web/src/app/imports/swatch.tsx`:

```tsx
import type { Coverage } from "@/lib/coverage";
import { cn } from "@/lib/utils";

const DRAW: Record<Coverage, string> = {
  covered: "bg-primary",
  partial: "bg-primary/35",
  gap: "border border-dashed border-chart-previous bg-background",
  outside: "",
};

/** One account-month on the board, and its key in the legend and the popover (spec section 4.2).
 * Decorative: the month buttons and the popover carry the words. */
export function Swatch({ state, className }: { state: Coverage; className?: string }) {
  return <span aria-hidden className={cn("block size-5 shrink-0 rounded-md", DRAW[state], className)} />;
}
```

- [ ] **Step 2: The month header and its popover**

Create `apps/web/src/app/imports/month-header.tsx`:

```tsx
"use client";

import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from "@/components/ui/popover";
import { monthSpan, type Coverage, type MonthDetail } from "@/lib/coverage";
import { dayRange, monthLabel, monthShort } from "@/lib/format";
import { plural } from "@/lib/labels";
import { cn } from "@/lib/utils";

import { Swatch } from "./swatch";

type Props = { month: string; detail: MonthDetail; today: string; onOpenChange: (open: boolean) => void };

const statements = (count: number) => (count > 1 ? ` · ${plural(count, "statement", "statements")}` : "");

/** A month's column header. It opens, on hover or click, the accounts and their state for that
 * month. Nothing here filters or links (spec section 4.2). */
export function MonthHeader({ month, detail, today, onOpenChange }: Props) {
  const label = monthShort(month);
  if (`${month}-01` > today) return <span className="text-center text-xs text-muted-foreground">{label}</span>;

  const ended = monthSpan(month).end < today;
  const withStatement = detail.covered.length + detail.partial.length;
  const empty = withStatement + detail.missing.length === 0;
  return (
    <Popover onOpenChange={onOpenChange}>
      <PopoverTrigger
        openOnHover
        render={
          <Button
            variant="ghost"
            size="sm"
            className={cn("w-full px-0 text-xs font-medium", !ended && "text-muted-foreground")}
            aria-label={`${monthLabel(month)}. ${withStatement} with a statement, ${detail.missing.length} missing.`}
          />
        }
      >
        {label}
      </PopoverTrigger>
      <PopoverContent className="w-72">
        <PopoverHeader>
          <PopoverTitle>{monthLabel(month)}</PopoverTitle>
          {empty && <PopoverDescription>No statement for this month yet.</PopoverDescription>}
        </PopoverHeader>
        {detail.covered.length > 0 && (
          <Group title={`Whole month · ${detail.covered.length}`}>
            {detail.covered.map((line) => (
              <Line key={line.id} state="covered">
                {line.name}
                {statements(line.count)}
              </Line>
            ))}
          </Group>
        )}
        {detail.partial.length > 0 && (
          <Group title={`Part of the month · ${detail.partial.length}`}>
            {detail.partial.map((line) => (
              <Line key={line.id} state="partial" aside={line.spans.map((span) => dayRange(span.start, span.end)).join(", ")}>
                {line.name}
                {statements(line.count)}
              </Line>
            ))}
          </Group>
        )}
        {detail.missing.length > 0 && (
          <Group title={`Missing · ${detail.missing.length}`}>
            {detail.missing.map((line) => (
              <Line key={line.id} state="gap">
                {line.name}
              </Line>
            ))}
          </Group>
        )}
      </PopoverContent>
    </Popover>
  );
}

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-1">
      <h3 className="text-xs text-muted-foreground">{title}</h3>
      <ul className="flex flex-col gap-0.5">{children}</ul>
    </section>
  );
}

function Line({ state, aside, children }: { state: Coverage; aside?: string; children: ReactNode }) {
  return (
    <li className="flex items-center gap-2">
      <Swatch state={state} className="size-2.5 rounded-sm" />
      <span className="min-w-0 flex-1 truncate">{children}</span>
      {aside && <span className="shrink-0 text-xs text-muted-foreground">{aside}</span>}
    </li>
  );
}
```

- [ ] **Step 3: The coverage card**

Create `apps/web/src/app/imports/coverage-board.tsx`:

```tsx
"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { buildYear, missingSummary, yearBounds, type AccountRef, type Coverage, type ImportSpan } from "@/lib/coverage";
import { monthName } from "@/lib/format";
import { cn } from "@/lib/utils";

import { MonthHeader } from "./month-header";
import { Swatch } from "./swatch";

const LEGEND: { state: Coverage; label: string }[] = [
  { state: "covered", label: "Whole month" },
  { state: "partial", label: "Part of the month" },
  { state: "gap", label: "Missing" },
  { state: "outside", label: "Not expected" },
];

type Props = { accounts: AccountRef[]; imports: ImportSpan[]; today: string };

/** Which months have a statement, for each account, one year at a time (spec section 4.2). */
export function CoverageBoard({ accounts, imports, today }: Props) {
  const bounds = yearBounds(imports, today);
  const [year, setYear] = useState(bounds.initial);
  const [openMonth, setOpenMonth] = useState<string | null>(null);
  const board = buildYear(accounts, imports, year, today);
  const missing = missingSummary(board);

  function go(next: number) {
    setOpenMonth(null);
    setYear(next);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Statement coverage</CardTitle>
        <CardDescription>Which months have a statement, for each account.</CardDescription>
        <CardAction className="flex items-center gap-1">
          <Button
            variant="outline"
            size="icon-sm"
            className="rounded-full"
            aria-label="Previous year"
            disabled={year <= bounds.first}
            onClick={() => go(year - 1)}
          >
            <ChevronLeft />
          </Button>
          <span className="w-12 text-center text-sm font-medium tabular-nums">{year}</span>
          <Button
            variant="outline"
            size="icon-sm"
            className="rounded-full"
            aria-label="Next year"
            disabled={year >= bounds.last}
            onClick={() => go(year + 1)}
          >
            <ChevronRight />
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
          {missing.length === 0 ? (
            <span className="text-muted-foreground">{`Nothing missing in ${year}.`}</span>
          ) : (
            <>
              <Swatch state="gap" className="size-3 rounded-sm" />
              <span className="font-medium">Missing:</span>
              <span>
                {missing
                  .map(({ month, names }) => `${monthName(month)} · ${names.length === 1 ? names[0] : `${names.length} accounts`}`)
                  .join(", ")}
              </span>
            </>
          )}
        </p>
        {/* Thirteen columns: the account, then January to December. On a phone the grid scrolls inside the card. */}
        <div className="overflow-x-auto">
          <div className="grid min-w-[44rem] grid-cols-[minmax(9rem,1.3fr)_repeat(12,minmax(0,1fr))] items-center gap-x-1 gap-y-2">
            {/* A real cell: sr-only is position:absolute, which takes it out of the grid and moves every square one month right. */}
            <span className="text-xs text-muted-foreground">Account</span>
            {board.months.map((month, index) => (
              <MonthHeader
                key={month}
                month={month}
                detail={board.byMonth[index]}
                today={today}
                onOpenChange={(open) => setOpenMonth((current) => (open ? month : current === month ? null : current))}
              />
            ))}
            {board.accounts.map((account) => (
              <div key={account.id} className="col-span-full grid grid-cols-subgrid items-center">
                <span className="truncate pr-2 text-sm" title={account.name}>
                  {account.name}
                  {account.digits && <span className="text-muted-foreground"> {account.digits}</span>}
                </span>
                {account.states.map((state, index) => (
                  <span
                    key={board.months[index]}
                    className={cn(
                      "flex justify-center rounded-md py-0.5",
                      openMonth === board.months[index] && "bg-primary/5",
                    )}
                  >
                    <Swatch state={state} />
                  </span>
                ))}
              </div>
            ))}
          </div>
        </div>
        <ul className="flex flex-wrap gap-x-4 gap-y-2 text-xs text-muted-foreground">
          {LEGEND.map(({ state, label }) => (
            <li key={state} className="flex items-center gap-1.5">
              <Swatch state={state} className={cn("size-3 rounded-sm", state === "outside" && "border border-input")} />
              {label}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 4: The history card**

Create `apps/web/src/app/imports/import-history.tsx`:

```tsx
import { NoData } from "@/components/money/no-data";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { Schemas } from "@/lib/api";
import { dateTime, dayRange, monthLabel } from "@/lib/format";
import { groupByEndMonth } from "@/lib/import-history";

/** Every import, one section per month in which a statement ends (spec section 4.3). The file
 * name stays in the API and is not shown. */
export function ImportHistory({ imports }: { imports: Schemas["ImportRecord"][] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Import history</CardTitle>
      </CardHeader>
      <CardContent>
        {imports.length === 0 ? (
          <p className="text-sm text-muted-foreground">No statements imported yet.</p>
        ) : (
          // On phones the table drops Imported and Rows, and the text cells wrap.
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Period</TableHead>
                <TableHead>Account</TableHead>
                <TableHead className="hidden sm:table-cell">Imported</TableHead>
                <TableHead className="hidden text-right md:table-cell">Rows</TableHead>
                <TableHead className="text-right">New</TableHead>
                <TableHead className="text-right">Duplicate</TableHead>
              </TableRow>
            </TableHeader>
            {groupByEndMonth(imports).map((group) => (
              <TableBody key={group.month ?? "none"}>
                <TableRow className="hover:bg-transparent">
                  <TableHead scope="rowgroup" colSpan={6} className="h-auto pt-4 pb-1 tracking-normal normal-case">
                    {group.month ? monthLabel(group.month) : "No period"}
                  </TableHead>
                </TableRow>
                {group.rows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="whitespace-normal">
                      {row.period_start && row.period_end ? dayRange(row.period_start, row.period_end) : <NoData />}
                    </TableCell>
                    <TableCell className="whitespace-normal wrap-anywhere">{row.account_name}</TableCell>
                    <TableCell className="hidden whitespace-normal text-muted-foreground sm:table-cell">
                      {dateTime(row.imported_at)}
                    </TableCell>
                    <TableCell className="hidden text-right md:table-cell">{row.rows_total}</TableCell>
                    <TableCell className="text-right">{row.rows_new}</TableCell>
                    <TableCell className="text-right">{row.rows_duplicate}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            ))}
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 5: Wire the page**

Replace `apps/web/src/app/imports/page.tsx` with:

```tsx
import type { Metadata } from "next";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { apiGet, type Schemas } from "@/lib/api";
import { accountDigits } from "@/lib/labels";

import { CoverageBoard } from "./coverage-board";
import { ImportHistory } from "./import-history";
import { UploadForm } from "./upload-form";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Imports" };

export default async function ImportsPage() {
  const [imports, accounts] = await Promise.all([
    apiGet<Schemas["ImportRecord"][]>("/imports"),
    apiGet<Schemas["Account"][]>("/accounts"),
  ]);
  // The server's own calendar day (spec section 2, Today). en-CA writes YYYY-MM-DD.
  const today = new Date().toLocaleDateString("en-CA");

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
      {imports.length > 0 && (
        <CoverageBoard
          today={today}
          accounts={accounts.map((account) => ({ id: account.id, name: account.name, digits: accountDigits(account) }))}
          imports={imports.map((row) => ({ accountId: row.account_id, start: row.period_start, end: row.period_end }))}
        />
      )}
      <ImportHistory imports={imports} />
    </>
  );
}
```

- [ ] **Step 6: Run the web gate**

Run: `cd apps/web && npm run lint && npx tsc --noEmit && npm test && npm run build`
Expected: all pass.

- [ ] **Step 7: Check in the browser (R1)**

1. At 1280×900, `open http://localhost:3000/imports`, `snapshot -i`, and take a full screenshot `task4-imports.png`. Compare it with the mockup's "Imports A": upload card, then coverage card (year and arrows on the right, the missing line, the grid, the legend), then history.
2. January's square sits under the "Jan" header. Compare `getBoundingClientRect().left` of the first account row's second cell with the "Jan" button's: `eval` both and expect the centres within 2 px.
3. Hover the "Aug" header (`hover @ref`), wait 500 ms, and `snapshot`. A dialog titled "August {year}" lists accounts under "Whole month", "Part of the month" or "Missing". The Aug column is tinted. Move away: it closes.
4. The October header in the current year is muted, and October's squares are blank, not dashed (`eval` the Oct column's classes for `border-dashed`, expect none). November and December are plain text, not buttons.
5. "Previous year" goes back one year and is disabled at the earliest year. "Next year" is disabled at the last year. The missing line changes with the year.
6. History: no "File" header. The first section header is the newest month of `period_end`. Each row's Period comes first.
7. At 390×844: the board scrolls sideways inside its card (`eval "document.documentElement.scrollWidth <= innerWidth"` prints `true`), and the history hides Imported and Rows. Screenshot `task4-imports-390.png`.
8. `errors` reports none, then `close`.

- [ ] **Step 8: Commit**

```bash
git add apps/web/src/app/imports
git commit -m "feat: statement coverage board and history grouped by month on imports"
```

---

### Task 5: Imports — the drop zone

**Files:**
- Modify: `apps/web/src/app/imports/upload-form.tsx` (whole file)

**Interfaces:**
- Consumes: `POST /imports` (unchanged), `ImportSummary`.
- Produces: `UploadForm()` (same name and no props, so `page.tsx` is untouched).

- [ ] **Step 1: Replace the form with the drop zone**

Replace `apps/web/src/app/imports/upload-form.tsx` with:

```tsx
"use client";

import { Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import { type ChangeEvent, useState } from "react";

import { buttonVariants } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { API_URL, type Schemas } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Drop or choose PDF statements; each one is imported as soon as it is picked (spec section 4.1).
 * The native file input covers the whole zone, so a click opens the picker and a drop lands on
 * the input, both without custom drag code. */
export function UploadForm() {
  const router = useRouter();
  const [messages, setMessages] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);

  async function onChange(event: ChangeEvent<HTMLInputElement>) {
    const input = event.currentTarget; // React clears currentTarget once the handler awaits
    const files = [...(input.files ?? [])];
    setOver(false);
    if (files.length === 0) return;
    setBusy(true);
    const results: string[] = [];
    try {
      for (const file of files) {
        try {
          const body = new FormData();
          body.append("file", file);
          const response = await fetch(`${API_URL}/imports`, { method: "POST", body });
          if (response.ok) {
            const summary = (await response.json()) as Schemas["ImportSummary"];
            results.push(`${file.name}: ${summary.rows_new} new, ${summary.rows_duplicate} duplicate`);
          } else {
            const text = await response.text();
            let detail: unknown;
            try {
              detail = JSON.parse(text).detail;
            } catch {
              detail = undefined;
            }
            results.push(
              typeof detail === "string" ? `${file.name}: ${detail}` : `${file.name}: ${response.status} ${text}`,
            );
          }
        } catch (error) {
          results.push(`${file.name}: ${error instanceof Error ? error.message : String(error)}`);
        }
      }
    } finally {
      input.value = ""; // the same file can be picked again
      setMessages(results);
      setBusy(false);
      router.refresh();
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div
        className={cn(
          "relative flex items-center gap-4 rounded-xl border-[1.5px] border-dashed border-input bg-background p-4 transition-colors has-[:focus-visible]:ring-3 has-[:focus-visible]:ring-ring/50",
          over && "border-primary bg-accent",
        )}
      >
        {busy ? (
          <Spinner className="size-5 shrink-0 text-muted-foreground" />
        ) : (
          <Upload aria-hidden className="size-5 shrink-0 text-muted-foreground" />
        )}
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="text-sm font-medium">{busy ? "Importing…" : "Drop PDF statements here"}</span>
          <span id="statements-help" className="text-xs text-muted-foreground">
            or choose files · a statement imported twice only adds its new rows
          </span>
        </div>
        <span aria-hidden className={cn(buttonVariants({ variant: "outline", size: "sm" }), "shrink-0")}>
          Choose files
        </span>
        <input
          type="file"
          name="files"
          accept="application/pdf"
          multiple
          disabled={busy}
          aria-label="Statement PDFs"
          aria-describedby="statements-help"
          className="absolute inset-0 cursor-pointer opacity-0 disabled:cursor-progress"
          onChange={onChange}
          onDragEnter={() => setOver(true)}
          onDragLeave={() => setOver(false)}
          onDrop={() => setOver(false)}
        />
      </div>
      <div aria-live="polite">
        {messages.length > 0 && (
          // A long file name without spaces wraps instead of running past the card on a phone.
          <ul className="text-sm wrap-anywhere text-muted-foreground">
            {/* By position: two picked files with the same name and outcome give the same message. The
                list is replaced whole on each import, never reordered. */}
            {messages.map((message, index) => (
              <li key={index}>{message}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Run the web gate**

Run: `cd apps/web && npm run lint && npx tsc --noEmit && npm test && npm run build`
Expected: all pass.

- [ ] **Step 3: Check the import on a scratch database (R2)**

Set up R2 (scratch copy, API :8001 with `TYPESAFE_API_KEY=`, web :3001). Pick one statement with `ls "$(git rev-parse --show-toplevel)"/data/raw/*.pdf | head -1`. Do not write its name in the report. Make a non-PDF with `printf 'zztest' > /private/tmp/zztest-not-a-statement.txt`.

1. `open http://localhost:3001/imports` and `snapshot -i`. A file input named "Statement PDFs" is described by the help line. There is no "Import" button.
2. Drag highlight: `eval "(() => { const i=document.querySelector('input[type=file]'); i.dispatchEvent(new DragEvent('dragenter',{bubbles:true})); return i.parentElement.className.includes('border-primary') })()"` prints `true`. Then dispatch `dragleave` and expect `false`.
3. `upload 'input[type=file]' <absolute path of the PDF>`. The zone shows "Importing…", then a message ending in "N new, M duplicate" (all duplicates, since the scratch copy already holds it). The history and the board re-render.
4. Review Focus 4: `upload 'input[type=file]' <absolute PDF path> /private/tmp/zztest-not-a-statement.txt`. One message per file: the PDF's counts, and "zztest-not-a-statement.txt: Only PDF statements are supported". Then upload the same PDF again: a third message list appears, which proves the input was reset.
5. Keyboard: Tab to the zone. The dashed zone shows the focus ring (screenshot `task5-focus.png`).
6. `errors` reports none, then `close`. Stop both processes and drop `scratch_review`.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/app/imports/upload-form.tsx
git commit -m "feat: drop zone that imports statements as soon as they are picked"
```

---

### Task 6: Settings — compact account rows and the category cards

**Files:**
- Modify: `apps/web/src/app/settings/account-name-form.tsx` (render only)
- Create: `apps/web/src/app/settings/category-browser.tsx`
- Modify: `apps/web/src/app/settings/page.tsx`

**Interfaces:**
- Consumes: from Task 1, `GET /dashboard/group-slots` as `Record<string, number>`. From the existing code, `groupColor`, `OTHER_COLOR` (`@/lib/colors`) and `byLevel1` (`@/lib/pickers`, returning `{ value, label, items }[]`).
- Produces: `CategoryBrowser({ categories, slots })`.

- [ ] **Step 1: The account row**

In `apps/web/src/app/settings/account-name-form.tsx`, keep the state, `onSubmit`, `NAME_MAX` and every comment. Change the imports to `import { Field, FieldLabel } from "@/components/ui/field";` (no `FieldDescription`), and replace the returned JSX with:

```tsx
  return (
    <form onSubmit={onSubmit} className="flex items-start gap-3 border-t border-input py-3 first:border-t-0 first:pt-0 last:pb-0">
      {/* The bank's initial: a quiet marker, the label below names the bank. */}
      <span
        aria-hidden
        className="grid size-9 shrink-0 place-items-center rounded-full bg-background text-xs font-semibold ring-1 ring-input"
      >
        {account.bank.charAt(0).toUpperCase()}
      </span>
      <Field className="min-w-0 flex-1 gap-1">
        <Input
          id={id}
          value={name}
          maxLength={NAME_MAX}
          // Locked while saving, so the saved name cannot overwrite what is typed meanwhile. Read-only,
          // not disabled: a disabled field would drop the keyboard focus after Enter.
          readOnly={busy}
          onChange={(event) => setName(event.target.value)}
        />
        {/* Under the field, but still its label: the field keeps "BBVA ····1234" as its name. */}
        <FieldLabel htmlFor={id} id={`${id}-label`} className="text-xs font-normal text-muted-foreground">
          {/* One string: Chrome drops a lone space between server-rendered text parts from the name. */}
          {`${account.bank.toUpperCase()} ${DIGITS_SEPARATOR}${account.iban_last4}`}
        </FieldLabel>
      </Field>
      {/* "Save <account>": every account has a Save button. */}
      <Button
        type="submit"
        variant="outline"
        id={`${id}-save`}
        aria-labelledby={`${id}-save ${id}-label`}
        disabled={busy || !trimmed || trimmed === saved}
      >
        {busy && <Spinner data-icon="inline-start" />}
        {busy ? "Saving…" : "Save"}
      </Button>
    </form>
  );
```

- [ ] **Step 2: The category browser**

Create `apps/web/src/app/settings/category-browser.tsx`:

```tsx
"use client";

import { useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { Schemas } from "@/lib/api";
import { OTHER_COLOR, groupColor } from "@/lib/colors";
import { byLevel1 } from "@/lib/pickers";

const TYPES = [
  { type: "expense", title: "Expenses" },
  { type: "income", title: "Income" },
  { type: "transfer", title: "Transfers" },
] as const;
type TxType = (typeof TYPES)[number]["type"];

type Props = { categories: Schemas["CategoryOut"][]; slots: Record<string, number> };

/** The taxonomy, read-only: one card per group of the chosen type, with the group's colour from
 * the overview (spec section 6.2). Names are shown as stored. */
export function CategoryBrowser({ categories, slots }: Props) {
  const [type, setType] = useState<TxType>("expense");
  const groupsOf = (of: TxType) => byLevel1(categories.filter((category) => category.tx_type === of));
  const groups = groupsOf(type);

  return (
    <section aria-labelledby="categories-title" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex max-w-xl flex-col gap-1">
          <h2 id="categories-title" className="text-base font-medium">
            Categories
          </h2>
          <p className="text-sm text-muted-foreground">
            A refund takes the category of its purchase. Transfers never count as income or spending.
          </p>
        </div>
        <ToggleGroup
          variant="segment"
          size="sm"
          aria-label="Category type"
          value={[type]}
          onValueChange={(value: string[]) => {
            // A pressed item cannot be released: Base UI sends [] for that, which keeps the type.
            const next = TYPES.find((item) => item.type === value[0]);
            if (next) setType(next.type);
          }}
        >
          {TYPES.map((item) => (
            <ToggleGroupItem key={item.type} value={item.type}>
              {item.title}
              <span className="text-muted-foreground"> {groupsOf(item.type).length}</span>
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </div>
      {groups.length === 0 ? (
        <p className="text-sm text-muted-foreground">No categories of this type yet.</p>
      ) : (
        // Columns, not a grid: cards of different heights then leave no holes.
        <div className="gap-3 sm:columns-2 lg:columns-3">
          {groups.map((group) => (
            <Card key={group.value} size="sm" className="mb-3 break-inside-avoid">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <span
                    aria-hidden
                    className="size-2 shrink-0 rounded-full"
                    style={{ background: type === "expense" ? groupColor(group.value, slots) : OTHER_COLOR }}
                  />
                  {group.label}
                  <span className="ml-auto text-xs font-normal text-muted-foreground">{group.items.length}</span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="flex flex-col gap-1">
                  {group.items.map((category) => (
                    <li key={category.slug}>{category.name}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 3: Wire the page**

Replace `apps/web/src/app/settings/page.tsx` with:

```tsx
import type { Metadata } from "next";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { apiGet, type Schemas } from "@/lib/api";

import { AccountNameForm } from "./account-name-form";
import { CategoryBrowser } from "./category-browser";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Settings" };

/** Rename accounts; the categories are read-only (spec 2026-10-17, section 6). */
export default async function SettingsPage() {
  const [accounts, categories, slots] = await Promise.all([
    apiGet<Schemas["Account"][]>("/accounts"),
    apiGet<Schemas["CategoryOut"][]>("/categories"),
    apiGet<Record<string, number>>("/dashboard/group-slots"),
  ]);
  return (
    <>
      <h1 className="text-xl font-semibold tracking-tight">Settings</h1>
      <Card>
        <CardHeader>
          <CardTitle>Accounts</CardTitle>
          <CardDescription>The name shown in lists and in the account filter, for example “Joint account”.</CardDescription>
        </CardHeader>
        <CardContent>
          {accounts.length === 0 ? (
            <p className="text-sm text-muted-foreground">No accounts yet: import a statement first.</p>
          ) : (
            <div className="flex flex-col">
              {accounts.map((account) => (
                <AccountNameForm key={account.id} account={account} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
      <CategoryBrowser categories={categories} slots={slots} />
    </>
  );
}
```

- [ ] **Step 4: Run the web gate**

Run: `cd apps/web && npm run lint && npx tsc --noEmit && npm test && npm run build`
Expected: all pass.

- [ ] **Step 5: Check the categories (R1, read-only)**

1. At 1280×900, `open http://localhost:3000/settings`, take a full screenshot `task6-settings.png`, and compare it with the mockup's "Settings A".
2. `snapshot`. A group "Category type" has Expenses pressed (`aria-pressed=true`). Category names read as stored, for example `find text "Software & AI"` and `find text "ATM withdrawals"`. There is no "Software ai" and no "Atm withdrawal". Each card's dot colour matches the same group's colour on `/` (pick one group present in both; `eval` the dot's computed `background-color` on both pages).
3. Press Income, then Transfers: the cards swap, with one card each and a grey dot. Press Transfers again: it stays pressed.
4. Each account row shows the bank initial, the field, "BBVA ····NNNN" under it, and Save, disabled. The help sentence appears once, in the card description.
5. The field is still named by its label: `snapshot -i` shows a textbox named "BBVA ····NNNN" (or the bank of that row).
6. At 390×844: the toggle wraps under the paragraph, the cards are one column, and the page does not scroll sideways. Screenshot `task6-settings-390.png`. Then `errors` reports none, and `close`.

- [ ] **Step 6: Check the rename (R2, scratch)**

On `http://localhost:3001/settings`: type a new name ("ZZTEST renamed") in the first row and press Enter. A toast says "Account renamed", Save is disabled again, and after a reload the name stays. Open `/imports` on :3001: the board row shows the new name. Then `close`, stop the processes and drop `scratch_review`.

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/app/settings
git commit -m "feat: compact account rows and category cards on settings"
```

---

### Task 7: Whole-branch verification

**Files:** none, unless a check fails. Each fix gets its own `fix:` commit.

- [ ] **Step 1: Every gate on the branch**

```bash
cd apps/api && uv run task lint && uv run task test && uv run task test-integration
cd apps/web && npm run lint && npx tsc --noEmit && npm test && npm run build
```

Expected: all pass. Check that `git grep -n "preview-ux\|label(category.slug)\|label(slug)" apps/web/src/app` returns nothing in `app/imports` or `app/settings`.

- [ ] **Step 2: Dogfood pass (once per slice)**

Run `agent-browser skills get dogfood` and follow it over the whole app on R1 (read-only). Write the report to `dogfood-output/imports-settings/report.md`, which is git-ignored. Fix anything this branch broke. List anything older as a follow-up for Raul, without fixing it.

- [ ] **Step 3: Hand over**

Report to Raul: the commits, the gates' output, the browser checks with any "not exercised" notes, and the dogfood findings. Then use superpowers:finishing-a-development-branch. Do not push or open the PR until Raul says so. Push with the credential helper in `CLAUDE.md` (Git section).
