from __future__ import annotations

import json
import re
import sys

OUTPUT_START_MARKER = "---NANOCLAW_OUTPUT_START---"
OUTPUT_END_MARKER = "---NANOCLAW_OUTPUT_END---"


def _strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text).strip()


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        result = {"status": "error", "result": None, "error": "invalid input"}
    else:
        prompt = str(payload.get("prompt") or "")
        reply = _strip_tags(prompt)
        if not reply:
            reply = "OK"
        result = {
            "status": "success",
            "result": f"Echo: {reply[:400]}",
        }

    sys.stdout.write(OUTPUT_START_MARKER + "\n")
    sys.stdout.write(json.dumps(result, ensure_ascii=True) + "\n")
    sys.stdout.write(OUTPUT_END_MARKER + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
