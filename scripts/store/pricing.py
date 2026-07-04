"""Usage extraction + cost estimation for recorded calls.

Costs are ESTIMATES computed from the rate table in ``scripts/config/pricing.toml``
— not billed amounts — so ``cost_estimated`` is always set. Video credits have no
public per-call price, so those are recorded with usage/cost unknown and flagged.
"""

from scripts.utils.config import load


def estimate(entry: dict) -> dict:
    """Return {input_units, output_units, unit_kind, cost_usd, estimated} for a call."""
    rates = load("pricing")
    provider = entry.get("provider")
    model = entry.get("model")
    operation = entry.get("operation")
    request = entry.get("request") or {}
    response = entry.get("response") or {}

    if provider == "claude":
        usage = (response or {}).get("usage") or {}
        in_u = usage.get("input_tokens", 0)
        out_u = usage.get("output_tokens", 0)
        rate = rates.get("claude", {}).get(model)
        cost = None
        if rate and (in_u or out_u):
            cost = round(in_u / 1e6 * rate["in_per_m"] + out_u / 1e6 * rate["out_per_m"], 6)
        return {
            "input_units": in_u,
            "output_units": out_u,
            "unit_kind": "tokens",
            "cost_usd": cost,
            "estimated": True,  # rates are placeholders
        }

    if provider == "elevenlabs" and operation == "synthesize":
        chars = len((request or {}).get("text", "") or "")
        rate = rates.get("elevenlabs")
        cost = round(chars / 1000 * rate["per_k_chars"], 6) if rate and chars else None
        return {
            "input_units": chars,
            "output_units": 0,
            "unit_kind": "chars",
            "cost_usd": cost,
            "estimated": True,
        }

    # Video credits and metadata calls (list/usage/status): usage/cost unknown.
    return {"input_units": 0, "output_units": 0, "unit_kind": None, "cost_usd": None, "estimated": True}
