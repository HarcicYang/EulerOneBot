import asyncio
from contextlib import suppress
from typing import Any, cast

from euleronebot.config import BotConfig, ForwardWebsocketConfig
from euleronebot.onebot import Adapter
from euleronebot.protocol import LagrangeProtocol
from euleronebot.utils import infomgr as im


def run(coro):
    return asyncio.run(coro)


class FakeClient:
    def __init__(self):
        self.cleared = False

    def _task_clear(self):
        self.cleared = True


class FakeLag:
    def __init__(self, exc: BaseException | None = None):
        self.client = FakeClient()
        self._exc = exc

    async def run(self):
        if self._exc is not None:
            raise self._exc


async def make_protocol(tmp_path, lag_exc: BaseException | None = None) -> LagrangeProtocol:
    cfg = BotConfig(login={"uin": 1})
    adapter = Adapter(impls=[])
    protocol = LagrangeProtocol(cfg, adapter)
    protocol.lag = cast(Any, FakeLag(lag_exc))
    await im.info_mgr.init(path=str(tmp_path / "test.db"), migrate_from=str(tmp_path / "cache.json"))
    return protocol


class TestRunCleanup:
    def test_normal_exit_cleans_tasks_and_db(self, tmp_path):
        async def main():
            protocol = await make_protocol(tmp_path)
            await protocol.run()
            assert all(t.done() for t in protocol._tasks)
            assert im.info_mgr.db is None

        run(main())

    def test_keyboard_interrupt_cleans_tasks_and_db(self, tmp_path):
        async def main():
            protocol = await make_protocol(tmp_path, lag_exc=KeyboardInterrupt())
            await protocol.run()
            assert protocol.lag.client.cleared  # type: ignore[attr-defined]
            assert all(t.done() for t in protocol._tasks)
            assert im.info_mgr.db is None

        run(main())


class TestConnectorClose:
    def test_close_stops_uvicorn_server(self, tmp_path):
        async def main():
            adapter = Adapter(impls=[ForwardWebsocketConfig(url="ws://127.0.0.1:0")])
            await adapter.setup()
            task = asyncio.create_task(adapter.connector.run())
            for _ in range(200):
                if adapter.connector._server is not None and adapter.connector._server.started:
                    break
                await asyncio.sleep(0.01)
            assert adapter.connector._server is not None and adapter.connector._server.started
            await adapter.close()
            for _ in range(200):
                if task.done():
                    break
                await asyncio.sleep(0.01)
            assert task.done()

        run(main())


class TestCycleSurvival:
    def test_cycle_survives_connector_crash(self):
        async def main():
            adapter = Adapter(impls=[ForwardWebsocketConfig(url="ws://bad")])
            await adapter.setup()
            task = asyncio.create_task(adapter.cycle())
            await asyncio.sleep(0.1)
            assert not task.done()
            assert adapter._connector_task is not None and adapter._connector_task.done()
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        run(main())
