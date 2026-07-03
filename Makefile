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
	@echo "Checking Python deps..."
	@$(PYTHON) -c "import dotenv; print('✓ python-dotenv')"
	@$(PYTHON) -c "import requests; print('✓ requests')"
	@$(PYTHON) -c "import rich; print('✓ rich')"
	@$(PYTHON) -c "import youtube_transcript_api; print('✓ youtube-transcript-api')"
	@$(PYTHON) -c "import dateutil; print('✓ python-dateutil')"
	@echo ""
	@echo "Checking Doppler..."
	@doppler --version 2>/dev/null && echo "✓ doppler CLI installed" || echo "✗ doppler not found — install from doppler.com/cli"
	@doppler me 2>/dev/null && echo "✓ doppler authenticated" || echo "✗ doppler not authenticated — run: doppler login"
	@echo ""
	@echo "Checking paths..."
	@$(DOPPLER) $(PYTHON) -c "import os; d=os.getenv('BASE_CONTENT_DIR',''); print('✓ BASE_CONTENT_DIR:', d) if d else print('✗ BASE_CONTENT_DIR not set')"
	@$(DOPPLER) $(PYTHON) -c "import os; d=os.getenv('SCRIPTS_DIR',''); print('✓ SCRIPTS_DIR:', d) if d else print('✗ SCRIPTS_DIR not set')"
	@echo ""
	@echo "Setup complete. Run 'make dirs' to create content folders, then 'make help'."

.PHONY: dirs
dirs: ## Create Google Drive content folder structure
	$(DOPPLER) $(PYTHON) -c "\
import os, sys; \
from pathlib import Path; \
def resolve(v): return os.path.expandvars(os.path.expanduser(v)) if v else ''; \
base = resolve(os.getenv('BASE_CONTENT_DIR', '')); \
sys.exit('✗ BASE_CONTENT_DIR not set — is Doppler injecting vars? Run: make env-check') if not base else None; \
dirs = [resolve(os.getenv(k,'')) for k in ('SCRIPTS_DIR','REPURPOSED_DIR','ANALYTICS_DIR','IDEAS_DIR')]; \
[Path(d).mkdir(parents=True, exist_ok=True) for d in dirs if d]; \
ideas = resolve(os.getenv('IDEAS_DIR','')); \
open(os.path.join(ideas, 'backlog.md'), 'a').close() if ideas else None; \
print('✓ Content directories created at', base) \
"

# ============================================================
# PIPELINE A — CONTENT OPERATION
# ============================================================

.PHONY: research
research: ## Research and generate ranked video ideas
	$(DOPPLER) $(PYTHON) $(SCRIPTS)/research.py

.PHONY: script
script: ## Generate a video script (prompts for topic)
	$(DOPPLER) $(PYTHON) $(SCRIPTS)/script.py

.PHONY: repurpose
repurpose: ## Repurpose a YouTube video into cross-platform content
	$(DOPPLER) $(PYTHON) $(SCRIPTS)/repurpose.py

.PHONY: schedule
schedule: ## Schedule content via Postiz (requires review first)
	$(DOPPLER) $(PYTHON) $(SCRIPTS)/schedule.py

.PHONY: analytics
analytics: ## Pull YouTube analytics and generate weekly report
	$(DOPPLER) $(PYTHON) $(SCRIPTS)/analytics.py

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
	$(DOPPLER) $(PYTHON) $(SCRIPTS)/generate_voice.py

.PHONY: generate-video
generate-video: ## Generate avatar video via HeyGen
	$(DOPPLER) $(PYTHON) $(SCRIPTS)/generate_video.py

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
	@$(DOPPLER) $(PYTHON) -c "\
import os; \
vars = { \
    'BASE_CONTENT_DIR':   os.getenv('BASE_CONTENT_DIR'), \
    'CHANNEL_NAME':       os.getenv('CHANNEL_NAME'), \
    'CHANNEL_ID':         os.getenv('CHANNEL_ID'), \
    'YOUTUBE_API_KEY':    os.getenv('YOUTUBE_API_KEY'), \
    'POSTIZ_API_KEY':     os.getenv('POSTIZ_API_KEY'), \
    'ELEVENLABS_API_KEY': os.getenv('ELEVENLABS_API_KEY'), \
    'HEYGEN_API_KEY':     os.getenv('HEYGEN_API_KEY'), \
}; \
[print(f'  {\"✓\" if v else \"✗\"} {k}: {v[:6]+\"...\" if v and \"KEY\" in k else (v or \"MISSING\")}') for k,v in vars.items()] \
"

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
