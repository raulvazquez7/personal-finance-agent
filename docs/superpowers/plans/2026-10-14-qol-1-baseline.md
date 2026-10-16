# Quality of life 1 — Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Subscriptions use a cadence the user can set, folded breakdown rows open, every transaction list opens the panel, and the small QA fixes from 2026-10-11 land.

**Architecture:** The subscription rule stays in `v_subscriptions`. `merchants.cadence` overrides detection. The API and `agent.subscriptions` only read the view. Folded rows travel inside `_other`. One panel component serves `/transactions` and the detail pages. Plan 2 reuses the cadence control and the panel.

**Tech Stack:** Postgres views, FastAPI, Pydantic v2, Next.js 16.3.6, React 19, the existing Base UI kit, Vitest, pytest, agent-browser.

**Spec:** `docs/superpowers/specs/2026-10-14-quality-of-life-design.md`, sections 3, 4, 5, 6 and 10. Do not implement sections 7, 8 or 9 (plan 2).

This plan was written from `main` at `20a3c79` and was not pre-executed in a sandbox. Copy the SQL and the tests. If a library behaves differently from the code below, stop and report instead of improvising. Before writing version-sensitive UI, read the current docs through Context7 (Next.js 16, Base UI, the AI SDK is not touched here).

## Global Constraints

- Everything in English: code, comments, docs, commits, UI copy (sentence case).
- Spec section 2 is binding. Do not reopen a call recorded there.
- Apply the new migration to the local database. Never run `supabase db reset`.
- Integration tests use `db_conn`, which rolls back. Browser checks that write use recipe R2 in `docs/superpowers/plans/2026-09-25-slice-3b-interface.md`, on a scratch database, never the real one.
- Read-only browser checks may use the API on :8000 and the web on :3000. Load `agent-browser skills get core` first. Screenshots go to `dogfood-output/qol-1/` by absolute path and are never committed.
- Web gate for a task that touches `apps/web`: `cd apps/web && npm run lint && npx next typegen && npx tsc --noEmit && npm test && npm run build`.
- API gate for a task that touches `apps/api`: `cd apps/api && uv run task lint` and `uv run task test`. Run `uv run task test-integration` when the task says so.
- After an API shape change, regenerate `apps/web/src/lib/api-types.ts` with the API running: `cd apps/web && npm run gen:api`.
- Conventional commits, no attribution trailer. One commit per task, messages as written in the task.
- No paid model calls. Do not widen `agent_reader` beyond `select` on the agent views.
- The repo is public: no real amounts, merchants or account digits in code, tests, docs or commits.

## File Structure

| File | Responsibility |
|---|---|
| `supabase/migrations/20261014120000_subscription_cadence.sql` | `merchants.cadence`, the new `v_subscriptions`, the new `agent.subscriptions` |
| `apps/api/finance/dashboard/subscriptions.py` | Split active and ended |
| `apps/api/finance/dashboard/models.py` | `latest_amount`, `cadence_source`, `ended`, `rows`, `category_count`, `top_categories`, `transfers` |
| `apps/api/finance/api/merchants.py` | `PATCH /merchants/{id}/cadence` |
| `apps/api/finance/categorization/labels.py` | Merge keeps a cadence |
| `apps/api/finance/dashboard/breakdowns.py` | Children of `_other`, category count, group subtitles |
| `apps/api/finance/dashboard/filters.py` | `merchant_id=none` |
| `apps/api/finance/agent/semantic/subscriptions.yaml` | The new rule |
| `apps/api/finance/agent/semantic/examples.yaml` | `latest_amount` |
| `apps/web/src/components/subscriptions/cadence-select.tsx` | The select plan 2 reuses |
| `apps/web/src/components/subscriptions/subscription-table.tsx` | Active rows and Ended |
| `apps/web/src/components/breakdown/folded-rows.tsx` | Expand and collapse |
| `apps/web/src/components/transactions/transaction-browser.tsx` | Table plus panel |
| `apps/web/src/components/shell/mobile-nav.tsx` | The menu sheet |

## Review Focus

1. A plan charged every 91 days shows a third of its latest charge per month and stays active at 80 days. Task 1.
2. A cadence set by hand beats the gap, and clearing it returns to detection. Tasks 1 and 2.
3. Expanding "Other" does not change the donut, and a disappeared key stays inside the subtotal's delta. Tasks 4 and 5.
4. The panel on a merchant page asks before discarding edits. Task 6.
5. Typing in Transactions search does not add a history entry per character. Task 7.

---

### Task 1: The subscription view

This task also moves every reader of the view to the new columns in the same commit. The API's lifespan runs `validate_layer`, so a view without `typical_amount` and a YAML that still names it would stop the API from starting, and `/dashboard/subscriptions` would select a column that is gone.

**Files:**
- Create: `supabase/migrations/20261014120000_subscription_cadence.sql`
- Modify: `apps/api/finance/categorization/labels.py` (the merge update)
- Modify: `apps/api/finance/dashboard/models.py` (`SubscriptionOut` only)
- Modify: `apps/api/finance/dashboard/subscriptions.py` (the SELECT only)
- Modify: `apps/api/finance/agent/semantic/subscriptions.yaml`
- Modify: `apps/api/finance/agent/semantic/examples.yaml`
- Modify: `apps/api/finance/agent/semantic/transactions.yaml` (the phrase "typical charge")
- Modify: `apps/api/tests/test_views.py`
- Modify: `apps/api/tests/test_labels.py` (one merge assertion)
- Modify: `apps/api/tests/test_agent_views.py` (`SUBSCRIPTIONS` list)
- Modify: `apps/web/src/app/subscriptions/page.tsx` (one field rename so the build keeps passing)
- Test: `apps/api/tests/test_views.py`

