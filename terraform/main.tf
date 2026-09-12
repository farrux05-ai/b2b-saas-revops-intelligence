
# ============================================================
# Terraform — RevOps Intelligence Engine
# Snowflake Infrastructure as Code
#
# Provider:  Snowflake-Labs/snowflake ~> 0.98
# Backend:   Local (terraform.tfstate)
#            → For team use, switch to Terraform Cloud or S3
#
# Auth:      Username + Password (from TF_VAR_* env vars)
#            → For production, migrate to key-pair authentication
#
# Usage:
#   cd terraform/environments/prod
#   terraform init
#   terraform plan
#   terraform apply
# ============================================================

terraform {
  required_version = ">= 1.9.0"

  required_providers {
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "~> 1.0"
    }
  }

  # ── Local Backend ────────────────────────────────────────────
  # State is stored in terraform.tfstate (gitignored).
  # For team environments, replace with:
  #
  # backend "remote" {
  #   organization = "your-org"
  #   workspaces { name = "revops-prod" }
  # }
  backend "local" {}
}

# ── Snowflake Provider — ACCOUNTADMIN ────────────────────────
# ACCOUNTADMIN is used for initial setup only.
# For day-to-day operations, each service account uses its
# assigned least-privilege role (TRANSFORMER, LOADER, REPORTER).
#
# NOTE: In a hardened production setup, split into 3 providers:
#   - SYSADMIN    → databases, warehouses
#   - SECURITYADMIN → roles, users, privilege grants
#   - ACCOUNTADMIN  → account-level grants only
provider "snowflake" {
  organization_name = var.snowflake_organization_name
  account_name      = var.snowflake_account_name
  user              = var.snowflake_username
  password          = var.snowflake_password
  role              = "ACCOUNTADMIN"
}
