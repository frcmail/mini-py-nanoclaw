from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATHS = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "README_zh.md",
    REPO_ROOT / "CLAUDE.md",
    REPO_ROOT / "CONTRIBUTING.md",
    REPO_ROOT / ".github" / "CODEOWNERS",
    REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md",
    REPO_ROOT / ".github" / "workflows" / "ci.yml",
]
DOC_PATHS.extend(sorted((REPO_ROOT / ".claude" / "skills").glob("*/SKILL.md")))


def test_no_legacy_tests_py_references() -> None:
    for path in DOC_PATHS:
        text = path.read_text(encoding="utf-8")
        assert "tests_py" not in text, f"legacy tests_py reference found in {path}"


def test_no_legacy_module_name_references_in_docs() -> None:
    for path in DOC_PATHS:
        text = path.read_text(encoding="utf-8")
        assert "mini_py_nanoclaw" not in text, f"legacy module name found in {path}"


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
