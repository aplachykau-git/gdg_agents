SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

UV_BIN := $(shell command -v uv || true)
NPM_BIN := $(shell command -v npm || true)

LINKEDIN_EVAL_DIR := agents/linkedin_post_generator/evaluation
LINKEDIN_EVAL_SET := $(LINKEDIN_EVAL_DIR)/post_generator_eval_set.json
LINKEDIN_EVAL_CONFIG := $(LINKEDIN_EVAL_DIR)/post_generator_eval_config.json
RECEIPT_EVAL_DIR := agents/receipt_scanner/evaluation
RECEIPT_EVAL_MODEL ?= gemini-3.7-flash

.PHONY: help tools linkedin-evals linkedin-judge-evals linkedin-evals-all \
	receipt-eval-discover receipt-eval-fixtures receipt-extraction-evals \
	receipt-conversion-evals receipt-evals-all video-editor-evals video-editor-evals-all \
	run-all deploy deploy-frontend

help: ## Show available commands.
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_-]+:.*##/ {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

tools: ## Show the resolved uv and npm executables.
	@printf 'UV_BIN=%s\nNPM_BIN=%s\n' "$(UV_BIN)" "$(NPM_BIN)"

linkedin-judge-evals: ## Run the held-out few-shot LinkedIn judge evaluation.
	@test -n "$(UV_BIN)" || { echo "uv was not found. Install uv and run uv sync --locked."; exit 1; }
	"$(UV_BIN)" run --locked --no-sync python -m agents.linkedin_post_generator.evaluation.run_judge_eval

linkedin-evals: ## Run the ADK end-to-end LinkedIn post-generator evaluation.
	@test -n "$(UV_BIN)" || { echo "uv was not found. Install uv and run uv sync --locked."; exit 1; }
	"$(UV_BIN)" run --locked --no-sync adk eval agents/linkedin_post_generator "$(LINKEDIN_EVAL_SET)" \
		--config_file_path "$(LINKEDIN_EVAL_CONFIG)" \
		--print_detailed_results

linkedin-evals-all: ## Run judge evaluation first, then the ADK LinkedIn evaluation.
	@$(MAKE) linkedin-judge-evals
	@$(MAKE) linkedin-evals

receipt-eval-discover: ## Discover receipt fixture candidates from OCR metadata.
	@test -n "$(UV_BIN)" || { echo "uv was not found. Install uv and run uv sync --locked."; exit 1; }
	"$(UV_BIN)" run --locked --no-sync python -m agents.receipt_scanner.evaluation.prepare_fixtures discover

receipt-eval-fixtures: ## Download and verify pinned receipt evaluation images.
	@test -n "$(UV_BIN)" || { echo "uv was not found. Install uv and run uv sync --locked."; exit 1; }
	"$(UV_BIN)" run --locked --no-sync python -m agents.receipt_scanner.evaluation.prepare_fixtures download

receipt-extraction-evals: ## Run live Gemini receipt extraction evaluations.
	@test -n "$(UV_BIN)" || { echo "uv was not found. Install uv and run uv sync --locked."; exit 1; }
	"$(UV_BIN)" run --locked --no-sync python -m agents.receipt_scanner.evaluation.prepare_fixtures verify
	RECEIPT_EVAL_MODEL="$(RECEIPT_EVAL_MODEL)" RECEIPT_SCANNER_MODEL="$(RECEIPT_EVAL_MODEL)" \
		"$(UV_BIN)" run --locked --no-sync python -m agents.receipt_scanner.evaluation.run_extraction_eval \
			--adk "$(UV_BIN) run --locked --no-sync adk"

receipt-conversion-evals: ## Run deterministic receipt currency conversion evaluations.
	@test -n "$(UV_BIN)" || { echo "uv was not found. Install uv and run uv sync --locked."; exit 1; }
	"$(UV_BIN)" run --locked --no-sync python -m agents.receipt_scanner.evaluation.run_conversion_eval

