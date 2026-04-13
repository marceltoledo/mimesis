data "azurerm_client_config" "current" {}

# ── Resource Group ────────────────────────────────────────────────────────────

resource "azurerm_resource_group" "main" {
  name     = "${local.prefix}-rg"
  location = var.location
  tags     = local.tags
}

# ── Managed Identity ──────────────────────────────────────────────────────────

resource "azurerm_user_assigned_identity" "main" {
  name                = "${local.prefix}-id"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  tags                = local.tags
}

# ── Key Vault ─────────────────────────────────────────────────────────────────
# RBAC authorization enabled — no access policies required.

resource "azurerm_key_vault" "main" {
  name                      = "${local.prefix}-kv"
  resource_group_name       = azurerm_resource_group.main.name
  location                  = var.location
  tenant_id                 = data.azurerm_client_config.current.tenant_id
  sku_name                  = "standard"
  enable_rbac_authorization = true

  # 7 days soft-delete (minimum); purge protection off for dev agility
  soft_delete_retention_days = 7
  purge_protection_enabled   = false
  tags                       = local.tags
}

# The Terraform operator principal needs Key Vault Administrator to write secrets.
# See rbac.tf for the assignment.

resource "azurerm_key_vault_secret" "youtube_api_key" {
  name         = "youtube-api-key"
  value        = var.youtube_api_key
  key_vault_id = azurerm_key_vault.main.id

  # Wait until the operator role assignment is propagated
  depends_on = [azurerm_role_assignment.kv_admin]
}

# ── Storage Account + Discovery Ledger Table ──────────────────────────────────
# Standard_LRS only — no geo-replication (G-ADR-01 / FinOps policy).

resource "azurerm_storage_account" "main" {
  name                     = local.storage_account_name
  resource_group_name      = azurerm_resource_group.main.name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"
  tags                     = local.tags
}

resource "azurerm_storage_table" "discovery_ledger" {
  name               = "discoveryLedger"
  storage_account_id = azurerm_storage_account.main.id
}

resource "azurerm_storage_table" "ingestion_ledger" {
  name               = "ingestionLedger"
  storage_account_id = azurerm_storage_account.main.id
}

resource "azurerm_storage_container" "raw_videos" {
  name               = "raw-videos"
  storage_account_id = azurerm_storage_account.main.id
}

resource "azurerm_storage_container" "extracted_audio" {
  name               = "extracted-audio"
  storage_account_id = azurerm_storage_account.main.id
}

resource "azurerm_storage_container" "video_metadata" {
  name               = "video-metadata"
  storage_account_id = azurerm_storage_account.main.id
}

# Deployment artifact containers for FC1 Flex Consumption function apps.
resource "azurerm_storage_container" "fn_fd_deploy" {
  name               = "fn-fd-deploy"
  storage_account_id = azurerm_storage_account.main.id
}

resource "azurerm_storage_container" "fn_fi_deploy" {
  name               = "fn-fi-deploy"
  storage_account_id = azurerm_storage_account.main.id
}

resource "azurerm_storage_management_policy" "main" {
  storage_account_id = azurerm_storage_account.main.id

  rule {
    name    = "delete-raw-videos-after-30-days"
    enabled = true

    filters {
      blob_types   = ["blockBlob"]
      prefix_match = ["raw-videos/"]
    }

    actions {
      base_blob {
        delete_after_days_since_modification_greater_than = 30
      }
    }
  }
}

# ── Service Bus ───────────────────────────────────────────────────────────────
# Standard SKU: supports AMQP, duplicate detection, and at-least-once delivery
# (ADR-02).

resource "azurerm_servicebus_namespace" "main" {
  name                = "${local.prefix}-bus"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  sku                 = "Standard"
  tags                = local.tags
}

resource "azurerm_servicebus_queue" "video_discovered" {
  name         = "sb-queue-video-discovered"
  namespace_id = azurerm_servicebus_namespace.main.id

  # Duplicate detection window — messageId = videoId prevents re-queuing
  # in case of retries within this window.
  requires_duplicate_detection            = true
  duplicate_detection_history_time_window = "PT10M"

  max_delivery_count = local.queue_max_delivery_count
}

