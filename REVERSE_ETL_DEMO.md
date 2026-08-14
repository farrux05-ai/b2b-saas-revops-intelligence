# 🔄 Reverse ETL Demo — Step-by-Step Walkthrough

> **Maqsad:** Mock data generatsiya qilish → HubSpot'ga seed → Snowflake warehouse build →
> Analytics natijalarini HubSpot CRM'ga qaytarish (Reverse ETL)

---

## 📦 Arxitektura

```
generate_mock_data.py
        │  JSON fayllar (data/raw/)
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
HubSpot CRM (enriched) 🎯
```

---

## 🚀 Ishga tushirish — 5 qadam

> **Har bir qadam** terminalda ketma-ket ishlating.
> Loyiha papkasida ekanligingizni tekshiring: `cd ~/data_projects/b2b-saas-revops`

---

### QADAM 1 — Mock data generatsiya

```bash
uv venv .venv && source .venv/bin/activate
python scripts/generate_mock_data.py
```

**Natija:**
```
✓ hubspot_companies.json     125 records
✓ hubspot_deals.json         184 records
✓ hubspot_contacts.json      438 records
✓ internal_events.json     31050 records
✅ Done. Files written to data/raw/
```

---

### QADAM 2 — HubSpot'ga seed (real data kiritish)

```bash
python scripts/seed_live_environments.py
```

> ⏱️ Bu **~5-7 daqiqa** davom etadi (rate limit: 0.15s/request)

**Natija:**
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

### QADAM 2.5 — JSON fayllarni real ID'lar bilan patch qilish

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

### QADAM 3 — Snowflake'ga ingest (dlt pipeline)

```bash
python ingestion/stackflow_pipeline.py
```

**Natija:**
```
HubSpot:  Pipeline LOADED into Snowflake — 1.8s
Stripe:   Pipeline LOADED into Snowflake — 2.4s
Internal: Pipeline LOADED into Snowflake — 11s
Zendesk:  Pipeline LOADED into Snowflake — 1.2s
```

---

### QADAM 4 — dbt build (Warehouse Build & Test)

```bash
dbt build --target snowflake --store-failures
```

> ⏱️ ~25 sekund

**Natija:**
```
Done. PASS=160 WARN=0 ERROR=0 SKIP=0 TOTAL=160
```

**Qurilgan modellar:**
| Model | Maqsad |
|-------|--------|
| `MARTS.DIM_ACCOUNTS` | Account health, MRR/ARR, segment |
| `MARTS.FCT_PQL_SIGNALS` | HOT/WARM PQL intent scores |
| `INTERMEDIATE.INT_USERS_JOINED` | Email/domain stitching |

---

### QADAM 5 — Reverse ETL (Snowflake → HubSpot)

#### Avval dry-run (preview, API call yo'q):
```bash
python scripts/reverse_etl_dlt.py --dry-run
```

#### So'ng live run:
```bash
python scripts/reverse_etl_dlt.py
```

**Natija:**
```
✅ Company KineticHR     | MRR=$288 | Health=At Risk
✅ Company IronMesh      | MRR=$240 | Health=Healthy
✅ Company Acme Corp     | MRR=$0   | Health=At Risk
...
🏁 Reverse ETL Complete — 125 companies, 4 HOT contacts tagged
```

---

## ✅ HubSpot'da ko'rinadigan natija

HubSpot'dagi har bir Company recordida endi yangi custom properties:

| Property | Misol qiymati | Manba |
|----------|--------------|-------|
| `mrr` | `288.0` | Snowflake → DIM_ACCOUNTS |
| `arr` | `3456.0` | Snowflake → DIM_ACCOUNTS |
| `health_status` | `At Risk` | dbt health scoring |
| `health_reason` | `Payment Failing` | Stripe past_due |
| `account_segment` | `SMB` | Employee count |
| `subscription_status` | `past_due` | Stripe |
| `is_ready_for_upsell` | `true` | dbt logic |
| `is_churning_soon` | `1` | dbt churn signals |

HubSpot'dagi Contact'larda:

| Property | Misol qiymati |
|----------|--------------|
| `intent_tier` | `HOT` |
| `recommended_action` | `Sales Qualification Call` |
| `gtm_priority` | `NOTIFY` |

---

## 🔧 Troubleshooting

### dlt pending packages xatosi
```bash
dlt pipeline revops_to_hubspot drop-pending-packages
```

### dlt state'ni to'liq reset qilish
```bash
rm -rf ~/.dlt/pipelines/revops_to_hubspot/
```

---

## 📁 Asosiy fayllar

| Fayl | Maqsad |
|------|--------|
| [`scripts/generate_mock_data.py`](scripts/generate_mock_data.py) | 125 company, 438 contact, 10K+ event |
| [`scripts/seed_live_environments.py`](scripts/seed_live_environments.py) | HubSpot'ga POST + real ID sync |
| [`ingestion/stackflow_pipeline.py`](ingestion/stackflow_pipeline.py) | JSON → Snowflake RAW_DATA (dlt) |
| [`scripts/reverse_etl_dlt.py`](scripts/reverse_etl_dlt.py) | Snowflake MARTS → HubSpot API |
| [`models/marts/core/dim_accounts.sql`](models/marts/core/dim_accounts.sql) | Account health & revenue model |
| [`models/marts/product/fct_pql_signals.sql`](models/marts/product/fct_pql_signals.sql) | PQL scoring model |
