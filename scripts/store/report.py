"""Show recently recorded provider calls: python -m scripts.store.report [N]"""

import sys

from scripts.store.repository import get_repository


def run(limit: int = 20) -> int:
    rows = get_repository().list_calls(limit)
    if not rows:
        print("No calls recorded yet.")
        return 0

    total = sum(r["cost_usd"] or 0 for r in rows)
    print(f"{'id':>4}  {'when':<19}  {'provider/op':<26}  {'status':<6}  {'units':>13}  {'cost($)':>9}  {'ms':>6}")
    print("-" * 100)
    for r in rows:
        units = f"{r['input_units'] or 0}/{r['output_units'] or 0} {r['unit_kind'] or ''}".strip()
        cost = f"~{r['cost_usd']:.4f}" if r["cost_usd"] is not None else "—"
        print(
            f"{r['id']:>4}  {r['ts']:<19}  {r['provider'] or '?'}/{r['operation'] or '?':<20.20}  "
            f"{r['status']:<6}  {units:>13}  {cost:>9}  {r['latency_ms'] or 0:>6}"
        )
    print("-" * 100)
    print(f"Σ estimated cost (last {len(rows)}): ~${total:.4f}  (costs are estimates — see store/pricing.py)")
    return 0


def main() -> int:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    return run(limit)


if __name__ == "__main__":
    raise SystemExit(main())
