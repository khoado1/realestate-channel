"""HyperFrames — animated video provider (Shorts)."""

import os

from scripts.providers import http
from scripts.providers.base import ProviderError, VideoProvider, VideoRequest, VideoStatus
from scripts.providers.registry import register

BASE_URL = "https://api.hyperframes.ai/v1"

# TODO(Phase 4): move render config into declarative provider config.
WIDTH = 1080
HEIGHT = 1920


@register("video", "hyperframes")
class HyperFramesProvider(VideoProvider):
    def _headers(self) -> dict:
        # Prefer a dedicated HyperFrames key; fall back to the legacy ElevenLabs
        # key that older integrations reused (see hyperframes.ai/docs for auth).
        key = os.getenv("HYPERFRAMES_API_KEY", "") or os.getenv("ELEVENLABS_API_KEY", "")
        if not key:
            raise ProviderError("HYPERFRAMES_API_KEY not set in .env")
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    def submit(self, req: VideoRequest) -> str:
        payload = {
            "title": req.title[:80],
            "script": req.script_text[:2000],
            "audio_url": "",  # HyperFrames may need hosted audio — see docs
            "dimensions": {"width": WIDTH, "height": HEIGHT},
            "style": "professional",  # professional | dynamic | minimal
            "topic": "real_estate",   # helps their visual matching
        }
        with http.call_context(provider="hyperframes", kind="video", operation="submit"):
            data = http.request_json("POST", f"{BASE_URL}/generate", headers=self._headers(), json=payload, timeout=60)
        # May legitimately be empty — the caller decides how to handle a no-id response.
        return data.get("job_id") or data.get("id", "")

    def status(self, job_id: str) -> VideoStatus:
        with http.call_context(provider="hyperframes", kind="video", operation="status"):
            data = http.request_json("GET", f"{BASE_URL}/status/{job_id}", headers=self._headers(), timeout=60)
        state = data.get("status", "")
        if state in ("completed", "done", "ready"):
            return VideoStatus("completed", video_url=data.get("video_url") or data.get("output_url", ""))
        if state in ("failed", "error"):
            return VideoStatus("failed", error=str(data.get("error", "")))
        return VideoStatus("pending")
