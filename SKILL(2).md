---
name: data-modeling-architect
description: Expert in data warehouse architecture and dimensional modeling using Kimball methodology. Use this skill whenever the user mentions dimensional modeling, star schema, snowflake schema, fact tables, dimension tables, data warehouse design, semantic layer, metrics layer, data mesh, SCD (slowly changing dimensions), surrogate keys, grain, or asks about how to structure data models, design analytics schemas, normalize vs denormalize, build a metrics layer, or organize data warehouse architecture. Also trigger when discussing data modeling patterns, table relationships, or designing for analytical queries. Even casual mentions like "should this be a fact or dimension" or "how to model this data" should trigger this skill.
---

# Data Modeling Architect

Expert guidance for designing production-grade data warehouses using dimensional modeling and Kimball methodology.

## Core Principles

### 1. **Business Process First**
Model around business processes (orders, subscriptions, payments), not source systems.

### 2. **Grain is Sacred**
Every fact table must have a clearly defined grain (one row = ?).

### 3. **Conformed Dimensions**
Reuse dimension tables across multiple fact tables.

### 4. **Denormalize for Query Performance**
Analytics is read-heavy; optimize for queries, not updates.

---

## Dimensional Modeling 101

### Star Schema Architecture

```
        dim_customers
              |
              |
        dim_products --- fct_orders --- dim_dates
              |
              |
        dim_locations
```

**Components**:
- **Fact table**: Numeric measurements (revenue, quantity)
- **Dimension tables**: Descriptive attributes (who, what, when, where)

---

## Fact Tables

### Definition
Stores **measurements** at a specific **grain**.

### Types of Facts

#### 1. **Transaction Facts**
One row per business event.

```sql
-- Grain: One row per order line item
CREATE TABLE fct_order_lines (
  order_line_id VARCHAR PRIMARY KEY,  -- Surrogate key
  order_id VARCHAR,
  customer_key VARCHAR,               -- FK to dim_customers
  product_key VARCHAR,                -- FK to dim_products
  order_date_key DATE,                -- FK to dim_dates
  quantity INT,                       -- Measure
  unit_price DECIMAL(10,2),           -- Measure
  line_total DECIMAL(10,2),           -- Measure
  discount_amount DECIMAL(10,2)       -- Measure
)
```

**Use for**: Orders, payments, events, clicks.

---

#### 2. **Periodic Snapshot Facts**
One row per time period.

```sql
-- Grain: One row per customer per day
CREATE TABLE fct_customer_daily (
  customer_key VARCHAR,
  date_key DATE,
  active_subscriptions INT,
  mrr DECIMAL(10,2),
  arr DECIMAL(10,2),
  total_users INT,
  PRIMARY KEY (customer_key, date_key)
)
```

**Use for**: Daily/monthly metrics, inventory levels, account balances.

---

#### 3. **Accumulating Snapshot Facts**
One row per lifecycle (updates over time).

```sql
-- Grain: One row per order (updated as it progresses)
CREATE TABLE fct_order_lifecycle (
  order_key VARCHAR PRIMARY KEY,
  customer_key VARCHAR,
  order_created_date_key DATE,
  order_shipped_date_key DATE,      -- Initially NULL
  order_delivered_date_key DATE,    -- Initially NULL
  days_to_ship INT,                 -- Calculated
  days_to_deliver INT,              -- Calculated
  order_amount DECIMAL(10,2)
)
```

**Use for**: Order fulfillment, support tickets, subscription lifecycle.

---

### Fact Table Design Rules

#### Rule 1: **All Foreign Keys Must Reference Dimensions**
```sql
-- Good
CREATE TABLE fct_revenue (
  customer_key VARCHAR,          -- FK to dim_customers
  product_key VARCHAR,           -- FK to dim_products
  date_key DATE,                 -- FK to dim_dates
  revenue DECIMAL(10,2)
)

-- Bad: Natural key instead of dimension FK
CREATE TABLE fct_revenue (
  customer_id VARCHAR,           -- Should be customer_key
  product_name VARCHAR,          -- Should be product_key
  ...
)
```

---

#### Rule 2: **Grain Must Be Explicit**
```sql
-- Bad: Unclear grain
CREATE TABLE fct_usage (
  user_id VARCHAR,
  product_id VARCHAR,
  usage_count INT
)
-- Question: Is this daily? Monthly? All-time?

-- Good: Clear grain
CREATE TABLE fct_usage_daily (
  user_key VARCHAR,
  product_key VARCHAR,
  date_key DATE,
  usage_count INT,
  PRIMARY KEY (user_key, product_key, date_key)
)
-- Answer: One row per user per product per day
```

