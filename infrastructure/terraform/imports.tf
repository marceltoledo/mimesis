# Import blocks reconcile resources that already exist in Azure with Terraform state.
# These blocks are safe to leave in place after the first apply; Terraform
# will simply verify the binding on subsequent runs.
#
# Terraform >= 1.7 supports expressions in the `id` field, so the IDs are
# derived from the same variables used by the resource definitions.

import {
  to = azurerm_monitor_metric_alert.dlq_age_warning
  id = "/subscriptions/${var.subscription_id}/resourceGroups/${local.prefix}-rg/providers/Microsoft.Insights/metricAlerts/${local.prefix}-dlq-age-warning"
}

import {
  to = azurerm_monitor_metric_alert.dlq_age_critical
  id = "/subscriptions/${var.subscription_id}/resourceGroups/${local.prefix}-rg/providers/Microsoft.Insights/metricAlerts/${local.prefix}-dlq-age-critical"
}