receipt-evals-all: ## Prepare fixtures, then run conversion and extraction evaluations.
	@$(MAKE) receipt-eval-fixtures
	@$(MAKE) receipt-conversion-evals
	@$(MAKE) receipt-extraction-evals

video-editor-evals: ## Run live ADK video-editor chat evaluations.
	@test -n "$(UV_BIN)" || { echo "uv was not found. Install uv and run uv sync --locked."; exit 1; }
	"$(UV_BIN)" run --locked --no-sync python -m agents.video_editor.evaluation.run_chat_eval \
		--adk "$(UV_BIN) run --locked --no-sync adk"

video-editor-evals-all: ## Run video-editor unit tests, then live chat evaluations.
	@test -n "$(UV_BIN)" || { echo "uv was not found. Install uv and run uv sync --locked."; exit 1; }
	"$(UV_BIN)" run --locked --no-sync python -m unittest tests.test_video_editor_workflow -v
	@$(MAKE) video-editor-evals

run-all: ## Start Video A2A, Receipt A2A, ADK web, and the frontend; Ctrl+C stops all.
	@test -n "$(UV_BIN)" || { echo "uv was not found. Install uv and run uv sync --locked."; exit 1; }
	@test -n "$(NPM_BIN)" || { echo "npm was not found. Install Node.js and npm."; exit 1; }
	@"$(UV_BIN)" sync --locked
	@UV_BIN="$(UV_BIN)" NPM_BIN="$(NPM_BIN)" \
		bash -eu -o pipefail -c '\
			pids=""; \
			cleanup() { \
				echo ""; \
				echo "Stopping all A2A agent services and frontend..."; \
				for pid in $$pids; do \
					if kill -0 "$$pid" 2>/dev/null; then kill "$$pid" 2>/dev/null || true; fi; \
				done; \
				wait 2>/dev/null || true; \
				echo "All services stopped cleanly."; \
			}; \
			trap cleanup INT TERM EXIT; \
			echo "Starting Video Editor A2A service on http://127.0.0.1:8081..."; \
			"$$UV_BIN" run --locked --no-sync uvicorn agents.video_editor.a2a_server:a2a_app --host 0.0.0.0 --port 8081 & pids="$$pids $$!"; \
			echo "Starting Receipt Scanner A2A service on http://127.0.0.1:8082..."; \
			"$$UV_BIN" run --locked --no-sync uvicorn agents.receipt_scanner.a2a_server:a2a_app --host 0.0.0.0 --port 8082 & pids="$$pids $$!"; \
			sleep 2; \
			echo "Starting Root Orchestrator on http://127.0.0.1:8080..."; \
			VIDEO_AGENT_A2A_URL=http://localhost:8081 RECEIPT_AGENT_A2A_URL=http://localhost:8082 ADK_SUPPRESS_A2A_EXPERIMENTAL_FEATURE_WARNINGS=true \
				"$$UV_BIN" run --locked --no-sync adk web --port 8080 agents & pids="$$pids $$!"; \
			echo "Starting frontend on http://localhost:5173..."; \
			"$$NPM_BIN" run dev --prefix frontend & pids="$$pids $$!"; \
				echo "All services are running. Press Ctrl+C to stop."; \
				wait \
		'

deploy: ## Deploy all Cloud Run services and Firebase Hosting.
	./deploy/deploy_a2a_cloudrun.sh

deploy-frontend: ## Build and deploy frontend to Firebase Hosting.
	npm run build --prefix frontend && npx -y firebase-tools deploy --only hosting

tf-init: ## Initialize Terraform module in terraform/.
	cd terraform && terraform init

tf-plan: ## Run Terraform dry-run execution plan.
	cd terraform && terraform plan

tf-apply: ## Apply Terraform infrastructure changes.
	cd terraform && terraform apply

tf-deploy: ## Full automated container build and Terraform deployment to target GCP project.
	./deploy/deploy_terraform.sh
