variable "subscription_id" {
  description = "Azure Subscription ID."
  type        = string
}

variable "tenant_id" {
  description = <<-EOT
    Azure AD Tenant ID or domain (e.g. 'MTOLEDO236.onmicrosoft.com' or the GUID).
    Retrieve the GUID with: az account show --query tenantId -o tsv
  EOT
  type        = string
}

variable "environment" {
  description = "Deployment environment: 'dev' or 'prod'."
  type        = string
  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment must be 'dev' or 'prod'."
  }
}

variable "location" {
  description = "Azure region for all resources.  Must be northeurope per G-ADR."
  type        = string
  default     = "northeurope"
}

variable "youtube_api_key" {
  description = <<-EOT
    YouTube Data API v3 key.  Stored in Key Vault; the raw value ends up in
    Terraform state.  For higher-security environments, set this variable to a
    placeholder and manage the secret out-of-band via:
      az keyvault secret set --vault-name <name> --name youtube-api-key --value <key>
    then remove the azurerm_key_vault_secret resource from the state.
  EOT
  type      = string
  sensitive = true
}
