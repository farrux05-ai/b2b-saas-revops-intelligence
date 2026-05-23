# dbt MetricFlow Semantic Layer — Best Practices & Lessons Learned

This document serves as a "skill" or knowledge base rulebook for building and maintaining the dbt Semantic Layer (MetricFlow) in this repository. It captures critical lessons learned during the initial implementation to prevent repeating the same errors in the future.

## 1. Global Measure Uniqueness (No Name Collisions)
**Mistake**: Naming measures generically like `total_mrr` or `upsell_ready_count` in multiple semantic models (e.g., in both `sm_core.yml` and `sm_customer_success.yml`). MetricFlow requires measure names to be **globally unique** across the entire project.
**Best Practice**: Always prefix measures with the domain or entity context if there is any chance of collision.
- ❌ Bad: `total_mrr`, `upsell_ready_count`
- ✅ Good: `accounts_mrr`, `cs_mrr_at_risk`, `accounts_upsell_ready`, `cs_upsell_ready_count`

## 2. Time Spine Requirement
**Mistake**: Assuming MetricFlow would parse without a time spine because the metrics were simple.
**Best Practice**: A `metricflow_time_spine` model is a strict requirement for the Semantic Layer. 
- You must create a SQL model (e.g., using `dbt_utils.date_spine`) generating daily dates (`date_day`).
- In dbt 1.9+, this must be registered in a YAML file using the `time_spines:` block (not in `dbt_project.yml` as `metric-flow-time-spine`, which is deprecated/removed).
```yaml
time_spines:
  - name: time_spine_day
    node_relation:
      alias: metricflow_time_spine
    primary_column:
      name: date_day
      time_granularity: day
```

## 3. EVERY Measure Needs an `agg_time_dimension`
**Mistake**: Using `agg_time_dimension: null` for snapshot or aggregate tables (like `unit_economics`, `attribution`, `pql_signals`) that don't naturally have a time-series grain. MetricFlow's parser will throw an `AssertionError` if a measure lacks a time dimension.
**Best Practice**: Every semantic model *must* have at least one time dimension, and every measure must map to it.
- If the table is a static aggregate, inject a dummy date in the SQL (e.g., `cast(current_date as date) as snapshot_date`).
- If the table has a creation date (e.g., `workspace_created_at`), use it.
- Map it in the YAML: `defaults: { agg_time_dimension: snapshot_date }`.

## 4. Ratios and Derived Metrics (dbt 1.9+ Syntax)
**Mistake**: Trying to use the `ratio` metric type by referencing `measure` names directly, and trying to use `fill_nulls_with: 0` inside the ratio type_params.
**Best Practice**: The `ratio` type has strict reference rules in newer dbt versions. The most flexible, robust way to calculate ratios or rates is using the **`derived`** metric type.
- Define the numerator and denominator as `simple` metrics first.
- Create a `derived` metric using `expr` and `metric()` references.
- `fill_nulls_with: 0` belongs ONLY on the `measure` definition inside the `simple` metric.
```yaml
# Correct Derived Metric (Rate/Ratio)
- name: win_rate
  type: derived
  type_params:
    expr: "metric('won_deals') / nullif(metric('total_deals'), 0)"
    metrics:
      - name: won_deals
      - name: total_deals
```

## 5. Metadata for BI Tools (Lightdash)
**Best Practice**: Always keep formatting, labels, and grouping in the `meta` tags of the `metrics.yml`. Lightdash will natively parse these and automatically organize the UI for business users.
```yaml
meta:
  group_label: "Sales"
  format: "percent"
  team: "Sales"
```
