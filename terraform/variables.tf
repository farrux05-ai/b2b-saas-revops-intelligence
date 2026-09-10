# ============================================================
# variables.tf — Root-level Input Variables
#
# Set via environment variables (recommended):
#   export TF_VAR_snowflake_organization_name="myorg"
#   export TF_VAR_snowflake_account_name="xy12345"
#   export TF_VAR_snowflake_username="TERRAFORM_USER"
#   export TF_VAR_snowflake_password="..."
#
# Or via terraform.tfvars (gitignored):
#   snowflake_organization_name = "myorg"
#   snowflake_account_name      = "xy12345"
# ============================================================

# ── Snowflake Connection ─────────────────────────────────────

variable "snowflake_organization_name" {
  description = "Snowflake organization name (the part before the dash in your account identifier, e.g. 'myorg' from 'myorg-xy12345')"
  type        = string
}

variable "snowflake_account_name" {
  description = "Snowflake account name (the part after the dash in your account identifier, e.g. 'xy12345' from 'myorg-xy12345')"
  type        = string
}

variable "snowflake_username" {
  description = "Snowflake username with ACCOUNTADMIN role — used for Terraform provisioning only"
  type        = string
}

variable "snowflake_password" {
  description = "Snowflake password for the provisioning user"
  type        = string
  sensitive   = true
}

# ── Database ─────────────────────────────────────────────────

variable "database_name" {
  description = "Name of the main Snowflake database"
  type        = string
  default     = "REVOPS_INTELLIGENCE"
}

variable "database_data_retention_days" {
  description = "Number of days to retain Time Travel data for the database"
  type        = number
  default     = 7
}

# ── Warehouses ───────────────────────────────────────────────

variable "compute_warehouse_size" {
  description = "Size of the production dbt warehouse"
  type        = string
  default     = "SMALL"
}

variable "ci_warehouse_size" {
  description = "Size of the CI warehouse (kept small to control costs)"
  type        = string
  default     = "X-SMALL"
}

variable "loading_warehouse_size" {
  description = "Size of the dlt ingestion warehouse"
  type        = string
  default     = "X-SMALL"
}

# ── Service Account Passwords ────────────────────────────────
# NOTE: For production, migrate to key-pair authentication.
# These passwords are for service accounts created by Terraform.
# Mark as sensitive — they will NOT appear in plan output.

variable "dbt_prod_password" {
  description = "Password for DBT_PROD_USER service account"
  type        = string
  sensitive   = true
}

variable "dbt_ci_password" {
  description = "Password for DBT_CI_USER service account"
  type        = string
  sensitive   = true
}

variable "dlt_loader_password" {
  description = "Password for DLT_LOADER_USER service account"
  type        = string
  sensitive   = true
}

variable "lightdash_password" {
  description = "Password for LIGHTDASH_USER service account"
  type        = string
  sensitive   = true
}
