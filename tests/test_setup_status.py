from nanoclaw.setup.status import emit_status


def test_emit_status_normal(capsys) -> None:
    emit_status("TEST_STEP", {"key1": "val1", "key2": 42})
    out = capsys.readouterr().out
    assert "=== NANOCLAW SETUP: TEST_STEP ===" in out
    assert "key1: val1" in out
    assert "key2: 42" in out
    assert "=== END ===" in out


def test_emit_status_empty_fields(capsys) -> None:
    emit_status("EMPTY", {})
    out = capsys.readouterr().out
    assert "=== NANOCLAW SETUP: EMPTY ===" in out
    assert "=== END ===" in out
    # Only header and footer, no key-value lines between
    lines = [line for line in out.strip().splitlines() if line.strip()]
    assert len(lines) == 2
