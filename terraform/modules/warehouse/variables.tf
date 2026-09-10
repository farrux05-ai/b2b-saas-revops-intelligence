# ============================================================
# modules/warehouse/variables.tf
# ============================================================

variable "compute_warehouse_size" {
  description = "Size of the production dbt warehouse (COMPUTE_WH)"
  type        = string
  default     = "SMALL"

  validation {
    condition = contains([
      "X-SMALL", "SMALL", "MEDIUM", "LARGE",
      "X-LARGE", "2X-LARGE", "3X-LARGE", "4X-LARGE"
    ], var.compute_warehouse_size)
    error_message = "Invalid warehouse size. Choose from: X-SMALL, SMALL, MEDIUM, LARGE, X-LARGE, etc."
  }
}

variable "ci_warehouse_size" {
  description = "Size of the GitHub Actions CI warehouse (CI_WH)"
  type        = string
  default     = "X-SMALL"

  validation {
    condition = contains([
      "X-SMALL", "SMALL", "MEDIUM", "LARGE",
      "X-LARGE", "2X-LARGE", "3X-LARGE", "4X-LARGE"
    ], var.ci_warehouse_size)
    error_message = "Invalid warehouse size."
  }
}

variable "loading_warehouse_size" {
  description = "Size of the dlt ingestion warehouse (LOADING_WH)"
  type        = string
  default     = "X-SMALL"

  validation {
    condition = contains([
      "X-SMALL", "SMALL", "MEDIUM", "LARGE",
      "X-LARGE", "2X-LARGE", "3X-LARGE", "4X-LARGE"
    ], var.loading_warehouse_size)
    error_message = "Invalid warehouse size."
  }
}
