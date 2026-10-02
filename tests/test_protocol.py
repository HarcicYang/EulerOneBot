import asyncio
from contextlib import suppress
from typing import Any, cast

import pytest

from euleronebot.config import BotConfig, ForwardWebsocketConfig
from euleronebot.onebot import Adapter
from euleronebot.protocol import LagrangeProtocol
from euleronebot.utils import infomgr as im

PROVIDER_SOURCE = "\n".join(
    [
        "def make_sign_provider(sign_url, uin, guid, qua):",
        "    async def get_sign(cmd, seq, buf):",
        '        return {"sign": "ab" * 32, "token": "", "extra": "cd" * 8}',
        "",
        "    return get_sign",
    ]
)


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
    protocol = LagrangeProtocol(BotConfig(login={"uin": 1}), Adapter(impls=[]))
    protocol.lag = cast(Any, FakeLag(lag_exc))
    await im.info_mgr.init(path=str(tmp_path / "test.db"), migrate_from=str(tmp_path / "cache.json"))
    return protocol


@pytest.mark.parametrize("lag_exc", [None, KeyboardInterrupt])
def test_protocol_run_cleans_tasks_database_and_client_on_exit(tmp_path, lag_exc):
    async def main():
        exc = None if lag_exc is None else lag_exc()
        protocol = await make_protocol(tmp_path, lag_exc=exc)
        await protocol.run()

        assert all(task.done() for task in protocol._tasks)
        assert im.info_mgr.db is None
        if lag_exc is not None:
            assert cast(Any, protocol.lag.client).cleared is True

    run(main())


def test_connector_close_stops_uvicorn_server():
    async def main():
        adapter = Adapter(impls=[ForwardWebsocketConfig(url="ws://127.0.0.1:0")])
        await adapter.setup()
        task = asyncio.create_task(adapter.connector.run())
        for _ in range(200):
            if adapter.connector._servers and adapter.connector._servers[0].started:
                break
            await asyncio.sleep(0.01)
        assert adapter.connector._servers and adapter.connector._servers[0].started

        await adapter.close()
        for _ in range(200):
            if task.done():
                break
            await asyncio.sleep(0.01)
        assert task.done()

    run(main())


def test_adapter_cycle_survives_connector_crash():
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


def test_lifecycle_events_disable_once_and_mark_connections_online():
    class RecordingAdapter:
        def __init__(self):
            self.calls = []

        async def trigger(self, event):
            self.calls.append((event.meta_event_type, event.sub_type, event.self_id))

    async def main():
        adapter = RecordingAdapter()
        protocol = LagrangeProtocol(BotConfig(login={"uin": 123}), cast(Any, adapter))
        assert protocol.status.online is False

        await protocol.emit_lifecycle("disable")
        await protocol.emit_lifecycle("disable")
        await protocol.emit_lifecycle("connect")

        assert adapter.calls == [("lifecycle", "disable", 123), ("lifecycle", "connect", 123)]
        assert protocol.status.online is True

    run(main())


def test_default_signer_url_embeds_token_and_uses_hiroqq_signer():
    cfg = BotConfig(login={"uin": 123, "signer_url": "https://sign.example.com", "signer_token": "tok"})
    protocol = LagrangeProtocol(cfg, Adapter(impls=[]))

    assert protocol.lag._custom_sign_provider is None
    assert protocol.lag._sign_url == "https://tok@sign.example.com/api/sign/sec-sign"


def test_custom_sign_provider_is_loaded_and_reused_when_lagrange_is_rebuilt(tmp_path):
    path = tmp_path / "provider.py"
    path.write_text(PROVIDER_SOURCE, encoding="utf-8")
    cfg = BotConfig(
        login={
            "uin": 123,
            "use_custom_sign_provider": True,
            "sign_provider_path": str(path),
            "sign_provider_entry": "make_sign_provider",
        }
    )
    protocol = LagrangeProtocol(cfg, Adapter(impls=[]))
    factory = cast(Any, protocol.lag._custom_sign_provider)
    assert callable(factory)

    get_sign = factory(protocol.lag._sign_url, 123, "00" * 16, "V1_LNX_NQ_3.2.26_46494_GW_B")
    assert asyncio.run(get_sign("MessageSvc.PbSendMsg", 1, b"\x00")) == {
        "sign": "ab" * 32,
        "token": "",
        "extra": "cd" * 8,
    }

    rebuilt = protocol._build_lagrange()
    assert rebuilt._custom_sign_provider is factory
    assert rebuilt.use_ipv6 is protocol.cfg.login.use_ipv6
