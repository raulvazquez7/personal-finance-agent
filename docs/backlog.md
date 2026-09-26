# Backlog

Ideas Raul wants to invest in soon. They are not designed or scheduled: each
one goes through its own brainstorm and spec before any code. Notes under each
idea record what already exists and the questions to answer first.

## 1. Tag spending with life events from the chat

Tell the chat "I was on holiday from 1 to 15 July at the seaside" and it tags
those transactions with a user-defined label ("Summer holiday 2026"). The tag
shows in the dashboards and the agent knows it when answering questions
("how much did the summer holiday cost?").

- Tags are not categories: a many-to-many transaction ↔ tag table, orthogonal
  to the taxonomy.
- Spec section 12 lists "labelling from chat" as out of scope for v1, and the
  agent's SQL tool is read-only (section 9.2). This needs a dedicated write
  tool with a confirm step.
- The slice 4 semantic layer should leave room for tags as a dimension (fits
  Raul's knowledge/attributes idea for slice 4).

## 2. Logos for subscriptions and well-known brands

Show a logo next to subscriptions and well-known merchants (supermarket
chains, streaming services).

- Needs a merchant → domain mapping and a logo source.
- Local-first: fetching logos per merchant from a third-party service sends
  the merchant list out. Cache locally, or make it opt-in.

## 3. "Do it with AI" in the review inbox

A button on `/review` that hands the pending items to an LLM agent: it
proposes a category, a merchant name or a merge for each item, and the user
accepts or corrects. Either inside the chat UI or as an inline assistant on
the review page.

- jev already made its call on these rows. The agent adds context: the user's
  notes, tags, the merchant's other transactions, maybe a web lookup of an
  unknown merchant.
- Decide how an AI-proposed, user-accepted label counts in
  `transaction_labels`: the golden set is `source = user` labels (spec 13.1),
  and scoring the system against labels a model proposed biases the eval.

## 4. Imports page: account periods and a coverage calendar

- Hide the file name. Each row shows the bank, the account's last four digits
  and the statement period, sorted by date.
- Mark an upload as duplicate (no new rows) or partially duplicate (some rows
  already existed). The `imports` table already stores `period_start`,
  `period_end`, `rows_new` and `rows_duplicate`.
- A coverage calendar: a months × years grid in the app's current style that
  shows at a glance which months have data and which are missing. Hovering a
  month shows which accounts cover it, since a month may have data for one
  account and not the others.
- Coverage should come from statement periods, not transaction dates: a month
  without movements is still covered.
