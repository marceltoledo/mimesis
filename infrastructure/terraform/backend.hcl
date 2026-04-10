# Remote backend configuration for Azure Blob Storage.
# Run once to bootstrap: see the bootstrap commands below, then:
#   make tf-init
#
# Bootstrap (one-time, run as your own Azure user):
#   az login
#   az group create -n mimesis-tfstate-rg -l northeurope \
#     --subscription 4bd495aa-ee07-4b54-a678-86d545b31c24
#   az storage account create -n mimesistfstatesa \
#     -g mimesis-tfstate-rg -l northeurope \
#     --sku Standard_LRS \
#     --subscription 4bd495aa-ee07-4b54-a678-86d545b31c24
#   az storage container create -n tfstate \
#     --account-name mimesistfstatesa \
#     --subscription 4bd495aa-ee07-4b54-a678-86d545b31c24

subscription_id      = "4bd495aa-ee07-4b54-a678-86d545b31c24"
resource_group_name  = "mimesis-tfstate-rg"
storage_account_name = "mimesistfstatesa"
container_name       = "tfstate"

# Change this key per environment before running tf-init:
#   dev:  "mimesis/dev/terraform.tfstate"
#   prod: "mimesis/prod/terraform.tfstate"
key = "mimesis/dev/terraform.tfstate"
