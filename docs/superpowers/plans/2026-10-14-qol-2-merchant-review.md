# Quality of life 2 — Merchant page, names and review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The merchant page sets the default category, the subscription and the cadence, names are readable in the app and the chat, groups stay distinguishable, and review separates duplicates from categories.

**Architecture:** Plan 1 already shipped `PATCH /merchants/{id}/cadence`, `CadenceSelect` and the transaction panel. This plan adds the merchant profile and a rename that does not relabel, stores display names beside the jev criteria, ranks every expense group for colour, and splits the review inbox.

**Tech Stack:** Postgres, FastAPI, Pydantic v2, Next.js 16.3.6, React 19, Base UI, Vitest, pytest, agent-browser.

**Spec:** `docs/superpowers/specs/2026-10-14-quality-of-life-design.md`, sections 7, 8, 9 and 10. Plan 1 must be merged first.

This plan was written from the plan 1 design and was not pre-executed in a sandbox. The name table in spec section 8.1 is the list to seed. A wording tweak in the YAML is in scope. Adding a slug is not.

## Global Constraints

- Everything in English: code, comments, docs, commits, UI copy (sentence case).
- Spec section 2 is binding.
- Never run `supabase db reset`. After the names migration, run `uv run finance seed` so existing categories gain names. Say so in the PR.
- jev still receives `what` and `not_for` only. Do not put display names into `jev_questions.py`.
- Writes go through recipe R2 (`docs/superpowers/plans/2026-09-25-slice-3b-interface.md`). Chat is not exercised against a paid model. If a task changes the semantic layer, `uv run pytest tests/test_catalog_db.py tests/test_agent_views.py -m integration` must pass, which checks the YAML against the views.
- Web gate: `cd apps/web && npm run lint && npx next typegen && npx tsc --noEmit && npm test && npm run build`.
- API gate: `cd apps/api && uv run task lint && uv run task test`, plus `test-integration` when the task says so.
- Regenerate `apps/web/src/lib/api-types.ts` after each API shape change.
- Conventional commits, no attribution trailer.
- No real bank data in code, tests, docs or commits. Screenshots only under `dogfood-output/qol-2/`.
- Read Context7 or the official docs before using a Next.js or Base UI API that this codebase does not already use.

## File Structure

| File | Responsibility |
|---|---|
| `apps/api/finance/categorization/labels.py` | `rename_merchant`, used by confirm and by PATCH |
| `apps/api/finance/api/merchants.py` | `GET /merchants/{id}`, `PATCH /merchants/{id}` |
| `apps/web/src/components/merchants/merchant-controls.tsx` | The control card |
| `supabase/migrations/20261014130000_display_names.sql` | `categories.name`, `category_groups`, view columns |
| `supabase/seed/categories.yaml` | `_name` and `name` from spec section 8.1 |
| `apps/api/finance/categorization/taxonomy.py` | Parser skips `_` keys and keeps `name` |
| `apps/web/src/lib/colors.ts` | Slots 1–8 and the grey scale |
| `apps/web/src/app/globals.css` | The new tokens and the hatch |
| `apps/api/finance/categorization/review_queue.py` | Merge cards, category cards from `needs_review` only |
| `apps/web/src/app/review/review-list.tsx` | Counts, filter, sort, skip |
| `apps/web/src/app/review/merge-card.tsx` | The yes/no question |

## Review Focus

1. Renaming a merchant onto an existing `match_key` merges, and does not write a user label. Task 1.
2. A merchant URL with no period becomes `last_12_months`, and the period picker agrees. Task 2.
3. The chat's `category_name` for `software_ai` is `Software & AI`, and jev's criterion text is unchanged. Task 3.
4. The ninth expense group by all-time spend is a grey, not `--chart-1`, and the folded row is hatched. Task 4.
5. A merchant that is only a merge suggestion is one card, and the badge equals categories plus merges. Task 5.

---

### Task 1: Rename without relabelling, and the profile

**Files:**
- Modify: `apps/api/finance/categorization/labels.py`
- Modify: `apps/api/finance/api/merchants.py`
- Modify: `apps/api/tests/test_labels.py`
- Modify: `apps/api/tests/test_review_api.py` (where the merchant routes are tested today)
- Test: `apps/api/tests/test_labels.py`

