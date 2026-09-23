# Spike: merchant, category and subscription with jev (2026-09-23)

Question: can jev (TypeSafe System One) name the merchant, pick a two-level
category and flag subscriptions for real Spanish bank transactions, cheaply
and without a hand-maintained merchant list?

Answer: yes. The round-4 baseline below is the design adopted for slice 2
(spec, "Slice 2 amendments"); round 5 kept it and validated the final
taxonomy (spec section 7). Five rounds ran over the local ledger (412
transactions, 3 accounts, BBVA and CaixaBank, June to August 2026) on
`jev-1.13.0`.

Examples in this file are invented; real statement text stays in the
git-ignored `output/` folder.

## How to rerun

```bash
supabase start                      # local ledger with imported statements
cd docs/superpowers/spikes/2026-09-23-jev-categorization
uv run --env-file ../../../../.env --with typesafe-sdk --with 'psycopg[binary]' python run.py v6
python3 report.py v6                # prints the summary, writes output/review_v6.csv
```

`run.py` is read-only against the database. Compare a new run with the
numbers below before changing a question or a threshold.

## The baseline (round 4)

```
Python   clean text, drop the card number, cut every 1-4 word fragment
jev #1   merchant_name  Choice over the fragments + none
         category       Choice over the level-2 slugs for the direction
         is_subscription Noul
Python   brand confidence = sum of nested fragments (BRAND, BRAND FOODS)
         exact match on the known merchants, ignoring spaces and punctuation
jev #2   only when a known merchant shares a word with the chosen name:
         known_merchant Choice over that shortlist + none; merge at >= 0.8
Python   level 1 = parent of the level-2 slug; its confidence = sum of its leaves
```

Example: `PAGO CON TARJETA EN SUPERMERCADOS | 1234567812345678 SUPER ACME 0042 L`
gives the fragments `SUPER`, `ACME`, `L`, `SUPER ACME`, `ACME L`, `SUPER ACME L`.
jev picks `SUPER ACME`, which is a new merchant unless one with the same key exists. The
card number and `0042` never reach jev.

## Results by round

| | v1 | v2 | v3 | v4 | v5 |
|---|---|---|---|---|---|
| Change | first design | clean fragments, names only, shortlist by shared word | two steps, exact key, brand confidence | name-to-name comparison, merge at 0.8 | final taxonomy with `what`/`not_for` criteria |
| Cost for 412 rows | $0.085 | $0.033 | $0.031 | $0.031 | $0.043 |
| Wrong merges | ~7, confidence up to 0.99 | 2 | 1 | 1 (generic word) | unchanged |
| Brand confidence >= 0.85 | n/a | n/a | 295 / 332 | 294 / 331 | 298 / 328 |
| Level-2 confidence >= 0.85 | 310 | 307 | 304 | 306 | 297 |
| Level-1 confidence >= 0.85 | 334 | 337 | 338 | 340 | 323 |
| Uncategorized expenses | | | | 33 (16 at >= 0.85) | 15 (none at >= 0.85) |

About 8 duplicates stay unmerged in v4 (for example `ACME` and `ACME FOODS`), all with a
merge confidence between 0.5 and 0.8. `/review` offers them as merge
suggestions: a duplicate is one click to fix, a wrong merge silently corrupts
the analytics.

### Round 5: the taxonomy

v5 changed only the categories (seed of spec section 7: new groups for
education, family, people and giving; beauty, hobbies, personal care,
gambling, self-employment and public benefits as level 2) and wrote every
criterion as `what` plus, where a neighbour competes, `not_for`. Longer
criteria cost about 40 percent more input tokens, still cents per run.

- Transfers to and from people (about 30 rows) left `uncategorized_expense`
  and `other_income`; those with BIZUM in the text scored 0.94 to 1.0.
  Donations, a school and a hairdresser landed in their new categories.
- The uncategorized bucket shrank from 33 to 15 rows, and none of them is
  confident any more: in v4, 16 rows were confidently "uncategorized", which
  counted as confident without saying anything.
- Confidence counts fell (level 2: 306 to 297) because more options split the
  mass and the new buckets compete with transfers. Counts across taxonomies
  are not comparable; accuracy against labelled rows is (spec section 5.2).
- No new mistake came with high confidence. Three kinds of rows stayed
  doubtful, and all go to review or to a rule: a transfer to the account
  holder's own name looks like a payment to a person (jev does not know the
  holder); a mortgage lender's direct debit splits between mortgage and loan;
  a short opaque card code flips between tobacco and transport under 0.4.
  After the run, `rent_mortgage` was extended with "mortgage lender"; the next
  run should confirm it.

## What we learned about jev

1. **It chooses, code owns the string.** jev has no free-text output
   (`Choice`, `Noul`, `Score` only). Generating candidate fragments in code
   and letting jev pick one is the documented extraction pattern, and it needs
   no merchant list: a supermarket abroad works on day one.
2. **Wrong answers with high confidence came from a badly posed question.**
   v1 showed known merchants with example texts that included the town; jev
   matched shops that only shared the town, at 0.97. Raising the threshold would not
   have helped. Rewriting the question (names only, `not_for` the same town,
   shortlist in code) did.
3. **Overlapping options split probability.** `ACME` and `ACME FOODS` are both
   right, so each gets a low confidence. Summing nested options, like summing
   leaves into their level-1 group, gives the confidence that matters.
4. **One call, many questions.** Merchant, category and subscription travel
   together. The questions are independent and it costs one round trip.
5. **Low confidence means missing information.** The uncertain rows were
   transfers to people, bank codes and donations, which a person could not
   label from the text either. They belong in `/review`, or in new
   categories.
6. **Deterministic and cheap.** About 1,800 input tokens per transaction at
   $0.042 per million. The model version is recorded with every label.

## Open items carried into the spec

- CaixaBank Bizum lines with a concept (`ENVIADO: ...`) should be detected in
  Python as Bizum, not read as a merchant.
- A transfer to the holder's own name needs own-account pairing (spec
  section 4.4) or a rule; jev cannot know whose name it is.
- Rosters above 254 shortlisted names need a trigram pre-filter; not needed at
  this volume.
