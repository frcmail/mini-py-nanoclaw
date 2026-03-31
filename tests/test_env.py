from __future__ import annotations

from nanoclaw.env import read_env_file


def test_read_env_file_basic(tmp_path) -> None:
    env = tmp_path / ".env"
    env.write_text('FOO=bar\nBAZ="qux"\nIGNORE=val\n', encoding="utf-8")
    result = read_env_file(["FOO", "BAZ"], env_path=env)
    assert result == {"FOO": "bar", "BAZ": "qux"}


def test_read_env_file_strips_quotes(tmp_path) -> None:
    env = tmp_path / ".env"
    env.write_text("A=\"hello\"\nB='world'\n", encoding="utf-8")
    result = read_env_file(["A", "B"], env_path=env)
    assert result == {"A": "hello", "B": "world"}


def test_read_env_file_comments_and_blanks(tmp_path) -> None:
    env = tmp_path / ".env"
    env.write_text("# comment\n\nKEY=value\n", encoding="utf-8")
    result = read_env_file(["KEY"], env_path=env)
    assert result == {"KEY": "value"}


def test_read_env_file_missing_file(tmp_path) -> None:
    result = read_env_file(["FOO"], env_path=tmp_path / "nonexistent")
    assert result == {}


def test_read_env_file_filters_keys(tmp_path) -> None:
    env = tmp_path / ".env"
    env.write_text("A=1\nB=2\nC=3\n", encoding="utf-8")
    result = read_env_file(["B"], env_path=env)
    assert result == {"B": "2"}
