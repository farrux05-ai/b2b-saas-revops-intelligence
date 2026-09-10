# ============================================================
# modules/warehouse/outputs.tf
# ============================================================

output "compute_warehouse_name" {
  description = "Production warehouse name — set as SNOWFLAKE_WAREHOUSE in dbt profiles"
  value       = snowflake_warehouse.compute.name
}

output "ci_warehouse_name" {
  description = "CI warehouse name — set as CI warehouse in GitHub Actions secrets"
  value       = snowflake_warehouse.ci.name
}

output "loading_warehouse_name" {
  description = "Ingestion warehouse name — configure in dlt pipeline settings"
  value       = snowflake_warehouse.loading.name
}
