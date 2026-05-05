---
name: sentinelguard-revops-standard
description: The ultimate standard for B2B SaaS RevOps data architecture.
---

# RevOps Intelligence Engine RevOps Standard

## 1. Naming & Structure
- **Staging**: `stg_[source]__[entity].sql` (Double underscore). Clean raw sources only.
- **Intermediate**: `int_[entity]_[verb].sql`. End with action (e.g., `_joined`, `_aggregated`, `_scored`).
- **Marts**: `dim_` (One Big Table) and `fct_` (Historical Waterfall).
- **Utilities**: Non-business infrastructure (e.g., `dim_dates`) in `models/utilities/`.

## 2. Identity Resolution (Spine)
- **Rule**: Never use `LEFT JOIN` as the spine.
- **Method**: Use `UNION ALL` across all sources (Workspaces, HubSpot, Stripe).
- **Nega?**: PLG Leakage'ni oldini olish uchun. CRM dagi Leadlar mahsulotga kirmasidan oldin ham ko'rinishi shart.

## 3. Intermediate 3-Stage Hierarchy
1. **Identity**: `_joined` models to stitch global IDs.
2. **Domains**: `_aggregated` models for Sales, Finance, usage, etc.
3. **Integration**: `_integrated` and `_scored` models to add business intelligence (Health, Risk).

## 4. Finance & MRR Waterfall
- **Rule**: No `now()` or current state for movements.
- **Method**: Use a **Date Spine** for point-in-time MRR snapshots.
- **Nega?**: "Silent Churn" va tarixiy MRR o'zgarishlarini faqat oylik kesimda tahlil qilish mumkin.

## 5. Metadata & Seeds
- **Seeds**: All static data (Holidays, segments) in CSV seeds.
- **Exposures**: Document dashboard dependencies in `exposures.yml`.
- **Nega?**: Data Lineage va tizimning moslashuvchanligi uchun.

## 6. Testing Philosophy (Data Quality)
- **Staging Layer (Source Contracts)**: Only test the contract with the source. `unique` and `not_null` on the natural Primary Key. Test `accepted_values` ONLY on source-managed enums (e.g. ticket status). Do NOT test business metrics (amounts, probabilities) here.
- **Intermediate Layer (Integration)**: Test foreign keys and surrogate keys. Test the outputs of business logic (e.g. does the score match an accepted value?).
- **Marts Layer (Business Reliability)**: Test business requirements (e.g. `dbt_expectations` row counts). Test primary keys for the dimension/fact tables.
- **Rule**: Do not duplicate tests across layers. If `unique` and `not_null` are verified in `int_accounts_integrated`, there is no need to re-test the exact same spine key in `int_accounts_scored`.
