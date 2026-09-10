# ============================================================
# modules/rbac/main.tf
#
# RBAC — Roles, Users, and Privilege Grants
#
# Role Hierarchy (Least Privilege):
#
#   ACCOUNTADMIN
#   └── SYSADMIN
#       ├── TRANSFORMER          ← dbt service accounts
#       │   └── LOADER           ← dlt ingestion (inherits nothing sensitive)
#       └── REPORTER             ← Lightdash / BI read-only
#
# Service Accounts:
#   DBT_PROD_USER    → TRANSFORMER  (production dbt runs)
#   DBT_CI_USER      → TRANSFORMER  (GitHub Actions CI)
#   DLT_LOADER_USER  → LOADER       (dlt ingestion pipeline)
#   LIGHTDASH_USER   → REPORTER     (Lightdash BI read-only)
# ============================================================

terraform {
  required_providers {
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "~> 1.0"
    }
  }
}


# ── Roles ────────────────────────────────────────────────────

resource "snowflake_account_role" "loader" {
  name    = "LOADER"
  comment = "dlt ingestion service role — WRITE access to RAW_DATA schema only. No read access to transformed layers."
}

resource "snowflake_account_role" "transformer" {
  name    = "TRANSFORMER"
  comment = "dbt transformation role — READ access to RAW_DATA, WRITE access to STAGING through MARTS. Inherits LOADER."
}

resource "snowflake_account_role" "reporter" {
  name    = "REPORTER"
  comment = "BI read-only role — SELECT on MARTS and SEMANTIC_LAYER only. Used by Lightdash."
}

# ── Role Hierarchy ────────────────────────────────────────────

# LOADER inherits into TRANSFORMER (dbt can read raw data)
resource "snowflake_grant_account_role" "loader_to_transformer" {
  role_name        = snowflake_account_role.loader.name
  parent_role_name = snowflake_account_role.transformer.name
}

# TRANSFORMER reports up to SYSADMIN
resource "snowflake_grant_account_role" "transformer_to_sysadmin" {
  role_name        = snowflake_account_role.transformer.name
  parent_role_name = "SYSADMIN"
}

# REPORTER reports up to SYSADMIN
resource "snowflake_grant_account_role" "reporter_to_sysadmin" {
  role_name        = snowflake_account_role.reporter.name
  parent_role_name = "SYSADMIN"
}

# ── Service Account Users ─────────────────────────────────────

resource "snowflake_user" "dbt_prod" {
  name         = "DBT_PROD_USER"
  login_name   = "DBT_PROD_USER"
  display_name = "dbt Production Service Account"
  comment      = "Service account for production dbt runs (dagster_pipeline.py). Managed by Terraform."
  password     = var.dbt_prod_password

  default_role      = snowflake_account_role.transformer.name
  default_warehouse = var.compute_warehouse_name

  # Force password change on first login — remove for service accounts
  must_change_password = false

  lifecycle {
    # Prevent Terraform from rotating passwords on every apply
    ignore_changes = [password]
  }
}

resource "snowflake_user" "dbt_ci" {
  name         = "DBT_CI_USER"
  login_name   = "DBT_CI_USER"
  display_name = "dbt CI Service Account"
  comment      = "Service account for GitHub Actions dbt Slim CI runs. Managed by Terraform."
  password     = var.dbt_ci_password

  default_role      = snowflake_account_role.transformer.name
  default_warehouse = var.ci_warehouse_name

  must_change_password = false

  lifecycle {
    ignore_changes = [password]
  }
}

resource "snowflake_user" "dlt_loader" {
  name         = "DLT_LOADER_USER"
  login_name   = "DLT_LOADER_USER"
  display_name = "dlt Ingestion Service Account"
  comment      = "Service account for dlt ingestion pipeline. Writes to RAW_DATA only. Managed by Terraform."
  password     = var.dlt_loader_password

  default_role      = snowflake_account_role.loader.name
  default_warehouse = var.loading_warehouse_name

  must_change_password = false

  lifecycle {
    ignore_changes = [password]
  }
}

resource "snowflake_user" "lightdash" {
  name         = "LIGHTDASH_USER"
  login_name   = "LIGHTDASH_USER"
  display_name = "Lightdash BI Service Account"
  comment      = "Read-only service account for Lightdash BI tool. SELECT on MARTS only. Managed by Terraform."
  password     = var.lightdash_password

  default_role      = snowflake_account_role.reporter.name
  default_warehouse = var.compute_warehouse_name

  must_change_password = false

  lifecycle {
    ignore_changes = [password]
  }
}

