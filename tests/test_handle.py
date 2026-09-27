import asyncio
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

from lagrange.client.events.friend import FriendPoke
from lagrange.client.events.group import GroupReaction

from euleronebot.config import BotConfig
from euleronebot.protocol import handle as handle_module
from euleronebot.protocol.handle import LagrangeEventHandler


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


def test_friend_poke_handler_reports_notice():
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


def test_friend_poke_handler_ignores_self_sent_event():
    async def main():
        handler, adapter = make_handler()
        await handler.friend_poke_handler(
            cast(Any, None),
            FriendPoke(
                from_uin=10001,
                from_uid="u_self",
                to_uin=20002,
                to_uid="u_friend",
                timestamp=123,
                sender_uid="10001",
                target_uid="20002",
                sender_uin=10001,
                target_uin=20002,
            ),
        )
        assert adapter.events == []

    run(main())


def test_reaction_handler_uses_configured_notice_type(monkeypatch):
    async def main():
        fake_info_mgr = SimpleNamespace(
            msgid_mgr=SimpleNamespace(
                search=AsyncMock(return_value=0),
                add=AsyncMock(return_value=123),
            )
        )
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
        assert adapter.events[-1]["notice_type"] == "group_msg_emoji_like"

    run(main())
