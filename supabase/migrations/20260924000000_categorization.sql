-- Slice 2: taxonomy, merchants, system rules, label history; card numbers leave `merchant`.

create table categories (
  slug     text primary key,
  tx_type  text not null check (tx_type in ('income', 'expense', 'transfer')),
  level1   text not null,
  what     text not null,
  not_for  text
);

create table merchants (
  id                  uuid primary key default gen_random_uuid(),
  name                text not null unique,
  match_key           text not null unique,
  confirmed           boolean not null default false,
  category_slug       text references categories(slug),
  is_subscription     boolean,
  merge_candidate_id  uuid references merchants(id) on delete set null,
  merge_confidence    real,
  created_at          timestamptz not null default now()
);

create table rules (
  id             uuid primary key default gen_random_uuid(),
  name           text not null unique,
  bank           bank,
  match_field    text not null check (match_field in ('bank_concept', 'merchant')),
  pattern        text not null,
  direction      text not null check (direction in ('outgoing', 'incoming', 'any')),
  category_slug  text not null references categories(slug),
  enabled        boolean not null default true
);

alter table transactions
  add column bank_concept            text,
  add column card_last4              char(4),
  add column merchant_id             uuid references merchants(id),
  add column merchant_source         text not null default 'none'
                                     check (merchant_source in ('jev', 'user', 'none')),
  add column merchant_confidence     real,
  add column category_probabilities  jsonb,
  add column subscription_score      real,
  drop column jev_suggestions,
  add constraint transactions_category_fk foreign key (category_slug) references categories(slug);

alter table transactions drop constraint transactions_category_source_check;
alter table transactions add constraint transactions_category_source_check
  check (category_source in ('rule', 'merchant', 'jev', 'user', 'none'));

create index transactions_review_idx on transactions (needs_review) where needs_review;
create index transactions_merchant_idx on transactions (merchant_id);

create table transaction_labels (
  id               uuid primary key default gen_random_uuid(),
  transaction_id   uuid not null references transactions(id) on delete cascade,
  merchant_id      uuid references merchants(id) on delete set null,
  category_slug    text references categories(slug),
  is_subscription  boolean not null default false,
  source           text not null check (source in ('rule', 'merchant', 'jev', 'user')),
  confidence       real,
  model            text,
  labeled_at       timestamptz not null default now()
);

create index transaction_labels_tx_idx on transaction_labels (transaction_id, labeled_at desc);

-- Backfill for rows imported in slice 1 (spec 4.2); it stays last and idempotent, since
-- tests/test_schema.py reruns it. A card number is a whole word of 12 to 19 digits.
update transactions t
set bank_concept = split_part(t.description_raw, ' | ', 1)
from accounts a
where a.id = t.account_id and a.bank = 'bbva';

update transactions
set card_last4 = right(substring(description_raw from '\m\d{12,19}\M'), 4)
where description_raw ~ '\m\d{12,19}\M';

update transactions
set merchant = nullif(btrim(regexp_replace(regexp_replace(merchant, '\m\d{12,19}\M', '', 'g'),
                                           '\s+', ' ', 'g')), '')
where merchant ~ '\m\d{12,19}\M';

-- A BBVA line without ' | ' copied its whole text, card number included, into bank_concept.
update transactions
set bank_concept = nullif(btrim(regexp_replace(regexp_replace(bank_concept, '\m\d{12,19}\M', '',
                                                              'g'), '\s+', ' ', 'g')), '')
where bank_concept ~ '\m\d{12,19}\M';
