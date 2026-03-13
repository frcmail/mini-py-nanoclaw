import json

from nanoclaw import mount_security
from nanoclaw.types import AdditionalMount


def test_validate_additional_mounts(tmp_path, monkeypatch) -> None:
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir(parents=True, exist_ok=True)
    (allowed_root / "repo").mkdir()

    allowlist_path = tmp_path / "mount-allowlist.json"
    allowlist_path.write_text(
        json.dumps(
            {
                "allowedRoots": [
                    {"path": str(allowed_root), "allowReadWrite": True},
                ],
                "blockedPatterns": ["secret"],
                "nonMainReadOnly": True,
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(mount_security, "MOUNT_ALLOWLIST_PATH", allowlist_path)
    mount_security.load_mount_allowlist.cache_clear()

    mounts = [AdditionalMount(host_path=str(allowed_root / "repo"), container_path="repo", readonly=False)]
    validated = mount_security.validate_additional_mounts(mounts, "main", is_main=True)

    assert len(validated) == 1
    assert validated[0]["containerPath"] == "/workspace/extra/repo"
    assert validated[0]["readonly"] is False