**Interfaces:**
- Consumes: `merge_merchants` and the `match_key` lookup inside `confirm_merchant`
- Produces: `rename_merchant(conn, merchant_id, name: str | None = None, merge_into_id: UUID | None = None) -> UUID`. `GET /merchants/{id}` returns `MerchantProfile`. `PATCH /merchants/{id}` body is `MerchantRename` with exactly one of `name` or `merge_into_id`. Response 200 `{ "id": "<survivor uuid>" }`.

- [ ] **Step 1: Write the failing test**

```python
def test_renaming_onto_an_existing_key_merges_without_a_user_label(db_conn, make_tx):
    source = _merchant(db_conn, "ZZTEST SOURCE", cadence="monthly")
    survivor = _merchant(db_conn, "ZZTEST SURVIVOR", cadence="yearly")
    tx = make_tx("-5.00", "ZZTEST SOURCE", booked_at=date(1999, 5, 1))
    db_conn.execute("update transactions set merchant_id = %s where id = %s", (source, tx))
    rename_merchant(db_conn, source, name="ZZTEST SURVIVOR")
    assert db_conn.execute("select id from merchants where id = %s", (source,)).fetchone() is None
    kept = db_conn.execute(
        "select cadence from merchants where id = %s", (survivor,)
    ).fetchone()["cadence"]
    assert kept == "yearly"
    moved = db_conn.execute("select merchant_id from transactions where id = %s", (tx,)).fetchone()
    assert moved["merchant_id"] == survivor
    labels = db_conn.execute(
        "select count(*) as n from transaction_labels where transaction_id = %s and source = 'user'",
        (tx,),
    ).fetchone()["n"]
    assert labels == 0
```

Use the file's existing `_merchant` helper. If it has no `cadence` argument, set the column with an update. The point is: merge happens, the survivor's cadence wins, and no user label is inserted.

Add an API test in `test_review_api.py` (its `client` fixture shares `db_conn`): `GET /merchants/{id}` returns `category_slug`, `cadence` and `rows_a_default_would_change`. A `jev` row and a `none` row count, a `user` row and a `rule` row do not. `GET` of an unknown id is 404. `PATCH` with both `name` and `merge_into_id`, or with neither, is 422. `PATCH` with a name that has no letter or digit is 422. `PATCH {"name": ...}` and `PATCH {"merge_into_id": ...}` of an unknown id are both 404. A plain rename returns 200 with the same id and the new name is stored.

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd apps/api && uv run pytest tests/test_labels.py::test_renaming_onto_an_existing_key_merges_without_a_user_label -m integration -q
```

Expected: FAIL because `rename_merchant` is not defined.

- [ ] **Step 3: Implement**

Move the name and `merge_into_id` block out of `confirm_merchant` into `rename_merchant`. `confirm_merchant` calls it first when `name` or `merge_into_id` is set, then does the category update it already does. `rename_merchant` alone does not update `category_slug` and does not run `_RELABEL_MERCHANT`.

The rename branch today updates without checking that the row exists (inside `confirm_merchant`, the later category update caught a missing id). Alone, it must not answer 200 for an unknown id: give the rename `update ... returning id` and raise `NotFound` when it returns nothing. `merge_merchants` already raises `NotFound`.

`MerchantProfile` fields are spec section 7. The effective cadence is a left join to `v_subscriptions` (`cadence` as `cadence_effective`, and `cadence_source`). The row count is the rows `_RELABEL_MERCHANT` can touch:

```sql
select count(*) as n from transactions
where merchant_id = %s and category_source in ('jev', 'merchant', 'none')
```

`MerchantRename` enforces "exactly one" with a Pydantic `model_validator(mode="after")`, so FastAPI answers 422. `PATCH` maps `NotFound` to 404 and `ValueError` (no letter or digit) to 422, like `review_merchant`. A success returns 200 `{ "id": "<survivor>" }`, which is the same id when the merchant was only renamed. The test asserts that body. Task 2 navigates when the returned id differs.

- [ ] **Step 4: Run the tests**

```bash
cd apps/api && uv run task lint && uv run pytest tests/test_labels.py tests/test_review_api.py -m integration -q
```

Expected: PASS, including the existing confirm tests. If `confirm_merchant` no longer relabels, those tests must still pass; that means the category update stayed in `confirm_merchant`.

- [ ] **Step 5: Commit**

```bash
git add apps/api/finance/categorization/labels.py apps/api/finance/api/merchants.py apps/api/tests/test_labels.py apps/api/tests/test_review_api.py
git commit -m "$(cat <<'EOF'
feat: rename or merge a merchant without rewriting its labels

