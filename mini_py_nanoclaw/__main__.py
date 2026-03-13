from __future__ import annotations

import asyncio

from .app import NanoClawApp


async def _noop_worker() -> None:
    return


def main() -> None:
    app = NanoClawApp()
    try:
        asyncio.run(app.start(_noop_worker))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
