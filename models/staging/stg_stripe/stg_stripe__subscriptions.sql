-- MODEL: stg_stripe__subscriptions
-- LAYER: Staging
-- SOURCE: raw_data.stripe.subscriptions
-- 
-- PHILOSOPHY: Thin Staging — typing and renaming only.
-- NO joins, group bys, case when business logic, or MRR computation.
-- =============================================================================

with source as (
    -- 1. RAW EXTRACTION: Select only required columns (no SELECT *!)
    select 
        id,
        customer_id,
        metadata__workspace_id,
        metadata__hubspot_company_id,
        status,
        plan_id,
        unit_amount,
        quantity,
        cancel_at_period_end,
        created,
        current_period_start,
        current_period_end,
        trial_end
    from {{ source('stripe', 'subscriptions') }}
),

renamed as (
    select
        -- ==========================================
        -- 2. IDENTITY: Natural Keys (source IDs)
        -- ==========================================
        cast(id as varchar)                             as subscription_id,
        cast(customer_id as varchar)                    as customer_id,
        
        -- ==========================================
        -- 3. EXTERNAL MAPPING: Keys from metadata.
        --    This is the ONLY way to link Stripe with other systems.
        -- ==========================================
        cast(metadata__workspace_id as varchar)         as workspace_id,
        cast(metadata__hubspot_company_id as varchar)   as hubspot_company_id,
        
        -- ==========================================
        -- 4. ATTRIBUTES: Proper typing
        -- ==========================================
        cast(status as varchar)                         as subscription_status,
        cast(plan_id as varchar)                        as plan_id,
        
        -- ==========================================
        -- 5. FINANCIALS: Cents to Dollars conversion.
        --    This is typing only, NOT computation!
        --    (Stripe contract: amounts are always in cents)
        -- ==========================================
        cast(unit_amount as decimal(18, 2)) / 100       as unit_amount,
        cast(quantity as integer)                       as seats_purchased,
        
        -- ==========================================
        -- 6. BOOLEANS: Cast Stripe string/boolean values to native boolean.
        -- ==========================================
        cast(
            case 
                when cancel_at_period_end is null then false
                when lower(cast(cancel_at_period_end as varchar)) in ('true', '1', 'yes') then true 
                else false 
            end 
            as boolean
        )                                               as is_cancel_at_period_end,
        
        -- ==========================================
        -- 7. TIMESTAMPS: Cast source timestamps to native timestamps.
        -- ==========================================
        cast(created as timestamp)                      as created_at,
        cast(current_period_start as timestamp)         as current_period_start_at,
        cast(current_period_end as timestamp)           as current_period_end_at,
        cast(trial_end as timestamp)                    as trial_end_at

    from source
)

-- ==========================================
-- 8. FINAL: No WHERE, GROUP BY, or JOIN clauses.
-- ==========================================
select * from renamed