import io
import json
import sys

from nanoclaw.constants import OUTPUT_END_MARKER, OUTPUT_START_MARKER
from nanoclaw.simple_agent import _strip_tags, main


def _run_main(input_str: str) -> str:
    old_stdin = sys.stdin
    old_stdout = sys.stdout
    try:
        sys.stdin = io.StringIO(input_str)
        buf = io.StringIO()
        sys.stdout = buf
        code = main()
        assert code == 0
        return buf.getvalue()
    finally:
        sys.stdin = old_stdin
        sys.stdout = old_stdout


def _parse_output(raw: str) -> dict:
    start = raw.index(OUTPUT_START_MARKER)
    end = raw.index(OUTPUT_END_MARKER)
    body = raw[start + len(OUTPUT_START_MARKER) : end].strip()
    return json.loads(body)


def test_main_valid_prompt_echo() -> None:
    out = _run_main(json.dumps({"prompt": "hello world"}))
    result = _parse_output(out)
    assert result["status"] == "success"
    assert "Echo:" in result["result"]
    assert "hello world" in result["result"]


def test_main_missing_prompt_returns_ok() -> None:
    out = _run_main(json.dumps({"other": "field"}))
    result = _parse_output(out)
    assert result["status"] == "success"
    assert result["result"] == "Echo: OK"


def test_main_empty_prompt_returns_ok() -> None:
    out = _run_main(json.dumps({"prompt": ""}))
    result = _parse_output(out)
    assert result["status"] == "success"
    assert result["result"] == "Echo: OK"


def test_main_invalid_json_returns_error() -> None:
    out = _run_main("not valid json {{")
    result = _parse_output(out)
    assert result["status"] == "error"
    assert result["error"] == "invalid input"
    assert result["result"] is None


def test_main_long_prompt_truncated() -> None:
    long_text = "x" * 500
    out = _run_main(json.dumps({"prompt": long_text}))
    result = _parse_output(out)
    assert result["status"] == "success"
    assert len(result["result"]) <= 406 + len("Echo: ")  # 400 chars + "Echo: "


def test_main_output_markers() -> None:
    out = _run_main(json.dumps({"prompt": "hi"}))
    assert OUTPUT_START_MARKER in out
    assert OUTPUT_END_MARKER in out


def test_strip_tags_removes_html() -> None:
    assert _strip_tags("<b>bold</b>") == "bold"
    assert _strip_tags("no tags") == "no tags"
    assert _strip_tags("<a href='x'>link</a> text") == "link  text"


def test_strip_tags_nested() -> None:
    assert _strip_tags("<div><span>hi</span></div>") == "hi"
