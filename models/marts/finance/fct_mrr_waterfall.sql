{{
    config(
        materialized='table',
        schema='marts'
    )
}}

-- Step 1: Create a Date Spine (Months)
with months as (
    select
        date_trunc('month', range)::date as month_date
    from range(
        date_trunc('year', now() - interval '2 years'), 
        date_trunc('month', now() + interval '1 month'), 
        interval '1 month'
    )
),

-- Step 2: Get all accounts and their active periods
accounts as (
    select
        account_id,
        workspace_name,
        date_trunc('month', min(created_at))::date as first_active_month
    from {{ ref('stg_stripe__subscriptions') }} s
    join {{ ref('int_accounts_joined') }} sp on s.workspace_id = sp.internal_workspace_id
    group by 1, 2
),

-- Step 3: Create Account-Month Spine (Only for active periods)
account_month_spine as (
    select
        a.account_id,
        a.workspace_name,
        m.month_date
    from accounts a
    cross join months m
    where m.month_date >= a.first_active_month
),

-- Step 4: Get Monthly MRR per Account
monthly_mrr as (
    select
        sp.account_id,
        date_trunc('month', s.created_at)::date as month_date,
        sum(s.mrr_amount) as mrr
    from {{ ref('stg_stripe__subscriptions') }} s
    join {{ ref('int_accounts_joined') }} sp on s.workspace_id = sp.internal_workspace_id
    group by 1, 2
),

-- Step 5: Join Spine with Actual Data and use LAG to get Previous MRR
mrr_history as (
    select
        ams.account_id,
        ams.workspace_name,
        ams.month_date,
        coalesce(mm.mrr, 0) as mrr,
        coalesce(lag(mm.mrr) over (partition by ams.account_id order by ams.month_date), 0) as previous_month_mrr
    from account_month_spine ams
    left join monthly_mrr mm 
        on ams.account_id = mm.account_id 
        and ams.month_date = mm.month_date
),

-- Step 6: Final Waterfall Logic (Movements)
final as (
    select
        *,
        case
            when mrr > 0 and previous_month_mrr = 0 then 'new'
            when mrr > previous_month_mrr and previous_month_mrr > 0 then 'expansion'
            when mrr < previous_month_mrr and mrr > 0 then 'contraction'
            when mrr = 0 and previous_month_mrr > 0 then 'churn'
            when mrr > 0 and previous_month_mrr = 0 and exists (
                select 1 from mrr_history h2 
                where h2.account_id = mrr_history.account_id 
                and h2.month_date < mrr_history.month_date 
                and h2.mrr > 0
            ) then 'resurrection'
            else 'retained'
        end as mrr_movement_type,
        
        mrr - previous_month_mrr as mrr_change_amount
        
    from mrr_history
    where mrr > 0 or previous_month_mrr > 0
)

select * from final