---

#### Rule 3: **Additive > Semi-Additive > Non-Additive**

**Additive**: Can sum across all dimensions
```sql
revenue DECIMAL(10,2)          -- Sum by customer, product, date
quantity INT                   -- Sum across everything
```

**Semi-Additive**: Can sum across some dimensions
```sql
account_balance DECIMAL(10,2)  -- Sum by customer, NOT by date
inventory_level INT            -- Sum by product, NOT by date
```

**Non-Additive**: Cannot sum (use AVG, MIN, MAX)
```sql
unit_price DECIMAL(10,2)       -- Average, not sum
temperature DECIMAL(5,2)       -- Average, not sum
```

---

## Dimension Tables

### Definition
Stores **descriptive attributes** for filtering and grouping.

### Basic Structure

```sql
CREATE TABLE dim_customers (
  customer_key VARCHAR PRIMARY KEY,    -- Surrogate key
  customer_id VARCHAR,                 -- Natural key
  customer_name VARCHAR,
  email VARCHAR,
  segment VARCHAR,                     -- SMB, Mid-Market, Enterprise
  industry VARCHAR,
  country VARCHAR,
  state VARCHAR,
  city VARCHAR,
  account_manager VARCHAR,
  -- Metadata
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  is_current BOOLEAN,                  -- For Type 2 SCD
  effective_date DATE,                 -- For Type 2 SCD
  expiration_date DATE                 -- For Type 2 SCD
)
```

---

### Dimension Design Rules

#### Rule 1: **Surrogate Keys**
Use generated keys, not natural keys.

```sql
-- Good
customer_key VARCHAR PRIMARY KEY DEFAULT UUID()

-- Bad: Natural key as primary
customer_id VARCHAR PRIMARY KEY  -- What if it changes?
```

**Why?**
- Natural keys can change
- Easier to maintain Type 2 SCD
- Better join performance (smaller keys)

---

#### Rule 2: **Denormalize Hierarchies**
Flatten hierarchies in dimension tables.

```sql
-- Good: Denormalized
CREATE TABLE dim_products (
  product_key VARCHAR PRIMARY KEY,
  product_name VARCHAR,
  product_category VARCHAR,           -- Denormalized
  product_subcategory VARCHAR,        -- Denormalized
  category_manager VARCHAR            -- Denormalized
)

-- Bad: Normalized
CREATE TABLE dim_products (
  product_key VARCHAR PRIMARY KEY,
  product_name VARCHAR,
  category_id INT                     -- FK to dim_categories
)
CREATE TABLE dim_categories (
  category_id INT PRIMARY KEY,
  category_name VARCHAR,
  subcategory_id INT                  -- FK to dim_subcategories
)
-- Too many joins for analytics!
```

---

#### Rule 3: **Role-Playing Dimensions**
Reuse dimensions for multiple purposes.

```sql
-- One date dimension, multiple roles
CREATE TABLE fct_orders (
  order_key VARCHAR PRIMARY KEY,
  order_date_key DATE,           -- FK to dim_dates
  ship_date_key DATE,            -- FK to dim_dates (same table)
  delivery_date_key DATE,        -- FK to dim_dates (same table)
  amount DECIMAL(10,2)
)
```

---

### Slowly Changing Dimensions (SCD)

#### **Type 1: Overwrite**
No history, just update.

```sql
-- Customer changes email
UPDATE dim_customers
SET email = 'new@example.com'
WHERE customer_key = 'cust_123'
```

**Use when**: History doesn't matter (typos, phone numbers).

---

#### **Type 2: Add New Row**
Keep full history.

```sql
-- Customer upgrades from SMB to Enterprise
INSERT INTO dim_customers (
  customer_key,
  customer_id,
  customer_name,
  segment,
  is_current,
  effective_date,
  expiration_date
) VALUES (
  'cust_123_v2',
  'C123',
  'Acme Corp',
  'Enterprise',
  TRUE,
  '2024-06-01',
  '9999-12-31'
)

-- Expire old row
UPDATE dim_customers
SET is_current = FALSE,
    expiration_date = '2024-05-31'
WHERE customer_key = 'cust_123_v1'
```

**Use when**: Need to analyze historical states (segment changes, pricing tiers).

---

#### **Type 3: Add New Column**
Track limited history.