**Interfaces:**
- Consumes: `v_transactions_enriched` (`is_subscription`, `tx_type`, `amount`, `merchant_id`, `booked_at`, `merchant_name`)
- Produces: `merchants.cadence` null or `monthly` | `quarterly` | `yearly`. View columns `merchant_id`, `merchant_name`, `charges`, `last_charge`, `latest_amount`, `cadence`, `cadence_source`, `monthly_equivalent`, `active`. `agent.subscriptions` the same without `merchant_id`. `merge_merchants` coalesces `cadence`. `SubscriptionOut` has `cadence: Literal["monthly","quarterly","yearly"]`, `cadence_source: Literal["auto","user"]`, `latest_amount: Decimal` and no `typical_amount`.

- [ ] **Step 1: Write the failing tests**

Add to `apps/api/tests/test_views.py`. Keep the two existing subscription tests, and point them at `latest_amount` instead of `typical_amount`. Their numbers do not change: every charge in those fixtures is the same amount, and their gaps stay monthly and yearly. Add `from datetime import timedelta` to the imports.

```python
def test_a_charge_every_91_days_is_quarterly_at_a_third_of_the_latest_charge(db_conn, make_tx):
    shop = db_conn.execute(
        "insert into merchants (name, match_key) values ('ZZTEST QUARTER', 'ZZTESTQUARTER') returning id"
    ).fetchone()["id"]
    for day, amount in (
        (date(1999, 1, 1), "-30.00"),
        (date(1999, 4, 2), "-60.00"),  # 91 days, and the later price
    ):
        tx = make_tx(amount, "ZZTEST QUARTER", booked_at=day)
        db_conn.execute(
            "update transactions set merchant_id = %s, is_subscription = true,"
            " category_slug = 'entertainment', tx_type = 'expense' where id = %s",
            (shop, tx),
        )
    row = db_conn.execute(
        "select cadence, cadence_source, latest_amount, monthly_equivalent, active"
        " from v_subscriptions where merchant_id = %s",
        (shop,),
    ).fetchone()
    assert (
        row["cadence"],
        row["cadence_source"],
        row["latest_amount"],
        row["monthly_equivalent"],
    ) == ("quarterly", "auto", Decimal("60.00"), Decimal("20.00"))


def test_a_manual_cadence_beats_the_gap_and_can_be_cleared(db_conn, make_tx):
    shop = db_conn.execute(
        "insert into merchants (name, match_key, cadence)"
        " values ('ZZTEST PIN', 'ZZTESTPIN', 'yearly') returning id"
    ).fetchone()["id"]
    for day in (date(1999, 1, 3), date(1999, 2, 3)):
        tx = make_tx("-12.00", "ZZTEST PIN", booked_at=day)
        db_conn.execute(
            "update transactions set merchant_id = %s, is_subscription = true,"
            " category_slug = 'entertainment', tx_type = 'expense' where id = %s",
            (shop, tx),
        )
    pinned = db_conn.execute(
        "select cadence, cadence_source, monthly_equivalent from v_subscriptions where merchant_id = %s",
        (shop,),
    ).fetchone()
    assert (pinned["cadence"], pinned["cadence_source"], pinned["monthly_equivalent"]) == (
        "yearly",
        "user",
        Decimal("1.00"),
    )
    db_conn.execute("update merchants set cadence = null where id = %s", (shop,))
    cleared = db_conn.execute(
        "select cadence, cadence_source from v_subscriptions where merchant_id = %s", (shop,)
    ).fetchone()
    assert (cleared["cadence"], cleared["cadence_source"]) == ("monthly", "auto")


def test_the_larger_charge_of_the_latest_day_is_the_latest_amount(db_conn, make_tx):
    shop = db_conn.execute(
        "insert into merchants (name, match_key) values ('ZZTEST SAMEDAY', 'ZZTESTSAMEDAY') returning id"
    ).fetchone()["id"]
    for day, amount in (
        (date(1999, 1, 5), "-50.00"),
        (date(1999, 2, 5), "-7.00"),
        (date(1999, 2, 5), "-12.00"),
    ):
        tx = make_tx(amount, "ZZTEST SAMEDAY", booked_at=day)
        db_conn.execute(
            "update transactions set merchant_id = %s, is_subscription = true,"
            " category_slug = 'entertainment', tx_type = 'expense' where id = %s",
            (shop, tx),
        )
    row = db_conn.execute(
        "select latest_amount from v_subscriptions where merchant_id = %s", (shop,)
    ).fetchone()
    assert row["latest_amount"] == Decimal("12.00")


def _anchored_subscription(db_conn, make_tx, name, days_before_latest):
    """Charges counted back from the ledger's latest day. An anchor row on that day keeps the
    latest day fixed when the ledger is empty."""
    latest = db_conn.execute("select max(booked_at) as d from transactions").fetchone()["d"]
    latest = latest or date(1999, 12, 31)
    make_tx("-1.00", "ZZTEST ANCHOR", booked_at=latest)
    shop = db_conn.execute(
        "insert into merchants (name, match_key) values (%s, %s) returning id",
        (name, name.replace(" ", "")),
    ).fetchone()["id"]
    for days in days_before_latest:
        tx = make_tx("-30.00", name, booked_at=latest - timedelta(days=days))
        db_conn.execute(
            "update transactions set merchant_id = %s, is_subscription = true,"
            " category_slug = 'entertainment', tx_type = 'expense' where id = %s",
            (shop, tx),
        )
    return shop


def test_a_quarterly_plan_stays_active_for_120_days(db_conn, make_tx):
    # 80 days after its last charge: out of the monthly 45-day window, inside the quarterly one.
    running = _anchored_subscription(db_conn, make_tx, "ZZTEST QRUNNING", (171, 80))
    # 130 days after its last charge: past the quarterly window too.
    ended = _anchored_subscription(db_conn, make_tx, "ZZTEST QENDED", (221, 130))
    rows = {
        r["merchant_id"]: (r["cadence"], r["active"])
        for r in db_conn.execute(
            "select merchant_id, cadence, active from v_subscriptions where merchant_id = any(%s)",
            ([running, ended],),
        ).fetchall()
    }
    assert rows == {running: ("quarterly", True), ended: ("quarterly", False)}
```

