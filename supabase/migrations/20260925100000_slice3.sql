-- Slice 3 (docs/superpowers/specs/2026-09-25-slice-3-design.md, sections 2-4).

-- The user's own account of a row ("AirPods Pro"). jev never sees it; the slice 4 agent does.
alter table transactions add column note text
  constraint transactions_note_length check (char_length(note) <= 500);

-- A system step names the merchant of a loan from its contract number (spec 2.3).
alter table transactions drop constraint transactions_merchant_source_check;
alter table transactions add constraint transactions_merchant_source_check
  check (merchant_source in ('jev', 'user', 'rule', 'none'));

-- A refund rule changes the options jev sees instead of naming a category (spec 2.2).
alter table rules add column kind text not null default 'categorize'
  check (kind in ('categorize', 'refund'));
alter table rules alter column category_slug drop not null;
alter table rules add constraint rules_kind_category_check
  check ((kind = 'categorize') = (category_slug is not null));

-- The row type follows the category, not the sign (spec 2.1). Uncategorized rows keep the
-- sign rule they got at import.
update transactions t set tx_type = c.tx_type, updated_at = now()
from categories c
where c.slug = t.category_slug and t.tx_type <> c.tx_type;

-- Only money going out is a subscription.
update transactions set is_subscription = false where is_subscription and amount > 0;
