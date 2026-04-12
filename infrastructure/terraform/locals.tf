locals {
  project = "mimesis"
  prefix  = "${local.project}-${var.environment}"

  video_discovery_function_app_name = "${local.prefix}-fd-fn"
  video_ingestion_function_app_name = "${local.prefix}-fi-fn"
  function_plan_name                = "${local.prefix}-fn-plan"

  queue_max_delivery_count = var.environment == "dev" ? 5 : 10

  # Storage account name: lowercase alphanumeric, max 24 chars
  # "mimesis" + env (max 4 chars) + "sa" = 13 chars max → safe
  storage_account_name = "${replace(local.prefix, "-", "")}sa"

  tags = {
    environment  = var.environment
    project      = local.project
    "managed-by" = "iac"
  }
}
