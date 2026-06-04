output "dataset_id" {
  description = "BigQuery dataset ID"
  value       = google_bigquery_dataset.st_louis.dataset_id
}

output "table_id" {
  description = "St. Louis parcels table ID"
  value       = google_bigquery_table.parcels.table_id
}

output "full_table_id" {
  description = "Fully qualified table ID for loading data"
  value       = "${var.project_id}.${google_bigquery_dataset.st_louis.dataset_id}.${google_bigquery_table.parcels.table_id}"
}