Add to the merge test in `apps/api/tests/test_labels.py` that already merges two merchants (`test_merge_repoints_rows_and_keeps_the_target_default`): give the survivor `cadence = 'yearly'` and the source `cadence = 'monthly'`, and assert the survivor still has `yearly` after `merge_merchants`. Give a second pair where only the source has `quarterly`, and assert the survivor gains `quarterly`. `_merchant(conn, name, **columns)` takes `cadence=` once the column exists.

Update `SUBSCRIPTIONS` in `apps/api/tests/test_agent_views.py` to:

```python
SUBSCRIPTIONS = [
    "merchant",
    "charges",
    "last_charge",
    "latest_amount",
    "cadence",
    "cadence_source",
    "monthly_equivalent",
    "active",
]
```

- [ ] **Step 2: Run the tests to verify they fail**

Apply the migration only after Step 3. Before the migration, run:

```bash
cd apps/api && uv run pytest tests/test_views.py::test_a_charge_every_91_days_is_quarterly_at_a_third_of_the_latest_charge -m integration -q
```

Expected: FAIL because `cadence` on `merchants` or `latest_amount` does not exist.

- [ ] **Step 3: Write the migration and the merge update**

`supabase/migrations/20261014120000_subscription_cadence.sql`:

```sql
-- Quality of life, plan 1: a subscription cadence the user can set
-- (docs/superpowers/specs/2026-10-14-quality-of-life-design.md, section 3).

alter table merchants
  add column cadence text check (cadence in ('monthly', 'quarterly', 'yearly'));

drop view if exists agent.subscriptions;
drop view if exists public.v_subscriptions;

create view v_subscriptions as
with charges as (
  select merchant_id, booked_at, -amount as charge,
         booked_at - lag(booked_at) over (
           partition by merchant_id order by booked_at, id
         ) as gap_days
  from v_transactions_enriched
  where is_subscription and tx_type = 'expense' and amount < 0 and merchant_id is not null
), per_merchant as (
  select merchant_id, count(*) as charges, max(booked_at) as last_charge,
         percentile_cont(0.5) within group (order by gap_days) as median_gap
  from charges
  group by merchant_id
), latest_charge as (
  select distinct on (merchant_id) merchant_id, charge as latest_amount
  from charges
  order by merchant_id, booked_at desc, charge desc
), latest as (
  select max(booked_at) as latest_day from transactions
), detected as (
  select p.merchant_id, p.charges, p.last_charge, l.latest_amount,
         case
           when p.median_gap is null or p.median_gap <= 60 then 'monthly'
           when p.median_gap <= 200 then 'quarterly'
           else 'yearly'
         end as detected_cadence
  from per_merchant p
  join latest_charge l using (merchant_id)
)
select d.merchant_id, m.name as merchant_name, d.charges, d.last_charge, d.latest_amount,
       coalesce(m.cadence, d.detected_cadence) as cadence,
       case when m.cadence is null then 'auto' else 'user' end as cadence_source,
       round(d.latest_amount / case coalesce(m.cadence, d.detected_cadence)
         when 'yearly' then 12 when 'quarterly' then 3 else 1 end, 2) as monthly_equivalent,
       d.last_charge >= latest.latest_day - case coalesce(m.cadence, d.detected_cadence)
         when 'yearly' then 400 when 'quarterly' then 120 else 45 end as active
from detected d
join merchants m on m.id = d.merchant_id
cross join latest;

comment on view v_subscriptions is
  'Flagged money-out expenses per merchant. Cadence is merchants.cadence when set, otherwise '
  'the median gap: up to 60 days monthly, 61 to 200 every 3 months, over 200 yearly. A single '
  'charge is monthly. The amount is the latest charge. Active is 45, 120 or 400 days before '
  'the latest imported transaction (docs/money-rules.md).';

create view agent.subscriptions as
select merchant_name as merchant, charges, last_charge, latest_amount, cadence, cadence_source,
       monthly_equivalent, active
from public.v_subscriptions;

grant select on agent.subscriptions to agent_reader;
```

In `merge_merchants`, extend the update that coalesces `category_slug` and `is_subscription`:

```python
"update merchants i set category_slug = coalesce(i.category_slug, s.category_slug),"
" is_subscription = coalesce(i.is_subscription, s.is_subscription),"
" cadence = coalesce(i.cadence, s.cadence), confirmed = true"
```

Move the readers to the new columns, without the ended split (Task 2):

- `models.py`: `SubscriptionOut` replaces `typical_amount` with `latest_amount: Decimal`, adds `cadence_source: Literal["auto", "user"]`, and `cadence` becomes `Literal["monthly", "quarterly", "yearly"]`, or a quarterly row fails validation.
- `subscriptions.py`: the SELECT reads `latest_amount, cadence_source` instead of `typical_amount`. It still reads only `where active`.
- `apps/web/src/app/subscriptions/page.tsx`: `item.typical_amount` becomes `item.latest_amount`, and `CADENCE` gains `quarterly: "Every 3 months"`. Task 3 rebuilds this page; this only keeps the build green.
- `examples.yaml`, the subscriptions example: `SELECT merchant, cadence, cadence_source, latest_amount, monthly_equivalent, last_charge, ...`.
- `transactions.yaml`: "typical charge" becomes "latest charge".
- `subscriptions.yaml`: `check_layer` requires every column to be described and every description to name a column. Replace the file's `use_for` third line with "When a subscription was last charged, and its latest amount." and its `attributes` with:

