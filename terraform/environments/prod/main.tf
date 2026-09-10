# ============================================================
# environments/prod/main.tf
#
# Production environment — wires all modules together.
#
# This is the entry point for terraform apply:
#   cd terraform/environments/prod
#   terraform init
#   terraform plan -out=plan.out
#   terraform apply plan.out
# ============================================================

terraform {
  required_version = ">= 1.9.0"

  required_providers {
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "~> 1.0"
    }
  }

  # Local backend — state stored in environments/prod/terraform.tfstate
  # To migrate to Terraform Cloud, run: terraform init -migrate-state
  backend "local" {
    path = "terraform.tfstate"
  }
}

provider "snowflake" {
  organization_name = var.snowflake_organization_name
  account_name      = var.snowflake_account_name
  user              = var.snowflake_username
  password          = var.snowflake_password
  role              = "ACCOUNTADMIN"
}

# ── Module: Database ──────────────────────────────────────────
module "database" {
  source = "../../modules/database"

  database_name       = var.database_name
  data_retention_days = var.database_data_retention_days
}

# ── Module: Warehouses ────────────────────────────────────────
module "warehouse" {
  source = "../../modules/warehouse"

  compute_warehouse_size = var.compute_warehouse_size
  ci_warehouse_size      = var.ci_warehouse_size
  loading_warehouse_size = var.loading_warehouse_size
}

# ── Module: RBAC ──────────────────────────────────────────────
# Depends on both database and warehouse modules to wire
# schema names and warehouse names into grants.
module "rbac" {
  source = "../../modules/rbac"

  # Identity
  database_name = module.database.database_name

  # Warehouses (from warehouse module outputs)
  compute_warehouse_name = module.warehouse.compute_warehouse_name
  ci_warehouse_name      = module.warehouse.ci_warehouse_name
  loading_warehouse_name = module.warehouse.loading_warehouse_name

  # Schema names (from database module outputs)
  raw_data_schema            = module.database.raw_data_schema
  staging_schema             = module.database.staging_schema
  identity_schema            = module.database.identity_schema
  domains_schema             = module.database.domains_schema
  integration_schema         = module.database.integration_schema
  marts_schema               = module.database.marts_schema
  semantic_layer_schema      = module.database.semantic_layer_schema
  marts_ci_schema            = module.database.marts_ci_schema
  elementary_schema          = module.database.elementary_schema
  marts_elementary_schema    = module.database.marts_elementary_schema
  marts_elementary_ci_schema = module.database.marts_elementary_ci_schema

  # Service account passwords (from tfvars / TF_VAR_* env vars)
  dbt_prod_password   = var.dbt_prod_password
  dbt_ci_password     = var.dbt_ci_password
  dlt_loader_password = var.dlt_loader_password
  lightdash_password  = var.lightdash_password

  depends_on = [module.database, module.warehouse]
}
