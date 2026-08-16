# 🔄 Reverse ETL Demo — Step-by-Step Walkthrough

> **Goal:** Generate mock data → Seed live HubSpot CRM → Build Snowflake Data Warehouse →
> Push calculated product & revenue analytics back into HubSpot CRM (Reverse ETL Loop).

---

## 📦 Architecture

```
generate_mock_data.py
        │  JSON Files (data/raw/)
        ▼
seed_live_environments.py
        │  HubSpot API → 125 Companies, 438 Contacts, 184 Deals
        ▼
ingestion/stackflow_pipeline.py   (dlt)
        │  JSON → Snowflake RAW_DATA schema
        ▼
dbt build --target snowflake
        │  RAW_DATA → STAGING → INTERMEDIATE → MARTS
        │  dim_accounts, fct_pql_signals, int_users_joined
        ▼
scripts/reverse_etl_dlt.py
        │  Snowflake MARTS → HubSpot API (PATCH)
        │  ✅ Companies: mrr, arr, health_status, account_segment
        │  ✅ Contacts:  intent_tier, recommended_action (HOT PQLs)
        │  ✅ L2A:       Contact ↔ Company associations
        ▼
HubSpot CRM (Enriched) 🎯
```

---

## 🚀 Execution Guide — 5 Steps

> **Execute each step** sequentially in your terminal.
> Ensure you are in the project root directory: `cd ~/data_projects/b2b-saas-revops`

---

### STEP 1 — Generate Mock Data

```bash
uv venv .venv && source .venv/bin/activate
python scripts/generate_mock_data.py
```

**Expected Output:**
```
✓ hubspot_companies.json     125 records
✓ hubspot_deals.json         184 records
✓ hubspot_contacts.json      438 records
✓ internal_events.json     31050 records
✅ Done. Files written to data/raw/
```

---

### STEP 2 — Seed Live HubSpot Environment

```bash
python scripts/seed_live_environments.py
```

> ⏱️ Takes **~5-7 minutes** (enforces rate limit: 0.15s/request)

**Expected Output:**
```
🏢 Seeding 125 companies...
  ✅ Created Company: Acme Corp (ID: 44289xxxx)
  ✅ Created Company: Brightwave Labs (ID: 44287xxxx)
  ...
👤 Seeding 438 contacts...
💸 Seeding 184 deals...
🎉 HubSpot seeding and ID synchronization complete.
```

---

### STEP 2.5 — Patch Local Raw JSON Files with Real HubSpot IDs

```bash
python3 - <<'EOF'
import json

with open('data/raw/hubspot_companies.json') as f:
    companies = json.load(f)

mock_to_real = {str(100_000 + idx): co['hs_object_id'] for idx, co in enumerate(companies)}
print(f"Mapping: {len(mock_to_real)} companies")

with open('data/raw/internal_workspaces.json') as f:
    workspaces = json.load(f)
updated = 0
for ws in workspaces:
    old = ws.get('hubspot_company_id')
    if old in mock_to_real:
        ws['hubspot_company_id'] = mock_to_real[old]
        updated += 1
with open('data/raw/internal_workspaces.json', 'w') as f:
    json.dump(workspaces, f, indent=2)
print(f"✅ Workspaces patched: {updated}")

with open('data/raw/stripe_subscriptions.json') as f:
    subs = json.load(f)
updated_s = 0
for sub in subs:
    old = sub.get('metadata', {}).get('hubspot_company_id')
    if old in mock_to_real:
        sub['metadata']['hubspot_company_id'] = mock_to_real[old]
        updated_s += 1
with open('data/raw/stripe_subscriptions.json', 'w') as f:
    json.dump(subs, f, indent=2)
print(f"✅ Stripe subscriptions patched: {updated_s}")
EOF
```

---

### STEP 3 — Ingest Data into Snowflake (dlt Pipeline)

```bash
python ingestion/stackflow_pipeline.py
```

**Expected Output:**
```
HubSpot:  Pipeline LOADED into Snowflake — 1.8s
Stripe:   Pipeline LOADED into Snowflake — 2.4s
Internal: Pipeline LOADED into Snowflake — 11s
Zendesk:  Pipeline LOADED into Snowflake — 1.2s
```