```yaml
attributes:
  - attribute: merchant
    kind: dimension
    description: >
      Business name, the same names as transactions.merchant. Names depend on the user's data:
      look them up before filtering.
  - attribute: charges
    kind: measure
    description: Number of charges flagged as a subscription for this merchant.
  - attribute: last_charge
    kind: time
    description: Date of the latest charge.
  - attribute: latest_amount
    kind: measure
    description: >
      The latest charge, a positive amount in euros. When two charges share the latest day, the
      larger one.
  - attribute: cadence
    kind: dimension
    description: >
      How often it charges. When cadence_source is user, the user set it in the app and it wins
      over the gaps between charges; otherwise it comes from the median gap.
    allowed_values:
      - value: monthly
        meaning: a median gap of 60 days or less, a single charge so far, or set by the user
      - value: quarterly
        meaning: every 3 months, a median gap of 61 to 200 days, or set by the user
      - value: yearly
        meaning: a median gap over 200 days, or set by the user
  - attribute: cadence_source
    kind: dimension
    description: Who decided the cadence.
    allowed_values:
      - value: auto
        meaning: detected from the gaps between charges
      - value: user
        meaning: set by the user in the app; it wins over the gaps
  - attribute: monthly_equivalent
    kind: measure
    description: >
      The latest amount divided by 1 (monthly), 3 (quarterly) or 12 (yearly), rounded to the
      cent. Summed over active rows, it is the monthly cost of subscriptions.
  - attribute: active
    kind: flag
    description: >
      true when the last charge is within 45 days (monthly), 120 days (quarterly) or 400 days
      (yearly) of the latest imported movement, not of today, so an old import does not make
      every subscription look cancelled.
```

The model description says "with the cadence, latest amount and active status the app computes from those charges".

- [ ] **Step 4: Apply the migration and run the tests**

```bash
supabase migration up --local
cd apps/api && uv run task lint && uv run task test
cd apps/api && uv run pytest tests/test_views.py tests/test_labels.py tests/test_agent_views.py tests/test_catalog_db.py tests/test_dashboard_api.py -m integration -q
cd apps/web && npx tsc --noEmit
```

Expected: PASS. `test_catalog_db` fails if a YAML attribute has no column or a column has no attribute. `tsc` needs the regenerated types: start the API and run `npm run gen:api` first. If `supabase migration up` is unavailable, apply that file with `psql` against the local database on port 54322. Do not reset the database.

- [ ] **Step 5: Commit**

```bash
git add supabase/migrations/20261014120000_subscription_cadence.sql apps/api/finance/categorization/labels.py apps/api/finance/dashboard/models.py apps/api/finance/dashboard/subscriptions.py apps/api/finance/agent/semantic apps/api/tests/test_views.py apps/api/tests/test_labels.py apps/api/tests/test_agent_views.py apps/web/src/app/subscriptions/page.tsx apps/web/src/lib/api-types.ts
git commit -m "$(cat <<'EOF'
feat: detect a quarterly subscription and keep a cadence set by hand

EOF
)"
```

---

### Task 2: Ended subscriptions and the cadence endpoint

**Files:**
- Modify: `apps/api/finance/dashboard/models.py` (`Subscriptions.ended`)
- Modify: `apps/api/finance/dashboard/subscriptions.py`
- Modify: `apps/api/finance/api/merchants.py`
- Modify: `docs/money-rules.md` (the Subscriptions section)
- Modify: `apps/api/tests/test_dashboard_api.py`
- Test: `apps/api/tests/test_dashboard_api.py`

**Interfaces:**
- Consumes: the view and `SubscriptionOut` from Task 1
- Produces: `Subscriptions` gains `ended: list[SubscriptionOut]`. Totals sum `items` only. `PATCH /merchants/{id}/cadence` body `CadenceUpdate` with `cadence: Literal["monthly","quarterly","yearly"] | None`, status 204.

- [ ] **Step 1: Write the failing tests**

In `apps/api/tests/test_dashboard_api.py`, add `timedelta` to the `datetime` import and:

```python
def test_ended_subscriptions_are_listed_apart_and_left_out_of_the_totals(client, db_conn, make_tx):
    latest = db_conn.execute("select max(booked_at) as d from transactions").fetchone()["d"]
    latest = latest or date(1999, 12, 31)
    make_tx("-1.00", "ZZTEST ANCHOR", booked_at=latest)
    # Every 91 days: quarterly. One last charged 80 days ago (running), one 130 days ago (ended).
    plans = {"ZZTEST QRUN": (171, 80), "ZZTEST QGONE": (221, 130)}
    for name, days in plans.items():
        shop = db_conn.execute(
            "insert into merchants (name, match_key) values (%s, %s) returning id",
            (name, name.replace(" ", "")),
        ).fetchone()["id"]
        for back in days:
            tx = make_tx("-90.00", name, booked_at=latest - timedelta(days=back))
            db_conn.execute(
                "update transactions set merchant_id = %s, is_subscription = true,"
                " category_slug = 'entertainment', tx_type = 'expense' where id = %s",
                (shop, tx),
            )
    body = client.get("/dashboard/subscriptions").json()

    def names(rows):  # only the synthetic names: a failure never prints the real ledger's
        return {r["merchant_name"] for r in rows if r["merchant_name"].startswith("ZZTEST")}

    assert names(body["items"]) == {"ZZTEST QRUN"}
    assert names(body["ended"]) == {"ZZTEST QGONE"}
    [running] = [r for r in body["items"] if r["merchant_name"] == "ZZTEST QRUN"]
    assert (running["cadence"], running["monthly_equivalent"]) == ("quarterly", "30.00")
    # The ended plan's 30.00 a month is not in the totals.
    monthly = Decimal(body["monthly_total"])
    assert monthly == sum((Decimal(r["monthly_equivalent"]) for r in body["items"]), Decimal(0))
    assert Decimal(body["yearly_total"]) == monthly * 12
```

Add a focused test for the endpoint:

```python
def test_patch_cadence_sets_and_clears(client, db_conn):
    merchant = db_conn.execute(
        "insert into merchants (name, match_key) values ('ZZTEST CADENCE', 'ZZTESTCADENCE') returning id"
    ).fetchone()["id"]
    assert client.patch(f"/merchants/{merchant}/cadence", json={"cadence": "quarterly"}).status_code == 204
    assert db_conn.execute("select cadence from merchants where id = %s", (merchant,)).fetchone()["cadence"] == "quarterly"
    assert client.patch(f"/merchants/{merchant}/cadence", json={"cadence": None}).status_code == 204
    assert db_conn.execute("select cadence from merchants where id = %s", (merchant,)).fetchone()["cadence"] is None
    missing = "00000000-0000-0000-0000-000000000099"
    assert client.patch(f"/merchants/{missing}/cadence", json={"cadence": "monthly"}).status_code == 404
    assert client.patch(f"/merchants/{merchant}/cadence", json={"cadence": "weekly"}).status_code == 422
```

