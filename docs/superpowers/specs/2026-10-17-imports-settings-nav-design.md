# Imports coverage, the settings taxonomy and the secondary menu

Date: 2026-10-17
Status: design, ready for one plan
Owner: Raul Vazquez

Raul chose the recommended option of each screen on 2026-10-17, from a mockup with
made-up data (`.superpowers/brainstorm/…/proposal-v4.html`, git-ignored). This spec
replaces the uncommitted 2026-10-16 draft and its throwaway route `/preview-ux`. The
plan deletes that route. Production code does not import from it.

Three changes, one PR:

- **Navigation.** The top bar keeps the pages used every day. Imports and Settings move
  into a menu behind one button.
- **Imports.** A year board shows which months have a statement, for each account, and
  which are missing. The history drops the file name and is grouped by month.
- **Settings.** Renaming accounts stays as it works today, in compact rows. Categories
  become cards with the same visual language as the rest of the app. Names stay read-only.

## 1. Delivery

One spec, one plan, one PR, on a branch off `main`. The plan runs with subagent-driven
development and ends with a review pass, an agent-browser check of each flow and the
slice's dogfood pass.

## 2. Decisions

| Topic | Call |
|---|---|
| Main navigation | Overview, Transactions, Subscriptions, Chat, Review (with its count). Unchanged order |
| Secondary menu | A round icon button at the far right of the top bar opens a dropdown with Imports and Settings |
| Below `lg` | The existing sheet (today below `sm`) now takes over below `lg` (1024 px). It lists the main pages, a separator, then Imports and Settings. The row and the icon button show from `lg` up. Measured on 2026-10-17 with the filters shown: the five main links and the button need about 860 px, so tablets would still scroll the row |
| Sidebar | Rejected. It would restructure the whole shell |
| What a filled month means | A statement for that account covers the month. Not "there was a transaction that day" |
| Board shape | One row per account, twelve month columns, arrows for the year. Not a day calendar, and no new dependency |
| Expected month | A month is expected only once it has ended. The current month is never "missing" |
| Partial month | A statement overlaps the month and none covers every day of it. Two partials that together fill the month stay partial |
| Gap | The month has ended, nothing overlaps it, and this account has a statement that ended before the month |
| Outside | Anything else: the month has not ended, or the account has no earlier statement. Drawn blank |
| Hover | A month opens a popover with each account's state. It does not filter anything and it has no link |
| Today | The server's local calendar day, passed into the client. The client does not recompute it |
| Default year | The year of the latest `period_end`. The arrows run from the earliest `period_start` year to the later of that year and the current year |
| Missing summary | One line above the board lists the visible year's gaps, newest month first |
| Upload | A drop zone. Dropping or choosing files starts the import at once. No separate Import button |
| History order | Newest `period_end` first, then account name, then newest `imported_at`. Null periods last |
| History grouping | One section per month of `period_end`, with the month as its header. The file name is not shown |
| List cap | `GET /imports` no longer stops at 100. The board reads this list |
| Filename | Stays on `ImportRecord`. The page does not render it |
| Account rows | A bank initial, the name field, the bank and digits under it, Save. The help sentence is shown once, as the card description |
| Category names | `category.name`, as stored. Never `label(slug)`, which turns "Software & AI" into "Software ai" |
| Categories layout | A segmented Expenses / Income / Transfers control, then one card per group, in columns |
| Group colour | `groupColor(level1, slots)` for expense groups, as on the overview. Income and transfers use `var(--chart-other)` |
| Slots source | A new `GET /dashboard/group-slots` that returns `group_slots()`. Settings does not call the overview |

## 3. Navigation

`components/shell/nav-links.tsx` splits `ITEMS` into `MAIN_ITEMS` (Overview,
Transactions, Subscriptions, Chat, Review) and `MORE_ITEMS` (Imports, Settings). Both
keep the existing `Item` shape. The desktop row renders `MAIN_ITEMS` only.

A new `components/shell/more-menu.tsx` holds the menu:

- The trigger is a `Button` `variant="secondary"` `size="icon-sm"` `rounded-full`,
  with the lucide `Settings` icon and the accessible name "Imports and settings".
  It is hidden below `lg`.
- When the current path starts with `/imports` or `/settings`, the trigger takes the
  active pill style (`bg-foreground text-background`), as an active nav link does.
- The content is the shadcn `dropdown-menu` (Base UI `Menu`), added with
  `npx shadcn add dropdown-menu`. No new npm dependency. It is aligned to the end.
- Each item is a link: an icon (`Upload` for Imports, `SlidersHorizontal` for Settings),
  the label, and one muted line under it: "Upload statements, see coverage" and
  "Account names, categories". The current page's item carries `aria-current="page"`.
- Links follow the Base UI documented way of rendering a menu item as a Next.js `Link`.
  Check the current docs (Context7) when you write it.

The button is the last thing in the top bar. On a filtered page it sits right after the
period pill. On other pages it is pushed to the right on its own.