EOF
)"
```

---

### Task 2: The merchant control card

**Files:**
- Create: `apps/web/src/components/merchants/merchant-controls.tsx`
- Modify: `apps/web/src/app/merchants/[id]/page.tsx`
- Modify: `apps/web/src/lib/params.ts` (`periodChanges`, and a `needsDefaultPeriod` helper)
- Modify: `apps/web/src/lib/params.test.ts`
- Modify: `apps/web/src/lib/api-types.ts`

**Interfaces:**
- Consumes: `CadenceSelect` from plan 1 (`cadence` may be null), the `merchants` list the merchant page already fetches since plan 1 task 6, `GET /merchants/{id}`, `PATCH /merchants/{id}`, `POST /merchants/{id}/review`, `DELETE /merchants/{id}/default`, `PATCH /merchants/{id}/cadence`
- Produces: the card described in spec section 7, rendered above the detail numbers

- [ ] **Step 1: Redirect when the URL has no period, and let "Latest month" stay a month**

The default period is written by leaving `period` out (`filterParams`, `periodChanges`). So "no `period`" also means "the user picked Latest month", and a redirect on that alone would make a single month unreachable on a merchant page.

Write the failing unit tests first in `params.test.ts`:

- `needsDefaultPeriod({})` is true; `needsDefaultPeriod({ month: "2026-07" })`, `needsDefaultPeriod({ period: "month" })` and `needsDefaultPeriod({ start: "2026-07-01", end: "2026-07-31" })` are false.
- `periodChanges({ period: "month" })` returns `period: "month"`, not `undefined`. Update the existing expectation at the `periodChanges({ period: "month", month: "2026-07" })` line to include `period=month`.

Then implement: `needsDefaultPeriod(params: SearchParams)` is true when none of `period`, `month`, `start` is present. `periodChanges` returns `period: choice.period` for every choice. `parseFilters` already reads `period=month` as the default, and `filterParams` still leaves it out of links, so other pages do not change.

In the merchant page, when `needsDefaultPeriod(query)`, `redirect` (from `next/navigation`) to the same path with `period=last_12_months` and every other param preserved. Check the Next.js 16 docs in `node_modules/next/dist/docs/` for `redirect` in a page that awaits `searchParams`.

- [ ] **Step 2: The card**

Fetch the profile in parallel with the detail. The card shows:

- Default category as `Group › Category` via `groupName` and `categoryName` (Task 3 adds them; until then `label`), or "No default". A category picker saves through `POST /review` with the current `is_subscription`. The line "Would change up to N transactions. Ones you or a rule labelled stay, and money out never becomes income." uses `rows_a_default_would_change`. Clear uses DELETE and the card says clearing also clears the subscription flag.
- The subscription switch. Disabled, with "Set a default category first.", when `category_slug` is null. Otherwise it posts the current category and the new flag. Under it: "Applies to the transactions you or a rule did not label." `is_subscription` null reads as off.
- `CadenceSelect`: when the stored `cadence` is set, pass `cadence={profile.cadence}` and `source="user"`. Otherwise pass `cadence={profile.cadence_effective}` (null without flagged charges, which reads plain "Auto") and `source="auto"`.
- Rename: a text field and a Save button. The PATCH body is `{ "name" }`. On `{ "id" }` different from the current id, `router.push` to that merchant, keeping the period.
- Merge: the merchant picker over the page's `merchants` without the current one, `allowCreate` false, Save sends `{ "merge_into_id" }`, then navigates to the returned id.

All of these refresh the page on success and toast the API detail on failure. Focus stays on the control that failed.

- [ ] **Step 3: Check it on a scratch database (R2)**

Open a merchant from Subscriptions and confirm the period is 12 months. Open a merchant URL with no params and confirm it redirects to 12 months; then pick "Latest month" in the period picker and confirm it stays on one month. Set a default category and confirm the "would change" count. Set the cadence and reload. Rename to a unique `ZZTEST` name, then rename it back. Do not leave a test merchant in the real database: this step is R2 only.

- [ ] **Step 4: Web gate and commit**

```bash
git add apps/web/src/components/merchants apps/web/src/app/merchants apps/web/src/lib/params.ts apps/web/src/lib/params.test.ts apps/web/src/lib/api-types.ts
git commit -m "$(cat <<'EOF'
feat: control a merchant's category, cadence and name from its page

