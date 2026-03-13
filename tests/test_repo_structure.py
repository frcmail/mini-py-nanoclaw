from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATHS = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "README_zh.md",
    REPO_ROOT / "CLAUDE.md",
    REPO_ROOT / "CONTRIBUTING.md",
    REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md",
]


def test_no_legacy_tests_py_references() -> None:
    for path in DOC_PATHS:
        text = path.read_text(encoding="utf-8")
        assert "tests_py" not in text, f"legacy tests_py reference found in {path}"


def test_no_repo_root_group_runtime_path_references() -> None:
    disallowed = (
        "`groups/{name}/CLAUDE.md`",
        "groups/main/CLAUDE.md",
        "groups/global/CLAUDE.md",
    )
    for path in DOC_PATHS:
        text = path.read_text(encoding="utf-8")
        for item in disallowed:
            assert item not in text, f"legacy group runtime path '{item}' found in {path}"
