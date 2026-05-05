{{
    config(
        materialized='table',
        schema='marts'
    )
}}

-- dim_dates: Universal date dimension table for time-series analysis
-- Grain: one row = one calendar date

with date_spine as (
    select 
        date_trunc('day', generated_date)::date as date_day
    from generate_series(
        '2020-01-01'::date,
        (current_date + interval '2 years')::date,
        '1 day'::interval
    ) as t(generated_date)
),

holidays as (
    select * from {{ ref('holidays') }}
)

select
    -- Identity
    d.date_day,
    d.date_day as date_id,
    
    -- Year-Quarter-Month
    extract(year from d.date_day)::int as year,
    extract(quarter from d.date_day)::int as quarter,
    extract(month from d.date_day)::int as month,
    strftime(d.date_day, '%Y-%m') as year_month,
    
    -- Week
    extract(week from d.date_day)::int as week_of_year,
    strftime(d.date_day, '%Y-W%V') as year_week,
    
    -- Day
    extract(day from d.date_day)::int as day_of_month,
    extract(dow from d.date_day)::int as day_of_week_num,
    case 
        when extract(dow from d.date_day) = 0 then 'Sunday'
        when extract(dow from d.date_day) = 1 then 'Monday'
        when extract(dow from d.date_day) = 2 then 'Tuesday'
        when extract(dow from d.date_day) = 3 then 'Wednesday'
        when extract(dow from d.date_day) = 4 then 'Thursday'
        when extract(dow from d.date_day) = 5 then 'Friday'
        when extract(dow from d.date_day) = 6 then 'Saturday'
    end as day_of_week_name,
    extract(doy from d.date_day)::int as day_of_year,
    
    -- Flags
    case when extract(dow from d.date_day) in (0, 6) then true else false end as is_weekend,
    
    -- Dynamic Holiday Logic from Seed
    case when h.holiday_date is not null then true else false end as is_holiday,
    h.holiday_name,
    
    -- Fiscal (assuming calendar year = fiscal year)
    extract(year from d.date_day)::int as fiscal_year,
    extract(quarter from d.date_day)::int as fiscal_quarter,
    extract(month from d.date_day)::int as fiscal_month,
    
    current_timestamp as updated_at

from date_spine d
left join holidays h on d.date_day = h.holiday_date
order by d.date_day
