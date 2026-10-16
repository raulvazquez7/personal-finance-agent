-- Quality of life, plan 1: a subscription cadence the user can set
-- (docs/superpowers/specs/2026-10-14-quality-of-life-design.md, section 3).

alter table merchants
  add column cadence text check (cadence in ('monthly', 'quarterly', 'yearly'));

drop view if exists agent.subscriptions;
drop view if exists public.v_subscriptions;

create view v_subscriptions as
with charges as (
  select merchant_id, booked_at, -amount as charge,
         booked_at - lag(booked_at) over (
           partition by merchant_id order by booked_at, id
         ) as gap_days
  from v_transactions_enriched
  where is_subscription and tx_type = 'expense' and amount < 0 and merchant_id is not null
), per_merchant as (
  select merchant_id, count(*) as charges, max(booked_at) as last_charge,
         percentile_cont(0.5) within group (order by gap_days) as median_gap
  from charges
  group by merchant_id
), latest_charge as (
  select distinct on (merchant_id) merchant_id, charge as latest_amount
  from charges
  order by merchant_id, booked_at desc, charge desc
), latest as (
  select max(booked_at) as latest_day from transactions
), detected as (
  select p.merchant_id, p.charges, p.last_charge, l.latest_amount,
         case
           when p.median_gap is null or p.median_gap <= 60 then 'monthly'
           when p.median_gap <= 200 then 'quarterly'
           else 'yearly'
         end as detected_cadence
  from per_merchant p
  join latest_charge l using (merchant_id)
)
select d.merchant_id, m.name as merchant_name, d.charges, d.last_charge, d.latest_amount,
       coalesce(m.cadence, d.detected_cadence) as cadence,
       case when m.cadence is null then 'auto' else 'user' end as cadence_source,
       round(d.latest_amount / case coalesce(m.cadence, d.detected_cadence)
         when 'yearly' then 12 when 'quarterly' then 3 else 1 end, 2) as monthly_equivalent,
       d.last_charge >= latest.latest_day - case coalesce(m.cadence, d.detected_cadence)
         when 'yearly' then 400 when 'quarterly' then 120 else 45 end as active
from detected d
join merchants m on m.id = d.merchant_id
cross join latest;

comment on view v_subscriptions is
  'Flagged money-out expenses per merchant. Cadence is merchants.cadence when set, otherwise '
  'the median gap: up to 60 days monthly, 61 to 200 every 3 months, over 200 yearly. A single '
  'charge is monthly. The amount is the latest charge. Active is 45, 120 or 400 days before '
  'the latest imported transaction (docs/money-rules.md).';

create view agent.subscriptions as
select merchant_name as merchant, charges, last_charge, latest_amount, cadence, cadence_source,
       monthly_equivalent, active
from public.v_subscriptions;

grant select on agent.subscriptions to agent_reader;