EOF
)"
```

---

### Task 3: Display names

**Files:**
- Create: `supabase/migrations/20261014130000_display_names.sql`
- Modify: `supabase/seed/categories.yaml`
- Modify: `apps/api/finance/categorization/taxonomy.py`
- Modify: `apps/api/finance/categorization/seed.py`
- Modify: `apps/api/finance/api/categories.py`
- Modify: `apps/api/finance/agent/semantic/transactions.yaml`
- Modify: `apps/api/tests/test_agent_views.py`
- Modify: `apps/api/tests/test_taxonomy.py`
- Modify: `apps/api/finance/evals/run.py` (`fingerprint` leaves the names out)
- Modify: `apps/api/tests/test_eval_metrics.py`
- Modify: `apps/web/src/lib/labels.ts`
- Modify: `apps/web/src/lib/labels.test.ts`
- Modify: `apps/web/src/lib/breakdown.ts`, `apps/web/src/lib/pickers.ts`
- Modify: every web call site in the list under Step 3
- Modify: the web fixtures that build `CategoryOut` (the test helpers and any object literals the type then rejects)

**Interfaces:**
- Consumes: the YAML tree. Keys starting with `_` are group metadata.
- Produces: `Category.name: str | None`, `Category.group_name: str | None`. `CategoryOut.name` and `CategoryOut.group_name`, both strings. `agent.transactions` columns `category_name` and `group_name`. In `labels.ts`: `categoryName(slug, categories)` and `groupName(level1, categories)`; `label(slug)` is unchanged and stays the fallback.

- [ ] **Step 1: Write the failing parser test**

In `test_taxonomy.py`, after the YAML has names, `read_categories_yaml` returns a category `software_ai` with `name == "Software & AI"` and `group_name == "Technology"`, and no category whose slug is `_name`. The count of categories stays the same as before this change. Every category has a non-empty `name` and `group_name` (the seed list is complete).

In `test_eval_metrics.py`, the fingerprint of the YAML categories equals the fingerprint of the same categories with `name` and `group_name` set to `None` (`model_copy(update=...)`): a display name is not part of what jev sees.

In `labels.test.ts`: `categoryName("software_ai", categories)` is `Software & AI` when the fixture carries that name, and `Software ai` for a slug that is not in the list; `groupName("uncategorized", categories)` is `Uncategorized`; `rowHint` of a group row with `top_categories: ["fuel", "parking_tolls"]` is `Fuel, Parking & tolls` when the fixture carries those names.

- [ ] **Step 2: Run it to verify it fails**

```bash
cd apps/api && uv run pytest tests/test_taxonomy.py -q
```

Expected: FAIL because `name` is missing. This test does not need the database.

- [ ] **Step 3: Implement**

Add every `_name` and `name` from spec section 8.1. Parser:

```python
group_name = leaves.get("_name")
for slug, criterion in leaves.items():
    if slug.startswith("_"):
        continue
    categories.append(
        Category(
            slug=slug,
            tx_type=tx_type,
            level1=level1,
            group_name=group_name,
            **criterion,
        )
    )
```

`Category` gains `name: str | None = None` and `group_name: str | None = None`. `**criterion` may include `name`. It must not include a key the model rejects; the YAML leaves only have `what`, `not_for` and `name`.

Migration:

```sql
alter table categories add column name text;

create table category_groups (
  level1 text primary key,
  name text not null
);

create or replace view v_transactions_enriched as
select t.id, t.account_id, a.name as account_name, a.bank, t.booked_at,
       to_char(t.booked_at, 'YYYY-MM') as month, t.amount, t.currency,
       case when t.amount < 0 then 'outgoing' else 'incoming' end as direction,
       t.tx_type, t.category_slug, c.level1, t.category_source,
       t.merchant_id, m.name as merchant_name, t.merchant as bank_merchant_text,
       t.description_raw, t.bank_concept, t.note, t.is_subscription, t.needs_review,
       t.transfer_pair_id,
       case when t.tx_type = 'expense' then -t.amount else 0 end as spend,
       case when t.tx_type = 'income' then t.amount else 0 end as income,
       coalesce(c.name, upper(left(replace(coalesce(t.category_slug, 'uncategorized'), '_', ' '), 1))
         || substr(replace(coalesce(t.category_slug, 'uncategorized'), '_', ' '), 2)) as category_name,
       coalesce(g.name, upper(left(replace(coalesce(c.level1, 'uncategorized'), '_', ' '), 1))
         || substr(replace(coalesce(c.level1, 'uncategorized'), '_', ' '), 2)) as group_name
