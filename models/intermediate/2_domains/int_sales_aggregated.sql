with deals as (
    select * from {{ ref('stg_hubspot__deals') }}
),

final as (
    select
        hubspot_company_id,
        count(deal_sk) filter (
            where deal_stage not in ('closed_won', 'closed_lost')
        )                                               as open_deals_count,
        sum(amount) filter (where deal_stage = 'closed_won') as lifetime_revenue,
        max(closed_at) filter (where deal_stage = 'closed_won') as last_won_date

    from deals
    group by 1
)

select * from final
