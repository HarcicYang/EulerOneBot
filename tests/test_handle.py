import asyncio
from dataclasses import replace
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

from lagrange.client.events.friend import FriendPoke
from lagrange.client.events.group import GroupMessage, GroupReaction
from lagrange.client.message import elems

from euleronebot.config import BotConfig
from euleronebot.protocol import handle as handle_module
from euleronebot.protocol.handle import LagrangeEventHandler
from euleronebot.utils import infomgr as im


def run(coro):
    return asyncio.run(coro)


class RecordingAdapter:
    def __init__(self):
        self.events: list[dict[str, Any]] = []

    async def trigger(self, event):
        self.events.append(event.model_dump())


def make_handler(cfg: BotConfig | None = None) -> tuple[LagrangeEventHandler, RecordingAdapter]:
    adapter = RecordingAdapter()
    lag = cast(Any, SimpleNamespace(client=SimpleNamespace(uin=10001, uid="u_self")))
    protocol = cast(Any, SimpleNamespace(cfg=cfg or BotConfig(login={"uin": 10001})))
    return LagrangeEventHandler(cast(Any, adapter), lag, protocol), adapter


def test_friend_poke_reports_notice_but_ignores_self_sent_events():
    async def main():
        handler, adapter = make_handler()
        await handler.friend_poke_handler(
            cast(Any, None),
            FriendPoke(
                from_uin=20002,
                from_uid="u_friend",
                to_uin=10001,
                to_uid="u_self",
                timestamp=123,
                sender_uid="20002",
                target_uid="10001",
                sender_uin=20002,
                target_uin=10001,
            ),
        )
        await handler.friend_poke_handler(
            cast(Any, None),
            FriendPoke(
                from_uin=10001,
                from_uid="u_self",
                to_uin=20002,
                to_uid="u_friend",
                timestamp=124,
                sender_uid="10001",
                target_uid="20002",
                sender_uin=10001,
                target_uin=20002,
            ),
        )

        assert adapter.events == [
            {
                "time": 123,
                "self_id": 10001,
                "post_type": "notice",
                "notice_type": "notify",
                "sub_type": "poke",
                "target_id": 10001,
                "user_id": 20002,
            }
        ]

    run(main())


def test_reaction_handler_uses_compatibility_name_and_reuses_existing_message(monkeypatch):
    async def main():
        add = AsyncMock(return_value=999)
        fake_info_mgr = SimpleNamespace(msgid_mgr=SimpleNamespace(search=AsyncMock(return_value=321), add=add))
        monkeypatch.setattr(handle_module, "info_mgr", fake_info_mgr)
        cfg = BotConfig(
            login={"uin": 10001},
            event_compatibility={"reaction_event_type": "group_msg_emoji_like"},
        )
        handler, adapter = make_handler(cfg)

        await handler.reaction_handler(
            cast(Any, None),
            GroupReaction(
                grp_id=30001,
                uid="",
                seq=10,
                emoji_id=7,
                emoji_type=2,
                emoji_count=1,
                type=1,
                total_operations=1,
            ),
        )

        event = adapter.events[-1]
        assert event["notice_type"] == "group_msg_emoji_like"
        assert event["message_id"] == 321
        add.assert_not_awaited()

    run(main())


def test_group_message_handler_emits_rich_event_and_persists_raw_message(tmp_path):
    class Client:
        async def get_grp_member_info(self, grp_id, uid):
            return SimpleNamespace(
                body=[
                    SimpleNamespace(
                        is_owner=True,
                        is_admin=False,
                        name=SimpleNamespace(string="Card"),
                        level=SimpleNamespace(num=7),
                    )
                ]
            )

        async def get_user_info(self, uid):
            return SimpleNamespace(
                age=18,
                country="CN",
                province="SH",
                city="City",
                name="Alice",
                sex=SimpleNamespace(name="female"),
            )

    async def main():
        await im.info_mgr.init(path=str(tmp_path / "test.db"), migrate_from=str(tmp_path / "cache.json"))
        try:
            handler, adapter = make_handler()
            client = Client()
            event = GroupMessage(
                grp_id=30001,
                uid="u_friend",
                seq=7,
                time=123,
                rand=9,
                uin=20002,
                grp_name="Group",
                nickname="Alice",
                sub_id=0,
                sender_type=0,
                msg="hi",
                msg_chain=[elems.Text(text="hi")],
            )

            await handler.grp_msg_handler(cast(Any, client), event)
            await handler.grp_msg_handler(cast(Any, client), replace(event, uin=10001))
            await handler.grp_msg_handler(cast(Any, client), replace(event, msg_chain=[]))

            assert len(adapter.events) == 1
            emitted = adapter.events[0]
            assert emitted["message"] == [{"type": "text", "data": {"text": "hi"}}]
            assert emitted["group_id"] == 30001
            assert emitted["user_id"] == 20002
            assert emitted["raw_message"] == "hi"
            assert emitted["sender"]["card"] == "Card"
            assert emitted["sender"]["level"] == "7"
            assert emitted["sender"]["role"] == "owner"
            assert emitted["sender"]["sex"] == "female"
            assert emitted["sender"]["area"] == "CN SH City"

            stored = await im.info_mgr.msgid_mgr.fetch(emitted["message_id"])
            assert (stored.scene_id, stored.seq, stored.uin, stored.text) == (30001, 7, 20002, "hi")
            assert isinstance(stored.raw_msg[0], elems.Text)
        finally:
            await im.info_mgr.close()

    run(main())
