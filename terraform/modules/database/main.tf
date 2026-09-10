# ============================================================
# modules/database/main.tf
#
# Provisions the main Snowflake database and all schemas
# required by the RevOps Intelligence dbt project.
#
# Schema → dbt layer mapping:
#   RAW_DATA         ← dlt ingestion landing zone  (source())
#   STAGING          ← stg_* models                (staging layer)
#   IDENTITY         ← int_*_joined models          (intermediate 1)
#   DOMAINS          ← int_*_aggregated models      (intermediate 2)
#   INTEGRATION      ← int_*_integrated/scored      (intermediate 3)
#   MARTS            ← dim_* / fct_* production     (marts layer)
#   SEMANTIC_LAYER   ← MetricFlow semantic models
#   MARTS_CI         ← Isolated CI test schema
#   ELEMENTARY       ← Elementary observability reports
#   MARTS_ELEMENTARY ← Elementary production schema
#   MARTS_ELEMENTARY_CI ← Elementary CI schema
# ============================================================

# Declare the provider source so Terraform resolves it correctly.
# Without this, Terraform defaults to hashicorp/snowflake (wrong namespace).
terraform {
  required_providers {
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "~> 1.0"
    }
  }
}


resource "snowflake_database" "revops" {
  name    = var.database_name
  comment = "RevOps Intelligence Engine — primary analytics database managed by Terraform"

  data_retention_time_in_days = var.data_retention_days

  # Transient databases skip Fail-safe storage to reduce cost.
  # Set to false to enable 7-day Fail-safe (recommended for production).
  is_transient = false
}

# ── Schemas ──────────────────────────────────────────────────

# Raw data landing zone — written by dlt ingestion pipeline
resource "snowflake_schema" "raw_data" {
  database = snowflake_database.revops.name
  name     = "RAW_DATA"
  comment  = "dlt ingestion landing zone — raw data from HubSpot, Stripe, PostHog, Zendesk, Internal DB"

  data_retention_time_in_days = var.data_retention_days
  is_transient                = false
}

# dbt staging layer
resource "snowflake_schema" "staging" {
  database = snowflake_database.revops.name
  name     = "STAGING"
  comment  = "dbt staging layer — stg_* models. Pure extraction, renaming, casting. No business logic."

  data_retention_time_in_days = 1
  is_transient                = false
}

# dbt intermediate layer 1 — identity resolution
resource "snowflake_schema" "identity" {
  database = snowflake_database.revops.name
  name     = "IDENTITY"
  comment  = "dbt intermediate layer 1 — int_*_joined models. Global surrogate key stitching across sources."

  data_retention_time_in_days = 1
  is_transient                = false
}

# dbt intermediate layer 2 — domain aggregations
resource "snowflake_schema" "domains" {
  database = snowflake_database.revops.name
  name     = "DOMAINS"
  comment  = "dbt intermediate layer 2 — int_*_aggregated models. Domain-specific metrics (Sales, Billing, Usage, Engagement)."

  data_retention_time_in_days = 1
  is_transient                = false
}

# dbt intermediate layer 3 — integration & scoring
resource "snowflake_schema" "integration" {
  database = snowflake_database.revops.name
  name     = "INTEGRATION"
  comment  = "dbt intermediate layer 3 — int_*_integrated / int_*_scored models. Account health, risk scoring."

  data_retention_time_in_days = 1
  is_transient                = false
}

# dbt marts layer — production output
resource "snowflake_schema" "marts" {
  database = snowflake_database.revops.name
  name     = "MARTS"
  comment  = "dbt marts layer — dim_* and fct_* production models. Primary BI consumption layer."

  data_retention_time_in_days = var.data_retention_days
  is_transient                = false
}

# MetricFlow semantic models
resource "snowflake_schema" "semantic_layer" {
  database = snowflake_database.revops.name
  name     = "SEMANTIC_LAYER"
  comment  = "MetricFlow semantic models for dbt Semantic Layer / dbt Cloud Explorer"

  data_retention_time_in_days = var.data_retention_days
  is_transient                = false
}

# CI isolated schema — transient, no Time Travel needed
resource "snowflake_schema" "marts_ci" {
  database = snowflake_database.revops.name
  name     = "MARTS_CI"
  comment  = "Isolated CI schema for GitHub Actions dbt Slim CI runs. Transient — no Time Travel."

  data_retention_time_in_days = 0
  is_transient                = true
}

# Elementary observability schemas
resource "snowflake_schema" "elementary" {
  database = snowflake_database.revops.name
  name     = "ELEMENTARY"
  comment  = "Elementary data observability — edr reports and anomaly detection results"

  data_retention_time_in_days = var.data_retention_days
  is_transient                = false
}

resource "snowflake_schema" "marts_elementary" {
  database = snowflake_database.revops.name
  name     = "MARTS_ELEMENTARY"
  comment  = "Elementary production observability schema (mirrors profiles.yml: schema: MARTS_elementary)"

  data_retention_time_in_days = var.data_retention_days
  is_transient                = false
}

resource "snowflake_schema" "marts_elementary_ci" {
  database = snowflake_database.revops.name
  name     = "MARTS_ELEMENTARY_CI"
  comment  = "Elementary CI observability schema. Transient."

  data_retention_time_in_days = 0
  is_transient                = true
}
