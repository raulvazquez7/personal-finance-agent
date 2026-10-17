-- Quality of life, plan 2: readable category and group names
-- (docs/superpowers/specs/2026-10-14-quality-of-life-design.md, section 8.1).
-- `finance seed` fills both from supabase/seed/categories.yaml. A missing name reads as the slug
-- with its first letter up ("software_ai" -> "Software ai"), the web's label().

alter table categories add column name text;

create table category_groups (
  level1 text primary key,
  name text not null
);

-- create or replace accepts new columns only at the end: the two names are last.
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

-- Replaced in place, not dropped, so agent_reader's grant stays.
create or replace view agent.transactions as
select booked_at, month, account_name as account, bank::text as bank, amount, direction,
       tx_type, spend, income,
       coalesce(category_slug, 'uncategorized') as category,
       coalesce(level1, 'uncategorized') as category_group,
       merchant_name as merchant, bank_merchant_text as bank_text,
       bank_concept as bank_operation, note, is_subscription, needs_review,
       category_name, group_name
from public.v_transactions_enriched;
