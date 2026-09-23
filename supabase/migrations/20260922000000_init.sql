-- Slice 1: accounts, imports and the normalized transaction ledger.

create type bank as enum ('bbva', 'caixabank');

create table accounts (
  id          uuid primary key default gen_random_uuid(),
  bank        bank not null,
  iban        text not null unique,
  name        text not null,
  currency    char(3) not null default 'EUR',
  created_at  timestamptz not null default now()
);

create table imports (
  id              uuid primary key default gen_random_uuid(),
  account_id      uuid not null references accounts(id),
  filename        text not null,
  file_sha256     text not null,
  period_start    date,
  period_end      date,
  rows_total      int not null,
  rows_new        int not null default 0,
  rows_duplicate  int not null default 0,
  imported_at     timestamptz not null default now()
);

create table transactions (
  id                   uuid primary key default gen_random_uuid(),
  account_id           uuid not null references accounts(id),
  import_id            uuid not null references imports(id),
  booked_at            date not null,
  value_date           date,
  amount               numeric(12,2) not null,
  currency             char(3) not null default 'EUR',
  description_raw      text not null,
  merchant             text,
  balance_after        numeric(12,2),
  dedup_key            text not null unique,
  tx_type              text not null check (tx_type in ('income', 'expense', 'transfer')),
  category_slug        text,
  category_source      text not null default 'none'
                       check (category_source in ('rule', 'jev', 'user', 'none')),
  category_confidence  real,
  jev_suggestions      jsonb,
  is_subscription      boolean not null default false,
  transfer_pair_id     uuid,
  needs_review         boolean not null default false,
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now()
);

create index transactions_account_booked_idx on transactions (account_id, booked_at desc);
