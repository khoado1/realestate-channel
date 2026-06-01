# realestate-channel
echo "# realestate-channel" >> README.md
git init
git add README.md
git commit -m "first commit"
git branch -M main
git remote add origin https://github.com/khoado1/realestate-channel.git
git push -u origin main

AI-powered YouTube content pipeline for real estate & loans content.

## Stack

| Layer | Tool | Purpose |
|---|---|---|
| Brain | Claude Code | Orchestration, scripting, research |
| Distribution | Postiz | Cross-platform scheduling |
| Analytics | YouTube Data API | Performance feedback loop |
| Voice (B) | ElevenLabs | AI voiceover |
| Video (B) | HeyGen | AI avatar video |

## Quick start

```bash
# 1. Clone and enter repo
git clone <repo-url>
cd realestate-channel

# 2. Set up environment
cp .env.example .env
# edit .env with your local paths and API keys

# 3. Install dependencies
make install

# 4. Verify setup
make setup

# 5. Create Google Drive folder structure
make dirs

# 6. Check everything is wired
make env-check
```

## Pipeline A — Content operation

```bash
make research      # generate ranked video ideas
make script        # write a video script
make repurpose     # repurpose a video across platforms
make schedule      # schedule via Postiz (review before running)
make analytics     # pull YouTube performance report
make pipeline-a    # run research → script → repurpose in sequence
```

## Pipeline B — AI creation (coming soon)

```bash
make generate-voice   # ElevenLabs voiceover
make generate-video   # HeyGen avatar video
make pipeline-b       # full AI video generation
```

## Git workflow

```bash
make save          # commit with custom message
make checkpoint    # quick timestamped commit
```

## Environment variables

See `.env.example` for all required variables. Key ones:

- `BASE_CHANNEL` — channel folder name
- `BASE_CODE_DIR` — local repo path
- `BASE_CONTENT_DIR` — Google Drive content path
- `YOUTUBE_API_KEY` — from Google Cloud Console
- `ELEVENLABS_API_KEY` — from elevenlabs.io
- `HEYGEN_API_KEY` — from heygen.com
- `POSTIZ_API_KEY` — from postiz.com

## Repo structure

```
realestate-channel/
├── CLAUDE.md              ← Claude's operating instructions
├── Makefile               ← pipeline commands
├── requirements.txt       ← Python dependencies
├── .env.example           ← environment template (committed)
├── .env                   ← your local secrets (gitignored)
├── .gitignore
├── README.md
└── scripts/               ← Python pipeline scripts
    ├── research.py
    ├── script.py
    ├── repurpose.py
    ├── schedule.py
    ├── analytics.py
    ├── generate_voice.py  ← Pipeline B
    └── generate_video.py  ← Pipeline B
```

---
_Content files live in Google Drive at `$BASE_CONTENT_DIR` — not in this repo._