from transactions t
join accounts a on a.id = t.account_id
left join categories c on c.slug = t.category_slug
left join merchants m on m.id = t.merchant_id
left join category_groups g on g.level1 = c.level1;
```

`CREATE OR REPLACE VIEW` in Postgres accepts new columns only at the end. The two names are last. Replace `agent.transactions` in place (do not drop it) so the existing grant stays:

```sql
create or replace view agent.transactions as
select booked_at, month, account_name as account, bank::text as bank, amount, direction,
       tx_type, spend, income,
       coalesce(category_slug, 'uncategorized') as category,
       coalesce(level1, 'uncategorized') as category_group,
       merchant_name as merchant, bank_merchant_text as bank_text,
       bank_concept as bank_operation, note, is_subscription, needs_review,
       category_name, group_name
from public.v_transactions_enriched;
```

Append `"category_name"` and `"group_name"` to `TRANSACTIONS` in `test_agent_views.py`, in that order.

`seed` writes `categories.name` and upserts `category_groups` from the distinct `(level1, group_name)` pairs. A null `group_name` skips the upsert. `list_categories` selects `name` and `group_name` with the same `coalesce` expression as the view, so a missing name reads `Software ai`, not `Software Ai`.

`transactions.yaml`: add `category_name` and `group_name` as attributes (`kind: dimension`, no `allowed_values`); `check_layer` requires every view column to be described. They are what the model says to the user. `category` and `category_group` stay the filter values. One sentence on each slug attribute points at the name column.

`fingerprint` in `evals/run.py` dumps `c.model_dump(exclude={"name", "group_name"})`, so the hash of a run stays what jev sees.

Names in the web. `label(slug)` keeps its body. Add to `labels.ts`:

```typescript
/** The stored name of a category (spec 8.1), or its readable slug. */
export function categoryName(slug: string | null | undefined, categories: Category[]): string {
  return categories.find((c) => c.slug === slug)?.name ?? label(slug);
}

/** The stored name of a group, read from any of its categories, or its readable slug. */
export function groupName(level1: string | null | undefined, categories: Category[]): string {
  return categories.find((c) => c.level1 === level1)?.group_name ?? label(level1);
}
```

Every place that shows a category or a group name goes through them. These are the call sites today (`rg "\blabel\(" apps/web/src` lists them; leave `label` only where no `categories` list can exist):

- `labels.ts`: `rowName` (group and category keys) gains a `categories` parameter, and `breakdown.ts` passes `context.categories`. `rowHint`'s `label(row.level1)` and `label(row.category_slug)`. `groupHint` and the `top_categories` hint join names with `, `, as stored ("Fuel, Parking & tolls").
- `pickers.ts`: group headers and category options.
- `components/pickers/category-picker.tsx`: `itemToStringLabel` and the option text.
- `components/transactions/transaction-row.tsx`: "Group · Category". `TransactionTable` and `TransactionBrowser` pass `categories` down.
- `app/transactions/transaction-panel.tsx`: the toast, the dialog text and plan 1's "Group › Category" line.
- `app/review/review-row.tsx`: the group next to the picker.
- `app/settings/page.tsx`: the category list.
- `app/spending/[group]/page.tsx`, `app/spending/[group]/[category]/page.tsx`, `app/income/[category]/page.tsx`: the title, the breadcrumbs, and `generateMetadata`. `generateMetadata` fetches `/categories` too; the page already fetches it, and Next.js memoizes the same GET in one request.
- `components/merchants/merchant-controls.tsx` from Task 2.

Apply the migration, run `uv run finance seed`, then the integration tests.

- [ ] **Step 4: Run the tests**

```bash
cd apps/api && uv run task lint && uv run task test
cd apps/api && uv run pytest tests/test_agent_views.py tests/test_catalog_db.py tests/test_views.py tests/test_seed.py -m integration -q
cd apps/web && npm run lint && npx next typegen && npx tsc --noEmit && npm test && npm run build
```

`uv run task test` covers `test_taxonomy.py` and `test_eval_metrics.py`, which are unit tests. Then a read-only look on :3000: the overview Groups view, a group page's breadcrumb and title, the category picker in the panel. No slug-style name such as "Software ai" or "Restaurants bars" is left on screen.

Expected: PASS. `test_views.py` still passes because the new view columns are additive.

- [ ] **Step 5: Commit**

```bash
git add supabase/migrations/20261014130000_display_names.sql supabase/seed/categories.yaml apps/api/finance/categorization/taxonomy.py apps/api/finance/categorization/seed.py apps/api/finance/api/categories.py apps/api/finance/agent/semantic/transactions.yaml apps/api/finance/evals/run.py apps/api/tests apps/web/src
git commit -m "$(cat <<'EOF'
feat: store readable category and group names and show them to the chat

