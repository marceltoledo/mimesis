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
  name                 = "discoveryLedger"
  storage_account_name = azurerm_storage_account.main.name
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

  max_delivery_count = 10
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
