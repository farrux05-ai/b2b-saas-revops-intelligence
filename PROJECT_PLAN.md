# StackFlow RevOps — Project Plan

## Maqsad
Mavjud `farrux05-ai-b2b-saas-revops` loyihasini to'liq ishlaydigan,
recruiter va senior engineer ko'rsa "bu haqiqiy narsa" deydigan
portfolio ga aylantirish.

## Texnologiyalar
- **Ingestion:** dlt (Data Load Tool)
- **Warehouse:** BigQuery (yoki DuckDB local testing uchun)
- **Transformation:** dbt
- **Orchestration:** Dagster
- **BI / Semantic Layer:** Lightdash
- **CRM:** HubSpot (Reverse ETL target)

---

## Bosqichlar

---

### PHASE 1 — Foundation (hozir shu yerda turibmiz)
**Status: ✅ Done** (Refactored to Senior Standard)

- [x] Biznes story (StackFlow) — inglizcha, real pain points bilan
- [x] Source schema dizayn — HubSpot, Stripe, Internal DB, Zendesk
- [x] Identity resolution logikasi — workspaces bridge table konsepti

**Output:** `BUSINESS_CONTEXT.md`

---

### PHASE 2 — Mock Data (dlt + seeds)
**Maqsad:** Loyihani clone qilgan har kim `dbt run` qila olsin.

#### 2.1 — Mock data generatsiya skriptlari
Fayl: `scripts/generate_mock_data.py`

Har bir source uchun realistic fake data:
- `hubspot_companies` — 50 company, real industry/domain bilan
- `hubspot_deals` — har company uchun 1-3 deal, stage distribution realistic
- `hubspot_contacts` — har company uchun 2-5 contact
- `stripe_subscriptions` — har workspace uchun 1 sub, plan mix: 60% starter, 30% growth, 10% enterprise
- `stripe_invoices` — 12 oylik history, ba'zilarida `past_due`
- `stripe_payments` — invoicelar ga mos, 5% failure rate
- `internal_workspaces` — 50 workspace, bridge IDlar bilan
- `internal_users` — har workspace uchun 3-15 user
- `internal_events` — 6 oylik event log, realistic distribution
- `zendesk_tickets` — har workspace uchun 0-10 ticket

**Muhim:** Mock data real biznes pattern ini aks ettirsin:
- 8 ta "at risk" account (past_due + kam activity)
- 5 ta "expansion ready" account (seat limit ga yaqin)
- 3 ta "PQL" account (trial, activated, Sales ga topshirilmagan)

#### 2.2 — dlt pipeline
Fayl: `ingestion/stackflow_pipeline.py`

```
dlt.source → BigQuery (yoki DuckDB)
  ├── hubspot_source()
  ├── stripe_source()
  ├── internal_db_source()
  └── zendesk_source()
```

Mock data ni JSON/CSV da `data/raw/` ga yozib, dlt orqali warehouse ga load qilamiz.

**Output:** `data/raw/*.json`, `ingestion/stackflow_pipeline.py`

---

### PHASE 3 — Staging Layer (dbt)
**Maqsad:** Raw data ni clean, typed, deduplicated holga keltirish.

Har bir staging model:
- Type casting (string → timestamp, cents → dollars)
- Column rename (HubSpot camelCase → snake_case)
- Deduplication (`row_number()` over partition by id, order by updated_at desc)
- Surrogate key (`dbt_utils.generate_surrogate_key`)

#### Modellar (qayta yoziladi, yangi schemaga mos):

```
staging/
  stg_hubspot/
    stg_hubspot__companies.sql
    stg_hubspot__deals.sql
    stg_hubspot__contacts.sql
  stg_stripe/
    stg_stripe__subscriptions.sql
    stg_stripe__invoices.sql
    stg_stripe__payments.sql
  stg_internal/
    stg_internal__workspaces.sql
    stg_internal__users.sql
    stg_internal__events.sql
  stg_zendesk/
    stg_zendesk__tickets.sql
```

**Output:** 10 ta staging model + `.yml` documentation

---

### PHASE 4 — Intermediate Layer (dbt)
**Maqsad:** Biznes logika. Bu loyihaning "miyasi."

#### 4.1 — Identity Resolution
```
int_accounts_spine.sql
```
- `workspaces` ni anchor qilib oladi
- HubSpot, Stripe, Zendesk ni birlashtiradi
- Fallback logic: direct ID → domain match
- Output: har bir account uchun bitta qator, barcha tizim IDlari bilan

#### 4.2 — MRR Waterfall
```
int_mrr_movements.sql
```
- Har oy har account uchun MRR o'zgarishi
- Movement types: `new` | `expansion` | `contraction` | `churn` | `reactivation`
- Stripe `subscription_update` events dan hisoblash
- Prorated charges ni to'g'ri handle qilish

#### 4.3 — Product Activation
```
int_product_activation.sql
```
- PLG activation definition: workspace converted bo'lish uchun nima kerak?
  - `git_integration_connected` event ✓
  - `project_created` event ✓
  - minimum 3 user `last_seen_at` within 7 days ✓
- Har workspace uchun: `is_activated` boolean + `activated_at` timestamp

#### 4.4 — Customer Health Score
```
int_customer_health_score.sql
```