EOF
)"
```

---

### Task 4: Eight colours, distinct greys, a hatched Other

**Files:**
- Modify: `apps/api/finance/dashboard/breakdowns.py` (`group_slots`)
- Modify: `apps/api/tests/test_breakdowns.py`
- Modify: `apps/web/src/lib/colors.ts`
- Modify: `apps/web/src/lib/colors.test.ts` (it exists and pins today's slots 1–5)
- Modify: `apps/web/src/lib/breakdown.ts` (a row's colour reads `level1 ?? "uncategorized"`; `_other` gets no slot colour)
- Modify: `apps/web/src/app/globals.css`
- Modify: `apps/web/src/components/charts/breakdown-donut.tsx`
- Modify: `apps/web/src/components/overview/where-money-went.tsx` (where slice fills are computed)
- Modify: `apps/web/src/components/breakdown/breakdown-table.tsx`

**Interfaces:**
- Consumes: `group_slots` ranked by all-time spend
- Produces: a slot for every expense group, `uncategorized` included. `groupColor` maps 1–8 to `--chart-1` … `--chart-8`, 9+ to `--chart-grey-1` onward, and a group with no slot to `--chart-other`. `BreakdownItem` gains `folded: boolean` (true on `_other`). The `_other` dot and slice use the hatch, not a slot.

- [ ] **Step 1: Update the slot test**

`test_group_slots_rank_all_time_spend` today inserts two huge spends and asserts `len(slots) <= 5`. Make the fixture independent of the ledger: insert huge spends in seven groups, larger than any real ledger, in this order: `fashion` −9e9 (shopping), `restaurants_bars` −8e9 (leisure), `fuel` −7e9 (transport), `flights` −6e9 (travel), `pharmacy` −5e9 (health), `courses` −4e9 (education), and one row with no category −3e9 (uncategorized; leave `category_slug` null). Use amounts like `"-9000000000.00"`, which `numeric(12, 2)` holds. Assert that slots are `1..n` with no gaps, and that the first seven are, in order, `shopping, leisure, transport, travel, health, education, uncategorized`.

In `colors.test.ts`, keep the `null` and unslotted cases (`var(--chart-other)`), and add: slot 6 is `var(--chart-6)`, slot 9 is `var(--chart-grey-1)`, slot 16 is `var(--chart-grey-8)`. In `breakdown.test.ts`, a category row with `level1: null` takes the `uncategorized` slot's colour, and `_other` has `folded: true`.

- [ ] **Step 2: Run them to verify they fail**

```bash
cd apps/api && uv run pytest tests/test_breakdowns.py::test_group_slots_rank_all_time_spend -m integration -q
cd apps/web && npm test -- src/lib/colors.test.ts src/lib/breakdown.test.ts
```

Expected: FAIL. `group_slots` stops at 5 and skips rows without a category; `groupColor` has no slot 6 or greys.

- [ ] **Step 3: Implement**

`group_slots`: group by `coalesce(level1, 'uncategorized')`, drop `level1 is not null` and `limit 5`. Return every group. Update its docstring and the `Overview.group_slots` comment ("1..5").

`colors.ts`:

```typescript
export function groupColor(level1: string | null | undefined, slots: Record<string, number>): string {
  const slot = level1 ? slots[level1] : undefined;
  if (!slot) return OTHER_COLOR; // no expense rows ever: not one of the greys
  if (slot <= 8) return `var(--chart-${slot})`;
  return `var(--chart-grey-${Math.min(slot - 8, 8)})`;
}
```

In `breakdownItems`, a row's colour is `groupColor(dimension === "group" ? row.key : (row.level1 ?? "uncategorized"), slots)`, and `_other` gets `color: undefined, folded: true`.

`_other` does not use `groupColor`. The table dot for a folded item uses a `folded-hatch` utility, defined in `globals.css` with Tailwind v4's `@utility` (a `repeating-linear-gradient` at 45° in `#9a9aa6` over `--chart-folded`); a colour token cannot carry a gradient. In `where-money-went.tsx`, a folded item's slice gets `fill: "url(#folded-hatch)"` (decided by `item.folded`, never by its name). Define the pattern once inside the pie chart; Recharts renders a `<defs>` child of `PieChart` as SVG. Check that against the Recharts 3.8 docs through Context7:

