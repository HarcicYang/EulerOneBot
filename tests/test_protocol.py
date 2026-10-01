import asyncio
from contextlib import suppress
from typing import Any, cast

from euleronebot.config import BotConfig, ForwardWebsocketConfig
from euleronebot.onebot import Adapter
from euleronebot.protocol import LagrangeProtocol
from euleronebot.utils import infomgr as im
from euleronebot.utils import sign_provider as sign_provider_module

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


class TestLifecycle:
    class RecordingAdapter:
        def __init__(self):
            self.calls = []

        async def trigger(self, event):
            self.calls.append((event.meta_event_type, event.sub_type, event.self_id))

    def test_disable_dedup_connect_and_self_id(self):
        async def main():
            adapter = self.RecordingAdapter()
            protocol = LagrangeProtocol(BotConfig(login={"uin": 123}), cast(Any, adapter))
            assert protocol.status.online is False

            await protocol.emit_lifecycle("disable")
            await protocol.emit_lifecycle("disable")
            assert adapter.calls == [("lifecycle", "disable", 123)]

            await protocol.emit_lifecycle("connect")
            assert protocol.status.online is True
            assert adapter.calls[-1] == ("lifecycle", "connect", 123)

        run(main())


class TestSignProviderWiring:
    def _cfg(self, tmp_path):
        path = tmp_path / "provider.py"
        path.write_text(PROVIDER_SOURCE, encoding="utf-8")
        return BotConfig(
            login={
                "uin": 123,
                "use_custom_sign_provider": True,
                "sign_provider_path": str(path),
                "sign_provider_entry": "make_sign_provider",
            }
        )

    def test_default_config_signs_via_url(self):
        cfg = BotConfig(login={"uin": 123, "signer_url": "https://sign.example.com", "signer_token": "tok"})
        protocol = LagrangeProtocol(cfg, Adapter(impls=[]))
        assert protocol.lag._custom_sign_provider is None
        assert protocol.lag._sign_url == "https://tok@sign.example.com/api/sign/sec-sign"

    def test_custom_provider_is_loaded_and_wired(self, tmp_path):
        protocol = LagrangeProtocol(self._cfg(tmp_path), Adapter(impls=[]))
        factory = cast(Any, protocol.lag._custom_sign_provider)
        assert callable(factory)

        get_sign = factory(protocol.lag._sign_url, 123, "00" * 16, "V1_LNX_NQ_3.2.26_46494_GW_B")
        assert asyncio.run(get_sign("MessageSvc.PbSendMsg", 1, b"\x00")) == {
            "sign": "ab" * 32,
            "token": "",
            "extra": "cd" * 8,
        }

    def test_relog_keeps_the_same_provider(self, tmp_path):
        protocol = LagrangeProtocol(self._cfg(tmp_path), Adapter(impls=[]))
        first = protocol.lag._custom_sign_provider
        rebuilt = protocol._build_lagrange()
        assert rebuilt._custom_sign_provider is first
        assert rebuilt.use_ipv6 is protocol.cfg.login.use_ipv6
        assert sign_provider_module.load_sign_provider is not None