`mobile-nav.tsx` renders `MAIN_ITEMS`, a `Separator`, then `MORE_ITEMS`, with the same
link style as today. Its trigger shows below `lg` (`lg:hidden`), and the desktop row from
`lg` up, instead of `sm`.

## 4. Imports page

Order: the upload card, the coverage card (only when there is at least one import), the
history card.

### 4.1 Upload card

Title and description are unchanged. The file input becomes a drop zone. It is a dashed,
`rounded-xl` area on the white background, with an `Upload` icon, "Drop PDF statements
here", and a muted line: "or choose files · a statement imported twice only adds its new
rows". A "Choose files" outline button sits on the right.

- The native `<input type="file" multiple accept="application/pdf">` covers the zone,
  transparent. Clicking anywhere opens the picker and a drop lands on the input. Both
  paths stay native.
- While a file is dragged over it, the zone shows the primary border.
- Keyboard focus on the input draws the focus ring on the zone (`has-[:focus-visible]`).
- On `change`, the selected files are imported one by one with the existing loop.
  Messages, `aria-live`, `router.refresh()` and error texts are unchanged. While
  importing, the zone shows a `Spinner` and "Importing…", and the input is disabled.
  The input is then reset, so the same file can be picked again.

### 4.2 Coverage card

Title "Statement coverage". Description: "Which months have a statement, for each
account." The year sits on the right of the header, between two icon buttons, "Previous
year" and "Next year", which are disabled at the ends.

**Missing line.** Under the header, one row of text:

- With gaps in the visible year: a dashed swatch, "Missing:", then one entry per month
  with a gap, newest first. An entry is "{Month} · {account name}" when one account
  misses it, or "{Month} · {n} accounts" when several do. Entries are joined with
  ", ". `{Month}` is the full month name.
- Without gaps: "Nothing missing in {year}."

**Board.** A grid of thirteen columns: the account name, then twelve months. The first
header cell reads "Account" and stays in normal flow. It is a real cell: an `sr-only`
cell leaves the grid and moves January's square under February. Each account cell shows
the name and its digits, muted (`accountDigits`). Accounts are ordered by name.

Month headers:

- A month whose first day is after today is muted text, not a button.
- Every other month is a ghost `Button`. Its accessible name is "{Month year}. {n} with
  a statement, {m} missing." Hover or click opens a popover (`openOnHover`, like
  `InfoTip`), and while it is open the column gets a faint primary tint.
- Months that have not ended use the muted text colour, but stay buttons.

The popover's title is `monthLabel`. Then, only for the groups that have rows:

- "Whole month · {n}": the account name, and "· 2 statements" when its count is over one
- "Part of the month · {n}": the account name, then the day range on the right, and the
  count in the same way
- "Missing · {n}": the account name

Each line starts with the state's swatch. With all three groups empty, the description
reads "No statement for this month yet." The popover has no link, and its width is
`w-72`.

Squares are `size-5 rounded-md`, one per account and month, `aria-hidden`:

| State | Draw |
|---|---|
| covered | `bg-primary` |
| partial | `bg-primary/35` |
| gap | dashed border in `--chart-previous`, white inside |
| outside | nothing |

The legend under the grid reads Whole month, Part of the month, Missing, Not expected.
On a narrow screen the grid scrolls sideways (`min-w-[44rem]` inside `overflow-x-auto`).

### 4.3 History card

Title "Import history". One `TableBody` per month of `period_end`, in API order. Each
body opens with a header row: a `th` with `scope="rowgroup"` and `colSpan`, holding the
`monthLabel`, muted. Rows with a null period go into a last group, "No period".

Columns: Period, Account, Imported, Rows, New, Duplicate. Rows is hidden below `md`,
Imported below `sm`. Period uses `dayRange`, or `NoData` when either end is null.
Imported uses `dateTime`. There is no File column.

## 5. Coverage model

`apps/web/src/lib/coverage.ts`, pure and without the DOM. Dates are `YYYY-MM-DD` strings
compared as text. A month runs from its first day to its last, in UTC, the way
`lib/format.ts` reads a day. Import rows with a null start or end are ignored here.

For one account and one month, given that account's periods:

1. If a period starts on or before the first day and ends on or after the last day, the
   state is `covered`.
2. Otherwise, if a period overlaps the month (inclusive), the state is `partial`.
3. Otherwise, if the month's last day is before today and the account has a period that
   ends before the month's first day, the state is `gap`.
4. Otherwise the state is `outside`.

The model exports:

- `yearBounds(imports, today)` returns `{ first, last, initial }` (section 2, Default year).
- `buildYear(accounts, imports, year, today)` returns the twelve month keys (`YYYY-MM`),
  each account's twelve states in data order (index 0 is January), and, per month, the
  `covered`, `partial` and `missing` lists for the popover. Each entry has the account
  name, the number of periods that overlap that month, and, for partial, the merged
  day spans. A span is the overlap of a period with the month. Spans that touch or
  overlap are merged.
- `missingSummary(board)` returns the entries for the missing line, newest month first.

