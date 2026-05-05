---
name: revops-metrics-expert
description: Expert in B2B SaaS revenue operations metrics and business logic. Use this skill whenever the user mentions SaaS metrics (ARR, MRR, NRR, churn, retention, CAC, LTV, cohorts, expansion, contraction), revenue calculations, subscription analytics, customer lifecycle analysis, revenue waterfall, bookings vs billings vs revenue, or asks about how to calculate, model, or analyze any B2B SaaS business metrics. Also use when debugging metric discrepancies, designing metric definitions, or building revenue reporting models. Even if the user doesn't explicitly say "RevOps" or "metrics," trigger this skill for any question about measuring SaaS business performance.
---

# RevOps Metrics Expert

Expert guidance for B2B SaaS revenue operations analytics, metric definitions, and business logic implementation.

## Core Principles

### 1. **Metric Definitions Must Be Unambiguous**
Every metric needs:
- **Clear calculation logic** (including edge cases)
- **Time grain** (daily, monthly, annual)
- **Point-in-time vs period** distinction
- **Denominator clarity** (per customer, per account, per logo)

### 2. **Revenue Recognition ≠ Cash Flow ≠ Bookings**
Always distinguish:
- **Bookings**: Signed contract value
- **Billings**: Invoice amount sent to customer
- **Revenue**: Recognized per accounting rules (ASC 606)
- **Cash**: Actual money received

### 3. **Cohort-Based Analysis Is King**
For churn, retention, expansion — always cohort by:
- Start date
- Product/plan type
- Customer segment
- ARR band

---

## Key Metrics Library

### ARR (Annual Recurring Revenue)

**Definition**: Normalized annual value of all active subscriptions at a point in time.

**Calculation**:
```sql
-- Point-in-time ARR snapshot
SELECT
  date_trunc('month', snapshot_date) AS month,
  SUM(mrr * 12) AS arr
FROM subscription_snapshots
WHERE status = 'active'
  AND snapshot_date = last_day_of_month
GROUP BY 1
```

**Common mistakes**:
- Including non-recurring revenue (setup fees, professional services)
- Not handling mid-month changes correctly
- Mixing bookings with ARR

**Edge cases**:
- Multi-year contracts: Divide total by years, or annualize current year only?
- Usage-based pricing: Use trailing 12-month average
- Paused subscriptions: Exclude from ARR
- Free trials: Only include if converting to paid

---

### MRR (Monthly Recurring Revenue)

**Components**:
```
MRR = New MRR + Expansion MRR - Contraction MRR - Churned MRR
```

**Movement categories**:
- **New MRR**: New customers going from $0 to $X
- **Expansion MRR**: Existing customers increasing spend (upsells, usage growth)
- **Contraction MRR**: Existing customers decreasing spend (downgrades)
- **Churned MRR**: Customers going from $X to $0
- **Reactivation MRR**: Previously churned customers returning

**Implementation**:
```sql
WITH mrr_changes AS (
  SELECT
    customer_id,
    month,
    mrr_current,
    LAG(mrr_current) OVER (PARTITION BY customer_id ORDER BY month) AS mrr_previous,
    LAG(month) OVER (PARTITION BY customer_id ORDER BY month) AS previous_month
  FROM monthly_mrr_snapshots
),
classified AS (
  SELECT
    customer_id,
    month,
    CASE
      WHEN mrr_previous IS NULL AND mrr_current > 0 THEN 'new'
      WHEN mrr_previous = 0 AND mrr_current > 0 THEN 'reactivation'
      WHEN mrr_previous > 0 AND mrr_current = 0 THEN 'churn'
      WHEN mrr_current > mrr_previous THEN 'expansion'
      WHEN mrr_current < mrr_previous THEN 'contraction'
      ELSE 'flat'
    END AS movement_type,
    mrr_current - COALESCE(mrr_previous, 0) AS mrr_change
  FROM mrr_changes
)
SELECT
  month,
  movement_type,
  SUM(mrr_change) AS total_change,
  COUNT(DISTINCT customer_id) AS customer_count
FROM classified
GROUP BY 1, 2
```

---

### NRR (Net Revenue Retention)

**Definition**: Percentage of revenue retained from a cohort over time, including expansion.

**Formula**:
```
NRR = (Starting ARR + Expansion - Contraction - Churn) / Starting ARR
```

**Gold standard calculation** (cohort-based):
```sql
WITH cohort_start AS (
  SELECT
    DATE_TRUNC('month', first_payment_date) AS cohort_month,
    customer_id,
    arr AS starting_arr
  FROM customers
  WHERE first_payment_date >= '2023-01-01'
),
cohort_current AS (
  SELECT
    cs.cohort_month,
    cs.customer_id,
    cs.starting_arr,
    COALESCE(s.arr, 0) AS current_arr,
    DATEDIFF('month', cs.cohort_month, CURRENT_DATE) AS months_since_start
  FROM cohort_start cs
  LEFT JOIN subscription_snapshots s
    ON cs.customer_id = s.customer_id
    AND s.snapshot_date = CURRENT_DATE
)
SELECT
  cohort_month,
  months_since_start,
  SUM(current_arr) / SUM(starting_arr) AS nrr
FROM cohort_current
GROUP BY 1, 2
ORDER BY 1, 2
```

