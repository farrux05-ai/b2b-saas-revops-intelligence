-- MODEL: stg_stripe__invoices
-- LAYER: Staging
-- SOURCE: raw_data.stripe.invoices
-- 
-- PHILOSOPHY: Thin Staging — typing and renaming only.
-- NO joins, group bys, case when business logic, or MRR computation.
-- =============================================================================

with source as (
    -- 1. RAW EXTRACTION: Select only required columns (no SELECT *!)
    select 
        id,
        subscription_id,
        customer_id,
        status,
        billing_reason,
        amount_due,
        amount_paid,
        amount_remaining,
        created,
        due_date,
        paid_at,
        period_start,
        period_end
    from {{ source('stripe', 'invoices') }}
),

renamed as (
    select
        -- ==========================================
        -- 2. IDENTITY: Natural Keys (source IDs)
        -- ==========================================
        cast(id as varchar)                             as invoice_id,
        cast(subscription_id as varchar)                as subscription_id,
        cast(customer_id as varchar)                    as customer_id,
        
        -- ==========================================
        -- 3. ATTRIBUTES: Proper typing
        -- ==========================================
        cast(status as varchar)                         as invoice_status,
        cast(billing_reason as varchar)                 as billing_reason,
        
        -- ==========================================
        -- 4. FINANCIALS: Cents to Dollars conversion.
        --    This is typing only, NOT computation!
        --    (Stripe contract: amounts are always in cents)
        -- ==========================================
        cast(amount_due as decimal(18, 2)) / 100        as amount_due,
        cast(amount_paid as decimal(18, 2)) / 100       as amount_paid,
        cast(amount_remaining as decimal(18, 2)) / 100  as amount_remaining,
        
        -- ==========================================
        -- 5. TIMESTAMPS: Cast source timestamps to native timestamps.
        -- ==========================================
        cast(created as timestamp)                      as created_at,
        cast(due_date as timestamp)                     as due_date,
        cast(paid_at as timestamp)                      as paid_at,
        cast(period_start as timestamp)                 as period_start,
        cast(period_end as timestamp)                   as period_end

    from source
)

-- ==========================================
-- 6. FINAL: No WHERE, GROUP BY, or JOIN clauses.
-- ==========================================
select * from renamed