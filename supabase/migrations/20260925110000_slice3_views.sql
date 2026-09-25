-- The money rules, once (docs/money-rules.md; spec 2026-09-25-slice-3-design.md section 5).
-- Every total in the dashboards and the slice 4 agent comes from v_transactions_enriched.

create view v_transactions_enriched as
select t.id, t.account_id, a.name as account_name, a.bank, t.booked_at,
       to_char(t.booked_at, 'YYYY-MM') as month, t.amount, t.currency,
       case when t.amount < 0 then 'outgoing' else 'incoming' end as direction,
       t.tx_type, t.category_slug, c.level1, t.category_source,
       t.merchant_id, m.name as merchant_name, t.merchant as bank_merchant_text,
       t.description_raw, t.bank_concept, t.note, t.is_subscription, t.needs_review,
       t.transfer_pair_id,
       case when t.tx_type = 'expense' then -t.amount else 0 end as spend,
       case when t.tx_type = 'income' then t.amount else 0 end as income
from transactions t
join accounts a on a.id = t.account_id
left join categories c on c.slug = t.category_slug
left join merchants m on m.id = t.merchant_id;

comment on view v_transactions_enriched is
  'One row per transaction. spend = money spent (refunds negative), income = real income; '
  'transfers are 0 in both. Rules: docs/money-rules.md';

create view v_monthly_summary as
select month, account_id, sum(income) as income, sum(spend) as expenses,
       sum(income) - sum(spend) as savings, count(*) as row_count
from v_transactions_enriched
group by month, account_id;

comment on view v_monthly_summary is
  'Income, expenses and savings per month and account. Savings rate = savings / income, '
  'computed after summing accounts (docs/money-rules.md)';

create view v_spend_by_category as
select month, account_id, coalesce(level1, 'uncategorized') as level1,
       coalesce(category_slug, 'uncategorized') as category_slug, merchant_id, merchant_name,
       sum(spend) as spend, count(*) as row_count
from v_transactions_enriched
where tx_type = 'expense'
group by month, account_id, 3, 4, merchant_id, merchant_name;

comment on view v_spend_by_category is
  'Spend per month, account, group, category and merchant, net of refunds (docs/money-rules.md)';

create view v_subscriptions as
with charges as (
  select merchant_id, merchant_name, booked_at, -amount as charge,
         booked_at - lag(booked_at) over (partition by merchant_id order by booked_at) as gap_days
  from v_transactions_enriched
  where is_subscription and tx_type = 'expense' and amount < 0 and merchant_id is not null
), per_merchant as (
  select merchant_id, merchant_name, count(*) as charges, max(booked_at) as last_charge,
         percentile_cont(0.5) within group (order by charge)::numeric(12, 2) as typical_amount,
         percentile_cont(0.5) within group (order by gap_days) as median_gap
  from charges
  group by merchant_id, merchant_name
), latest as (
  select max(booked_at) as latest_day from transactions
)
select merchant_id, merchant_name, charges, last_charge, typical_amount,
       case when median_gap > 200 then 'yearly' else 'monthly' end as cadence,
       case when median_gap > 200 then round(typical_amount / 12, 2) else typical_amount end
         as monthly_equivalent,
       last_charge >= latest_day - case when median_gap > 200 then 400 else 45 end as active
from per_merchant cross join latest;

comment on view v_subscriptions is
  'Flagged money-out expenses per merchant. Active = charged within 45 days (monthly) or 400 '
  'days (yearly) of the latest imported transaction, not of today (docs/money-rules.md)';
