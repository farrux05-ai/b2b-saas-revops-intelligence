# ============================================================
# modules/database/outputs.tf
# ============================================================

output "database_name" {
  description = "The name of the provisioned database"
  value       = snowflake_database.revops.name
}

output "schema_names" {
  description = "All provisioned schema names"
  value = [
    snowflake_schema.raw_data.name,
    snowflake_schema.staging.name,
    snowflake_schema.identity.name,
    snowflake_schema.domains.name,
    snowflake_schema.integration.name,
    snowflake_schema.marts.name,
    snowflake_schema.semantic_layer.name,
    snowflake_schema.marts_ci.name,
    snowflake_schema.elementary.name,
    snowflake_schema.marts_elementary.name,
    snowflake_schema.marts_elementary_ci.name,
  ]
}

# Individual schema outputs — used by rbac module for precise grants
output "raw_data_schema" { value = snowflake_schema.raw_data.name }
output "staging_schema" { value = snowflake_schema.staging.name }
output "identity_schema" { value = snowflake_schema.identity.name }
output "domains_schema" { value = snowflake_schema.domains.name }
output "integration_schema" { value = snowflake_schema.integration.name }
output "marts_schema" { value = snowflake_schema.marts.name }
output "semantic_layer_schema" { value = snowflake_schema.semantic_layer.name }
output "marts_ci_schema" { value = snowflake_schema.marts_ci.name }
output "elementary_schema" { value = snowflake_schema.elementary.name }
output "marts_elementary_schema" { value = snowflake_schema.marts_elementary.name }
output "marts_elementary_ci_schema" { value = snowflake_schema.marts_elementary_ci.name }
