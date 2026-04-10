.PHONY: install test test-all lint fmt typecheck tf-init tf-validate tf-plan-dev tf-apply-dev tf-plan-prod tf-apply-prod

install:
	pip install -e ".[dev]"

test:
	pytest

test-all:
	pytest -m ""

lint:
	ruff check src/ tests/

fmt:
	black src/ tests/

typecheck:
	mypy src/

tf-init:
	terraform -chdir=infrastructure/terraform init -backend-config=backend.hcl

tf-validate:
	terraform -chdir=infrastructure/terraform validate

tf-plan-dev:
	terraform -chdir=infrastructure/terraform plan \
	  -var-file=dev.tfvars \
	  -var-file=dev.secrets.tfvars

tf-apply-dev:
	terraform -chdir=infrastructure/terraform apply \
	  -var-file=dev.tfvars \
	  -var-file=dev.secrets.tfvars

tf-plan-prod:
	terraform -chdir=infrastructure/terraform plan \
	  -var-file=prod.tfvars \
	  -var-file=prod.secrets.tfvars

tf-apply-prod:
	terraform -chdir=infrastructure/terraform apply \
	  -var-file=prod.tfvars \
	  -var-file=prod.secrets.tfvars
