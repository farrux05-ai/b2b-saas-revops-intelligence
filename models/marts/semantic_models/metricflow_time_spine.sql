-- =============================================================================
-- MetricFlow Time Spine
--
-- Required by dbt MetricFlow semantic layer (dbt 1.6+).
-- Provides the date dimension used for all time-series metric queries.
--
-- Usage:  MetricFlow uses this to generate granularities (day, week, month,
--         quarter, year) automatically from the 'date_day' column.
--
-- Range:  2018-01-01 → current_date + 2 years (handles historical + forecasts)
--
-- Docs:   https://docs.getdbt.com/docs/build/metricflow-time-spine
-- =============================================================================

with

date_spine as (
    {{ dbt_utils.date_spine(
        datepart   = "day",
        start_date = "cast('2018-01-01' as date)",
        end_date   = "cast(current_date + interval '2 years' as date)"
    ) }}
)

select
    cast(date_day as date) as date_day

from date_spine
