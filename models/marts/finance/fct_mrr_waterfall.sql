{{ config(materialized='table') }}

-- =============================================================================
-- MODEL: fct_mrr_waterfall
-- MART: finance
-- GRAIN: One row per account_id x month_date
--
-- TARGET AUDIENCE: Finance & Executive Leadership — Monthly MRR Waterfall (New, Expansion, Contraction, Churn, Resurrection).
--
-- BUSINESS LOGIC:
--   Classic SaaS MRR Waterfall using account-month date spine + LAG window function.
--
-- FIX (2026-08, audit): this model used to source monthly MRR from
-- int_billing_aggregated's CURRENT subscription billing window
-- (current_period_start_at/current_period_end_at, ~1 month wide) matched
-- against a 24-month date spine. Since that window only ever covers the
-- most recent month, virtually every other month in the spine received
-- $0 MRR, which made almost every account look "new" in a single month
-- and left starting_mrr at $0 everywhere else — cascading into NRR/GRR
-- being NULL for nearly every month downstream (fct_retention_cohorts).
-- Monthly MRR now comes from int_mrr_monthly, which reconstructs real
-- historical recurring revenue from paid Stripe invoices (each invoice is
-- a dated billing cycle), giving genuine month-by-month history.
-- =============================================================================

-- Step 0: Account identity spine
with spine as (
    select * from {{ ref('dim_accounts') }}
),

-- Step 1: Real historical monthly billing, mapped to accounts
monthly_billing as (
    select
        m.workspace_id,
        sp.account_id,
        sp.workspace_name,
        sp.company_name,
        m.month_date,
        m.mrr,
        m.at_risk_mrr
    from {{ ref('int_mrr_monthly') }} m
    join spine sp on m.workspace_id = sp.internal_workspace_id
),

-- Step 2: Collapse to account grain (defensive — guards against an account
-- ever being linked to more than one workspace)
account_monthly as (
    select
        account_id,
        max(workspace_name)                             as workspace_name,
        max(company_name)                               as company_name,
        month_date,
        sum(mrr)                                        as mrr,
        sum(at_risk_mrr)                                as at_risk_mrr
    from monthly_billing
    group by account_id, month_date
),

-- Step 3: Date Spine (Monthly sequence across active window)
months as (
    select
        date_month as month_date
    from (
        {{ dbt_utils.date_spine(
            datepart="month",
            start_date="cast(date_trunc('year', dateadd(year, -2, current_date())) as date)",
            end_date="cast(date_trunc('month', dateadd(month, 1, current_date())) as date)"
        ) }}
    )
),

-- Step 4: Account active date range
accounts_active_range as (
    select
        account_id,
        max(workspace_name)                             as workspace_name,
        max(company_name)                               as company_name,
        min(month_date)                                 as first_active_month
    from account_monthly
    group by 1
),

-- Step 5: Account-Month Spine
-- (bounded to "now" — no point projecting months we have no invoice data for yet)
account_month_spine as (
    select
        a.account_id,
        a.workspace_name,
        a.company_name,
        m.month_date
    from accounts_active_range a
    cross join months m
    where m.month_date >= a.first_active_month
      and m.month_date <= date_trunc('month', current_date)::date
),

-- Step 6: Attach real monthly MRR onto the spine
mrr_history as (
    select
        ams.account_id,
        ams.workspace_name,
        ams.company_name,
        ams.month_date,
        coalesce(am.mrr, 0)                             as mrr,
        coalesce(am.at_risk_mrr, 0)                     as at_risk_mrr,
        coalesce(
            lag(coalesce(am.mrr, 0)) over (
                partition by ams.account_id
                order by ams.month_date
            ), 0
        )                                               as previous_month_mrr
    from account_month_spine ams
    left join account_monthly am
        on ams.account_id = am.account_id
        and ams.month_date = am.month_date
),

-- Step 7: MRR Waterfall Classification
final as (
    select
        {{ dbt_utils.generate_surrogate_key(['account_id', 'month_date']) }} as waterfall_id,
        account_id,
        workspace_name,
        company_name,
        month_date,
        mrr,
        at_risk_mrr,
        previous_month_mrr,
        mrr - previous_month_mrr                        as mrr_change_amount,

        case
            -- Previously churned, returned to active state
            when mrr > 0
             and previous_month_mrr = 0
             and exists (
                 select 1 from mrr_history h2
                 where h2.account_id = mrr_history.account_id
                   and h2.month_date < mrr_history.month_date
                   and h2.mrr > 0
             )                                          then 'resurrection'
            -- Brand new customer
            when mrr > 0 and previous_month_mrr = 0    then 'new'
            -- Increased MRR compared to last month
            when mrr > previous_month_mrr
             and previous_month_mrr > 0                 then 'expansion'
            -- Decreased MRR compared to last month (non-zero)
            when mrr < previous_month_mrr
             and mrr > 0                                then 'contraction'
            -- Dropped to zero MRR
            when mrr = 0
             and previous_month_mrr > 0                 then 'churn'
            -- Unchanged MRR
            else 'retained'
        end                                             as mrr_movement_type

    from mrr_history
    where mrr > 0 or previous_month_mrr > 0  -- Filter out completely inactive months
)

select * from final