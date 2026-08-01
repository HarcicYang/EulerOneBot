import asyncio
from contextlib import suppress
from typing import Any, cast

from lagrange.client.message import elems

from euleronebot.onebot import Adapter
from euleronebot.onebot.api import SendPrivateMessage
from euleronebot.onebot.api_data import SendGroupMsgData, SetFriendAddRequestData
from euleronebot.onebot.models import TargetInfo
from euleronebot.onebot.segments import At, AtData, Text, TextData
from euleronebot.protocol.impl import LagrangeImpl
from euleronebot.utils import infomgr as im
from euleronebot.utils.transformer import to_lagrange_msg


def run(coro):
    return asyncio.run(coro)


async def init_mgr(tmp_path):
    await im.info_mgr.init(path=str(tmp_path / "test.db"), migrate_from=str(tmp_path / "cache.json"))
    return im.info_mgr


class StubClient:
    def __init__(self):
        self.uid = "u_bot"
        self.uin = 1
        self.calls = []

    async def send_grp_msg(self, grp_id, msg_chain):
        self.calls.append(("send_grp_msg", grp_id))
        return 42

    async def get_grp_msg(self, **kw):
        return []

    async def set_friend_request(self, target_uid, accept):
        self.calls.append(("set_friend_request", target_uid, accept))


class StubLag:
    def __init__(self):
        self.client = StubClient()


def make_impl() -> LagrangeImpl:
    return LagrangeImpl(cast(Any, None), cast(Any, StubLag()), cast(Any, None))


def stub_client(impl: LagrangeImpl) -> StubClient:
    return cast(Any, impl.lag.client)


class TestSendGroupMessage:
    def test_rand_fetch_failure_still_reports_ok(self, tmp_path):
        async def main():
            mgr = await init_mgr(tmp_path)
            try:
                impl = make_impl()
                rsp = await impl.send_group_message(
                    SendGroupMsgData(group_id=123, message=[Text(data=TextData(text="hi"))])
                )
                assert rsp.status == "ok"
                assert rsp.data.message_id != 0
                assert stub_client(impl).calls == [("send_grp_msg", 123)]
            finally:
                await mgr.close()

        run(main())


class TestAtDegradation:
    def test_unknown_uin_at_skipped_rest_sent(self, tmp_path):
        async def main():
            mgr = await init_mgr(tmp_path)
            try:
                out = await to_lagrange_msg(
                    [
                        Text(data=TextData(text="hello")),
                        At(data=AtData(qq="999999")),
                        Text(data=TextData(text=" world")),
                    ],
                    lgrc=cast(Any, None),
                    target=TargetInfo(target="group", id=1),
                )
                assert len(out) == 2
                assert all(isinstance(o, elems.Text) for o in out)
            finally:
                await mgr.close()

        run(main())


class TestSetFriendAddRequest:
    def test_set_friend_add_request_calls_client(self):
        async def main():
            impl = make_impl()
            rsp = await impl.set_friend_add_request(SetFriendAddRequestData(flag="u_abc", approve=True, remark=""))
            assert rsp.status == "ok"
            assert stub_client(impl).calls == [("set_friend_request", "u_abc", True)]

        run(main())


class TestAdapterCycle:
    def test_invalid_call_gets_failed_response_with_echo(self):
        async def main():
            adapter = Adapter(impls=[])
            results = []

            async def fake_report(rsp):
                results.append(rsp.model_dump())

            adapter.report = fake_report
            task = asyncio.create_task(adapter.cycle())
            await adapter.connector.received.put('{"action": "no_such_action", "params": {}, "echo": "abc123"}')
            for _ in range(200):
                if results:
                    break
                await asyncio.sleep(0.01)
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            assert results
            assert results[0]["status"] == "failed"
            assert results[0]["retcode"] == 1400
            assert results[0]["echo"] == "abc123"

        run(main())

    def test_valid_call_queued(self):
        async def main():
            adapter = Adapter(impls=[])
            task = asyncio.create_task(adapter.cycle())
            await adapter.connector.received.put(
                '{"action": "send_private_msg", "params": {"user_id": 1, "message": []}, "echo": "x"}'
            )
            got = await asyncio.wait_for(adapter.api_calls.get(), timeout=2)
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            assert isinstance(got, SendPrivateMessage)
            assert got.echo == "x"

        run(main())


class TestSubscription:
    def test_subscribe_registers_impl_handlers(self):
        impl = LagrangeImpl(cast(Any, None), cast(Any, StubLag()), cast(Any, None))
        impl.subscribe()
        assert "send_group_msg" in impl.subscriptions
        assert "set_friend_add_request" in impl.subscriptions
        assert len(impl.subscriptions) == 29


class TestOnDecorator:
    def test_on_sets_ev_type(self):
        from lagrange.client.events.service import ClientOnline

        from euleronebot.protocol.handle import on

        @on(ClientOnline)
        async def handler(client, event):
            pass

        assert cast(Any, handler).ev_type is ClientOnline

    def test_on_sets_call_type(self):
        from euleronebot.onebot.api import SendGroupMessage
        from euleronebot.protocol.impl import on as impl_on

        @impl_on(SendGroupMessage)
        async def handler(data):
            pass

        assert cast(Any, handler).call_type is SendGroupMessage


class TestGetMessageFallback:
    def test_user_info_failure_returns_ok_with_safe_sender(self, tmp_path):
        from euleronebot.onebot.api_data import GetMsgData
        from euleronebot.utils.infomgr import MsgInfo

        class FailClient(StubClient):
            async def get_user_info(self, uid_or_uin):
                raise AttributeError("boom")

        async def main():
            mgr = await init_mgr(tmp_path)
            try:
                impl = LagrangeImpl(cast(Any, None), cast(Any, StubLag()), cast(Any, None))
                impl.lag = cast(Any, StubLag())
                impl.lag.client = FailClient()
                nid = await mgr.msgid_mgr.add(MsgInfo(scene_type="user", scene_id=1, seq=1, uin=123, uid="", text="hi"))
                rsp = await impl.get_message(GetMsgData(message_id=nid))
                assert rsp.status == "ok"
                assert rsp.data.sender.nickname == ""
                assert rsp.data.sender.sex == "unknown"
                assert rsp.data.sender.age == 0
            finally:
                await mgr.close()

        run(main())