resource "azurerm_servicebus_queue" "video_ingested" {
  name         = "sb-queue-video-ingested"
  namespace_id = azurerm_servicebus_namespace.main.id

  requires_duplicate_detection            = true
  duplicate_detection_history_time_window = "PT10M"
  max_delivery_count                      = local.queue_max_delivery_count
}

# ── Function Apps (BC-01 + BC-02) ───────────────────────────────────────────

resource "azurerm_service_plan" "functions" {
  name                = local.function_plan_name
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  os_type             = "Linux"
  sku_name            = "FC1"
  tags                = local.tags
}

resource "azurerm_linux_function_app_flex_consumption" "video_discovery" {
  name                = local.video_discovery_function_app_name
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location

  service_plan_id = azurerm_service_plan.functions.id

  storage_container_type            = "blobContainer"
  storage_container_endpoint        = "${azurerm_storage_account.main.primary_blob_endpoint}${azurerm_storage_container.fn_fd_deploy.name}"
  storage_authentication_type       = "UserAssignedIdentity"
  storage_user_assigned_identity_id = azurerm_user_assigned_identity.main.id

  runtime_name    = "python"
  runtime_version = "3.12"

  maximum_instance_count = 5
  instance_memory_in_mb  = 2048

  https_only = true

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.main.id]
  }

  site_config {}

  app_settings = {
    APPINSIGHTS_INSTRUMENTATIONKEY        = azurerm_application_insights.main.instrumentation_key
    APPLICATIONINSIGHTS_CONNECTION_STRING = azurerm_application_insights.main.connection_string

    MIMESIS_KEY_VAULT_URL                  = azurerm_key_vault.main.vault_uri
    MIMESIS_STORAGE_ACCOUNT_URL            = azurerm_storage_account.main.primary_table_endpoint
    MIMESIS_DISCOVERY_LEDGER_TABLE         = azurerm_storage_table.discovery_ledger.name
    MIMESIS_SERVICE_BUS_NAMESPACE          = "${azurerm_servicebus_namespace.main.name}.servicebus.windows.net"
    MIMESIS_SERVICE_BUS_QUEUE              = azurerm_servicebus_queue.video_discovered.name
    MIMESIS_DEFAULT_MAX_RESULTS            = "15"
    MIMESIS_APP_INSIGHTS_CONNECTION_STRING = azurerm_application_insights.main.connection_string
  }

  tags = local.tags
}

resource "azurerm_linux_function_app_flex_consumption" "video_ingestion" {
  name                = local.video_ingestion_function_app_name
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location

  service_plan_id = azurerm_service_plan.functions.id

  storage_container_type            = "blobContainer"
  storage_container_endpoint        = "${azurerm_storage_account.main.primary_blob_endpoint}${azurerm_storage_container.fn_fi_deploy.name}"
  storage_authentication_type       = "UserAssignedIdentity"
  storage_user_assigned_identity_id = azurerm_user_assigned_identity.main.id

  runtime_name    = "python"
  runtime_version = "3.12"

  maximum_instance_count = 5
  instance_memory_in_mb  = 2048

  https_only = true

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.main.id]
  }

  site_config {}

  app_settings = {
    APPINSIGHTS_INSTRUMENTATIONKEY        = azurerm_application_insights.main.instrumentation_key
    APPLICATIONINSIGHTS_CONNECTION_STRING = azurerm_application_insights.main.connection_string

    MIMESIS_STORAGE_ACCOUNT_URL            = azurerm_storage_account.main.primary_table_endpoint
    MIMESIS_INGESTION_LEDGER_TABLE         = azurerm_storage_table.ingestion_ledger.name
    MIMESIS_SERVICE_BUS_NAMESPACE          = "${azurerm_servicebus_namespace.main.name}.servicebus.windows.net"
    MIMESIS_SERVICE_BUS_INGESTED_QUEUE     = azurerm_servicebus_queue.video_ingested.name
    MIMESIS_APP_INSIGHTS_CONNECTION_STRING = azurerm_application_insights.main.connection_string

    MIMESIS_SERVICE_BUS__fullyQualifiedNamespace = "${azurerm_servicebus_namespace.main.name}.servicebus.windows.net"
  }

  tags = local.tags
}

