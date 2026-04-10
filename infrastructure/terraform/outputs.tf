output "resource_group_name" {
  description = "Name of the Azure Resource Group."
  value       = azurerm_resource_group.main.name
}

output "managed_identity_client_id" {
  description = "Client ID of the user-assigned Managed Identity (set on compute resources)."
  value       = azurerm_user_assigned_identity.main.client_id
}

output "managed_identity_principal_id" {
  description = "Principal (object) ID of the Managed Identity."
  value       = azurerm_user_assigned_identity.main.principal_id
}

output "key_vault_url" {
  description = "URI of the Azure Key Vault — set as MIMESIS_KEY_VAULT_URL."
  value       = azurerm_key_vault.main.vault_uri
}

output "storage_account_url" {
  description = "Primary table endpoint — set as MIMESIS_STORAGE_ACCOUNT_URL."
  value       = azurerm_storage_account.main.primary_table_endpoint
}

output "service_bus_namespace" {
  description = "Fully-qualified Service Bus hostname — set as MIMESIS_SERVICE_BUS_NAMESPACE."
  value       = "${azurerm_servicebus_namespace.main.name}.servicebus.windows.net"
}

output "service_bus_queue" {
  description = "Service Bus queue name — set as MIMESIS_SERVICE_BUS_QUEUE."
  value       = azurerm_servicebus_queue.video_discovered.name
}

output "app_insights_connection_string" {
  description = "Application Insights connection string — set as MIMESIS_APP_INSIGHTS_CONNECTION_STRING."
  value       = azurerm_application_insights.main.connection_string
  sensitive   = true
}
