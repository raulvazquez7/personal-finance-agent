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

## 5. Account balances in the chat

The agent cannot answer "how much do I have in my account" yet: `balance_after` is stored but
the order of movements within a day is not, so "the balance on a date" could pick the wrong
row. Store each movement's position in its statement at import, then expose the balance per
account and date in the `agent` schema. (Slice 4 spec, section 15.)

## 6. Chat evals

A golden set of questions with reference SQL, run against the agent with repeats (consistent,
flaky, failing), to measure prompt, semantic-layer and model changes. Start from Langfuse
traces of real use (a dataset per version). Include the money rules a model gets wrong, such as
a category total that nets a refund against its purchase.

## 7. Loan instalments recognised by their contract

Some banks print only the loan's contract number on an instalment, with no merchant and no
bank concept, so no rule can catch it and each new instalment arrives uncategorized. Once a
loan is known (a merchant linked to its contract), any new movement that carries the same
contract number should become that loan's instalment (`loan_payment`, same merchant) before
jev runs. It extends what `link_loans` already does for rows that are categorized as a loan.

## 8. Numbers the chat agent can be trusted with

A live test showed the agent can state an amount that no query of the turn returned: it ran
only the lookups and skipped the final query, or copied a result wrongly. Small prompt edits
changed how often it happened (a rule against text between queries made it much worse), so a
prompt is not a guarantee. Add a deterministic check: every amount in the final answer must
appear in a query result of the turn; if one does not, nudge the model once to run the query,
otherwise show a warning. Measure with repeated runs of the same questions (with backlog 6).
The same work can fix two format slips seen live: the "How I counted it" heading left in
English in Spanish answers, and a category slug shown in an answer.

## 9. Keep the agent wiki fresh in CI

Run `openwiki code --update --print` on a schedule (OpenWiki ships `examples/openwiki-update.yml`
for GitHub Actions) and open a docs PR when the wiki changes. Needs a provider key in the repo
secrets and accepts a small daily spend. Until then, run `npx -y openwiki@0.7.2 code --update`
before a slice merges. The OpenWiki block in `AGENTS.md` already says a scheduled workflow
refreshes the wiki: that sentence is OpenWiki's own text, rewritten on every run, and it stays
wrong until this is built. `openwiki --init` writes `.github/workflows/openwiki-update.yml` when
none exists; it was deleted here, so after a future `--init` delete or review that file.
