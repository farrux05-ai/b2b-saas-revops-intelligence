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
    "RAW_DATA",
    "STAGING",
    "IDENTITY",
    "DOMAINS",
    "INTEGRATION",
    "MARTS",
    "SEMANTIC_LAYER",
    "MARTS_CI",
    "ELEMENTARY",
    "MARTS_ELEMENTARY",
    "MARTS_ELEMENTARY_CI",
  ]
}

# Individual schema outputs — used by rbac module for precise grants
output "raw_data_schema" { value = "RAW_DATA" }
output "staging_schema" { value = "STAGING" }
output "identity_schema" { value = "IDENTITY" }
output "domains_schema" { value = "DOMAINS" }
output "integration_schema" { value = "INTEGRATION" }
output "marts_schema" { value = "MARTS" }
output "semantic_layer_schema" { value = "SEMANTIC_LAYER" }
output "marts_ci_schema" { value = "MARTS_CI" }
output "elementary_schema" { value = "ELEMENTARY" }
output "marts_elementary_schema" { value = "MARTS_ELEMENTARY" }
output "marts_elementary_ci_schema" { value = "MARTS_ELEMENTARY_CI" }
