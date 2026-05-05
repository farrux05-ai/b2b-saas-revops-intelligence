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