| Dimension | Weight | Signal |
|---|---|---|
| Financial | 30% | subscription status, overdue invoices |
| Product | 40% | DAU/MAU ratio, feature breadth, activation |
| Support | 30% | ticket volume, priority, satisfaction |

Score: 0–100 → `healthy` / `at_risk` / `inactive` / `churned`

#### 4.5 — PQL Signal
```
int_pql_signal.sql
```
- Trial workspaces + `is_activated = true` + seat usage > 60% of limit
- Bu Reverse ETL uchun trigger

**Output:** 5 ta intermediate model

---

### PHASE 5 — Marts Layer (dbt)
**Status: ✅ Done** (BI Ready & Semantic Layer defined)

```
marts/
  core/
    dim_accounts.sql       -- Golden record: har bir company uchun bitta qator (OBT)
    models/utilities/dim_dates.sql  -- Standard date spine (Moved to Utilities)
    dim_users.sql          -- Active users summary
  finance/
    fct_mrr.sql            -- MRR waterfall, oylik
    fct_arr_movements.sql  -- ARR level aggregation
  sales/
    fct_pipeline.sql       -- Deal funnel, stage conversion rates
    fct_activities.sql     -- Sales rep activity tracking
  product/
    fct_activation.sql     -- PLG funnel: signup → activate → convert
    fct_feature_usage.sql  -- Feature adoption heatmap
  customer_success/
    fct_health.sql         -- Health score history, trend
  marketing/
    fct_attribution.sql    -- Campaign → Deal → Revenue attribution
```

**Output:** 10 ta mart model + full `.yml` documentation

---

### PHASE 6 — Reverse ETL
**Status: ✅ Done** (Syncing Health & PQL to HubSpot)

#### Nima push qilamiz HubSpot ga:
| Field | Source | HubSpot target |
|---|---|---|
| `health_score` | `fct_health` | Custom property: `stackflow_health_score` |
| `health_status` | `fct_health` | Custom property: `stackflow_health_status` |
| `mrr` | `dim_accounts` | Custom property: `current_mrr` |
| `is_pql` | `int_pql_signal` | Custom property: `is_product_qualified` |
| `seat_utilization` | `dim_accounts` | Custom property: `seat_utilization_pct` |
| `last_active_at` | `dim_accounts` | Custom property: `last_product_activity` |

Fayl: `scripts/reverse_etl_to_hubspot.py`
- HubSpot API v3 (PATCH `/crm/v3/objects/companies/{id}`)
- Faqat o'zgargan recordlarni push qiladi (incremental)
- Run: har kuni Dagster orqali

**Output:** `scripts/reverse_etl_to_hubspot.py`

---

### PHASE 7 — Semantic Layer (Lightdash)
**Status: ✅ Done** (Metrics defined in .yml)

#### Key metrics define qilamiz:
- `mrr` — sum of current MRR across active accounts
- `arr` — mrr × 12
- `net_revenue_retention` — (beg MRR + expansion - contraction - churn) / beg MRR
- `logo_churn_rate` — churned accounts / total accounts (oylik)
- `activation_rate` — activated workspaces / total trial workspaces
- `avg_health_score` — weighted average
- `pql_count` — count of accounts where `is_pql = true`
- `seat_utilization` — avg seats used / seat limit

Har bir metric: `label`, `description`, `format`, `filters` bilan.

**Output:** Updated `.yml` files with Lightdash metric definitions

---

### PHASE 8 — Orchestration (Dagster)
**Status: ✅ Done** (dagster_pipeline.py implemented)

```
Daily pipeline:
  07:00 UTC  →  dlt ingestion (all sources)
  08:00 UTC  →  dbt run (staging → intermediate → marts)
  09:00 UTC  →  dbt test
  09:30 UTC  →  Reverse ETL → HubSpot
```

Assets:
- Source freshness alerts
- Test failure notifications
- MRR anomaly detection (>10% swing triggers alert)

**Output:** `dagster_pipeline.py`

---

## Fayl Strukturasi (final)

```
stackflow-revops/
  README.md                        -- Project overview + architecture diagram
  BUSINESS_CONTEXT.md              -- Bu fayl (story + schema)
  PROJECT_PLAN.md                  -- Bu fayl
  dbt_project.yml
  profiles.yml
  requirements.txt
  
  data/
    raw/                           -- Mock JSON files (dlt source)
      hubspot_companies.json
      hubspot_deals.json
      ...
  
  ingestion/
    stackflow_pipeline.py          -- dlt pipeline
  
  scripts/
    generate_mock_data.py          -- Mock data generator
    reverse_etl_to_hubspot.py      -- Reverse ETL
  
  models/
    staging/                       -- Phase 3
    intermediate/                  -- Phase 4
    marts/                         -- Phase 5
  
  tests/                           -- Existing + new custom tests
  snapshots/                       -- SCD Type 2 for deals + subscriptions
  
  dagster_pipeline.py              -- Phase 8
```

---

## Har bir session uchun context

Agar conversation yangilansa, shu plan faylni paste qil va qaysi phase da ekanligingni ayt. Har bir phase independent — oldingi bitmasa ham keyingisiga o'tsa bo'ladi, faqat staging tugaguncha intermediate boshlanmasin.

**Hozirgi holat:** Phase 1 tugadi. Keyingi: Phase 2 (mock data generator skripti).