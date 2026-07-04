"""HeyGen — avatar video provider (long-form)."""

import os
from pathlib import Path

from scripts.providers import http
from scripts.providers.base import ProviderError, VideoProvider, VideoRequest, VideoStatus
from scripts.providers.registry import register

BASE_URL = "https://api.heygen.com"

# TODO(Phase 4): move render config into declarative provider config.
STOCK_AVATAR_ID = "Daisy-inskirt-20220818"  # professional, neutral fallback
STOCK_AVATAR_STYLE = "normal"
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
BACKGROUND_COLOR = "#f5f5f5"


@register("video", "heygen")
class HeyGenProvider(VideoProvider):
    def _key(self) -> str:
        key = os.getenv("HEYGEN_API_KEY", "")
        if not key:
            raise ProviderError("HEYGEN_API_KEY not set in .env")
        return key

    def resolve_avatar(self) -> tuple[str, str]:
        """Return (avatar_id, label): custom avatar from env, else stock fallback."""
        avatar_id = os.getenv("HEYGEN_AVATAR_ID", "")
        if avatar_id:
            return avatar_id, "custom avatar"
        return STOCK_AVATAR_ID, f"stock avatar ({STOCK_AVATAR_ID})"

    def upload_audio(self, audio_path: Path) -> str:
        headers = {"X-Api-Key": self._key(), "Content-Type": "audio/mpeg"}
        data = http.request_json(
            "POST", f"{BASE_URL}/v1/asset", headers=headers, data=audio_path.read_bytes(), timeout=120
        )
        asset_id = data.get("data", {}).get("id") or data.get("id", "")
        if not asset_id:
            raise ProviderError(f"No asset ID in HeyGen response: {data}")
        return asset_id

    def submit(self, req: VideoRequest) -> str:
        avatar_id, _ = self.resolve_avatar()
        payload = {
            "video_inputs": [
                {
                    "character": {
                        "type": "avatar",
                        "avatar_id": avatar_id,
                        "avatar_style": STOCK_AVATAR_STYLE,
                    },
                    "voice": {"type": "audio", "audio_asset_id": req.audio_asset_id},
                    "background": {"type": "color", "value": BACKGROUND_COLOR},
                }
            ],
            "dimension": {"width": VIDEO_WIDTH, "height": VIDEO_HEIGHT},
            "caption": False,
            "title": req.title[:50],
        }
        headers = {"X-Api-Key": self._key(), "Content-Type": "application/json"}
        data = http.request_json(
            "POST", f"{BASE_URL}/v2/video/generate", headers=headers, json=payload, timeout=60
        )
        job_id = data.get("data", {}).get("video_id") or data.get("video_id", "")
        if not job_id:
            raise ProviderError(f"No job ID in HeyGen response: {data}")
        return job_id

    def status(self, job_id: str) -> VideoStatus:
        headers = {"X-Api-Key": self._key(), "Content-Type": "application/json"}
        data = http.request_json(
            "GET", f"{BASE_URL}/v1/video_status.get?video_id={job_id}", headers=headers, timeout=60
        )
        d = data.get("data", {})
        state = d.get("status", "")
        if state == "completed":
            return VideoStatus("completed", video_url=d.get("video_url", ""))
        if state == "failed":
            return VideoStatus("failed", error=str(d.get("error", "")))
        return VideoStatus("pending")
