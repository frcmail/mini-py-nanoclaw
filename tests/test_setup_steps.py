from pathlib import Path

import pytest

from nanoclaw.setup import container, environment, groups, mounts, register, verify


def test_setup_groups_and_register(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(groups, "GROUPS_DIR", tmp_path / "groups")
    monkeypatch.setattr(register, "DATA_DIR", tmp_path / "data")
    stored = {}

    class _FakeDB:
        def set_registered_group(self, jid, group):
            stored[jid] = group

        def close(self):
            return None

    monkeypatch.setattr(register, "NanoClawDB", _FakeDB)

    groups.run([])
    assert (tmp_path / "groups" / "main" / "CLAUDE.md").exists()
    assert (tmp_path / "groups" / "global" / "CLAUDE.md").exists()

    register.run([])
    assert (tmp_path / "data").exists()
    assert "local:main" in stored


def test_setup_mounts_and_verify(tmp_path, monkeypatch) -> None:
    allowlist = tmp_path / "config" / "mount-allowlist.json"
    monkeypatch.setattr(mounts, "MOUNT_ALLOWLIST_PATH", allowlist)
    mounts.run([])
    assert allowlist.exists()

    monkeypatch.setattr(verify, "GROUPS_DIR", tmp_path / "groups")
    monkeypatch.setattr(verify, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(verify, "DATA_DIR", tmp_path / "data")
    (tmp_path / "groups").mkdir(parents=True, exist_ok=True)
    (tmp_path / "store").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    verify.run([])


def test_setup_container_step_without_docker(monkeypatch) -> None:
    monkeypatch.setattr(container.shutil, "which", lambda _name: None)
    container.run([])


def test_setup_groups_writes_packaged_templates(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(groups, "GROUPS_DIR", tmp_path / "groups")
    groups.run([])

    template_root = Path(groups.__file__).resolve().parent.parent / "templates" / "groups"
    expected_main = (template_root / "main" / "CLAUDE.md").read_text(encoding="utf-8")
    expected_global = (template_root / "global" / "CLAUDE.md").read_text(encoding="utf-8")

    assert (tmp_path / "groups" / "main" / "CLAUDE.md").read_text(encoding="utf-8") == expected_main
    assert (tmp_path / "groups" / "global" / "CLAUDE.md").read_text(encoding="utf-8") == expected_global


def test_setup_groups_template_fallback(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(groups, "GROUPS_DIR", tmp_path / "groups")
    monkeypatch.setattr(groups, "_load_template", lambda _folder, fallback: fallback)

    groups.run([])

    assert (tmp_path / "groups" / "main" / "CLAUDE.md").read_text(encoding="utf-8") == groups.DEFAULT_MAIN
    assert (tmp_path / "groups" / "global" / "CLAUDE.md").read_text(encoding="utf-8") == groups.DEFAULT_GLOBAL


def test_setup_environment_ok(monkeypatch) -> None:
    monkeypatch.setattr("sys.version_info", (3, 12, 0))
    environment.run([])


def test_setup_environment_too_old(monkeypatch) -> None:
    monkeypatch.setattr("sys.version_info", (3, 8, 0))
    with pytest.raises(RuntimeError, match="Python 3.9"):
        environment.run([])


def test_setup_container_docker_not_running(monkeypatch) -> None:
    monkeypatch.setattr(container.shutil, "which", lambda _name: "/usr/bin/docker")
    import subprocess

    def _bad_run(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "docker info")

    monkeypatch.setattr(container.subprocess, "run", _bad_run)
    container.run([])


def test_setup_verify_missing_dir(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(verify, "GROUPS_DIR", tmp_path / "groups")
    monkeypatch.setattr(verify, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(verify, "DATA_DIR", tmp_path / "data")
    with pytest.raises(RuntimeError, match="incomplete"):
        verify.run([])


def test_setup_verify_writable(tmp_path, monkeypatch) -> None:
    for d in ("groups", "store", "data"):
        (tmp_path / d).mkdir()
    monkeypatch.setattr(verify, "GROUPS_DIR", tmp_path / "groups")
    monkeypatch.setattr(verify, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(verify, "DATA_DIR", tmp_path / "data")
    verify.run([])


def test_setup_verify_not_writable(tmp_path, monkeypatch) -> None:
    for d in ("groups", "store", "data"):
        (tmp_path / d).mkdir()
    monkeypatch.setattr(verify, "GROUPS_DIR", tmp_path / "groups")
    monkeypatch.setattr(verify, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(verify, "DATA_DIR", tmp_path / "data")

    # Make one dir read-only
    (tmp_path / "store").chmod(0o555)
    try:
        with pytest.raises(RuntimeError, match="not_writable"):
            verify.run([])
    finally:
        (tmp_path / "store").chmod(0o755)
