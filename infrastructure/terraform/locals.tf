locals {
  project = "mimesis"
  prefix  = "${local.project}-${var.environment}"

  # Storage account name: lowercase alphanumeric, max 24 chars
  # "mimesis" + env (max 4 chars) + "sa" = 13 chars max → safe
  storage_account_name = "${replace(local.prefix, "-", "")}sa"

  tags = {
    environment  = var.environment
    project      = local.project
    "managed-by" = "iac"
  }
}
