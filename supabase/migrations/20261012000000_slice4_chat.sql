-- Slice 4: what the chat agent can read, and the chat tables
-- (docs/superpowers/specs/2026-10-12-slice-4-chat-design.md, sections 4 and 8).

-- The agent reads only this schema. Its views are thin projections of the slice 3 views, so the
-- money rules stay in v_transactions_enriched. Not exposed: ids, raw bank descriptions (they can
-- hold a full card number), IBANs and confidences. The Supabase Data API does not expose `agent`.
create schema agent;

create view agent.transactions as
select booked_at, month, account_name as account, bank::text as bank, amount, direction,
       tx_type, spend, income,
       coalesce(category_slug, 'uncategorized') as category,
       coalesce(level1, 'uncategorized') as category_group,
       merchant_name as merchant, bank_merchant_text as bank_text,
       bank_concept as bank_operation, note, is_subscription, needs_review
from public.v_transactions_enriched;

create view agent.subscriptions as
select merchant_name as merchant, charges, last_charge, typical_amount, cadence,
       monthly_equivalent, active
from public.v_subscriptions;

-- The API switches to this role for every agent query (SET LOCAL ROLE, read-only transaction).
-- No login and no password: one database URL for everything. Roles are cluster-wide, so a
-- re-run of the migrations finds it already there.
do $$
begin
  if not exists (select from pg_roles where rolname = 'agent_reader') then
    create role agent_reader nologin;
  end if;
end
$$;

grant usage on schema agent to agent_reader;
grant select on all tables in schema agent to agent_reader;
-- Postgres 16+ gives the creator of a role no SET right on it (createrole_self_grant is empty on
-- Supabase): grant it explicitly to the user that runs the migrations, the API's user.
grant agent_reader to current_user with inherit false, set true;

create table chat_threads (
  id            uuid primary key default gen_random_uuid(),
  title         text check (char_length(title) <= 200),
  title_source  text check (title_source in ('model', 'fallback', 'user')),
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create index chat_threads_updated_idx on chat_threads (updated_at desc);

-- What the user sees. The agent's own memory is the LangGraph checkpoint, which summarization
-- rewrites; this history never shrinks.
create table chat_messages (
  id                 uuid primary key default gen_random_uuid(),
  thread_id          uuid not null references chat_threads(id) on delete cascade,
  role               text not null check (role in ('user', 'assistant')),
  content            text not null,
  queries            jsonb not null default '[]',
  status             text not null default 'ok' check (status in ('ok', 'error', 'stopped')),
  feedback           text check (feedback in ('up', 'down')),
  langfuse_trace_id  text,
  created_at         timestamptz not null default now()
);

create index chat_messages_thread_idx on chat_messages (thread_id, created_at);
