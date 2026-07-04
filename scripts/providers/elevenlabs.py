"""ElevenLabs — audio (text-to-speech) provider."""

import os
from pathlib import Path

from scripts.providers import http
from scripts.providers.base import AudioProvider, ProviderError
from scripts.providers.registry import register

BASE_URL = "https://api.elevenlabs.io/v1"

# TODO(Phase 4): move the model id + voice settings into declarative provider config.
MODEL = "eleven_multilingual_v2"  # best quality
VOICE_SETTINGS = {
    "stability":         0.45,   # lower = more expressive, higher = more consistent
    "similarity_boost":  0.82,   # how closely to match the voice
    "style":             0.35,   # speaking style exaggeration
    "use_speaker_boost": True,   # enhances voice clarity
}


@register("audio", "elevenlabs")
class ElevenLabsProvider(AudioProvider):
    def _headers(self, extra: dict | None = None) -> dict:
        key = os.getenv("ELEVENLABS_API_KEY", "")
        if not key:
            raise ProviderError("ELEVENLABS_API_KEY not set in .env")
        return {"xi-api-key": key, **(extra or {})}

    def synthesize(self, text: str, voice_id: str, out_path: Path, *, timeout: int = 120) -> int:
        headers = self._headers({"Content-Type": "application/json", "Accept": "audio/mpeg"})
        payload = {"text": text, "model_id": MODEL, "voice_settings": VOICE_SETTINGS}
        return http.stream_to_file(
            "POST",
            f"{BASE_URL}/text-to-speech/{voice_id}",
            out_path,
            headers=headers,
            json=payload,
            timeout=timeout,
        )

    def list_voices(self) -> list[dict]:
        data = http.request_json("GET", f"{BASE_URL}/voices", headers=self._headers(), timeout=15)
        return data.get("voices", [])

    def usage(self) -> dict:
        data = http.request_json(
            "GET", f"{BASE_URL}/user/subscription", headers=self._headers(), timeout=10
        )
        used = data.get("character_count", 0)
        limit = data.get("character_limit", 0)
        return {
            "used": used,
            "limit": limit,
            "remaining": limit - used,
            "pct_used": round(used / limit * 100, 1) if limit > 0 else 0,
        }
