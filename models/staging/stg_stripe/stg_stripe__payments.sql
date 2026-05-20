-- MODEL: stg_stripe__payments
-- LAYER: Staging
-- SOURCE: raw_data.stripe.payments
-- 
-- PHILOSOPHY: Thin Staging — typing and renaming only.
-- NO joins, group bys, case when business logic, or MRR computation.
-- =============================================================================

with source as (
    -- 1. RAW EXTRACTION: Select only required columns (no SELECT *!)
    select 
        id,
        invoice_id,
        customer_id,
        status,
        failure_code,
        amount,
        currency,
        created
    from {{ source('stripe', 'payments') }}
),

renamed as (
    select
        -- ==========================================
        -- 2. IDENTITY: Natural Keys (source IDs)
        -- ==========================================
        cast(id as varchar)                             as payment_id,
        cast(invoice_id as varchar)                     as invoice_id,
        cast(customer_id as varchar)                    as customer_id,
        
        -- ==========================================
        -- 3. ATTRIBUTES: Proper typing
        -- ==========================================
        cast(status as varchar)                         as payment_status,
        cast(failure_code as varchar)                   as failure_code,
        cast(currency as varchar)                       as currency,
        
        -- ==========================================
        -- 4. FINANCIALS: Cents to Dollars conversion.
        --    This is typing only, NOT computation!
        --    (Stripe contract: amounts are always in cents)
        -- ==========================================
        cast(amount as decimal(18, 2)) / 100            as amount,
        
        -- ==========================================
        -- 5. TIMESTAMPS: Cast source timestamps to native timestamps.
        -- ==========================================
        cast(created as timestamp)                      as created_at

    from source
)

-- ==========================================
-- 6. FINAL: No WHERE, GROUP BY, or JOIN clauses.
-- ==========================================
select * from renamed