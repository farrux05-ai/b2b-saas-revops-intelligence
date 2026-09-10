# ============================================================
# outputs.tf — Root-level Outputs
#
# These values are printed after `terraform apply` and can be
# used by CI/CD pipelines and team members to verify the setup.
# ============================================================

# ── Database ─────────────────────────────────────────────────

output "database_name" {
  description = "Name of the provisioned Snowflake database"
  value       = module.database.database_name
}

output "schemas" {
  description = "List of all provisioned schemas"
  value       = module.database.schema_names
}

# ── Warehouses ───────────────────────────────────────────────

output "compute_warehouse_name" {
  description = "Production dbt warehouse name — use in profiles.yml"
  value       = module.warehouse.compute_warehouse_name
}

output "ci_warehouse_name" {
  description = "CI warehouse name — use in GitHub Actions secrets"
  value       = module.warehouse.ci_warehouse_name
}

output "loading_warehouse_name" {
  description = "dlt ingestion warehouse name"
  value       = module.warehouse.loading_warehouse_name
}

# ── RBAC ─────────────────────────────────────────────────────

output "transformer_role" {
  description = "Role name for dbt service accounts"
  value       = module.rbac.transformer_role_name
}

output "loader_role" {
  description = "Role name for dlt ingestion service account"
  value       = module.rbac.loader_role_name
}

output "reporter_role" {
  description = "Role name for BI tool (Lightdash) read-only access"
  value       = module.rbac.reporter_role_name
}

output "service_accounts" {
  description = "All provisioned service account usernames"
  value       = module.rbac.service_account_names
}

# ── Connection String Template ───────────────────────────────

output "dbt_profiles_snippet" {
  description = "Ready-to-use snippet for profiles.yml — copy these values into your .env"
  value       = <<-EOT
    # ── Snowflake (provisioned by Terraform) ─────────────────
    SNOWFLAKE_ACCOUNT=${var.snowflake_organization_name}-${var.snowflake_account_name}
    SNOWFLAKE_USER=DBT_PROD_USER
    SNOWFLAKE_PASSWORD=<dbt_prod_password from tfvars>
    SNOWFLAKE_ROLE=${module.rbac.transformer_role_name}
    SNOWFLAKE_WAREHOUSE=${module.warehouse.compute_warehouse_name}
    SNOWFLAKE_DATABASE=${module.database.database_name}
  EOT
}
