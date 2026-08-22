import asyncio
from contextlib import suppress
from typing import cast
from unittest.mock import AsyncMock

from lagrange.client.base import BaseClient

from euleronebot.extensions.patch import apply_patches


def test_heartbeat_survives_non_timeout_error(monkeypatch):
    async def main():
        apply_patches()
        monkeypatch.setattr(
            BaseClient,
            "sso_heartbeat",
            AsyncMock(side_effect=AssertionError(1001, "unexpected")),
        )

        class StubClient:
            online = asyncio.Event()
            _heartbeat_interval = 0.01
            destroy_calls = 0

            def destroy_network(self):
                self.destroy_calls += 1

        stub = StubClient()
        task = asyncio.create_task(BaseClient._heartbeat_task(cast(BaseClient, stub)))
        stub.online.set()
        for _ in range(200):
            if stub.destroy_calls == 1:
                break
            await asyncio.sleep(0.01)
        else:
            raise AssertionError("heartbeat did not trigger recovery")

        assert not task.done()
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    asyncio.run(main())
