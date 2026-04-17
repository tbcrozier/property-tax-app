variable "project_id" {
  description = "GCP Project ID"
  type        = string
  default     = "public-data-dev"
}

variable "region" {
  description = "GCP region for BigQuery dataset"
  type        = string
  default     = "US"
}

variable "dataset_id" {
  description = "BigQuery dataset ID"
  type        = string
  default     = "dallas"
}
