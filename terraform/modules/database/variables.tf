# ============================================================
# modules/database/variables.tf
# ============================================================

variable "database_name" {
  description = "Name of the Snowflake database to create"
  type        = string
  default     = "REVOPS_INTELLIGENCE"
}

variable "data_retention_days" {
  description = "Time Travel data retention period in days (0–90 for Standard edition)"
  type        = number
  default     = 7

  validation {
    condition     = var.data_retention_days >= 0 && var.data_retention_days <= 90
    error_message = "data_retention_days must be between 0 and 90."
  }
}
