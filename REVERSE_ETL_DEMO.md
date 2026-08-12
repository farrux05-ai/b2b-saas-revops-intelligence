# 🔄 Reverse ETL Demo — Qadam-baqadam

> **Maqsad:** Mock data generatsiya qilish → HubSpot'ga seed → DuckDB warehouse build →
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
        │  JSON → DuckDB raw_data schema
        ▼
dbt run
        │  raw → staging → intermediate → marts
        │  dim_accounts, fct_pql_signals, int_users_joined
        ▼
scripts/reverse_etl_dlt.py
        │  DuckDB marts → HubSpot API (PATCH)
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
source .venv/bin/activate
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

> **Muhim:** Script JSON fayllaridagi eski mock ID'larni (`100000`, `100001`...)
> real HubSpot ID'lari bilan avtomatik yangilaydi.

---

### QADAM 2.5 — JSON fayllarni real ID'lar bilan patch qilish

> Bu qadam `seed_live_environments.py` faqat `hubspot_companies.json`ni yangilaydi,
> lekin `internal_workspaces.json` va `stripe_subscriptions.json` ham kerak.

```bash
python3 - <<'EOF'
import json

with open('data/raw/hubspot_companies.json') as f:
    companies = json.load(f)

# mock_id -> real_id mapping
mock_to_real = {str(100_000 + idx): co['hs_object_id'] for idx, co in enumerate(companies)}
print(f"Mapping: {len(mock_to_real)} companies")

# Patch internal_workspaces.json
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

# Patch stripe_subscriptions.json
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

### QADAM 3 — DuckDB'ga ingest (dlt pipeline)

```bash
python ingestion/stackflow_pipeline.py
```

**Natija:**
```
HubSpot:  Pipeline LOADED — 1.8s
Stripe:   Pipeline LOADED — 2.4s
Internal: Pipeline LOADED — 11s
Zendesk:  Pipeline LOADED — 1.2s
```

---

### QADAM 4 — dbt run (warehouse build)

```bash
dbt run --no-version-check
```

> ⏱️ ~35 sekund

**Natija:**
```
Done. PASS=70 WARN=0 ERROR=0 SKIP=0 TOTAL=70
```

**Qurilgan modellar:**
| Model | Maqsad |
|-------|--------|
| `main_marts.dim_accounts` | Account health, MRR/ARR, segment |
| `main_marts.fct_pql_signals` | HOT/WARM PQL intent scores |
| `main_identity.int_users_joined` | Email/domain stitching |

---

### QADAM 5 — Reverse ETL (DuckDB → HubSpot)

#### Avval dry-run (preview, API call yo'q):
```bash
python scripts/reverse_etl_dlt.py --dry-run
```

#### So'ng live run:
```bash
python scripts/reverse_etl_dlt.py
```

**Yoki alohida resource:**
```bash
python scripts/reverse_etl_dlt.py --resource companies   # faqat enrichment
python scripts/reverse_etl_dlt.py --resource pql         # faqat PQL tagging
python scripts/reverse_etl_dlt.py --resource l2a         # faqat associations
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
| `mrr` | `288.0` | DuckDB → dim_accounts |
| `arr` | `3456.0` | DuckDB → dim_accounts |
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
# > y (tasdiqlash)
```

### dlt state'ni to'liq reset qilish
```bash
rm -rf ~/.dlt/pipelines/revops_to_hubspot/
```

### HubSpot'dagi barcha datani tozalash
```bash
python3 - <<'EOF'
import os, requests, time
from dotenv import load_dotenv
load_dotenv()
token = os.getenv('HUBSPOT_ACCESS_TOKEN')
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

def batch_delete(obj_type):
    deleted, after = 0, None
    while True:
        params = {'limit': 100}
        if after: params['after'] = after
        data = requests.get(f'https://api.hubapi.com/crm/v3/objects/{obj_type}', headers=headers, params=params).json()
        results = data.get('results', [])
        if not results: break
        requests.post(f'https://api.hubapi.com/crm/v3/objects/{obj_type}/batch/archive',
                      headers=headers, json={'inputs': [{'id': r['id']} for r in results]})
        deleted += len(results)
        after = data.get('paging', {}).get('next', {}).get('after')
        if not after: break
        time.sleep(0.2)
    print(f'✅ {obj_type}: {deleted} deleted')

for obj in ['deals', 'contacts', 'companies']:
    batch_delete(obj)
EOF
```

---

## 📁 Asosiy fayllar

| Fayl | Maqsad |
|------|--------|
| [`scripts/generate_mock_data.py`](scripts/generate_mock_data.py) | 125 company, 438 contact, 10K+ event |
| [`scripts/seed_live_environments.py`](scripts/seed_live_environments.py) | HubSpot'ga POST + real ID sync |
| [`ingestion/stackflow_pipeline.py`](ingestion/stackflow_pipeline.py) | JSON → DuckDB (dlt) |
| [`scripts/reverse_etl_dlt.py`](scripts/reverse_etl_dlt.py) | DuckDB → HubSpot (dlt custom destination) |
| [`models/marts/dim_accounts.sql`](models/marts/dim_accounts.sql) | Account health & revenue model |
| [`models/marts/fct_pql_signals.sql`](models/marts/fct_pql_signals.sql) | PQL scoring model |
