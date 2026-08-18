import asyncio
import base64
from contextlib import suppress
from types import SimpleNamespace
from typing import Any, cast

from lagrange.client.message import elems

from euleronebot.onebot import Adapter
from euleronebot.onebot.api import SendPrivateMessage
from euleronebot.onebot.api_data import (
    GetGroupFileUrlData,
    GetPrivateFileUrlData,
    GetStatusData,
    SendGroupMsgData,
    SetFriendAddRequestData,
    UploadGroupFileData,
    UploadPrivateFileData,
)
from euleronebot.onebot.models import BotStatus, TargetInfo
from euleronebot.onebot.segments import At, AtData, File, FileData, Text, TextData, Video, VideoData
from euleronebot.protocol.impl import LagrangeImpl
from euleronebot.utils import infomgr as im
from euleronebot.utils.transformer import to_lagrange_msg, to_onebot_msg


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

    @staticmethod
    async def get_grp_msg(**kw):
        return []

    async def set_friend_request(self, target_uid, accept):
        self.calls.append(("set_friend_request", target_uid, accept))

    async def upload_grp_file(self, file, grp_id, target_directory="/", file_name=None):
        self.calls.append(("upload_grp_file", grp_id, target_directory, file_name, file.read()))
        return None

    async def upload_friend_file(self, file, uid, file_name=None):
        self.calls.append(("upload_friend_file", uid, file_name, file.read()))
        return None

    async def fetch_grp_file_url(self, grp_id, file_id):
        self.calls.append(("fetch_grp_file_url", grp_id, file_id))
        return "https://group.example/file"

    async def fetch_friend_file_url(self, file_uuid, file_hash, uid):
        self.calls.append(("fetch_friend_file_url", file_uuid, file_hash, uid))
        return "https://friend.example/file"


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
            assert results[0]["retcode"] == 1404
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
        assert len(impl.subscriptions) == 34


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


class TestFileUploadHandlers:
    def test_upload_group_file(self, tmp_path):
        async def main():
            mgr = await init_mgr(tmp_path)
            try:
                path = tmp_path / "data.txt"
                path.write_text("hello", encoding="utf-8")
                impl = make_impl()
                rsp = await impl.upload_group_file(
                    UploadGroupFileData(group_id=123, file=str(path), name="renamed.bin", folder="/sub")
                )
                assert rsp.status == "ok"
                assert stub_client(impl).calls == [
                    ("upload_grp_file", 123, "/sub", "renamed.bin", b"hello"),
                ]
            finally:
                await mgr.close()

        run(main())

    def test_upload_private_file(self, tmp_path):
        async def main():
            mgr = await init_mgr(tmp_path)
            try:
                await mgr.uid_mgr.add("u_456", 456)
                path = tmp_path / "private.txt"
                path.write_text("world", encoding="utf-8")
                impl = make_impl()
                rsp = await impl.upload_private_file(UploadPrivateFileData(user_id=456, file=str(path), name="p.bin"))
                assert rsp.status == "ok"
                assert stub_client(impl).calls == [
                    ("upload_friend_file", "u_456", "p.bin", b"world"),
                ]
            finally:
                await mgr.close()

        run(main())

    def test_get_group_file_url(self):
        async def main():
            impl = make_impl()
            rsp = await impl.get_group_file_url(GetGroupFileUrlData(group_id=123, file_id="fid"))
            assert rsp.status == "ok"
            assert rsp.data.url == "https://group.example/file"
            assert stub_client(impl).calls == [("fetch_grp_file_url", 123, "fid")]

        run(main())

    def test_get_private_file_url(self, tmp_path):
        async def main():
            mgr = await init_mgr(tmp_path)
            try:
                await mgr.uid_mgr.add("u_456", 456)
                impl = make_impl()
                rsp = await impl.get_private_file_url(
                    GetPrivateFileUrlData(user_id=456, file_id="uuid", file_hash="hash")
                )
                assert rsp.status == "ok"
                assert rsp.data.url == "https://friend.example/file"
                assert stub_client(impl).calls == [("fetch_friend_file_url", "uuid", "hash", "u_456")]
            finally:
                await mgr.close()

        run(main())


class TestVideoAndFileSegments:
    class VideoClient:
        def __init__(self):
            self.calls = []

        async def upload_grp_video(self, file, grp_id, thumb=None):
            self.calls.append(("grp", grp_id, file.read()))
            return elems.Video(
                name="v.mp4",
                size=1,
                url="",
                id=0,
                md5=b"\x00" * 16,
                qmsg=None,
                width=1,
                height=1,
                time=1,
                file_key="",
            )

        async def upload_friend_video(self, file, uid, thumb=None):
            self.calls.append(("friend", uid, file.read()))
            return "uploaded-video"

    def test_send_group_video(self):
        async def main():
            client = self.VideoClient()
            out = await to_lagrange_msg(
                [Video(data=VideoData(file="base64://" + base64.b64encode(b"video").decode()))],
                lgrc=cast(Any, client),
                target=TargetInfo(target="group", id=123),
            )
            assert len(out) == 1
            assert isinstance(out[0], elems.Video)
            assert client.calls == [("grp", 123, b"video")]

        run(main())

    def test_file_segment_is_not_sent_via_message(self):
        async def main():
            out = await to_lagrange_msg(
                [File(data=FileData(file_name="a.txt", file_id="fid", url="https://example.com/a.txt"))],
                lgrc=cast(Any, None),
                target=TargetInfo(target="group", id=123),
            )
            assert out == []

        run(main())

    def test_incoming_file_converts_to_file_segment(self, tmp_path):
        from euleronebot.utils.infomgr import MsgInfo

        async def main():
            mgr = await init_mgr(tmp_path)
            try:
                raw = [
                    elems.File(
                        file_size=3,
                        file_name="a.txt",
                        file_md5=b"\x00" * 16,
                        file_url="https://example.com/a.txt",
                        file_id="fid",
                        file_uuid=None,
                        file_hash=None,
                    )
                ]
                out = await to_onebot_msg(
                    adp=cast(Any, None),
                    msg=MsgInfo(scene_type="group", scene_id=1, seq=1, raw_msg=raw),
                )
                assert len(out) == 1
                assert isinstance(out[0], File)
                assert out[0].data.file_name == "a.txt"
                assert out[0].data.file_id == "fid"
                assert out[0].data.url == "https://example.com/a.txt"
            finally:
                await mgr.close()

        run(main())


class TestGetStatus:
    def test_returns_protocol_status_and_standard_fields(self):
        async def main():
            protocol = SimpleNamespace(status=BotStatus(online=False, good=True))
            impl = LagrangeImpl(cast(Any, None), cast(Any, StubLag()), cast(Any, protocol))
            rsp = await impl.get_status(GetStatusData())
            assert rsp.status == "ok"
            assert rsp.data.app_initialized is True
            assert rsp.data.app_enabled is True
            assert rsp.data.plugins_good is None
            assert rsp.data.app_good is True
            assert rsp.data.online is False
            assert rsp.data.good is True
            assert rsp.data.memory >= 0

        run(main())