# ── Assign Roles to Users ─────────────────────────────────────

resource "snowflake_grant_account_role" "transformer_to_dbt_prod" {
  role_name = snowflake_account_role.transformer.name
  user_name = snowflake_user.dbt_prod.name
}

resource "snowflake_grant_account_role" "transformer_to_dbt_ci" {
  role_name = snowflake_account_role.transformer.name
  user_name = snowflake_user.dbt_ci.name
}

resource "snowflake_grant_account_role" "loader_to_dlt" {
  role_name = snowflake_account_role.loader.name
  user_name = snowflake_user.dlt_loader.name
}

resource "snowflake_grant_account_role" "reporter_to_lightdash" {
  role_name = snowflake_account_role.reporter.name
  user_name = snowflake_user.lightdash.name
}

# ── Database-Level Grants ─────────────────────────────────────

# LOADER: USAGE on database (to see it exists)
resource "snowflake_grant_privileges_to_account_role" "loader_database_usage" {
  account_role_name = snowflake_account_role.loader.name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "DATABASE"
    object_name = var.database_name
  }
}

# TRANSFORMER: USAGE on database
resource "snowflake_grant_privileges_to_account_role" "transformer_database_usage" {
  account_role_name = snowflake_account_role.transformer.name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "DATABASE"
    object_name = var.database_name
  }
}

# REPORTER: USAGE on database
resource "snowflake_grant_privileges_to_account_role" "reporter_database_usage" {
  account_role_name = snowflake_account_role.reporter.name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "DATABASE"
    object_name = var.database_name
  }
}

# ── Warehouse Grants ──────────────────────────────────────────

# TRANSFORMER: USAGE + OPERATE on production warehouse
resource "snowflake_grant_privileges_to_account_role" "transformer_compute_wh" {
  account_role_name = snowflake_account_role.transformer.name
  privileges        = ["USAGE", "OPERATE"]
  on_account_object {
    object_type = "WAREHOUSE"
    object_name = var.compute_warehouse_name
  }
}

# TRANSFORMER: USAGE + OPERATE on CI warehouse
resource "snowflake_grant_privileges_to_account_role" "transformer_ci_wh" {
  account_role_name = snowflake_account_role.transformer.name
  privileges        = ["USAGE", "OPERATE"]
  on_account_object {
    object_type = "WAREHOUSE"
    object_name = var.ci_warehouse_name
  }
}

# LOADER: USAGE + OPERATE on loading warehouse
resource "snowflake_grant_privileges_to_account_role" "loader_loading_wh" {
  account_role_name = snowflake_account_role.loader.name
  privileges        = ["USAGE", "OPERATE"]
  on_account_object {
    object_type = "WAREHOUSE"
    object_name = var.loading_warehouse_name
  }
}

# REPORTER: USAGE on production warehouse (for Lightdash queries)
resource "snowflake_grant_privileges_to_account_role" "reporter_compute_wh" {
  account_role_name = snowflake_account_role.reporter.name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "WAREHOUSE"
    object_name = var.compute_warehouse_name
  }
}

# ── Schema-Level Grants — LOADER ──────────────────────────────
# LOADER: Full write access to RAW_DATA only

resource "snowflake_grant_privileges_to_account_role" "loader_raw_data_schema" {
  account_role_name = snowflake_account_role.loader.name
  privileges        = ["USAGE", "CREATE TABLE", "CREATE STAGE", "CREATE FILE FORMAT"]
  on_schema {
    schema_name = "${var.database_name}.${var.raw_data_schema}"
  }
}

resource "snowflake_grant_privileges_to_account_role" "loader_raw_data_tables" {
  account_role_name = snowflake_account_role.loader.name
  privileges        = ["SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"]
  on_schema_object {
    all {
      object_type_plural = "TABLES"
      in_schema          = "${var.database_name}.${var.raw_data_schema}"
    }
  }
}

# Future tables in RAW_DATA — ensures new dlt tables are auto-granted
resource "snowflake_grant_privileges_to_account_role" "loader_raw_data_future_tables" {
  account_role_name = snowflake_account_role.loader.name
  privileges        = ["SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"]
  on_schema_object {
    future {
      object_type_plural = "TABLES"
      in_schema          = "${var.database_name}.${var.raw_data_schema}"
    }
  }
}

