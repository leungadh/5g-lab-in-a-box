# 5G Core Lab-in-a-Box — task runner
# Thin wrapper over docker-compose + helper scripts so the whole lab is `make`-driven.

SHELL := /bin/bash
CORE ?= open5gs
COMPOSE := docker compose -f deploy/$(CORE)/docker-compose.yml --env-file deploy/$(CORE)/.env
DURATION ?= 120
ATTACK ?=

.DEFAULT_GOAL := help

.PHONY: help bootstrap up down provision-subscriber ran-up ran-down smoke-test capture attack clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

bootstrap: ## One-time host prep (docker, kernel modules, sysctl, NAT)
	./scripts/bootstrap.sh

up: ## Bring up the core network + WebUI
	$(COMPOSE) up -d
	@echo "Core '$(CORE)' starting. WebUI (open5gs) → http://localhost:9999"

down: ## Stop the core network
	$(COMPOSE) down

provision-subscriber: ## Add the test subscriber from .env
	./scripts/provision_subscriber.sh $(CORE)

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

clean: ## Remove captured pcaps and generated data
	rm -rf capture/pcaps/*.pcap capture/data/*.parquet 2>/dev/null || true
