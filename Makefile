# 5G Core Lab-in-a-Box — task runner
# Thin wrapper over docker-compose + helper scripts so the whole lab is `make`-driven.

SHELL := /bin/bash
CORE ?= open5gs
COMPOSE := docker compose -f deploy/$(CORE)/docker-compose.yml --env-file deploy/$(CORE)/.env
DURATION ?= 120
ATTACK ?=
OPEN5GS_IMAGE ?= gradiant/open5gs:2.7.5

.DEFAULT_GOAL := help

.PHONY: help bootstrap env configs up down provision-subscriber webui-admin ran-up ran-down smoke-test capture attack clean detector-synth detector-train

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

bootstrap: ## One-time host prep (docker, kernel modules, sysctl, NAT)
	./scripts/bootstrap.sh

env: ## Create .env files from examples if missing
	@[ -f .env ] || { cp .env.example .env && echo "created .env"; }
	@[ -f deploy/$(CORE)/.env ] || { cp deploy/$(CORE)/.env.example deploy/$(CORE)/.env && echo "created deploy/$(CORE)/.env"; }
	@echo "env ready"

configs: ## Populate Open5GS NF configs from the image defaults (one-time)
	@echo "removing any dirs Docker auto-created in place of config files..."
	@find deploy/$(CORE)/configs -maxdepth 1 -type d -name '*.yaml' -exec rmdir {} + 2>/dev/null || true
	@echo "extracting default configs from $(OPEN5GS_IMAGE)..."
	docker run --rm --entrypoint sh $(OPEN5GS_IMAGE) \
	  -c 'cd /opt/open5gs/etc/open5gs && tar -c *.yaml' | tar -x -C deploy/$(CORE)/configs
	@echo "configs written. Reconcile amf/smf/upf with .env before ran-up (see docs/PLATFORM.md §7)."

up: env ## Bring up the core network + WebUI (auto-creates .env)
	@ls deploy/$(CORE)/configs/nrf.yaml >/dev/null 2>&1 || { echo "NF configs missing — run 'make configs' first (see docs/PLATFORM.md §7)"; exit 1; }
	$(COMPOSE) up -d
	@echo "Core '$(CORE)' starting. WebUI → http://localhost:9999  (login: admin / 1423)"
	@echo "If login fails with 'wrong password', run: make webui-admin"

down: ## Stop the core network
	$(COMPOSE) down

provision-subscriber: ## Add the test subscriber from .env
	./scripts/provision_subscriber.sh $(CORE)

webui-admin: ## Seed/reset the WebUI admin account (admin/1423) — fixes 'wrong password'
	./scripts/create_webui_admin.sh $(CORE)

ran-up: ## Start UERANSIM gNB then UE
	./scripts/ran.sh up

ran-down: ## Stop UERANSIM
	./scripts/ran.sh down

smoke-test: ## Verify end-to-end data path (UE → N6)
	./tests/smoke_test.sh

capture: ## Capture N3/N4 for DURATION seconds (make capture DURATION=300)
	./capture/capture.sh $(DURATION)

attack: ## Run one attack script (make attack ATTACK=gtpu/malformed_gtpu.py)
	@test -n "$(ATTACK)" || { echo "set ATTACK=<path under attacks/>"; exit 1; }
	python3 attacks/$(ATTACK)

detector-synth: ## Validate the baseline detector on synthetic data
	python3 detector/baseline.py --synth --model isoforest

detector-train: ## Run the baseline detector on captured features (DATA=path, MODEL=isoforest|autoencoder|both)
	python3 detector/baseline.py --data $(or $(DATA),capture/data/features.parquet) --model $(or $(MODEL),isoforest)

clean: ## Remove captured pcaps and generated data
	rm -rf capture/pcaps/*.pcap capture/data/*.parquet detector/out/* 2>/dev/null || true
