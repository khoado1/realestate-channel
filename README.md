# realestate-channel
echo "# realestate-channel" >> README.md
git init
git add README.md
git commit -m "first commit"
git branch -M main
git remote add origin https://github.com/khoado1/realestate-channel.git
git push -u origin main

3 directories:
$HOME/$BASE_CHANNEL -> $BASE_CHANNEL = realestate-channel , This is where I setup the video production pipeline and code
$HOME/Library/CloudStorage/OneDrive-Personal/BASE_CHANNEL -> This is where I store my files that are big like video and audio files
'$HOME/Library/CloudStorage/GoogleDrive-do.khoa.d@gmail.com/My Drive/$BASE_CHANEL' -> This is where I store my content like scripts, ideas, analysis

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

Use Doppler for secrets
doppler secrets upload .env
doppler secrets upload .env.example --project video_production --config dev

doppler run -- npm run dev
doppler run -- node server.js


#Anthropic API
url: https://platform.claude.com/
username: do.khoa.d@gmail.com
password: (google account)

# Social media distribution
url: https://platform.postiz.com
username: do.khoa.d@gmail.com
password: (google account)

url: https://elevenlabs.io
username: do.khoa.d@gmail.com
password: (google account)

# This is my voice
# ELEVENLABS_VOICE_ID=mww6wtfhAgllehLmX1fh
# This is Adam's voice (existing professional voice)
# ELEVENLABS_FALLBACK_VOICE_ID=wBXNqKUATyqu0RtYt25i

url: https://app.heygen.com/home
username: do.khoa.d@gmail.com
password: (google account)

url: https://console.cloud.google.com
username: pdrealestate2025@gmail.com
password: (google account)
To enable API access for YouTube and find your API key, you'll need to follow these steps in the Google Cloud Console while logged in with your account, pdrealestate2025@gmail.com.

1. Enable the YouTube Data API
Before you can create a key, you must enable the specific API for your project:

Go to the API Library  in the Google Cloud Console.
In the search bar, type "YouTube Data API v3" and select it from the results.
Click the Enable button.
2. Create and Find Your API Key
Once the API is enabled, you can generate the credentials:

Navigate to the Credentials page .
Click the + Create Credentials button at the top of the screen.
Select API key from the dropdown menu.
A dialog box will appear showing your new API key. You can copy it from there.

#Channel Id and Name
url: https://studio.youtube.com
username: pdrealestate2025@gmail.com
CHANNEL_NAME=PdRealestateAI
CHANNEL_ID=UCoWSG72c84VwYaLMeodEd8g
User Id=oWSG72c84VwYaLMeodEd8g

# --- Testing (no env var needed — use CLI flags directly) ---
# python3 .claude/commands/generate_voice.py --dry-run
# python3 .claude/commands/generate_video.py --dry-run
# Both scripts skip all API calls and print what they would have done.
