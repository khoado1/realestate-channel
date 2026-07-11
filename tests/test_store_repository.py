import pytest

from scripts.store.repository import SQLiteCallRepository


def make_call_row(**overrides) -> dict:
    row = {
        "ts": "2026-07-05T12:00:00",
        "provider": "claude",
        "kind": "ai",
        "operation": "research",
        "model": "claude-sonnet-4-20250514",
        "method": "POST",
        "url": "https://api.anthropic.com/v1/messages",
        "request_json": "{}",
        "response_json": "{}",
        "http_status": 200,
        "status": "ok",
        "error": None,
        "latency_ms": 250,
        "input_units": 100,
        "output_units": 50,
        "unit_kind": "tokens",
        "cost_usd": 0.01,
        "cost_estimated": 0,
    }
    row.update(overrides)
    return row


@pytest.fixture
def repo(tmp_path):
    return SQLiteCallRepository(tmp_path / "calls.db")


def test_insert_call_returns_incrementing_ids(repo):
    id1 = repo.insert_call(make_call_row())
    id2 = repo.insert_call(make_call_row())
    assert id2 == id1 + 1


def test_get_call_returns_the_inserted_row(repo):
    call_id = repo.insert_call(make_call_row(operation="analytics"))
    row = repo.get_call(call_id)
    assert row is not None
    assert row["operation"] == "analytics"
    assert row["status"] == "ok"


def test_get_call_returns_none_for_missing_id(repo):
    assert repo.get_call(999) is None


def test_list_calls_orders_newest_first_and_respects_limit(repo):
    ids = [repo.insert_call(make_call_row(operation=f"op{i}")) for i in range(5)]

    rows = repo.list_calls(limit=3)

    assert [r["id"] for r in rows] == list(reversed(ids))[:3]


def test_insert_artifact_links_to_its_call(repo):
    call_id = repo.insert_call(make_call_row())
    repo.insert_artifact(
        {
            "call_id": call_id,
            "direction": "out",
            "kind": "audio",
            "path": "/tmp/out.mp3",
            "bytes": 12345,
            "sha256": "deadbeef",
            "mime": "audio/mpeg",
        }
    )
    row = repo._conn.execute(
        "SELECT * FROM artifacts WHERE call_id = ?", (call_id,)
    ).fetchone()
    assert row is not None
    assert row["path"] == "/tmp/out.mp3"
