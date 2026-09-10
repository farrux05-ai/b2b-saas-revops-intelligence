# ============================================================
# modules/rbac/variables.tf
# ============================================================

# ── Identity ──────────────────────────────────────────────────

variable "database_name" {
  description = "Snowflake database name — used for constructing fully-qualified schema paths"
  type        = string
}

# ── Warehouses (passed from warehouse module outputs) ─────────

variable "compute_warehouse_name" {
  description = "Production warehouse name — set as default for dbt service accounts"
  type        = string
}

variable "ci_warehouse_name" {
  description = "CI warehouse name — set as default for DBT_CI_USER"
  type        = string
}

variable "loading_warehouse_name" {
  description = "Loading warehouse name — set as default for DLT_LOADER_USER"
  type        = string
}

# ── Schema Names (passed from database module outputs) ────────

variable "raw_data_schema" { type = string }
variable "staging_schema" { type = string }
variable "identity_schema" { type = string }
variable "domains_schema" { type = string }
variable "integration_schema" { type = string }
variable "marts_schema" { type = string }
variable "semantic_layer_schema" { type = string }
variable "marts_ci_schema" { type = string }
variable "elementary_schema" { type = string }
variable "marts_elementary_schema" { type = string }
variable "marts_elementary_ci_schema" { type = string }

# ── Service Account Passwords ─────────────────────────────────

variable "dbt_prod_password" {
  description = "Password for DBT_PROD_USER"
  type        = string
  sensitive   = true
}

variable "dbt_ci_password" {
  description = "Password for DBT_CI_USER"
  type        = string
  sensitive   = true
}

variable "dlt_loader_password" {
  description = "Password for DLT_LOADER_USER"
  type        = string
  sensitive   = true
}

variable "lightdash_password" {
  description = "Password for LIGHTDASH_USER"
  type        = string
  sensitive   = true
}
