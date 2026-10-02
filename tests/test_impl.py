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
from euleronebot.onebot.segments import (
    At,
    AtData,
    Dice,
    DiceData,
    File,
    FileData,
    GreyTips,
    GreyTipsData,
    Poke,
    PokeData,
    Rps,
    RpsData,
    Text,
    TextData,
    Video,
    VideoData,
)
from euleronebot.protocol.impl import LagrangeImpl
from euleronebot.utils import infomgr as im
from euleronebot.utils.infomgr import MsgInfo
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

    async def upload_friend_file(self, file, uid, file_name=None):
        self.calls.append(("upload_friend_file", uid, file_name, file.read()))

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


def test_group_message_uses_zero_rand_when_history_lookup_fails(tmp_path):
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


def test_unknown_at_segment_is_skipped_without_dropping_other_text(tmp_path):
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
            assert all(isinstance(item, elems.Text) for item in out)
        finally:
            await mgr.close()

    run(main())


def test_set_friend_add_request_delegates_approval_to_lagrange():
    async def main():
        impl = make_impl()
        rsp = await impl.set_friend_add_request(SetFriendAddRequestData(flag="u_abc", approve=True, remark=""))
        assert rsp.status == "ok"
        assert stub_client(impl).calls == [("set_friend_request", "u_abc", True)]

    run(main())


def test_adapter_cycle_reports_invalid_calls_and_queues_valid_ones():
    async def main():
        adapter = Adapter(impls=[])
        reported = []

        async def fake_report(rsp):
            reported.append(rsp.model_dump())

        adapter.report = fake_report
        task = asyncio.create_task(adapter.cycle())
        await adapter.connector.received.put('{"action": "no_such_action", "params": {}, "echo": "bad"}')
        await adapter.connector.received.put(
            '{"action": "send_private_msg", "params": {"user_id": 1, "message": []}, "echo": "ok"}'
        )
        queued = await asyncio.wait_for(adapter.api_calls.get(), timeout=2)
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

        assert isinstance(queued, SendPrivateMessage)
        assert queued.echo == "ok"
        assert reported[0]["status"] == "failed"
        assert reported[0]["retcode"] == 1404
        assert reported[0]["echo"] == "bad"

    run(main())


def test_subscriptions_cover_every_registered_api_action():
    adapter = Adapter(impls=[])
    impl = LagrangeImpl(cast(Any, adapter), cast(Any, StubLag()), cast(Any, None))
    impl.subscribe()

    assert set(impl.subscriptions) == adapter.api_actions


def test_get_message_returns_safe_sender_when_user_lookup_fails(tmp_path):
    from euleronebot.onebot.api_data import GetMsgData

    class FailClient(StubClient):
        async def get_user_info(self, uid_or_uin):
            raise AttributeError("boom")

    async def main():
        mgr = await init_mgr(tmp_path)
        try:
            impl = LagrangeImpl(cast(Any, None), cast(Any, StubLag()), cast(Any, None))
            impl.lag.client = cast(Any, FailClient())
            nid = await mgr.msgid_mgr.add(MsgInfo(scene_type="user", scene_id=1, seq=1, uin=123, uid="", text="hi"))
            rsp = await impl.get_message(GetMsgData(message_id=nid))
            assert rsp.status == "ok"
            assert (rsp.data.sender.nickname, rsp.data.sender.sex, rsp.data.sender.age) == ("", "unknown", 0)
        finally:
            await mgr.close()

    run(main())


def test_upload_file_handlers_open_local_files_and_delegate(tmp_path):
    async def main():
        mgr = await init_mgr(tmp_path)
        try:
            await mgr.uid_mgr.add("u_456", 456)
            group_path = tmp_path / "group.txt"
            private_path = tmp_path / "private.txt"
            group_path.write_text("group-data", encoding="utf-8")
            private_path.write_text("private-data", encoding="utf-8")
            impl = make_impl()

            group_rsp = await impl.upload_group_file(
                UploadGroupFileData(group_id=123, file=str(group_path), name="renamed.bin", folder="/sub")
            )
            private_rsp = await impl.upload_private_file(
                UploadPrivateFileData(user_id=456, file=str(private_path), name="private.bin")
            )

            assert group_rsp.status == private_rsp.status == "ok"
            assert stub_client(impl).calls == [
                ("upload_grp_file", 123, "/sub", "renamed.bin", b"group-data"),
                ("upload_friend_file", "u_456", "private.bin", b"private-data"),
            ]
        finally:
            await mgr.close()

    run(main())


