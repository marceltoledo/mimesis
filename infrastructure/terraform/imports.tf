# Import blocks reconcile resources that already exist in Azure with Terraform state.
# These blocks are safe to leave in place after the first apply; Terraform
# will simply verify the binding on subsequent runs.

import {
  to = azurerm_monitor_metric_alert.dlq_age_warning
  id = "/subscriptions/4bd495aa-ee07-4b54-a678-86d545b31c24/resourceGroups/mimesis-dev-rg/providers/Microsoft.Insights/metricAlerts/mimesis-dev-dlq-age-warning"
}

import {
  to = azurerm_monitor_metric_alert.dlq_age_critical
  id = "/subscriptions/4bd495aa-ee07-4b54-a678-86d545b31c24/resourceGroups/mimesis-dev-rg/providers/Microsoft.Insights/metricAlerts/mimesis-dev-dlq-age-critical"
}
