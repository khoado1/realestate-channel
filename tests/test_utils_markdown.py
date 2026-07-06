from scripts.utils.markdown import append_once


def test_first_append_writes_content_and_marker(tmp_path):
    path = tmp_path / "backlog.md"
    appended = append_once(path, "## batch A\n- idea 1\n")
    assert appended is True
    text = path.read_text()
    assert "## batch A" in text
    assert "- idea 1" in text
    assert text.count("<!-- signal:") == 1


def test_identical_rerun_is_a_no_op(tmp_path):
    path = tmp_path / "backlog.md"
    content = "## batch A\n- idea 1\n"
    append_once(path, content)
    first_text = path.read_text()

    appended_again = append_once(path, content)

    assert appended_again is False
    assert path.read_text() == first_text  # nothing was written a second time


def test_different_content_still_appends(tmp_path):
    path = tmp_path / "backlog.md"
    append_once(path, "## batch A\n- idea 1\n")
    appended = append_once(path, "## batch B\n- idea 2\n")

    assert appended is True
    text = path.read_text()
    assert "batch A" in text and "batch B" in text
    assert text.count("<!-- signal:") == 2


def test_creates_parent_directory_if_missing(tmp_path):
    path = tmp_path / "nested" / "dir" / "backlog.md"
    appended = append_once(path, "content\n")
    assert appended is True
    assert path.exists()


def test_adds_trailing_newline_before_marker_if_missing(tmp_path):
    path = tmp_path / "backlog.md"
    append_once(path, "no trailing newline")
    text = path.read_text()
    assert "no trailing newline\n<!-- signal:" in text
