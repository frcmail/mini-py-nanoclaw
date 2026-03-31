import asyncio

import pytest

from nanoclaw.group_queue import GroupQueue


@pytest.mark.asyncio
async def test_group_queue_single_group_serial_execution() -> None:
    queue = GroupQueue(max_concurrent_containers=2)
    in_flight = 0
    max_in_flight = 0

    async def process(_jid: str) -> bool:
        nonlocal in_flight, max_in_flight
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.05)
        in_flight -= 1
        return True

    queue.set_process_messages_fn(process)
    queue.enqueue_message_check("g1")
    queue.enqueue_message_check("g1")
    await asyncio.sleep(0.2)

    assert max_in_flight == 1


@pytest.mark.asyncio
async def test_group_queue_retries() -> None:
    queue = GroupQueue(max_concurrent_containers=1, base_retry_ms=10)
    calls = 0

    async def process(_jid: str) -> bool:
        nonlocal calls
        calls += 1
        return calls > 1

    queue.set_process_messages_fn(process)
    queue.enqueue_message_check("g1")
    await asyncio.sleep(0.08)

    assert calls >= 2


@pytest.mark.asyncio
async def test_group_queue_shutdown_cancels_pending_retry() -> None:
    queue = GroupQueue(max_concurrent_containers=1, base_retry_ms=50)
    calls = 0

    async def process(_jid: str) -> bool:
        nonlocal calls
        calls += 1
        return False

    queue.set_process_messages_fn(process)
    queue.enqueue_message_check("g1")
    await asyncio.sleep(0.02)

    calls_before_shutdown = calls
    await queue.shutdown()
    await asyncio.sleep(0.08)

    assert calls_before_shutdown >= 1
    assert calls == calls_before_shutdown
