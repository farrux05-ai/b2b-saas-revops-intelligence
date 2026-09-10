# ============================================================
# modules/rbac/outputs.tf
# ============================================================

output "transformer_role_name" {
  description = "TRANSFORMER role name — use as SNOWFLAKE_ROLE in dbt profiles"
  value       = snowflake_account_role.transformer.name
}

output "loader_role_name" {
  description = "LOADER role name — use in dlt pipeline configuration"
  value       = snowflake_account_role.loader.name
}

output "reporter_role_name" {
  description = "REPORTER role name — use in Lightdash connection settings"
  value       = snowflake_account_role.reporter.name
}

output "service_account_names" {
  description = "All provisioned service account usernames"
  value = {
    dbt_prod  = snowflake_user.dbt_prod.name
    dbt_ci    = snowflake_user.dbt_ci.name
    dlt       = snowflake_user.dlt_loader.name
    lightdash = snowflake_user.lightdash.name
  }
}