The `client` fixture in this file overrides `db` with `db_conn`, so the API sees the test's uncommitted rows and everything rolls back.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd apps/api && uv run pytest tests/test_dashboard_api.py -m integration -q -k "ended_subscriptions or patch_cadence"
```

Expected: FAIL. `ended` is missing from the response, and the PATCH route answers 405.

- [ ] **Step 3: Implement**

`subscriptions.py` reads every row (drop `where active`, select `active` too), splits on `active`, and sums `monthly_equivalent` over the active ones. Order both lists by `monthly_equivalent desc, merchant_name`. Keep the function name `active_subscriptions` and its two callers in `api/dashboard.py`; `summary` keeps counting `items`, so the overview card stays active-only.

```python
class CadenceUpdate(BaseModel):
    cadence: Literal["monthly", "quarterly", "yearly"] | None


@router.patch("/{merchant_id}/cadence", status_code=204)
def set_cadence(merchant_id: UUID, body: CadenceUpdate, conn: Db) -> Response:
    row = conn.execute(
        "update merchants set cadence = %s where id = %s returning id",
        (body.cadence, merchant_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"merchant {merchant_id}")
    return Response(status_code=204)
```

Replace the bullets of the Subscriptions section of `docs/money-rules.md` that describe the old rule (typical amount, cadence, single charge, active) with the rule in spec section 3.1: three cadences, the bands, a user cadence wins, the latest charge (the larger one on a shared day), ÷1, ÷3, ÷12, and the 45/120/400-day windows. Keep the unchanged bullets: only money going out counts, and credit-card subscriptions are not listed.

- [ ] **Step 4: Run the tests**

```bash
cd apps/api && uv run task lint && uv run task test && uv run pytest tests/test_dashboard_api.py tests/test_agent_views.py tests/test_catalog_db.py -m integration -q
```

Expected: PASS, including the existing `test_a_subscription_is_active_relative_to_the_latest_import`.

- [ ] **Step 5: Commit**

```bash
git add apps/api/finance/dashboard apps/api/finance/api/merchants.py docs/money-rules.md apps/api/tests/test_dashboard_api.py
git commit -m "$(cat <<'EOF'
feat: return ended subscriptions and let a cadence be set or cleared

EOF
)"
```

---

### Task 3: The subscriptions page

**Files:**
- Create: `apps/web/src/components/subscriptions/cadence-select.tsx`
- Create: `apps/web/src/components/subscriptions/subscription-table.tsx`
- Modify: `apps/web/src/app/subscriptions/page.tsx`
- Modify: `apps/web/src/app/page.tsx` (the overview card copy)
- Modify: `apps/web/src/lib/api-types.ts` (generated)

**Interfaces:**
- Consumes: `Schemas["SubscriptionOut"]` and `Schemas["Subscriptions"]` from Task 2, including `ended`
- Produces: `CadenceSelect` with props `{ merchantId: string; merchantName: string; cadence: "monthly" | "quarterly" | "yearly" | null; source: "auto" | "user" }`. `cadence` is the effective cadence; null only when nothing is detected yet (plan 2's merchant page without flagged charges). Plan 2 imports it.

- [ ] **Step 1: Regenerate the types**

Start the API and run `cd apps/web && npm run gen:api`. `Subscriptions` must contain `ended` (Task 2); `SubscriptionOut` already has `latest_amount`, `cadence_source` and `quarterly` from Task 1.

- [ ] **Step 2: Build the select**

`CadenceSelect` is a client component. Options: `auto`, `monthly`, `quarterly`, `yearly`, labelled Auto, Monthly, Every 3 months, Yearly. The value is `auto` when `source` is `auto`, otherwise `cadence`. The trigger text when auto is `Auto · {detected label}`, or `Auto` when `cadence` is null. It PATCHes `/merchants/{id}/cadence` with `{ cadence: null }` for Auto and the value otherwise. While pending, the trigger is disabled. On failure, toast the API detail, leave the previous value selected, and the trigger keeps focus (it never unmounts on failure). On success, `router.refresh()`; a row that moves between the active list and Ended remounts, and losing focus then is accepted. `aria-label` is `Cadence for {merchantName}`. Use the repo's `Select` from `@/components/ui/select` the way `explorer-filters.tsx` does (`items`, `value`, `onValueChange`).

- [ ] **Step 3: Build the table and the page**

`subscription-table.tsx` renders the columns from spec section 3.5. Below `sm`, the amount column is not rendered. The merchant link is `/merchants/{id}?period=last_12_months`.

The page keeps the three totals from `items` only. The intro replaces the 45/400 sentence with the three windows and says the amount is the latest charge. Ended is a `<details>` closed by default, summary `Ended ({ended.length})`, omitted when empty, with the explanation from spec section 3.5 and the same table.

The overview card description in `apps/web/src/app/page.tsx` names the three windows and the latest imported transaction. It does not mention a median.

- [ ] **Step 4: Check it in the browser**

Web gate, then recipe R2 because changing a cadence writes. On the scratch app: open `/subscriptions`, change one row to Every 3 months, reload, and see that value still selected. Set it back to Auto. Open Ended if it has rows and confirm the select is there at 390 px width. Open a merchant name and confirm the URL contains `period=last_12_months`.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/subscriptions apps/web/src/app/subscriptions/page.tsx apps/web/src/app/page.tsx apps/web/src/lib/api-types.ts
git commit -m "$(cat <<'EOF'
feat: edit a subscription cadence from the list, including on a phone

EOF
)"
```

---

### Task 4: Folded rows and the no-merchant filter

