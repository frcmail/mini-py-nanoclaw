from mini_py_nanoclaw.group_folder import (
    assert_valid_group_folder,
    is_valid_group_folder,
    resolve_group_folder_path,
)


def test_valid_group_folder() -> None:
    assert is_valid_group_folder("team_01")


def test_invalid_reserved_folder() -> None:
    assert not is_valid_group_folder("global")


def test_invalid_path_traversal() -> None:
    assert not is_valid_group_folder("../x")


def test_resolve_group_folder_path() -> None:
    path = resolve_group_folder_path("main")
    assert path.name == "main"


def test_assert_invalid_folder() -> None:
    try:
        assert_valid_group_folder("../oops")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
