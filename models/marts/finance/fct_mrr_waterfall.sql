-- =============================================================================
-- fct_mrr_waterfall: Monthly MRR Movements (New / Expansion / Contraction / Churn)
-- Mart: finance
--
-- Classic SaaS MRR Waterfall using account-month spine + LAG window function.
-- FIX 1: Subscription logic now uses validity period (start/end) instead of created_at.
-- FIX 2: Consolidated int_accounts_joined to avoid double joins.
-- FIX 3: Handles resurrection before new biz signal.
-- =============================================================================

-- Step 0: Get account spine (Single source for joins)
with spine as (
    select * from {{ ref('int_accounts_joined') }}
),

-- Step 1: Compute MRR from subscriptions (with validity dates)
subscriptions_with_mrr as (
    select
        s.workspace_id,
        sp.account_id,
        sp.workspace_name,
        s.created_at,
        s.current_period_start_at,
        s.current_period_end_at,
        s.subscription_status,
        s.mrr_amount
    from {{ ref('int_subscriptions_enriched') }} s
    join spine sp on s.workspace_id = sp.internal_workspace_id
),

-- Step 2: Create a Date Spine (last 2 years)
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

-- Step 3: Get all accounts and their first active month
accounts_active_range as (
    select
        account_id,
        workspace_name,
        date_trunc('month', min(created_at))::date      as first_active_month
    from subscriptions_with_mrr
    group by 1, 2
),

-- Step 4: Account-Month spine (only for each account's active period)
account_month_spine as (
    select
        a.account_id,
        a.workspace_name,
        m.month_date
    from accounts_active_range a
    cross join months m
    where m.month_date >= a.first_active_month
),

-- Step 5: Actual MRR per account per month
-- FIXED: Joins subscriptions with months on range conditions to avoid CROSS JOIN fan-out
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

-- Step 6: Join spine with actual MRR, compute previous month via LAG
mrr_history as (
    select
        ams.account_id,
        ams.workspace_name,
        ams.month_date,
        coalesce(mm.mrr, 0)                             as mrr,
        coalesce(mm.at_risk_mrr, 0)                      as at_risk_mrr,
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

-- Step 7: MRR Waterfall Movement Classification
final as (
    select
        -- Surrogate key for PK testing
        {{ dbt_utils.generate_surrogate_key(['account_id', 'month_date']) }} as waterfall_id,
        account_id,
        workspace_name,
        month_date,
        mrr,
        at_risk_mrr,
        previous_month_mrr,
        mrr - previous_month_mrr                        as mrr_change_amount,

        case
            -- Churned before, came back
            when mrr > 0
             and previous_month_mrr = 0
             and exists (
                 select 1 from mrr_history h2
                 where h2.account_id = mrr_history.account_id
                   and h2.month_date < mrr_history.month_date
                   and h2.mrr > 0
             )                                          then 'resurrection'
            -- Completely new account
            when mrr > 0 and previous_month_mrr = 0    then 'new'
            -- Paying more than last month
            when mrr > previous_month_mrr
             and previous_month_mrr > 0                 then 'expansion'
            -- Paying less than last month, but not zero
            when mrr < previous_month_mrr
             and mrr > 0                                then 'contraction'
            -- Went to zero
            when mrr = 0
             and previous_month_mrr > 0                 then 'churn'
            -- Same MRR
            else 'retained'
        end                                             as mrr_movement_type

    from mrr_history
    where mrr > 0 or previous_month_mrr > 0  -- exclude inactive months
)

select * from final
