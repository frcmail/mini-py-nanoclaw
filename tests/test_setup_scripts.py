import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_setup_script(script_path: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["NANOCLAW_HOME"] = str(REPO_ROOT / ".tmp-test-home")
    return subprocess.run(
        [str(script_path), "environment"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_root_setup_script_runs_environment_step() -> None:
    result = _run_setup_script(REPO_ROOT / "setup.sh")
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "=== NANOCLAW SETUP: ENVIRONMENT ===" in result.stdout
    assert "STATUS: success" in result.stdout


def test_scripts_setup_script_runs_environment_step() -> None:
    result = _run_setup_script(REPO_ROOT / "scripts" / "setup.sh")
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "=== NANOCLAW SETUP: ENVIRONMENT ===" in result.stdout
    assert "STATUS: success" in result.stdout
