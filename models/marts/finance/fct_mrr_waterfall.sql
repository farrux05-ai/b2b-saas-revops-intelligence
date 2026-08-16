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
--   Sourced from int_billing_aggregated and int_accounts_joined.
-- =============================================================================

-- Step 0: Account identity spine
with spine as (
    select * from {{ ref('int_accounts_joined') }}
),

-- Step 1: Billing subscriptions with active date ranges
subscriptions_with_mrr as (
    select
        s.workspace_id,
        sp.account_id,
        sp.workspace_name,
        s.current_period_start_at,
        s.current_period_end_at,
        s.latest_subscription_status                    as subscription_status,
        s.total_mrr                                     as mrr_amount
    from {{ ref('int_billing_aggregated') }} s
    join spine sp on s.workspace_id = sp.internal_workspace_id
),

-- Step 2: Date Spine (Monthly sequence across active window)
months as (
    select
        date_month as month_date
    from (
        {{ dbt_utils.date_spine(
            datepart="month",
            start_date="cast(date_trunc('year', current_date - interval '2 years') as date)",
            end_date="cast(date_trunc('month', current_date + interval '1 month') as date)"
        ) }}
    )
),

-- Step 3: Account active date range
accounts_active_range as (
    select
        account_id,
        workspace_name,
        date_trunc('month', min(current_period_start_at))::date as first_active_month
    from subscriptions_with_mrr
    group by 1, 2
),

-- Step 4: Account-Month Spine
account_month_spine as (
    select
        a.account_id,
        a.workspace_name,
        m.month_date
    from accounts_active_range a
    cross join months m
    where m.month_date >= a.first_active_month
),

-- Step 5: Monthly MRR aggregation
monthly_mrr as (
    select
        s.account_id,
        m.month_date,
        sum(
            case when s.subscription_status in ('active', 'trialing') 
            then s.mrr_amount else 0 end
        )                                               as mrr,
        sum(
            case when s.subscription_status = 'past_due' 
            then s.mrr_amount else 0 end
        )                                               as at_risk_mrr
    from subscriptions_with_mrr s
    join months m
      on date_trunc('month', s.current_period_start_at)::date <= m.month_date
     and date_trunc('month', s.current_period_end_at)::date   >= m.month_date
    where s.subscription_status in ('active', 'trialing', 'past_due')
    group by 1, 2
),

-- Step 6: Compute LAG for previous month MRR
mrr_history as (
    select
        ams.account_id,
        ams.workspace_name,
        ams.month_date,
        coalesce(mm.mrr, 0)                             as mrr,
        coalesce(mm.at_risk_mrr, 0)                     as at_risk_mrr,
        coalesce(
            lag(coalesce(mm.mrr, 0)) over (
                partition by ams.account_id
                order by ams.month_date
            ), 0
        )                                               as previous_month_mrr
    from account_month_spine ams
    left join monthly_mrr mm
        on ams.account_id = mm.account_id
        and ams.month_date = mm.month_date
),

-- Step 7: MRR Waterfall Classification
final as (
    select
        {{ dbt_utils.generate_surrogate_key(['account_id', 'month_date']) }} as waterfall_id,
        account_id,
        workspace_name,
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