# ── Monitoring + Alerts ──────────────────────────────────────────────────────

resource "azurerm_monitor_diagnostic_setting" "service_bus_logs" {
  name                       = "${local.prefix}-sb-diag"
  target_resource_id         = azurerm_servicebus_namespace.main.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  enabled_log {
    category = "OperationalLogs"
  }

  metric {
    category = "AllMetrics"
  }
}

resource "azurerm_monitor_metric_alert" "dlq_count_warning" {
  name                = "${local.prefix}-dlq-count-warning"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_servicebus_namespace.main.id]
  description         = "Warning when DLQ count is >= 1 for 10 minutes."

  severity    = 2
  frequency   = "PT5M"
  window_size = "PT15M"

  criteria {
    metric_namespace = "Microsoft.ServiceBus/namespaces"
    metric_name      = "DeadletteredMessages"
    aggregation      = "Average"
    operator         = "GreaterThanOrEqual"
    threshold        = 1
  }

  tags = local.tags
}

resource "azurerm_monitor_metric_alert" "dlq_count_critical" {
  name                = "${local.prefix}-dlq-count-critical"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_servicebus_namespace.main.id]
  description         = "Critical when DLQ count is >= 5 for 10 minutes."

  severity    = 0
  frequency   = "PT5M"
  window_size = "PT15M"

  criteria {
    metric_namespace = "Microsoft.ServiceBus/namespaces"
    metric_name      = "DeadletteredMessages"
    aggregation      = "Average"
    operator         = "GreaterThanOrEqual"
    threshold        = 5
  }

  tags = local.tags
}

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "function_failure_warning" {
  name                = "${local.prefix}-fn-failure-warning"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  scopes              = [azurerm_application_insights.main.id]
  description         = "Warning when function failure rate is > 5% over 15 minutes."
  severity            = 2

  window_duration      = "PT15M"
  evaluation_frequency = "PT5M"

  criteria {
    query = <<-KQL
      let window = 15m;
      let total = toscalar(requests
        | where timestamp > ago(window)
        | where cloud_RoleName in ('mimesis-video-discovery', 'mimesis-video-ingestion')
        | count);
      let failed = toscalar(requests
        | where timestamp > ago(window)
        | where cloud_RoleName in ('mimesis-video-discovery', 'mimesis-video-ingestion')
        | where success == false
        | count);
      print failure_rate = iif(total == 0, 0.0, todouble(failed) * 100.0 / todouble(total))
    KQL

    operator                = "GreaterThan"
    threshold               = 5
    time_aggregation_method = "Maximum"
    metric_measure_column   = "failure_rate"

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  tags = local.tags
}

resource "azurerm_monitor_scheduled_query_rules_alert_v2" "function_failure_critical" {
  name                = "${local.prefix}-fn-failure-critical"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  scopes              = [azurerm_application_insights.main.id]
  description         = "Critical when function failure rate is > 20% over 15 minutes."
  severity            = 0

  window_duration      = "PT15M"
  evaluation_frequency = "PT5M"

  criteria {
    query = <<-KQL
      let window = 15m;
      let total = toscalar(requests
        | where timestamp > ago(window)
        | where cloud_RoleName in ('mimesis-video-discovery', 'mimesis-video-ingestion')
        | count);
      let failed = toscalar(requests
        | where timestamp > ago(window)
        | where cloud_RoleName in ('mimesis-video-discovery', 'mimesis-video-ingestion')
        | where success == false
        | count);
      print failure_rate = iif(total == 0, 0.0, todouble(failed) * 100.0 / todouble(total))
    KQL

    operator                = "GreaterThan"
    threshold               = 20
    time_aggregation_method = "Maximum"
    metric_measure_column   = "failure_rate"

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  tags = local.tags
}

# ── Log Analytics Workspace (required by workspace-based App Insights) ────────

resource "azurerm_log_analytics_workspace" "main" {
  name                = "${local.prefix}-law"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = local.tags
}

# ── Application Insights ──────────────────────────────────────────────────────

resource "azurerm_application_insights" "main" {
  name                = "${local.prefix}-ai"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "other"
  tags                = local.tags
}