```sql
CREATE TABLE dim_customers (
  customer_key VARCHAR PRIMARY KEY,
  customer_name VARCHAR,
  current_segment VARCHAR,
  previous_segment VARCHAR,
  segment_change_date DATE
)
```

**Use when**: Only need one previous value.

---

### Junk Dimensions
Combine low-cardinality flags.

```sql
-- Instead of multiple boolean columns in fact table
CREATE TABLE dim_order_flags (
  order_flag_key VARCHAR PRIMARY KEY,
  is_rush_order BOOLEAN,
  is_gift BOOLEAN,
  is_discounted BOOLEAN,
  requires_signature BOOLEAN
)

-- Fact table references junk dimension
CREATE TABLE fct_orders (
  order_key VARCHAR PRIMARY KEY,
  customer_key VARCHAR,
  order_flag_key VARCHAR,  -- FK to dim_order_flags
  order_amount DECIMAL(10,2)
)
```

---

### Degenerate Dimensions
Dimension exists only in fact table (no separate dimension table).

```sql
CREATE TABLE fct_orders (
  order_key VARCHAR PRIMARY KEY,
  customer_key VARCHAR,
  order_number VARCHAR,         -- Degenerate dimension
  invoice_number VARCHAR,       -- Degenerate dimension
  order_amount DECIMAL(10,2)
)
```

**Use for**: Order numbers, invoice IDs, transaction IDs.

---

## Date Dimension

**Critical**: Always use a date dimension.

```sql
CREATE TABLE dim_dates (
  date_key DATE PRIMARY KEY,
  full_date DATE,
  day_of_week INT,
  day_name VARCHAR,
  day_of_month INT,
  day_of_year INT,
  week_of_year INT,
  month INT,
  month_name VARCHAR,
  quarter INT,
  year INT,
  is_weekend BOOLEAN,
  is_holiday BOOLEAN,
  fiscal_year INT,
  fiscal_quarter INT,
  fiscal_month INT
)
```

**Generate dates**:
```sql
INSERT INTO dim_dates
SELECT
  date AS date_key,
  date AS full_date,
  DAYOFWEEK(date) AS day_of_week,
  DAYNAME(date) AS day_name,
  DAY(date) AS day_of_month,
  DAYOFYEAR(date) AS day_of_year,
  WEEKOFYEAR(date) AS week_of_year,
  MONTH(date) AS month,
  MONTHNAME(date) AS month_name,
  QUARTER(date) AS quarter,
  YEAR(date) AS year,
  DAYOFWEEK(date) IN (0, 6) AS is_weekend,
  NULL AS is_holiday,  -- Populate separately
  -- Fiscal calculations
  CASE
    WHEN MONTH(date) >= 7 THEN YEAR(date) + 1
    ELSE YEAR(date)
  END AS fiscal_year,
  CASE
    WHEN MONTH(date) IN (7, 8, 9) THEN 1
    WHEN MONTH(date) IN (10, 11, 12) THEN 2
    WHEN MONTH(date) IN (1, 2, 3) THEN 3
    WHEN MONTH(date) IN (4, 5, 6) THEN 4
  END AS fiscal_quarter,
  CASE
    WHEN MONTH(date) >= 7 THEN MONTH(date) - 6
    ELSE MONTH(date) + 6
  END AS fiscal_month
FROM TABLE(GENERATOR(ROWCOUNT => 3650))  -- 10 years
```

---

## Kimball Design Process

### Step 1: **Select Business Process**
E.g., "Order Fulfillment", "Subscription Billing", "Customer Support".

### Step 2: **Declare Grain**
E.g., "One row per order line item", "One row per customer per day".

### Step 3: **Identify Dimensions**
Who, what, when, where, why, how.

E.g., Customer, Product, Date, Location.

### Step 4: **Identify Facts**
Numeric measurements.

E.g., Quantity, Revenue, Discount.

### Example: Order Fulfillment

```
Business Process: Order Fulfillment
Grain: One row per order line item

Dimensions:
- dim_customers (who)
- dim_products (what)
- dim_dates (when)
- dim_locations (where)

Facts:
- quantity
- unit_price
- line_total
- discount_amount
```

**Result**:
```sql
CREATE TABLE fct_order_lines (
  order_line_key VARCHAR PRIMARY KEY,
  customer_key VARCHAR,        -- FK to dim_customers
  product_key VARCHAR,         -- FK to dim_products
  order_date_key DATE,         -- FK to dim_dates
  ship_date_key DATE,          -- FK to dim_dates
  location_key VARCHAR,        -- FK to dim_locations
  quantity INT,
  unit_price DECIMAL(10,2),
  line_total DECIMAL(10,2),
  discount_amount DECIMAL(10,2)
)
```

