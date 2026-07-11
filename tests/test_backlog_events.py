import scripts.analytics as analytics
import scripts.research as research


def test_research_append_to_backlog_publishes_appended_event(tmp_path, monkeypatch):
    research.runtime.IDEAS_DIR = str(tmp_path)
    published = []
    monkeypatch.setattr(research, "publish_event", lambda event, payload: published.append((event, payload)))

    research.append_to_backlog({"ARM loans": [{"title": "Why ARMs are back", "rank": 1}]})

    assert published == [("backlog.appended", {"source": "research", "path": str(tmp_path / "backlog.md")})]


def test_research_append_to_backlog_publishes_skipped_event_on_rerun(tmp_path, monkeypatch):
    research.runtime.IDEAS_DIR = str(tmp_path)
    published = []
    monkeypatch.setattr(research, "publish_event", lambda event, payload: published.append((event, payload)))

    results = {"ARM loans": [{"title": "Why ARMs are back", "rank": 1}]}
    research.append_to_backlog(results)
    research.append_to_backlog(results)  # identical rerun

    assert [event for event, _ in published] == ["backlog.appended", "backlog.skipped_duplicate"]


def test_analytics_append_feedback_publishes_appended_event(tmp_path, monkeypatch):
    analytics.runtime.IDEAS_DIR = str(tmp_path)
    published = []
    monkeypatch.setattr(analytics, "publish_event", lambda event, payload: published.append((event, payload)))

    analytics.append_feedback_to_backlog({"top_by_views": [{"title": "Video A", "views": 5000}], "below_avg": []})

    assert published == [("backlog.appended", {"source": "analytics", "path": str(tmp_path / "backlog.md")})]


def test_analytics_append_feedback_publishes_skipped_event_on_rerun(tmp_path, monkeypatch):
    analytics.runtime.IDEAS_DIR = str(tmp_path)
    published = []
    monkeypatch.setattr(analytics, "publish_event", lambda event, payload: published.append((event, payload)))

    analysis = {"top_by_views": [{"title": "Video A", "views": 5000}], "below_avg": []}
    analytics.append_feedback_to_backlog(analysis)
    analytics.append_feedback_to_backlog(analysis)  # identical rerun

    assert [event for event, _ in published] == ["backlog.appended", "backlog.skipped_duplicate"]
