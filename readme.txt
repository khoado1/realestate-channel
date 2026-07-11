
win11/wsl2: password: 12345

sudo --login

Setup Hard Requirements:

Python 3.10+
https://www.python.org/downloads/

uv
https://docs.astral.sh/uv/getting-started/installation/
curl -LsSf https://astral.sh/uv/install.sh | sh

#set a new environment
uv venv
source .venv/bin/activate

Git
https://git-scm.com/install/
sudo apt update
sudo apt install git
git --version

Doppler
https://dashboard.doppler.com/
macos: brew install dopplerhq/cli/doppler

win11/wsl2: 
sudo apt update && sudo apt install -y gnupg curl
(curl -Ls --tlsv1.2 --proto "=https" --retry 3 https://cli.doppler.com/install.sh || wget -t 3 -qO- https://cli.doppler.com/install.sh) | sh

SQLite
Included with Python

Java
note: for Kafka

https://www.oracle.com/java/technologies/downloads/#java25
or
macos: brew install openjdk@25

win11/wsl2: 
sudo apt update
sudo apt install openjdk-25-jdk -y

Kafka
macos: brew install kafka

win11/wsl2:
KAFKA=kafka_2.13-4.3.1
KAFKAF=kafka_2.13-4.3.1.tgz
# Download the Kafka tarball
wget https://downloads.apache.org/kafka/4.3.1/$KAFKAF

# Extract the files
tar -xzf $KAFKAF

# Move the directory to /opt for cleaner organization
sudo mv $KAFKAF /opt/kafka

# Clean up the downloaded file (delete folder)
# rm $KAFKAF

unset KAFKA
unset KAFKAF

# Format storage for KRaft mode (first-time only — no Zookeeper needed)
KAFKA_CLUSTER_ID=$(/opt/kafka/bin/kafka-storage.sh random-uuid)
/opt/kafka/bin/kafka-storage.sh format -t $KAFKA_CLUSTER_ID -c /opt/kafka/config/kraft/server.properties


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