Formatting stays out of the model: the component turns spans into text with `dayRange`
and months into text with `monthLabel`, `monthShort` and the full month name.

`apps/web/src/lib/import-history.ts` (also pure) groups the API's import list into
`{ month: string | null; rows }[]` by the `YYYY-MM` of `period_end`, keeping the API
order. `null` is the "No period" group, and it comes last.

## 6. Settings page

### 6.1 Accounts card

The title stays "Accounts". The description is the sentence that today repeats under
every field: "The name shown in lists and in the account filter, for example “Joint
account”." `AccountNameForm` drops its `FieldDescription` and the `aria-describedby`
that pointed at it.

Each account is one row, with a hairline between rows:

- A round `size-9` avatar on white with a hairline ring, holding the bank's first letter
  in upper case. It is `aria-hidden`.
- The name `Input`. Under it, the `FieldLabel`, muted and small: the existing
  "{BANK} ····{last4}" string. It stays the input's label (`htmlFor`), so the field
  keeps its accessible name.
- The Save button on the right, with the same disabled rule and accessible name as today.

Save, the dirty check, read-only while saving, the toast and `router.refresh()` are
unchanged.

### 6.2 Categories

A section, not one big card. A heading "Categories", and the paragraph "A refund takes
the category of its purchase. Transfers never count as income or spending." On the
right (below it on phones) sits a `ToggleGroup` `variant="segment"` `size="sm"`, labelled
"Category type", with Expenses, Income and Transfers. Each item shows the number of
groups of that type, muted. The default is Expenses. The value is component state, not
the URL.

Under it come the cards, in CSS columns (`sm:columns-2 lg:columns-3`), each
`break-inside-avoid`, so cards of different heights leave no holes. There is one `Card`
`size="sm"` per `byLevel1` group of the selected type, in the order `GET /categories`
returns. The card shows:

- A title row: a `size-2` dot, the group label, and the number of categories on the
  right, muted. The dot follows section 2, Group colour.
- A list of `category.name`, one per line, `text-sm`. Not an input, not a badge, not a
  link.

The interactive part is a client component, `app/settings/category-browser.tsx`. The
page fetches `/accounts`, `/categories` and `/dashboard/group-slots` in parallel.

## 7. API

`GET /imports` returns every import, with no `limit`:

```sql
select i.*, a.name as account_name
from imports i
join accounts a on a.id = i.account_id
order by i.period_end desc nulls last, a.name, i.imported_at desc
```

`GET /dashboard/group-slots` returns `group_slots(conn)` as `dict[str, int]`. The
overview keeps calling `group_slots()` itself, so the two cannot drift. `ImportRecord`
and every other route stay unchanged. `npm run gen:api` regenerates `api-types.ts`.

## 8. Tests

`lib/coverage.test.ts`:

- a period that contains the month is `covered`
- a period that ends on the 5th, with nothing else, is `partial`, with the span 1st–5th
- two partials that together fill the month stay `partial`, with one merged span
- a hole between two periods, in an ended month, is `gap`
- the current month with no statement is `outside`, not `gap`
- the current month with a statement up to the 10th is `partial`
- a month before the account's first period is `outside`
- a period with a null end paints nothing and does not, alone, make a later month a gap
- two periods that each cover the month count 2 and stay one `covered` state
- a covered January is index 0 of the account's states
- `yearBounds` gives the latest `period_end` year as initial, and stretches `last` to the
  current year
- `missingSummary` lists the newest month first, with a name for one account and a count
  for several

`lib/import-history.test.ts`: rows keep API order inside a month; a period that spans
two months lands in its `period_end` month; null periods form the last group.

API: an integration test seeds imports with an older, a newer and a null period, and
expects `GET /imports` in `period_end desc nulls last` order. A handful of rows cannot
prove that a cap is gone, so a unit test asserts that the `list_imports` SQL has no
`limit`. `GET /dashboard/group-slots` returns the same dict as `group_slots()` on the
same database.

Web, with agent-browser on the real pages after `/preview-ux` is gone:

- The menu button opens, Imports and Settings navigate, and the button shows active on
  both pages. At 1024 px the five links, the filters and the button fit without scrolling.
  At 820 px and on a phone, the sheet lists both pages after the separator.
- January's square sits under January. The August popover lists each account's state.
  The October header is not a gap. The year arrows move and stop at the ends.
- Dropping a PDF imports it and the counts appear. Run this on a scratch database,
  recipe R2 in `docs/superpowers/plans/2026-09-25-slice-3b-interface.md`.
- The history has no file name and is grouped by month.
- Expenses / Income / Transfers swaps the cards. Category names read as stored
  ("Software & AI"). Renaming an account still saves (scratch database, R2).

## 9. Out of scope

Editing category names. Linking a category to a spending page. A day calendar or a new
calendar dependency. Filtering Transactions, the overview or the history from the
board. Pagination of the history. A per-account colour. A sidebar shell. A badge on the
menu button for missing statements.
