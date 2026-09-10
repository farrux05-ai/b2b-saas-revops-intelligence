# ============================================================
# modules/warehouse/main.tf
#
# Provisions 3 virtual warehouses following the principle of
# workload isolation — each pipeline stage gets its own WH.
#
#   COMPUTE_WH   → Production dbt runs (SMALL, auto-suspend 60s)
#   CI_WH        → GitHub Actions CI (X-SMALL, auto-suspend 30s)
#   LOADING_WH   → dlt ingestion (X-SMALL, auto-suspend 60s)
#
# Auto-suspend prevents credit waste during idle periods.
# Auto-resume ensures warehouses start on first query.
# ============================================================

terraform {
  required_providers {
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "~> 1.0"
    }
  }
}


# ── Production Warehouse ──────────────────────────────────────
# Used by dbt production runs and Lightdash BI queries.
resource "snowflake_warehouse" "compute" {
  name    = "COMPUTE_WH"
  comment = "Production warehouse for dbt runs and Lightdash BI queries. Managed by Terraform."

  warehouse_size = var.compute_warehouse_size
  warehouse_type = "STANDARD"

  # Auto-suspend after 60 seconds of inactivity — prevents idle credit burn
  auto_suspend = 60
  # Auto-resume on first query — zero friction for users
  auto_resume = true

  # Initially suspended — starts only on demand
  initially_suspended = true

  # Maximum concurrent clusters (Snowflake Standard: always 1)
  max_cluster_count = 1
  min_cluster_count = 1

  # Statement timeout: 30 minutes max per query
  statement_timeout_in_seconds = 1800

  # Tag for cost allocation in Snowflake cost management
  query_acceleration_max_scale_factor = 0
}

# ── CI Warehouse ──────────────────────────────────────────────
# Used exclusively by GitHub Actions dbt Slim CI jobs.
# X-SMALL size to minimize CI cost — CI runs fewer models (state:modified+).
resource "snowflake_warehouse" "ci" {
  name    = "CI_WH"
  comment = "CI warehouse for GitHub Actions dbt Slim CI. X-SMALL to minimize cost. Managed by Terraform."

  warehouse_size = var.ci_warehouse_size
  warehouse_type = "STANDARD"

  # Aggressive auto-suspend — CI jobs are bursty, not sustained
  auto_suspend = 30
  auto_resume  = true

  initially_suspended = true

  max_cluster_count = 1
  min_cluster_count = 1

  # Shorter timeout for CI — fail fast
  statement_timeout_in_seconds = 900
}

# ── Loading Warehouse ─────────────────────────────────────────
# Used by dlt ingestion pipeline to write to RAW_DATA schema.
# Kept separate to isolate ingestion load from dbt transforms.
resource "snowflake_warehouse" "loading" {
  name    = "LOADING_WH"
  comment = "Ingestion warehouse for dlt pipeline writes to RAW_DATA. Managed by Terraform."

  warehouse_size = var.loading_warehouse_size
  warehouse_type = "STANDARD"

  auto_suspend = 60
  auto_resume  = true

  initially_suspended = true

  max_cluster_count = 1
  min_cluster_count = 1

  statement_timeout_in_seconds = 3600
}
