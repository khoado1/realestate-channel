"""Parse JSON out of an LLM text response that may be wrapped in markdown fences."""

import json


def parse_json_response(raw: str):
    """Strip accidental markdown code fences and parse the remaining JSON.

    Raises ``json.JSONDecodeError`` on malformed input — callers choose their
    own failure UX (placeholder value, logged warning, etc.), matching the
    provider-boundary convention of raising and staying silent.
    """
    clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    return json.loads(clean)
