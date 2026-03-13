from __future__ import annotations

import argparse

from ..logger import logger
from . import container, environment, groups, mounts, register, service, verify
from .status import emit_status

STEPS = {
    "environment": environment.run,
    "container": container.run,
    "groups": groups.run,
    "register": register.run,
    "mounts": mounts.run,
    "service": service.run,
    "verify": verify.run,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="NanoClaw setup runner")
    parser.add_argument("--step", required=True, choices=sorted(STEPS.keys()))
    parser.add_argument("args", nargs="*")
    ns = parser.parse_args()

    step_fn = STEPS[ns.step]
    try:
        step_fn(ns.args)
    except Exception as exc:
        logger.error("setup step failed step=%s error=%s", ns.step, exc)
        emit_status(ns.step.upper(), {"STATUS": "failed", "ERROR": str(exc)})
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