---

## Semantic Layer / Metrics Layer

### What Is It?
A layer that defines business metrics once, consistently.

### Components

#### 1. **Entities**
Business objects (customers, orders, products).

#### 2. **Measures**
Numeric values (revenue, count, average).

#### 3. **Dimensions**
Attributes for slicing (date, segment, region).

#### 4. **Metrics**
Calculated business KPIs.

---

### Example: dbt Metrics Layer

```yaml
# models/metrics.yml
version: 2

metrics:
  - name: total_revenue
    label: Total Revenue
    model: ref('fct_orders')
    description: Sum of all order revenue
    calculation_method: sum
    expression: order_amount
    timestamp: order_date
    time_grains: [day, week, month, quarter, year]
    dimensions:
      - customer_segment
      - product_category
      - region

  - name: average_order_value
    label: Average Order Value
    model: ref('fct_orders')
    description: Average revenue per order
    calculation_method: average
    expression: order_amount
    timestamp: order_date
    time_grains: [day, week, month, quarter, year]

  - name: monthly_active_customers
    label: Monthly Active Customers
    model: ref('fct_orders')
    description: Count of distinct customers per month
    calculation_method: count_distinct
    expression: customer_key
    timestamp: order_date
    time_grains: [month, quarter, year]
```

**Query**:
```sql
-- dbt automatically generates
SELECT
  DATE_TRUNC('month', order_date) AS month,
  customer_segment,
  SUM(order_amount) AS total_revenue,
  AVG(order_amount) AS average_order_value,
  COUNT(DISTINCT customer_key) AS monthly_active_customers
FROM {{ ref('fct_orders') }}
GROUP BY 1, 2
```

---

## Common Patterns

### 1. **Conformed Dimensions**
Share dimensions across fact tables.

```
fct_orders -----> dim_customers <----- fct_subscriptions
fct_support -----> dim_customers <----- fct_payments
```

### 2. **Bridge Tables**
Handle many-to-many relationships.

```sql
-- Products can have multiple categories
CREATE TABLE bridge_product_categories (
  product_key VARCHAR,
  category_key VARCHAR,
  PRIMARY KEY (product_key, category_key)
)
```

### 3. **Aggregate Fact Tables**
Pre-aggregate for performance.

```sql
-- Daily aggregation
CREATE TABLE fct_revenue_daily AS
SELECT
  customer_key,
  date_key,
  SUM(revenue) AS total_revenue,
  COUNT(DISTINCT order_key) AS order_count
FROM fct_order_lines
GROUP BY 1, 2
```

---

## Anti-Patterns (Don't Do This)

### 1. **Entity Tables Instead of Star Schema**
```sql
-- Bad: 3NF in a data warehouse
CREATE TABLE orders (
  order_id INT,
  customer_id INT,  -- FK to customers table
  product_id INT    -- FK to products table
)
-- Too many joins!
```

### 2. **Facts in Dimensions**
```sql
-- Bad: Revenue in customer dimension
CREATE TABLE dim_customers (
  customer_key VARCHAR,
  customer_name VARCHAR,
  total_lifetime_revenue DECIMAL(10,2)  -- This is a fact!
)
-- Facts belong in fact tables!
```

### 3. **No Grain Definition**
```sql
-- Bad: What does one row represent?
CREATE TABLE revenue_table (
  revenue DECIMAL(10,2)
)
```

---

## Best Practices Summary

1. **Star schema** over normalized schemas
2. **Surrogate keys** in dimensions
3. **Type 2 SCD** for important historical changes
4. **Conformed dimensions** across fact tables
5. **Clear grain** in every fact table
6. **Date dimension** always
7. **Denormalize** dimension hierarchies
8. **Semantic layer** for metric consistency
9. **Document** grain and business rules
10. **Test** referential integrity

---

## When to Use This Skill

Claude should reference this skill when:
- Designing fact or dimension tables
- Choosing between star vs snowflake schema
- Implementing slowly changing dimensions
- Building a semantic or metrics layer
- Deciding table grain
- Creating conformed dimensions
- Modeling complex relationships
- Reviewing data warehouse architecture

---

## References

For business metrics definitions, see: `revops-metrics-expert` skill
For dbt implementation, see: `dbt-snowflake-expert` skill
