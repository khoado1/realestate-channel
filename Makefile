# ============================================================
# realestate-channel — Makefile
# ============================================================
# Usage: make <target>
# Requires: Python 3.9+, .env file at repo root
# Cross-platform: macOS native, Windows via WSL2 or make for Windows
# ============================================================

# Load .env automatically
ifneq (,$(wildcard .env))
    include .env
    export
endif

PYTHON := python3
PIP := pip3
SCRIPTS := scripts

# ============================================================
# SETUP
# ============================================================

.PHONY: install
install: ## Install Python dependencies
	$(PIP) install -r requirements.txt

.PHONY: setup
setup: install ## First-time setup: install deps + verify environment
	@echo "Checking environment..."
	@$(PYTHON) -c "import dotenv; print('✓ python-dotenv')"
	@$(PYTHON) -c "import requests; print('✓ requests')"
	@$(PYTHON) -c "import openai; print('✓ openai')" 2>/dev/null || echo "⚠ openai not installed (needed for Pipeline B)"
	@echo ""
	@echo "Checking paths..."
	@test -d "$(BASE_CONTENT_DIR)" && echo "✓ Google Drive content dir found" || echo "✗ Content dir not found: $(BASE_CONTENT_DIR)"
	@test -d "$(SCRIPTS_DIR)" && echo "✓ scripts/" || echo "✗ scripts/ missing — run: make dirs"
	@test -d "$(REPURPOSED_DIR)" && echo "✓ repurposed/" || echo "✗ repurposed/ missing — run: make dirs"
	@test -d "$(ANALYTICS_DIR)" && echo "✓ analytics/" || echo "✗ analytics/ missing — run: make dirs"
	@test -d "$(IDEAS_DIR)" && echo "✓ ideas/" || echo "✗ ideas/ missing — run: make dirs"
	@echo ""
	@echo "Setup complete. Run 'make help' to see available commands."

.PHONY: dirs
dirs: ## Create Google Drive content folder structure
	mkdir -p "$(SCRIPTS_DIR)"
	mkdir -p "$(REPURPOSED_DIR)"
	mkdir -p "$(ANALYTICS_DIR)"
	mkdir -p "$(IDEAS_DIR)"
	@touch "$(IDEAS_DIR)/backlog.md"
	@echo "✓ Content directories created at $(BASE_CONTENT_DIR)"

# ============================================================
# PIPELINE A — CONTENT OPERATION
# ============================================================

.PHONY: research
research: ## Research and generate ranked video ideas
	$(PYTHON) $(SCRIPTS)/research.py

.PHONY: script
script: ## Generate a video script (prompts for topic)
	$(PYTHON) $(SCRIPTS)/script.py

.PHONY: repurpose
repurpose: ## Repurpose a YouTube video into cross-platform content
	$(PYTHON) $(SCRIPTS)/repurpose.py

.PHONY: schedule
schedule: ## Schedule content via Postiz (requires review first)
	$(PYTHON) $(SCRIPTS)/schedule.py

.PHONY: analytics
analytics: ## Pull YouTube analytics and generate weekly report
	$(PYTHON) $(SCRIPTS)/analytics.py

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
	$(PYTHON) $(SCRIPTS)/generate_voice.py

.PHONY: generate-video
generate-video: ## Generate avatar video via HeyGen
	$(PYTHON) $(SCRIPTS)/generate_video.py

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
env-check: ## Verify .env is loaded and key vars are set
	@echo "BASE_CHANNEL:      $(BASE_CHANNEL)"
	@echo "BASE_CODE_DIR:     $(BASE_CODE_DIR)"
	@echo "BASE_CONTENT_DIR:  $(BASE_CONTENT_DIR)"
	@echo "SCRIPTS_DIR:       $(SCRIPTS_DIR)"
	@echo "YOUTUBE_API_KEY:   $$([ -n '$(YOUTUBE_API_KEY)' ] && echo '✓ set' || echo '✗ missing')"
	@echo "ELEVENLABS_API_KEY:$$([ -n '$(ELEVENLABS_API_KEY)' ] && echo '✓ set' || echo '✗ missing')"
	@echo "HEYGEN_API_KEY:    $$([ -n '$(HEYGEN_API_KEY)' ] && echo '✓ set' || echo '✗ missing')"
	@echo "POSTIZ_API_KEY:    $$([ -n '$(POSTIZ_API_KEY)' ] && echo '✓ set' || echo '✗ missing')"

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