**Key insights**:
- NRR > 100% = negative churn (expansion > churn)
- NRR 90-100% = healthy retention
- NRR < 90% = concerning churn problem

**Segmentation matters**:
```sql
-- NRR by customer segment
SELECT
  cohort_month,
  CASE
    WHEN starting_arr < 10000 THEN 'SMB'
    WHEN starting_arr < 50000 THEN 'Mid-Market'
    ELSE 'Enterprise'
  END AS segment,
  SUM(current_arr) / SUM(starting_arr) AS nrr
FROM cohort_current
GROUP BY 1, 2
```

---

### Churn Rate

**Two types**:
1. **Logo Churn**: % of customers who leave
2. **Revenue Churn**: % of ARR lost

**Critical distinction**:
```sql
-- Logo churn (count-based)
SELECT
  month,
  COUNT(DISTINCT churned_customer_id) / 
    COUNT(DISTINCT starting_customer_id) AS logo_churn_rate
FROM monthly_cohorts
GROUP BY 1

-- Revenue churn (dollar-based)
SELECT
  month,
  SUM(churned_arr) / SUM(starting_arr) AS revenue_churn_rate
FROM monthly_cohorts
GROUP BY 1
```

**Cohort-based churn** (the right way):
```sql
WITH monthly_cohorts AS (
  SELECT
    DATE_TRUNC('month', first_payment_date) AS cohort_month,
    customer_id,
    arr AS starting_arr
  FROM customers
),
churn_events AS (
  SELECT
    mc.cohort_month,
    mc.customer_id,
    mc.starting_arr,
    ce.churn_date,
    DATEDIFF('month', mc.cohort_month, ce.churn_date) AS months_to_churn
  FROM monthly_cohorts mc
  LEFT JOIN churn_events ce ON mc.customer_id = ce.customer_id
)
SELECT
  cohort_month,
  months_to_churn,
  COUNT(DISTINCT CASE WHEN churn_date IS NOT NULL THEN customer_id END) / 
    COUNT(DISTINCT customer_id) AS cumulative_churn_rate
FROM churn_events
GROUP BY 1, 2
ORDER BY 1, 2
```

---

### CAC (Customer Acquisition Cost)

**Formula**:
```
CAC = (Sales + Marketing Spend) / New Customers Acquired
```

**Implementation**:
```sql
WITH spend AS (
  SELECT
    DATE_TRUNC('month', expense_date) AS month,
    SUM(amount) AS total_spend
  FROM expenses
  WHERE department IN ('Sales', 'Marketing')
  GROUP BY 1
),
customers AS (
  SELECT
    DATE_TRUNC('month', first_payment_date) AS month,
    COUNT(DISTINCT customer_id) AS new_customers
  FROM customers
  GROUP BY 1
)
SELECT
  s.month,
  s.total_spend / c.new_customers AS cac,
  s.total_spend,
  c.new_customers
FROM spend s
JOIN customers c ON s.month = c.month
```

**Segmented CAC**:
```sql
-- CAC by channel
SELECT
  acquisition_channel,
  SUM(spend) / COUNT(DISTINCT customer_id) AS cac_by_channel
FROM customer_acquisition
GROUP BY 1
```

**Payback period**:
```sql
-- Months to recover CAC
SELECT
  customer_id,
  acquisition_cost / monthly_revenue AS months_to_payback
FROM customers
```

---

### LTV (Lifetime Value)

**Simple formula**:
```
LTV = ARPU / Churn Rate
```

**Better formula** (with gross margin):
```
LTV = (ARPU × Gross Margin %) / Churn Rate
```

**Cohort-based LTV**:
```sql
WITH customer_revenue AS (
  SELECT
    customer_id,
    DATE_TRUNC('month', first_payment_date) AS cohort_month,
    SUM(revenue) AS total_revenue,
    MIN(first_payment_date) AS first_date,
    MAX(last_payment_date) AS last_date,
    DATEDIFF('month', MIN(first_payment_date), MAX(last_payment_date)) AS lifetime_months
  FROM payments
  GROUP BY 1, 2
)
SELECT
  cohort_month,
  AVG(total_revenue) AS avg_ltv,
  AVG(lifetime_months) AS avg_lifetime_months,
  AVG(total_revenue) / AVG(lifetime_months) AS avg_monthly_revenue
FROM customer_revenue
GROUP BY 1
ORDER BY 1
```

**LTV:CAC Ratio**:
```sql
SELECT
  cohort_month,
  AVG(ltv) / AVG(cac) AS ltv_cac_ratio
FROM customer_metrics
GROUP BY 1

-- Rule of thumb:
-- LTV:CAC > 3.0 = healthy
-- LTV:CAC 1.5-3.0 = acceptable
-- LTV:CAC < 1.5 = unprofitable
```

---

### Quick Ratio

**Definition**: Growth efficiency metric.