**Files:**
- Modify: `apps/api/finance/dashboard/models.py`
- Modify: `apps/api/finance/dashboard/breakdowns.py`
- Modify: `apps/api/finance/dashboard/filters.py`
- Modify: `apps/api/finance/dashboard/transactions.py`
- Modify: `apps/api/finance/api/transactions.py`
- Modify: `apps/api/finance/api/dashboard.py`
- Modify: `apps/api/tests/test_breakdowns.py`
- Modify: `apps/api/tests/test_transactions_api.py`
- Test: those two test files

**Interfaces:**
- Consumes: `breakdown()` and `WHERE`
- Produces: `BreakdownRow.rows: list[BreakdownRow] = []`, `BreakdownRow.category_count: int = 1`, `BreakdownRow.top_categories: list[str] = []`. `Scope.no_merchant: bool = False`. Query param `merchant_id` is a UUID or `none`.

- [ ] **Step 1: Write the failing tests**

In `test_breakdowns.py`, the existing fold test (`top=2`) asserts the `_other` row's `rows` contain the tail keys, and each child's `share` is the share it had as its own row. Add a case where a group exists only in the previous period: `_other.previous` includes that group's amount, and that key is not in `rows`.

Assert a merchant with two categories in one period has `category_count == 2`.

In `test_transactions_api.py`, `GET /transactions?merchant_id=none` returns only rows whose `merchant_id` is null, and `merchant_id=nope` returns 422.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd apps/api && uv run pytest tests/test_breakdowns.py::test_the_folded_tail_is_kept_on_the_other_row -m integration -q
```

Expected: FAIL because `rows` is not a field. Name the test exactly that, and write it in Step 1 before this run.

- [ ] **Step 3: Implement**

In `breakdown`, the tail rows are already built before summing. Attach them:

```python
head.append(
    BreakdownRow(
        # ... the existing _other fields ...
        rows=tail,
    )
)
```

Add `count(distinct coalesce(category_slug, 'uncategorized')) as category_count` to `_query` and pass it on every row. For `_other`, `category_count` is the sum of the children's counts only as a stored number; the hint does not use it. Set it to `len({row.category_slug for row in tail})`.

`top_categories`: `dashboard.py` after the group breakdown (the one with `top=None`), fill each group row's `top_categories` from the category breakdown computed with `top=None` for this request only, grouped by `level1`, top 3 by amount descending then slug. Do not fold that extra list into the response's `by_category`. The overview's `by_category` stays top 5.

`WHERE` becomes:

```sql
and (
  (%(no_merchant)s and merchant_id is null)
  or (not %(no_merchant)s and (%(merchant_id)s::uuid is null or merchant_id = %(merchant_id)s))
)
```

`Scope.params` adds `"no_merchant": self.no_merchant`. `list_transactions` takes `merchant_id: str | None = None`. `none` sets `no_merchant=True` and passes no uuid. A value that is neither `none` nor a UUID raises 422. A real UUID is parsed with `UUID()`.

- [ ] **Step 4: Run the tests**

```bash
cd apps/api && uv run task lint && uv run pytest tests/test_breakdowns.py tests/test_transactions_api.py -m integration -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/finance/dashboard apps/api/finance/api/transactions.py apps/api/finance/api/dashboard.py apps/api/tests/test_breakdowns.py apps/api/tests/test_transactions_api.py
git commit -m "$(cat <<'EOF'
feat: send folded breakdown rows and filter transactions with no merchant

EOF
)"
```

---

### Task 5: Expand the folded row

**Files:**
- Create: `apps/web/src/components/breakdown/folded-rows.tsx`
- Modify: `apps/web/src/components/breakdown/breakdown-table.tsx`
- Modify: `apps/web/src/components/detail/detail-page.tsx` (its hint override also covers `rows`)
- Modify: `apps/web/src/lib/breakdown.ts`
- Modify: `apps/web/src/lib/labels.ts`
- Modify: `apps/web/src/lib/params.ts`
- Modify: `apps/web/src/components/pickers/merchant-picker.tsx`
- Modify: `apps/web/src/app/transactions/explorer-filters.tsx`
- Modify: `apps/web/src/lib/breakdown.test.ts`
- Modify: `apps/web/src/lib/labels.test.ts`
- Modify: `apps/web/src/lib/params.test.ts`
- Modify: `apps/web/src/lib/api-types.ts`

**Interfaces:**
- Consumes: `BreakdownRow.rows` and `category_count` from Task 4
- Produces: `BreakdownItem.rows: BreakdownItem[]`. `parseExplorer` accepts `merchant_id=none`. `rowHint` for a merchant with `category_count > 1` returns `{n} categories · {count} transactions`.

- [ ] **Step 1: Write the failing unit tests**

`breakdownItems` maps `row.rows` through the same function, and a child keeps its href. `hrefOf` for a row with no `merchant_id` and key `category:groceries` is `withFilters("/transactions", filters, { tx_type: type, category: "groceries", merchant_id: "none" })`: the period, the accounts and the type are kept. On the income page that type is `income`, so assert both an expense and an income case. `parseExplorer` keeps `merchant_id=none` and still drops `merchant_id=nope`. `rowHint` of a merchant row with `category_count: 2` and `count: 4` is `2 categories · 4 transactions`.

Regenerate API types first so `rows` and `category_count` exist on `BreakdownRow`. The test helper `row()` in `labels.test.ts` and `breakdown.test.ts` must default the new fields.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd apps/web && npm test -- src/lib/breakdown.test.ts src/lib/labels.test.ts src/lib/params.test.ts
```

Expected: FAIL on the new assertions.

- [ ] **Step 3: Implement**

`folded-rows.tsx` is a client component. It receives the `_other` item and renders the button plus, when open, the child rows with `pl-6`. The button text is `Show {folded} merchants` or `Show {folded} categories` from the item name, and `Hide` when open. `aria-expanded` follows the state.

`BreakdownTable` renders `FoldedRows` when `item.key === "_other"` and `item.rows.length > 0`. Other rows stay as they are. Extract the existing row markup into one `BreakdownTableRow` in `breakdown-table.tsx`, so `FoldedRows` renders the subtotal row (with the button) and the children with the same cells, never a copy. `BreakdownTable` stays a server component; `FoldedRows` is the only client part. Do not lift the open state to the donut.

