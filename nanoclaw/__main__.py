from __future__ import annotations

import asyncio
import contextlib

from .app import NanoClawApp, build_default_main_group


async def _run() -> None:
    app = NanoClawApp()
    app.load_state()

    main_jid, main_group = build_default_main_group()
    if main_jid not in app.registered_groups:
        app.register_group(main_jid, main_group)

    await app.setup_channels()
    await app.start_background_services()

    try:
        await app.run_loop()
    finally:
        await app.shutdown()


def main() -> None:
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(_run())


if __name__ == "__main__":
    main()