```tsx
<defs>
  <pattern id="folded-hatch" patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">
    <rect width="6" height="6" fill="#ececf1" />
    <line x1="0" y1="0" x2="0" y2="6" stroke="#9a9aa6" strokeWidth="2" />
  </pattern>
</defs>
```

Add the tokens from spec section 8.2 to `:root`, and set `.dark` `--chart-1` through `--chart-8` to the same hues at lightness about 0.75 so they stay distinct. Add `--chart-grey-1` through `--chart-grey-8` in both.

Wire Tailwind colours the way `--chart-1` is already wired in `globals.css` (`--color-chart-6` and the greys), or the classes will not emit.

- [ ] **Step 4: Gates and a read-only look**

API integration test, web gate, then open the overview Categories view. The folded row's dot is striped. Two groups that used to share one grey no longer do. Screenshot to `dogfood-output/qol-2/`, not the repo.

- [ ] **Step 5: Commit**

```bash
git add apps/api/finance/dashboard apps/api/tests/test_breakdowns.py apps/web/src/lib apps/web/src/app/globals.css apps/web/src/components/charts/breakdown-donut.tsx apps/web/src/components/overview/where-money-went.tsx apps/web/src/components/breakdown/breakdown-table.tsx
git commit -m "$(cat <<'EOF'
feat: give the top eight groups stable colours and hatch the folded row

EOF
)"
```

---

### Task 5: Review cards that say what they count

**Files:**
- Modify: `apps/api/finance/categorization/review_queue.py`
- Modify: `apps/api/finance/api/review.py`
- Modify: `apps/api/tests/test_review_queue.py`
- Modify: `apps/api/tests/test_review_api.py`
- Create: `apps/web/src/app/review/merge-card.tsx`
- Modify: `apps/web/src/app/review/review-list.tsx`
- Modify: `apps/web/src/app/review/review-row.tsx`
- Modify: `apps/web/src/app/review/review-help.tsx`
- Modify: `apps/web/src/app/transactions/explorer-filters.tsx`
- Modify: `apps/web/src/lib/api.ts` (`apiPatch` takes `keepalive`)
- Modify: `apps/web/src/lib/api-types.ts`

**Interfaces:**
- Consumes: `build_review_items`, `ReviewCount`, the merge PATCH from Task 1, `POST /merchants/{id}/dismiss-merge`
- Produces: `PendingMerge(BaseModel)` with `merchant: MerchantOut` (the source) and `suggestion: MergeSuggestion` (the candidate). `build_review_items(rows, merges: list[PendingMerge], taxonomy)`. `ReviewItem.kind` includes `"merge"`. `ReviewCount` keeps `pending` and `uncategorized` and gains `categories` and `merges`. A merge card's key is `merge:{source merchant id}`. `apiPatch(path, body, init = {})` with `init.keepalive`.

- [ ] **Step 1: Write the failing tests**

In `test_review_queue.py` (unit tests, no database): a merge with no review rows produces one item, `kind == "merge"`, `transactions == []`, `merchant` the source and `merge` the candidate. A merchant with one review row plus a merge produces two items: a `merchant` card with only that row and `merge is None`, and a `merge` card. Replace `test_merge_suggestion_is_attached_to_its_merchant`, which pins the old banner. Every other call passes `[]` instead of `{}` for merges.

In `test_review_api.py` (integration): a merchant with no `needs_review` row and a pending `merge_candidate_id` (`confirmed` false) is one card of kind `merge` in `GET /review`, and `GET /review/count` has `pending == categories + merges` and still returns `uncategorized`.

- [ ] **Step 2: Run them to verify they fail**

```bash
cd apps/api && uv run pytest tests/test_review_queue.py -q
cd apps/api && uv run pytest tests/test_review_api.py -m integration -q
```

`test_review_queue.py` has no integration marker: never pass `-m integration` for it, or pytest deselects every test and exits 5. Expected: FAIL, because `build_review_items` takes a dict and has no merge kind.

- [ ] **Step 3: Implement**

Change `_ROWS` so the merge branch is gone: `where t.category_source <> 'user' and t.needs_review`. Build category and transaction cards as today, with `merge` always null.

