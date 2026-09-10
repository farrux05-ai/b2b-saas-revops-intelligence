# ============================================================
# environments/prod/variables.tf
# ============================================================

# ── Snowflake Connection ──────────────────────────────────────

variable "snowflake_organization_name" {
  description = "Snowflake organization name (e.g. 'myorg' from 'myorg-xy12345')"
  type        = string
}

variable "snowflake_account_name" {
  description = "Snowflake account name (e.g. 'xy12345' from 'myorg-xy12345')"
  type        = string
}

variable "snowflake_username" {
  description = "Admin username for Terraform provisioning (must have ACCOUNTADMIN)"
  type        = string
}

variable "snowflake_password" {
  description = "Admin password for Terraform provisioning"
  type        = string
  sensitive   = true
}

# ── Database ──────────────────────────────────────────────────

variable "database_name" {
  type    = string
  default = "REVOPS_INTELLIGENCE"
}

variable "database_data_retention_days" {
  type    = number
  default = 7
}

# ── Warehouses ────────────────────────────────────────────────

variable "compute_warehouse_size" {
  type    = string
  default = "SMALL"
}

variable "ci_warehouse_size" {
  type    = string
  default = "X-SMALL"
}

variable "loading_warehouse_size" {
  type    = string
  default = "X-SMALL"
}

# ── Service Account Passwords ─────────────────────────────────

variable "dbt_prod_password" {
  type      = string
  sensitive = true
}

variable "dbt_ci_password" {
  type      = string
  sensitive = true
}

variable "dlt_loader_password" {
  type      = string
  sensitive = true
}

variable "lightdash_password" {
  type      = string
  sensitive = true
}
