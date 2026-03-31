from nanoclaw.setup.service import run


def test_service_run_emits_status(capsys) -> None:
    run([])
    out = capsys.readouterr().out
    assert "=== NANOCLAW SETUP: SERVICE ===" in out
    assert "MODE: manual" in out
    assert "STATUS: success" in out
    assert "=== END ===" in out
