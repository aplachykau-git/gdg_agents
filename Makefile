SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

# Prefer project-local virtual-environment tools, then fall back to PATH.
PYTHON_BIN := $(shell if [ -x .venv/bin/python3 ]; then printf '%s' .venv/bin/python3; elif [ -x .venv/bin/python ]; then printf '%s' .venv/bin/python; else command -v python3 || command -v python || true; fi)
ADK_BIN := $(shell if [ -x .venv/bin/adk ]; then printf '%s' .venv/bin/adk; else command -v adk || true; fi)
UVICORN_BIN := $(shell if [ -x .venv/bin/uvicorn ]; then printf '%s' .venv/bin/uvicorn; else command -v uvicorn || true; fi)
NPM_BIN := $(shell command -v npm || true)

LINKEDIN_EVAL_DIR := agents/linkedin_post_generator/evaluation
LINKEDIN_EVAL_SET := $(LINKEDIN_EVAL_DIR)/post_generator_eval_set.json
LINKEDIN_EVAL_CONFIG := $(LINKEDIN_EVAL_DIR)/post_generator_eval_config.json
RECEIPT_EVAL_DIR := agents/receipt_scanner/evaluation
RECEIPT_EVAL_MODEL ?= gemini-3.6-flash

.PHONY: help tools linkedin-evals linkedin-judge-evals linkedin-evals-all \
	receipt-eval-discover receipt-eval-fixtures receipt-extraction-evals \
	receipt-conversion-evals receipt-evals-all run-all

help: ## Show available commands.
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_-]+:.*##/ {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

tools: ## Show the resolved Python, ADK, Uvicorn, and npm executables.
	@printf 'PYTHON_BIN=%s\nADK_BIN=%s\nUVICORN_BIN=%s\nNPM_BIN=%s\n' \
		"$(PYTHON_BIN)" "$(ADK_BIN)" "$(UVICORN_BIN)" "$(NPM_BIN)"

linkedin-judge-evals: ## Run the held-out few-shot LinkedIn judge evaluation.
	@test -n "$(PYTHON_BIN)" || { echo "Python was not found. Create .venv or install python3."; exit 1; }
	"$(PYTHON_BIN)" -m agents.linkedin_post_generator.evaluation.run_judge_eval

linkedin-evals: ## Run the ADK end-to-end LinkedIn post-generator evaluation.
	@test -n "$(ADK_BIN)" || { echo "ADK was not found. Create .venv or install google-adk."; exit 1; }
	"$(ADK_BIN)" eval agents/linkedin_post_generator "$(LINKEDIN_EVAL_SET)" \
		--config_file_path "$(LINKEDIN_EVAL_CONFIG)" \
		--print_detailed_results

linkedin-evals-all: ## Run judge evaluation first, then the ADK LinkedIn evaluation.
	@$(MAKE) linkedin-judge-evals
	@$(MAKE) linkedin-evals

receipt-eval-discover: ## Discover receipt fixture candidates from OCR metadata.
	@test -n "$(PYTHON_BIN)" || { echo "Python was not found. Create .venv or install python3."; exit 1; }
	"$(PYTHON_BIN)" -m agents.receipt_scanner.evaluation.prepare_fixtures discover

receipt-eval-fixtures: ## Download and verify pinned receipt evaluation images.
	@test -n "$(PYTHON_BIN)" || { echo "Python was not found. Create .venv or install python3."; exit 1; }
	"$(PYTHON_BIN)" -m agents.receipt_scanner.evaluation.prepare_fixtures download

receipt-extraction-evals: ## Run live Gemini receipt extraction evaluations.
	@test -n "$(PYTHON_BIN)" || { echo "Python was not found. Create .venv or install python3."; exit 1; }
	@test -n "$(ADK_BIN)" || { echo "ADK was not found. Create .venv or install google-adk."; exit 1; }
	"$(PYTHON_BIN)" -m agents.receipt_scanner.evaluation.prepare_fixtures verify
	RECEIPT_EVAL_MODEL="$(RECEIPT_EVAL_MODEL)" RECEIPT_SCANNER_MODEL="$(RECEIPT_EVAL_MODEL)" \
		"$(PYTHON_BIN)" -m agents.receipt_scanner.evaluation.run_extraction_eval --adk "$(ADK_BIN)"

receipt-conversion-evals: ## Run deterministic receipt currency conversion evaluations.
	@test -n "$(PYTHON_BIN)" || { echo "Python was not found. Create .venv or install python3."; exit 1; }
	"$(PYTHON_BIN)" -m agents.receipt_scanner.evaluation.run_conversion_eval

receipt-evals-all: ## Prepare fixtures, then run conversion and extraction evaluations.
	@$(MAKE) receipt-eval-fixtures
	@$(MAKE) receipt-conversion-evals
	@$(MAKE) receipt-extraction-evals

run-all: ## Start Video A2A, Receipt A2A, ADK web, and the frontend; Ctrl+C stops all.
	@test -n "$(PYTHON_BIN)" || { echo "Python was not found. Create .venv or install python3."; exit 1; }
	@test -n "$(ADK_BIN)" || { echo "ADK was not found. Create .venv or install google-adk."; exit 1; }
	@test -n "$(UVICORN_BIN)" || { echo "Uvicorn was not found. Create .venv or install uvicorn."; exit 1; }
	@test -n "$(NPM_BIN)" || { echo "npm was not found. Install Node.js and npm."; exit 1; }
	@PYTHON_BIN="$(PYTHON_BIN)" ADK_BIN="$(ADK_BIN)" UVICORN_BIN="$(UVICORN_BIN)" NPM_BIN="$(NPM_BIN)" \
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
			"$$UVICORN_BIN" agents.video_editor.a2a_server:a2a_app --host 0.0.0.0 --port 8081 & pids="$$pids $$!"; \
			echo "Starting Receipt Scanner A2A service on http://127.0.0.1:8082..."; \
			"$$UVICORN_BIN" agents.receipt_scanner.a2a_server:a2a_app --host 0.0.0.0 --port 8082 & pids="$$pids $$!"; \
			sleep 2; \
			echo "Starting Root Orchestrator on http://127.0.0.1:8080..."; \
			VIDEO_AGENT_A2A_URL=http://localhost:8081 RECEIPT_AGENT_A2A_URL=http://localhost:8082 ADK_SUPPRESS_A2A_EXPERIMENTAL_FEATURE_WARNINGS=true \
				"$$ADK_BIN" web --port 8080 agents & pids="$$pids $$!"; \
			echo "Starting frontend on http://localhost:5173..."; \
			"$$NPM_BIN" run dev --prefix frontend & pids="$$pids $$!"; \
			echo "All services are running. Press Ctrl+C to stop."; \
			wait \
		'