**Formula**:
```
Quick Ratio = (New MRR + Expansion MRR) / (Churned MRR + Contraction MRR)
```

**Implementation**:
```sql
WITH mrr_movements AS (
  SELECT
    month,
    SUM(CASE WHEN movement_type = 'new' THEN mrr_change ELSE 0 END) AS new_mrr,
    SUM(CASE WHEN movement_type = 'expansion' THEN mrr_change ELSE 0 END) AS expansion_mrr,
    SUM(CASE WHEN movement_type = 'churn' THEN ABS(mrr_change) ELSE 0 END) AS churned_mrr,
    SUM(CASE WHEN movement_type = 'contraction' THEN ABS(mrr_change) ELSE 0 END) AS contraction_mrr
  FROM mrr_changes
  GROUP BY 1
)
SELECT
  month,
  (new_mrr + expansion_mrr) / NULLIF(churned_mrr + contraction_mrr, 0) AS quick_ratio
FROM mrr_movements
```

**Interpretation**:
- Quick Ratio > 4 = very healthy growth
- Quick Ratio 2-4 = good growth
- Quick Ratio < 2 = struggling to grow

---

## Revenue Waterfall

**Movement from one period to next**:
```
Ending ARR = Starting ARR + New + Expansion - Contraction - Churn + Reactivation
```

**SQL implementation**:
```sql
SELECT
  'Starting ARR' AS metric, starting_arr AS value
UNION ALL
SELECT 'New ARR', new_arr
UNION ALL
SELECT 'Expansion ARR', expansion_arr
UNION ALL
SELECT 'Contraction ARR', -contraction_arr
UNION ALL
SELECT 'Churned ARR', -churned_arr
UNION ALL
SELECT 'Reactivation ARR', reactivation_arr
UNION ALL
SELECT 'Ending ARR', ending_arr
FROM monthly_waterfall
WHERE month = '2024-12-01'
ORDER BY
  CASE metric
    WHEN 'Starting ARR' THEN 1
    WHEN 'New ARR' THEN 2
    WHEN 'Expansion ARR' THEN 3
    WHEN 'Contraction ARR' THEN 4
    WHEN 'Churned ARR' THEN 5
    WHEN 'Reactivation ARR' THEN 6
    WHEN 'Ending ARR' THEN 7
  END
```

---

## Common Pitfalls & Debugging

### 1. **Double-Counting Customers**
Problem: Customer appears in both "new" and "reactivation" bucket.

Solution:
```sql
-- Define clear precedence
CASE
  WHEN first_payment_date = month THEN 'new'
  WHEN previous_arr = 0 AND current_arr > 0 THEN 'reactivation'
  ...
END
```

### 2. **ARR Trending Down But Revenue Up**
Cause: Multi-year contracts recognized vs. booked.

Debug:
```sql
SELECT
  month,
  arr,
  bookings,
  revenue_recognized
FROM metrics
WHERE arr_delta < 0 AND revenue > 0
```

### 3. **Churn Doesn't Match Revenue Loss**
Cause: Contraction being counted as churn.

Fix: Separate logo churn from revenue churn.

### 4. **NRR > 120%**
Either:
- Massive expansion (good!)
- Bug in expansion vs. upsell logic (bad)

Debug:
```sql
SELECT
  customer_id,
  starting_arr,
  current_arr,
  current_arr / starting_arr AS retention_rate
FROM cohort_analysis
WHERE current_arr / starting_arr > 2.0
-- Inspect these outliers
```

---

## Best Practices

### 1. **Always Use Snapshots**
Don't rely on current state to calculate historical metrics.

```sql
-- Good: Point-in-time snapshot
SELECT arr FROM arr_snapshots WHERE snapshot_date = '2024-01-31'

-- Bad: Current state
SELECT SUM(mrr * 12) FROM subscriptions WHERE created_at <= '2024-01-31'
```

### 2. **Handle Edge Cases Explicitly**
- Paused subscriptions
- Partial month changes
- Currency conversions
- Refunds and credits

### 3. **Document Metric Definitions**
Every metric should have:
```yaml
metric_name: net_revenue_retention
definition: Revenue retained from a cohort including expansion
calculation: (Starting ARR + Expansion - Contraction - Churn) / Starting ARR
grain: Monthly cohorts
filters: Active paying customers only
exclusions: Free trials, paused accounts
owner: RevOps team
```

### 4. **Test Against Known Periods**
```sql
-- Validate totals
SELECT
  SUM(new_mrr + expansion_mrr - contraction_mrr - churned_mrr) AS net_change,
  ending_mrr - starting_mrr AS expected_change
FROM monthly_movements
-- These should match!
```

---

## When to Use This Skill

Claude should reference this skill when:
- Calculating any SaaS metric
- Debugging metric discrepancies
- Designing data models for RevOps
- Writing SQL for cohort analysis
- Explaining business logic to stakeholders
- Building dashboards or reports
- Reviewing metric definitions for accuracy

---

## References

For Snowflake-specific optimization, see: `dbt-snowflake-expert` skill
For data modeling patterns, see: `data-modeling-architect` skill
