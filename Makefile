# ============================================================
# realestate-channel — Makefile
# ============================================================
# Usage: make <target>
# Requires: Python 3.9+, Doppler CLI for secrets injection
# Cross-platform: macOS native, Windows via WSL2 or make for Windows
# ============================================================

PYTHON  := python3
SCRIPTS := scripts

# Doppler — override on the command line if needed:
#   make research DOPPLER_PROJECT=my-project DOPPLER_CONFIG=prd
DOPPLER_PROJECT ?= video_production
DOPPLER_CONFIG  ?= dev
DOPPLER         := doppler run --project $(DOPPLER_PROJECT) --config $(DOPPLER_CONFIG) --

# ============================================================
# SETUP
# ============================================================

.PHONY: install
install: ## Install Python dependencies via uv
	uv pip install -r requirements.txt

.PHONY: setup
setup: install ## First-time setup: install deps + verify environment
	$(DOPPLER) $(PYTHON) -m scripts.setup_check

.PHONY: dirs
dirs: ## Create Google Drive content folder structure
	$(DOPPLER) $(PYTHON) -m scripts.make_dirs

# ============================================================
# PIPELINE A — CONTENT OPERATION
# ============================================================

.PHONY: research
research: ## Research and generate ranked video ideas
	$(DOPPLER) $(PYTHON) -m scripts.research

.PHONY: script
script: ## Generate a video script (prompts for topic)
	$(DOPPLER) $(PYTHON) -m scripts.script

.PHONY: repurpose
repurpose: ## Repurpose a YouTube video into cross-platform content
	$(DOPPLER) $(PYTHON) -m scripts.repurpose

.PHONY: schedule
schedule: ## Schedule content via Postiz (requires review first)
	$(DOPPLER) $(PYTHON) -m scripts.schedule

.PHONY: analytics
analytics: ## Pull YouTube analytics and generate weekly report
	$(DOPPLER) $(PYTHON) -m scripts.analytics

.PHONY: pipeline-a
pipeline-a: research script repurpose ## Run full Pipeline A sequence (research → script → repurpose)

# ============================================================
# PIPELINE B — AI CREATION (stub, built in next phase)
# ============================================================
.PHONY: pipeline-b
pipeline-b: ## Run full Pipeline B sequence (voice → video)
	@echo "Pipeline B is under development. Run 'make help' for available commands."

.PHONY: generate-voice
generate-voice: ## Generate voiceover via ElevenLabs
	$(DOPPLER) $(PYTHON) -m scripts.generate_voice

.PHONY: generate-video
generate-video: ## Generate avatar video via HeyGen
	$(DOPPLER) $(PYTHON) -m scripts.generate_video

.PHONY: pipeline-b
pipeline-b: generate-voice generate-video ## Run full Pipeline B sequence (voice → video)

# ============================================================
# GIT HELPERS
# ============================================================

.PHONY: save
save: ## Commit all changes with a prompted message
	@read -p "Commit message: " msg; git add -A && git commit -m "$$msg"

.PHONY: checkpoint
checkpoint: ## Quick checkpoint commit (auto-message with timestamp)
	git add -A && git commit -m "checkpoint: $$(date '+%Y-%m-%d %H:%M')"

# ============================================================
# UTILITIES
# ============================================================

.PHONY: env-check
env-check: ## Verify all env vars are injected correctly via Doppler
	$(DOPPLER) $(PYTHON) -m scripts.env_check

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