---

### STEP 4 — Run dbt Build (Transform & Test Warehouse)

```bash
dbt build --target snowflake --store-failures
```

> ⏱️ ~25 seconds

**Expected Output:**
```
Done. PASS=200 WARN=0 ERROR=0 SKIP=0 TOTAL=200
```

**Core Built Models:**
| Model | Description |
|-------|-------------|
| `MARTS.DIM_ACCOUNTS` | Account health, MRR/ARR, customer segmentation |
| `MARTS.FCT_PQL_SIGNALS` | Product-Qualified Lead (HOT/WARM intent scores) |
| `INTERMEDIATE.INT_USERS_JOINED` | Cross-domain user & account stitching |

---

### STEP 5 — Reverse ETL (Snowflake → HubSpot CRM)

#### Run Dry-Run Mode First (Preview without making API calls):
```bash
python scripts/reverse_etl_dlt.py --dry-run
```

#### Run Live Sync:
```bash
python scripts/reverse_etl_dlt.py
```

**Expected Output:**
```
✅ Company KineticHR     | MRR=$288 | Health=At Risk
✅ Company IronMesh      | MRR=$240 | Health=Healthy
✅ Company Acme Corp     | MRR=$0   | Health=At Risk
...
🏁 Reverse ETL Complete — 125 companies, 4 HOT contacts tagged
```

---

## ✅ Enriched Results in HubSpot CRM

Each Company record in HubSpot will now display updated custom properties:

| Property | Example Value | Source Model |
|----------|---------------|--------------|
| `mrr` | `288.0` | Snowflake → `DIM_ACCOUNTS` |
| `arr` | `3456.0` | Snowflake → `DIM_ACCOUNTS` |
| `health_status` | `At Risk` | dbt health scoring |
| `health_reason` | `Payment Failing` | Stripe `past_due` |
| `account_segment` | `SMB` | Employee count / MRR tier |
| `subscription_status` | `past_due` | Stripe Billing |
| `is_ready_for_upsell` | `true` | dbt business logic |
| `is_churning_soon` | `1` | dbt churn risk signals |

On HubSpot Contact records:

| Property | Example Value |
|----------|---------------|
| `intent_tier` | `HOT` |
| `recommended_action` | `Sales Qualification Call` |
| `gtm_priority` | `NOTIFY` |

---

## 🔧 Troubleshooting

### Clear dlt Pending Packages
```bash
dlt pipeline revops_to_hubspot drop-pending-packages
```

### Reset Local dlt Pipeline State
```bash
rm -rf ~/.dlt/pipelines/revops_to_hubspot/
```

---

## 📁 Key File References

| File | Description |
|------|-------------|
| [`scripts/generate_mock_data.py`](file:///home/farrux/data_projects/b2b-saas-revops/scripts/generate_mock_data.py) | Generates 125 companies, 438 contacts, 31K+ events |
| [`scripts/seed_live_environments.py`](file:///home/farrux/data_projects/b2b-saas-revops/scripts/seed_live_environments.py) | Seeds HubSpot via POST & syncs live IDs |
| [`ingestion/stackflow_pipeline.py`](file:///home/farrux/data_projects/b2b-saas-revops/ingestion/stackflow_pipeline.py) | Ingests JSON into Snowflake `RAW_DATA` via `dlt` |
| [`scripts/reverse_etl_dlt.py`](file:///home/farrux/data_projects/b2b-saas-revops/scripts/reverse_etl_dlt.py) | Pushes Snowflake `MARTS` insights back into HubSpot API |
| [`models/marts/core/dim_accounts.sql`](file:///home/farrux/data_projects/b2b-saas-revops/models/marts/core/dim_accounts.sql) | Golden Record Account dimension model |
| [`models/marts/product/fct_pql_signals.sql`](file:///home/farrux/data_projects/b2b-saas-revops/models/marts/product/fct_pql_signals.sql) | Product-Qualified Lead scoring model |
