output "dataset_id" {
  description = "BigQuery dataset ID"
  value       = google_bigquery_dataset.property_tax.dataset_id
}

output "table_id" {
  description = "Davidson parcels table ID"
  value       = google_bigquery_table.davidson_parcels.table_id
}

output "full_table_id" {
  description = "Fully qualified table ID for loading data"
  value       = "${var.project_id}.${google_bigquery_dataset.property_tax.dataset_id}.${google_bigquery_table.davidson_parcels.table_id}"
}