def test_file_url_handlers_resolve_uid_and_delegate(tmp_path):
    async def main():
        mgr = await init_mgr(tmp_path)
        try:
            await mgr.uid_mgr.add("u_456", 456)
            impl = make_impl()

            group_rsp = await impl.get_group_file_url(GetGroupFileUrlData(group_id=123, file_id="fid"))
            private_rsp = await impl.get_private_file_url(
                GetPrivateFileUrlData(user_id=456, file_id="uuid", file_hash="hash")
            )

            assert group_rsp.data.url == "https://group.example/file"
            assert private_rsp.data.url == "https://friend.example/file"
            assert stub_client(impl).calls == [
                ("fetch_grp_file_url", 123, "fid"),
                ("fetch_friend_file_url", "uuid", "hash", "u_456"),
            ]
        finally:
            await mgr.close()

    run(main())


def test_group_video_is_uploaded_before_sending():
    class VideoClient:
        def __init__(self):
            self.calls = []

        async def upload_grp_video(self, file, grp_id, thumb=None):
            self.calls.append((grp_id, file.read()))
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

    async def main():
        client = VideoClient()
        out = await to_lagrange_msg(
            [Video(data=VideoData(file="base64://" + base64.b64encode(b"video").decode()))],
            lgrc=cast(Any, client),
            target=TargetInfo(target="group", id=123),
        )
        assert len(out) == 1
        assert isinstance(out[0], elems.Video)
        assert client.calls == [(123, b"video")]

    run(main())


def test_file_segments_are_received_but_not_sent_as_message_payload(tmp_path):
    async def main():
        mgr = await init_mgr(tmp_path)
        try:
            sent = await to_lagrange_msg(
                [File(data=FileData(file_name="a.txt", file_id="fid", url="https://example.com/a.txt"))],
                lgrc=cast(Any, None),
                target=TargetInfo(target="group", id=123),
            )
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
            received = await to_onebot_msg(
                adp=cast(Any, None),
                msg=MsgInfo(scene_type="group", scene_id=1, seq=1, raw_msg=raw),
            )
            assert sent == []
            assert isinstance(received[0], File)
            assert received[0].data.model_dump() == {
                "file_name": "a.txt",
                "file_hash": "",
                "file_id": "fid",
                "url": "https://example.com/a.txt",
            }
        finally:
            await mgr.close()

    run(main())


def test_special_segments_convert_in_both_directions_and_skip_invalid_values():
    async def main():
        sent = await to_lagrange_msg(
            [
                Poke(data=PokeData(id="2003", type="126")),
                Rps(data=RpsData()),
                Dice(data=DiceData()),
                GreyTips(data=GreyTipsData(text="tip")),
            ],
            lgrc=cast(Any, None),
            target=TargetInfo(target="group", id=1),
        )
        invalid = await to_lagrange_msg(
            [Poke(data=PokeData(id="bad", type="126"))],
            lgrc=cast(Any, None),
            target=TargetInfo(target="group", id=1),
        )
        received = await to_onebot_msg(
            adp=cast(Any, None),
            msg=MsgInfo(
                scene_type="group",
                scene_id=1,
                seq=1,
                raw_msg=[
                    elems.Emoji(id=359),
                    elems.Emoji(id=358),
                    elems.Emoji(id=1),
                    elems.Poke(id=2003, f7=126, f8=0),
                    elems.GreyTips(text="tip"),
                ],
            ),
        )

        assert isinstance(sent[0], elems.Poke) and (sent[0].id, sent[0].f7, sent[0].f8) == (2003, 126, 0)
        assert [isinstance(item, elems.Emoji) and item.id for item in sent[1:3]] == [359, 358]
        assert isinstance(sent[3], elems.GreyTips) and sent[3].text == "tip"
        assert invalid == []
        assert isinstance(received[0], Rps)
        assert isinstance(received[1], Dice)
        assert received[2].type == "face" and received[2].data.id == "1"
        assert isinstance(received[3], Poke) and received[3].data.model_dump() == {"id": "2003", "type": "126"}
        assert len(received) == 4

    run(main())


def test_get_status_returns_protocol_state_and_process_metrics():
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
