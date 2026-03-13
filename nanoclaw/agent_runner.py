from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

OUTPUT_START_MARKER = "---NANOCLAW_OUTPUT_START---"
OUTPUT_END_MARKER = "---NANOCLAW_OUTPUT_END---"
IPC_POLL_MS = 0.5
IPC_INPUT_DIR = Path("/workspace/ipc/input")
IPC_CLOSE_SENTINEL = IPC_INPUT_DIR / "_close"
ENABLE_IPC_LOOP = os.getenv("NANOCLAW_AGENT_ENABLE_IPC_LOOP", "0") == "1"


@dataclass
class ContainerInput:
    prompt: str
    sessionId: Optional[str]
    groupFolder: str
    chatJid: str
    isMain: bool
    isScheduledTask: bool = False
    assistantName: Optional[str] = None


def _write_output(payload: dict) -> None:
    sys.stdout.write(OUTPUT_START_MARKER + "\n")
    sys.stdout.write(json.dumps(payload, ensure_ascii=True) + "\n")
    sys.stdout.write(OUTPUT_END_MARKER + "\n")
    sys.stdout.flush()


def _read_input() -> ContainerInput:
    raw = sys.stdin.read()
    data = json.loads(raw)
    return ContainerInput(
        prompt=str(data.get("prompt") or ""),
        sessionId=data.get("sessionId"),
        groupFolder=str(data.get("groupFolder") or "main"),
        chatJid=str(data.get("chatJid") or "local:main"),
        isMain=bool(data.get("isMain", False)),
        isScheduledTask=bool(data.get("isScheduledTask", False)),
        assistantName=data.get("assistantName"),
    )


def _run_claude(prompt: str, session_id: Optional[str], cwd: Path) -> tuple[str, Optional[str], Optional[str]]:
    claude_bin = shutil.which("claude")
    if not claude_bin:
        return f"Echo: {prompt[:400]}", session_id, None

    cmd = [claude_bin, "-p", prompt]
    if session_id:
        cmd += ["--resume", session_id]

    try:
        proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=1800)
    except subprocess.TimeoutExpired:
        return "", session_id, "Claude CLI timed out"
    except Exception as exc:
        return "", session_id, f"Claude CLI failed: {exc}"

    if proc.returncode != 0:
        stderr = (proc.stderr or "")[-500:]
        return "", session_id, f"Claude CLI exited with code {proc.returncode}: {stderr}"

    result = (proc.stdout or "").strip()
    if not result:
        result = ""
    return result, session_id, None


def _group_workspace() -> Path:
    path = Path("/workspace/group")
    if path.exists():
        return path
    return Path.cwd()


def _ensure_ipc_dir() -> None:
    IPC_INPUT_DIR.mkdir(parents=True, exist_ok=True)


def _should_close() -> bool:
    if IPC_CLOSE_SENTINEL.exists():
        IPC_CLOSE_SENTINEL.unlink(missing_ok=True)
        return True
    return False


def _drain_ipc_inputs() -> list[str]:
    _ensure_ipc_dir()
    messages: list[str] = []
    for file_path in sorted(IPC_INPUT_DIR.glob("*.json")):
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            if data.get("type") == "message" and isinstance(data.get("text"), str):
                messages.append(data["text"])
        except json.JSONDecodeError:
            pass
        finally:
            file_path.unlink(missing_ok=True)
    return messages


def main() -> int:
    try:
        input_data = _read_input()
    except Exception as exc:
        _write_output({"status": "error", "result": None, "error": f"Invalid input: {exc}"})
        return 1

    workspace = _group_workspace()
    session_id = input_data.sessionId

    result, session_id, err = _run_claude(input_data.prompt, session_id, workspace)
    if err:
        _write_output({"status": "error", "result": None, "error": err})
        return 0

    _write_output(
        {
            "status": "success",
            "result": result,
            "newSessionId": session_id,
        }
    )

    if not ENABLE_IPC_LOOP:
        return 0

    # Keep consuming follow-up IPC input until close sentinel is received.
    while True:
        if _should_close():
            break

        messages = _drain_ipc_inputs()
        if not messages:
            time.sleep(IPC_POLL_MS)
            continue

        follow_up = "\n".join(messages)
        result, session_id, err = _run_claude(follow_up, session_id, workspace)
        if err:
            _write_output({"status": "error", "result": None, "error": err})
            continue

        _write_output(
            {
                "status": "success",
                "result": result,
                "newSessionId": session_id,
            }
        )

    # Final success marker keeps host logic aligned with streaming behavior.
    _write_output({"status": "success", "result": None, "newSessionId": session_id})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