# ── Schema-Level Grants — TRANSFORMER ────────────────────────
# TRANSFORMER: READ on RAW_DATA, FULL WRITE on all dbt output schemas

locals {
  # Schemas where dbt creates and manages objects
  transformer_write_schemas = [
    var.staging_schema,
    var.identity_schema,
    var.domains_schema,
    var.integration_schema,
    var.marts_schema,
    var.semantic_layer_schema,
    var.marts_ci_schema,
    var.elementary_schema,
    var.marts_elementary_schema,
    var.marts_elementary_ci_schema,
  ]
}

# READ access to raw data (via inherited LOADER role)
resource "snowflake_grant_privileges_to_account_role" "transformer_raw_data_read" {
  account_role_name = snowflake_account_role.transformer.name
  privileges        = ["USAGE"]
  on_schema {
    schema_name = "${var.database_name}.${var.raw_data_schema}"
  }
}

resource "snowflake_grant_privileges_to_account_role" "transformer_raw_data_select" {
  account_role_name = snowflake_account_role.transformer.name
  privileges        = ["SELECT"]
  on_schema_object {
    all {
      object_type_plural = "TABLES"
      in_schema          = "${var.database_name}.${var.raw_data_schema}"
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "transformer_raw_data_future_select" {
  account_role_name = snowflake_account_role.transformer.name
  privileges        = ["SELECT"]
  on_schema_object {
    future {
      object_type_plural = "TABLES"
      in_schema          = "${var.database_name}.${var.raw_data_schema}"
    }
  }
}

# WRITE access to all dbt output schemas
resource "snowflake_grant_privileges_to_account_role" "transformer_schema_usage" {
  for_each = toset(local.transformer_write_schemas)

  account_role_name = snowflake_account_role.transformer.name
  privileges        = ["USAGE", "CREATE TABLE", "CREATE VIEW", "CREATE SCHEMA", "MODIFY"]
  on_schema {
    schema_name = "${var.database_name}.${each.value}"
  }
}

resource "snowflake_grant_privileges_to_account_role" "transformer_future_tables" {
  for_each = toset(local.transformer_write_schemas)

  account_role_name = snowflake_account_role.transformer.name
  privileges        = ["SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES"]
  on_schema_object {
    future {
      object_type_plural = "TABLES"
      in_schema          = "${var.database_name}.${each.value}"
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "transformer_future_views" {
  for_each = toset(local.transformer_write_schemas)

  account_role_name = snowflake_account_role.transformer.name
  privileges        = ["SELECT", "REFERENCES"]
  on_schema_object {
    future {
      object_type_plural = "VIEWS"
      in_schema          = "${var.database_name}.${each.value}"
    }
  }
}

# ── Schema-Level Grants — REPORTER ───────────────────────────
# REPORTER: SELECT-only on MARTS and SEMANTIC_LAYER

resource "snowflake_grant_privileges_to_account_role" "reporter_marts_schema" {
  account_role_name = snowflake_account_role.reporter.name
  privileges        = ["USAGE"]
  on_schema {
    schema_name = "${var.database_name}.${var.marts_schema}"
  }
}

resource "snowflake_grant_privileges_to_account_role" "reporter_semantic_schema" {
  account_role_name = snowflake_account_role.reporter.name
  privileges        = ["USAGE"]
  on_schema {
    schema_name = "${var.database_name}.${var.semantic_layer_schema}"
  }
}

resource "snowflake_grant_privileges_to_account_role" "reporter_marts_select" {
  account_role_name = snowflake_account_role.reporter.name
  privileges        = ["SELECT"]
  on_schema_object {
    future {
      object_type_plural = "TABLES"
      in_schema          = "${var.database_name}.${var.marts_schema}"
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "reporter_semantic_select" {
  account_role_name = snowflake_account_role.reporter.name
  privileges        = ["SELECT"]
  on_schema_object {
    future {
      object_type_plural = "TABLES"
      in_schema          = "${var.database_name}.${var.semantic_layer_schema}"
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "reporter_marts_views" {
  account_role_name = snowflake_account_role.reporter.name
  privileges        = ["SELECT"]
  on_schema_object {
    future {
      object_type_plural = "VIEWS"
      in_schema          = "${var.database_name}.${var.marts_schema}"
    }
  }
}
