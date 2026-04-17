output "dataset_id" {
  description = "BigQuery dataset ID"
  value       = google_bigquery_dataset.dallas.dataset_id
}

output "dataset_location" {
  description = "BigQuery dataset location"
  value       = google_bigquery_dataset.dallas.location
}

output "table_ids" {
  description = "List of BigQuery table IDs"
  value = {
    abatement_exempt   = google_bigquery_table.abatement_exempt.table_id
    account_apprl_year = google_bigquery_table.account_apprl_year.table_id
    account_info       = google_bigquery_table.account_info.table_id
    account_tif        = google_bigquery_table.account_tif.table_id
    acct_exempt_value  = google_bigquery_table.acct_exempt_value.table_id
    applied_std_exempt = google_bigquery_table.applied_std_exempt.table_id
    com_detail         = google_bigquery_table.com_detail.table_id
    freeport_exemption = google_bigquery_table.freeport_exemption.table_id
    land               = google_bigquery_table.land.table_id
    multi_owner        = google_bigquery_table.multi_owner.table_id
    res_addl           = google_bigquery_table.res_addl.table_id
    res_detail         = google_bigquery_table.res_detail.table_id
    taxable_object     = google_bigquery_table.taxable_object.table_id
    total_exemption    = google_bigquery_table.total_exemption.table_id
  }
}

output "view_ids" {
  description = "List of BigQuery view IDs"
  value = {
    v_property_core       = google_bigquery_table.view_property_core.table_id
    v_residential         = google_bigquery_table.view_residential.table_id
    v_commercial          = google_bigquery_table.view_commercial.table_id
    v_property_exemptions = google_bigquery_table.view_property_exemptions.table_id
  }
}