`detail-page.tsx` rewrites merchant hints to "N transactions" on visible rows only. Apply the same rewrite to `item.rows`, so a child of the folded row reads like a visible row.

`MerchantPicker` gains `allowNone?: boolean`. When true, the first option is `{ id: "none", name: "No merchant" }` and it is not a create. `explorer-filters.tsx` passes `allowNone` and, when the URL has `merchant_id=none`, the value is that option. Choosing it writes `merchant_id=none`. Choosing a merchant writes the uuid. Clearing writes undefined.

- [ ] **Step 4: Run the web gate and check the browser**

Read-only on :3000 is enough for expand. Open the overview Merchants view, expand the Other row, and confirm the donut's slice count did not change. Open a "No merchant" child if one is visible and confirm the transactions URL. At 390 px the expanded table does not scroll sideways.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/breakdown apps/web/src/components/detail/detail-page.tsx apps/web/src/lib/breakdown.ts apps/web/src/lib/breakdown.test.ts apps/web/src/lib/labels.ts apps/web/src/lib/labels.test.ts apps/web/src/lib/params.ts apps/web/src/lib/params.test.ts apps/web/src/components/pickers/merchant-picker.tsx apps/web/src/app/transactions/explorer-filters.tsx apps/web/src/lib/api-types.ts
git commit -m "$(cat <<'EOF'
feat: expand a folded breakdown row and link rows with no merchant

EOF
)"
```

---

### Task 6: The panel on every transaction list

**Files:**
- Create: `apps/web/src/components/transactions/transaction-browser.tsx`
- Modify: `apps/web/src/app/transactions/transaction-list.tsx`
- Modify: `apps/web/src/app/transactions/transaction-panel.tsx`
- Modify: `apps/web/src/components/detail/detail-page.tsx` (new prop `merchants`)
- Modify: `apps/web/src/components/transactions/transaction-table.tsx`
- Modify: the five pages that render `DetailPage`, which fetch `/merchants?limit=5000` in their `Promise.all` and pass it: `app/spending/[group]/page.tsx`, `app/spending/[group]/[category]/page.tsx`, `app/merchants/[id]/page.tsx`, `app/income/page.tsx`, `app/income/[category]/page.tsx`

**Interfaces:**
- Consumes: `TransactionPanel` and `TransactionTable` as they are
- Produces: `TransactionBrowser` with props `{ items: Transaction[]; categories: CategoryOut[]; merchants: MerchantOut[]; showSource?: boolean; onSaved?: (change: LabelChange) => void }`. Detail pages omit `onSaved` and rely on `router.refresh()` inside the panel.

- [ ] **Step 1: Move the open state**

`transaction-list.tsx` today holds `selected` and renders the panel. Move that pair into `TransactionBrowser`, and make `transaction-list.tsx` render the browser plus the load-more control it already has. `detail-page.tsx` replaces `<TransactionTable items={detail.latest} />` with `<TransactionBrowser items={detail.latest} categories={categories} merchants={merchants} />`. `TransactionPanel` requires `onSaved`; the browser passes a no-op when its own `onSaved` is absent.

`TransactionTable` already takes `onOpen`. The browser passes it.

- [ ] **Step 2: The warning and the discard question**

Under the category field, when `tx.merchant_id` is set, add a `FieldDescription`: `Saving can apply this category to every transaction of {tx.merchant_name}.`

When a category is selected, the category field's existing description starts with `{label(level1)} › {label(slug)}. ` and then the sentence it has today.

The dirty state lives in `PanelForm`, but Escape and the backdrop reach the `Sheet`'s `onOpenChange` in `TransactionPanel`. Wire it like this:

- `TransactionPanel` holds `dirty` (boolean state) and `discarding` (boolean state). `PanelForm` gets `onDirtyChange(dirty: boolean)` and calls it from an effect on `labelChanged || noteChanged`. `PanelForm` remounts per transaction (`key={tx.id}`), so `TransactionPanel` resets `dirty` to false whenever it opens a new `tx`.
- `requestClose()` in `TransactionPanel`: when `dirty`, set `discarding`; otherwise call `onClose`. `Sheet onOpenChange(false)` and the form's Cancel button both call `requestClose`. The `Sheet` is controlled (`open={tx !== null}`), so not calling `onClose` keeps it open.
- The `AlertDialog` "Discard unsaved changes?" with Keep editing (closes the dialog only) and Discard (clears `dirty`, then `onClose`) lives in `TransactionPanel`.
- `save()` keeps calling `onClose` directly, never `requestClose`: after a save the form still differs from the stale `tx` prop, and asking "Discard?" then would be wrong.

- [ ] **Step 3: Check it in the browser (R2)**

On the scratch app, open a merchant page, open a transaction, change the category, press Escape, and confirm the dialog. Choose Keep editing and confirm the new category is still selected. Discard and confirm the sheet is gone. Save with "Only this one" and reload the merchant page: the row shows the new category.

- [ ] **Step 4: Web gate and commit**

```bash
git add apps/web/src/components/transactions apps/web/src/app/transactions apps/web/src/components/detail/detail-page.tsx apps/web/src/app/spending apps/web/src/app/merchants apps/web/src/app/income
git commit -m "$(cat <<'EOF'
feat: open the transaction panel from every list and ask before discarding edits

