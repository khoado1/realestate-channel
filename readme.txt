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