`_MERGES` also selects the source's name: `select m.id, m.name as source_name, c.id as merchant_id, c.name, m.merge_confidence as confidence ...`. `review_items` turns each row into a `PendingMerge`.

Append one `ReviewItem` per `PendingMerge`: `kind="merge"`, `key=f"merge:{pm.merchant.id}"`, `merchant=pm.merchant`, `merge=pm.suggestion`, `transactions=[]`, `count=0`, `total=Decimal(0)`, `suggestion=Suggestion(category_slug=None, level1=None, confidence=None, is_subscription=False, top=[])`. `ReviewItem.kind` becomes `Literal["merchant", "transaction", "merge"]`. Merge cards sort after the category cards, by `merge.confidence` descending. The header does not depend on order.

`ReviewCount.categories` is the number of non-merge cards, `merges` the rest, `pending` the sum. `uncategorized` stays as it is; `app/review/page.tsx` still passes it. The nav already shows `pending`; keep that.

`apiPatch` gains the same `init: { keepalive?: boolean } = {}` as `apiPost`. The undo schedule sends with `keepalive` when the page is left inside the undo window.

`merge-card.tsx` asks "Is {merchant.name} the same merchant as {merge.name}?" Buttons Yes and No. Yes calls `schedule(item, null, "Merged", (keepalive) => apiPatch(`/merchants/${merchant.id}`, { merge_into_id: merge.merchant_id }, { keepalive }), sourceCard)`. `sourceCard` is the source's own category card (`kind === "merchant"` with the same merchant id), or null. `schedule` already takes that card off the list with it and Undo restores both: its rows belong to the survivor once the merge is sent, and confirming the stale card would 404. No posts dismiss-merge through `schedule` the way the list already does.

`review-row.tsx` drops the merge banner. The single-transaction confirm button uses `size="default"` and the text `Confirm` next to the icon. Remove `aria-label="Confirm"` once the visible word is Confirm, so the name is not doubled.

`review-list.tsx` header: `{pending} to review: {categories} categories · {merges} possible duplicates`, using the count endpoint, not the filtered list. Filter buttons All, Categories, Duplicates. Sort Amount (absolute total, the current order) and Date (latest `booked_at` on the card; a merge card sorts last when sorting by date). Skip writes the card key to `sessionStorage` `review-skip:v1` and moves it to the end. Help is a `<details>` that renders open, reads `localStorage` `review-help:v1` in an effect after mount (reading it during render would not match the server HTML), and stores `closed` when the user closes it. Wrap storage calls in `try`, as private browsing can throw.

Under the transactions "Needs review only" switch, add the description "Counts transactions that need a category, not review cards."

- [ ] **Step 4: Tests, web gate, and R2**

```bash
cd apps/api && uv run task lint && uv run task test && uv run pytest tests/test_review_api.py -m integration -q
```

Then the web gate.

On the scratch app, open `/review`. If the ledger has both kinds, the header adds up. Filter Duplicates and confirm a category card disappears. Skip one card, reload the tab, and confirm it is still last. Close the help, reload, and confirm it stays closed.

- [ ] **Step 5: Commit**

```bash
git add apps/api/finance/categorization/review_queue.py apps/api/finance/api/review.py apps/api/tests/test_review_queue.py apps/api/tests/test_review_api.py apps/web/src/app/review apps/web/src/app/transactions/explorer-filters.tsx apps/web/src/lib/api.ts apps/web/src/lib/api-types.ts
git commit -m "$(cat <<'EOF'
feat: count review cards apart from duplicate suggestions

EOF
)"
```

---

### Task 6: Dogfood this delivery

- [ ] **Step 1: Core checks**

`agent-browser skills get core`, session `qol2`. Read-only on :3000 for the merchant page, the overview colours, and `/review`. Recipe R2 for a default-category change, a rename, a merge Yes and a merge No. Recipe R3 is not required: this plan does not change the chat transport. The semantic-layer test in Task 3 is the chat check.

- [ ] **Step 2: Dogfood and the four scenarios**

`agent-browser skills get dogfood`. Report in `dogfood-output/qol-2/report.md`. All four scenarios from spec section 10, including scenario 4. Scenario 1 can cite the plan 1 report if the quarterly plan was already checked, and this pass confirms the merchant page still shows that cadence.

- [ ] **Step 3: PR note**

The PR says to run `uv run finance seed` after migrating, because names are not backfilled by the migration alone.