EOF
)"
```

---

### Task 7: The small QA fixes

**Files:**
- Modify: `apps/web/src/lib/delta.ts`
- Modify: `apps/web/src/lib/delta.test.ts`
- Modify: `apps/web/src/lib/labels.ts`
- Modify: `apps/web/src/lib/labels.test.ts`
- Modify: `apps/web/src/app/transactions/explorer-filters.tsx`
- Modify: `apps/web/src/components/pickers/merchant-picker.tsx`
- Modify: `apps/web/src/components/shell/nav-links.tsx`
- Create: `apps/web/src/components/shell/mobile-nav.tsx`
- Modify: `apps/api/finance/dashboard/models.py` (`TransactionPage.transfers`)
- Modify: `apps/api/finance/dashboard/transactions.py`
- Modify: `apps/web/src/app/transactions/page.tsx`
- Test: `apps/web/src/lib/delta.test.ts`, `apps/api/tests/test_transactions_api.py`

**Interfaces:**
- Consumes: `groupHint`, `delta`, `TransactionPage`
- Produces: `delta` text `>999%` when the percent change is greater than 999. `TransactionPage.transfers: Decimal`. `groupHint` uses `row.top_categories` when that list is non-empty.

- [ ] **Step 1: Write the failing tests**

`delta(2000, 1, "down", "percent")` has `text` `>999%` and `direction` `up`. `delta(5, 0, "down", "percent")` stays `{ kind: "new" }`. `delta(1, 1000, "down", "percent")` is not capped.

`rowHint` of a group row whose `top_categories` are `["fuel", "parking_tolls"]` returns `Fuel, parking tolls`, not the alphabetical taxonomy line: the same formatting as `groupHint` (slug words, only the first letter capitalized, `, ` between). Plan 2 switches it to stored names. `groupHint` stays the fallback when `top_categories` is empty.

In `test_transactions_api.py`, the totals test asserts `transfers` is the sum of `abs(amount)` of the transfer rows in the filtered set. Read the fixture before writing the number, and add a transfer row if it has none.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd apps/web && npm test -- src/lib/delta.test.ts src/lib/labels.test.ts
cd apps/api && uv run pytest tests/test_transactions_api.py -m integration -q
```

Expected: FAIL on `>999%`, on the group hint, and on the missing `transfers` field.

- [ ] **Step 3: Implement the four UI fixes and the transfer total**

Search: in `explorer-filters.tsx`, a 300 ms timeout after `onType` calls `router.replace` with the trimmed `q`. Enter clears the timeout and replaces immediately. An empty box still clears `q` at once. Clear the timeout on unmount. Do not use `router.push` for search.

The box follows the URL today (`if (explorer.q !== urlQ) { ...; setQ(explorer.q ?? "") }`). With a debounce that overwrites what was typed while a replace was in flight: the URL lands on "ab" after the user typed "abc". Keep a `sent` state, set to the trimmed value each time the box itself writes `q`. In the follow block, still update `urlQ`, but call `setQ` only when `explorer.q !== sent` (a change from elsewhere: Back, Clear filters). Use state, not a ref: refs are not read during render here.

Merchant hint: `MerchantPicker` shows `Showing 50 of {n} · type to search` when `allowCreate` is false and the matching count is greater than 50. Count with the same matcher the list uses, as the Base UI docs show for `limit`: take `contains` from `Combobox.useFilter()` (`import { Combobox } from "@base-ui/react/combobox"`). Count `merchants` whose name `contains` the trimmed query, or all of them when the query is empty. Check through Context7 whether the Root's default filter matches `useFilter()`'s `contains`. If not, pass that `contains` as the Root's `filter` prop, so the list and the count never disagree. Render the hint as a line under the input with an id, appended to the input's `aria-describedby`.

`rowHint`, for a group row with a non-empty `top_categories`, formats those slugs in order the way `groupHint` does. `groupHint` remains the fallback when the list is empty.

`mobile-nav.tsx`: a Menu button, `className` including `sm:hidden`, opens a `Sheet` listing `ITEMS` from `nav-links.tsx`. Export `ITEMS` from `nav-links.tsx`. The review entry shows the badge. The sheet is controlled and closes when a link is clicked, so it is not left open over the next page. `nav-links.tsx` hides the scrolling `<nav>` below `sm` (`hidden sm:flex`) and renders `MobileNav` beside it. The scroll-into-view effect stays on the desktop row.

Transfers: add to `_TOTALS`:

```sql
coalesce(sum(abs(amount)) filter (where tx_type = 'transfer'), 0) as transfers
```

The header appends ` · incl. {money(transfers)} transfers` when `transfers > 0`. Always render a button `aria-label="What these totals include"` that opens a popover with: "In and out are cash flow: every credit and debit in this list, including transfers and refunds. Income and expenses on Overview leave transfers out, and a refund reduces the spending of its category."

- [ ] **Step 4: Gates and a read-only browser check**

API integration test for `transfers`, web gate, then on :3000 at 390 px open the menu and reach Review, Imports and Settings. Search on `/transactions` and press Back once: the list is the page you came from, not the previous keystroke. A delta above 999% on a long range reads `>999%` if one is on screen; the unit test is the proof when the ledger has no such jump.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/lib/delta.ts apps/web/src/lib/delta.test.ts apps/web/src/lib/labels.ts apps/web/src/lib/labels.test.ts apps/web/src/app/transactions apps/web/src/components/pickers/merchant-picker.tsx apps/web/src/components/shell apps/api/finance/dashboard/models.py apps/api/finance/dashboard/transactions.py apps/api/tests/test_transactions_api.py apps/web/src/lib/api-types.ts
git commit -m "$(cat <<'EOF'
fix: search without history spam, cap huge deltas, and open the nav on a phone

EOF
)"
```

---

### Task 8: Dogfood the baseline

**Files:**
- Modify: `CLAUDE.md` only if a command or a page in the verification section is now wrong. Do not add a feature.

- [ ] **Step 1: Core checks**

`agent-browser skills get core`, session `qol1`, real data, read-only, on :3000. Cover `/`, a group, a category, a merchant, `/income`, `/transactions`, `/subscriptions`, at 1280 px and 390 px. Then recipe R2 for one cadence change, one panel save, and one discard.

- [ ] **Step 2: Dogfood**

`agent-browser skills get dogfood`, session `qol1-dogfood`. Write `dogfood-output/qol-1/report.md`. Include the four scenarios from spec section 10. Scenario 4 is plan 2; write "not in this PR" for it. No real merchant names in the report's headings.

- [ ] **Step 3: Commit the doc touch, if there was one**

```bash
git commit -m "$(cat <<'EOF'
docs: note the baseline quality-of-life checks

EOF
)"
```

Skip the commit when nothing changed.
