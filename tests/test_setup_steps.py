from pathlib import Path

from nanoclaw.setup import container, groups, mounts, register, verify


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
