import time
import traceback
from collections.abc import Callable
from typing import (
    TYPE_CHECKING,
    Any,
    Protocol,
    TypeVar,
    cast,
    runtime_checkable,
)

from lagrange import Client, Lagrange
from lagrange.client.events import BaseEvent
from lagrange.client.events.friend import (
    FriendAddNotify,
    FriendMessage,
    FriendRecall,
    FriendRequest,
)
from lagrange.client.events.group import (
    GroupAdminChange,
    GroupMemberJoined,
    GroupMemberJoinedByInvite,
    GroupMemberJoinRequest,
    GroupMemberQuit,
    GroupMessage,
    GroupMuteMember,
    GroupNudge,
    GroupReaction,
    GroupRecall,
)
from lagrange.client.events.service import ClientOffline, ClientOnline, ServerKick

from ..hyperogger import Logger
from ..onebot import Adapter as OneBotAdapter
from ..onebot import events as onebot_events
from ..utils.infomgr import MsgInfo, info_mgr
from ..utils.transformer import to_onebot_msg

if TYPE_CHECKING:
    from . import LagrangeProtocol
else:
    LagrangeProtocol = Any

__all__ = ["LagrangeEventHandler"]

logger = Logger.fetch("euler").name_custom("euler.protocol.handle")
LagrangeEvent = BaseEvent
F = TypeVar("F", bound=Callable[..., object])


@runtime_checkable
class RegisteredHandler(Protocol):
    ev_type: type[LagrangeEvent]


def on(ev_type: type[LagrangeEvent]) -> Callable[[F], F]:
    def dec(func: F) -> F:
        cast(RegisteredHandler, func).ev_type = ev_type
        return func

    return dec


class LagrangeEventHandler:
    def __init__(self, onebot_adapter: OneBotAdapter, lag: Lagrange, protocol: LagrangeProtocol):
        self.adapter = onebot_adapter
        self.lag = lag
        self.info_updated = False
        self.protocol = protocol

    @staticmethod
    def _make_safe(handler):
        """Wrap handler to prevent exceptions from silently disappearing into lagrange's _task_exec."""

        async def wrapper(client, event):
            try:
                await handler(client, event)
            except Exception:
                logger.error(f"事件处理异常: {type(event).__name__}")
                logger.trace(traceback.format_exc())

        return wrapper

    def subscribe(self) -> None:
        for i in dir(self):
            attr = getattr(self, i)  # it seems like py3.14 has a **** change
            func = getattr(attr, "__func__", attr)
            if isinstance(func, RegisteredHandler):
                self.lag.subscribe(func.ev_type, self._make_safe(attr))  # type: ignore

    @on(ClientOnline)
    async def online_handler(self, client: Client, _event: ClientOnline) -> None:
        if self.info_updated:
            return
        self.adapter.connector.self_id = client.uin
        await info_mgr.uid_mgr.load_all(client)
        self.info_updated = True

    @on(ClientOffline)
    async def offline_handler(self, _client: Client, event: ClientOffline) -> None:
        logger.warning(f"client offline! recoverable = {event.recoverable}")
        await self.protocol.set_offline(event.recoverable)

    @on(ServerKick)
    async def kick_handler(self, _client: Client, event: ServerKick) -> None:
        logger.error(f"Kicked by server: {event.title} {event.tips}")

    @on(GroupMessage)
    async def grp_msg_handler(self, client: Client, event: GroupMessage) -> None:
        if event.uin == self.lag.client.uin or len(event.msg_chain) == 0:
            return
        logger.info(f"[Group] {event.grp_name}({event.grp_id}): @{event.nickname}({event.uin}): {event.msg}")
        if not await info_mgr.uid_mgr.is_exist(event.uid):
            await info_mgr.uid_mgr.add(event.uid, event.uin)
        guser_info = (await client.get_grp_member_info(event.grp_id, event.uid)).body[0]
        user_info = await client.get_user_info(event.uid)
        if guser_info.is_owner:
            role = "owner"
        elif guser_info.is_admin:
            role = "admin"
        else:
            role = "member"
        ev = onebot_events.GroupMessageEvent(
            time=event.time,
            self_id=self.lag.client.uin,
            message_id=await info_mgr.msgid_mgr.add(
                MsgInfo(
                    raw_msg=event.msg_chain,
                    scene_type="group",
                    scene_id=event.grp_id,
                    seq=event.seq,
                    timestamp=event.time,
                    uin=event.uin,
                    uid=event.uid,
                    text=event.msg,
                    rand=event.rand,
                )
            ),
            user_id=event.uin,
            message=await to_onebot_msg(event=event, adp=self.protocol),
            group_id=event.grp_id,
            raw_message=event.msg,
            sender=onebot_events.GroupSender(
                age=user_info.age,
                area=f"{user_info.country} {user_info.province} {user_info.city}",
                card="" if not guser_info.name else guser_info.name.string,
                level="" if not guser_info.level else str(guser_info.level.num),
                nickname=user_info.name,
                role=role,
                sex="unknown",
                title="",
                user_id=event.uin,
            ),
        )
        await self.adapter.trigger(ev)

    @on(FriendMessage)
    async def pri_msg_handler(self, _client: Client, event: FriendMessage) -> None:
        if event.from_uin == self.lag.client.uin or len(event.msg_chain) == 0:
            return
        logger.info(f"[Friend] {event.from_uin} -> {event.to_uin}: {event.msg}")
        if not await info_mgr.uid_mgr.is_exist(event.from_uid):
            await info_mgr.uid_mgr.add(event.from_uid, event.from_uin)
        user_info = await self.lag.client.get_user_info(event.from_uid)
        ev = onebot_events.PrivateMessageEvent(
            time=event.timestamp,
            self_id=self.lag.client.uin,
            message_id=await info_mgr.msgid_mgr.add(
                MsgInfo(
                    raw_msg=event.msg_chain,
                    scene_type="user",
                    scene_id=event.from_uin,
                    seq=event.seq,
                    timestamp=event.timestamp,
                    uin=event.from_uin,
                    uid=event.from_uid,
                    rand=event.msg_id,  # 我实在想不明白为什么私聊的 msg_id 是 random
                    text=event.msg,
                )
            ),
            user_id=event.from_uin,
            message=await to_onebot_msg(event=event, adp=self.protocol),
            raw_message=event.msg,
            sender=onebot_events.PrivateSender(
                age=user_info.age,
                nickname=user_info.name,
                sex=user_info.sex.name if user_info.sex.name != "notset" else "unknown",  # type: ignore
                user_id=event.from_uin,
            ),
        )
        await self.adapter.trigger(ev)

    @on(GroupRecall)
    async def grp_recall_handler(self, _client: Client, event: GroupRecall) -> None:
        logger.info(f"[Group] {event.grp_id}: message {event.seq} had been deleted")
        msgid = await info_mgr.msgid_mgr.search(MsgInfo(scene_id=event.grp_id, scene_type="group", seq=event.seq))
        if not msgid:
            return
        try:
            opt_uin = await info_mgr.uid_mgr.from_uid(event.uid)
        except ValueError:
            opt_uin = 0
        real_info = await info_mgr.msgid_mgr.fetch(msgid)
        ev = onebot_events.GroupRecallEvent(
            group_id=event.grp_id,
            message_id=msgid,
            operator_id=opt_uin,
            self_id=self.lag.client.uin,
            time=event.time,
            user_id=real_info.uin,
        )
        await self.adapter.trigger(ev)

    @on(FriendRecall)
    async def pri_recall_handler(self, _client: Client, event: FriendRecall) -> None:
        if event.from_uin == self.lag.client.uin:
            return
        logger.info(f"[Friend] {event.from_uin} -> {event.to_uin}: message {event.seq} had been deleted")
        msgid = await info_mgr.msgid_mgr.search(MsgInfo(scene_id=event.from_uin, scene_type="user", seq=event.seq))
        if not msgid:
            return
        ev = onebot_events.FriendRecallEvent(
            message_id=msgid,
            self_id=self.lag.client.uin,
            time=event.timestamp,
            user_id=event.from_uin,
        )
        await self.adapter.trigger(ev)

    @on(GroupMuteMember)
    async def grp_mute_handler(self, _client: Client, event: GroupMuteMember) -> None:
        logger.info(
            f"[Group] {event.grp_id}: member {event.target_uid} had been muted "
            f"by {event.operator_uid} for {event.duration}s"
        )
        try:
            opt_uin = await info_mgr.uid_mgr.from_uid(event.operator_uid)
            uin = 0 if not event.target_uid else await info_mgr.uid_mgr.from_uid(event.target_uid)
        except ValueError:
            return
        ev = onebot_events.GroupMuteEvent(
            duration=event.duration,
            group_id=event.grp_id,
            operator_id=opt_uin,
            self_id=self.lag.client.uin,
            sub_type="lift_ban" if event.duration == 0 else "ban",
            time=round(time.time()),
            user_id=uin,
        )
        await self.adapter.trigger(ev)

    @on(GroupMemberJoined)
    async def grp_join_handler(self, _client: Client, event: GroupMemberJoined) -> None:
        logger.info(f"[Group] {event.grp_id}: member {event.uid} has joined")
        try:
            uin = await info_mgr.uid_mgr.from_uid(event.uid)
        except ValueError:
            rs = await self.lag.client.get_grp_member_info(grp_id=event.grp_id, uid=event.uid)
            uin = rs.body[0].account.uin or 0
            if uin:
                await info_mgr.uid_mgr.add(event.uid, uin)
        ev = onebot_events.GroupIncreaseEvent(
            group_id=event.grp_id,
            operator_id=0,
            self_id=self.lag.client.uin,
            sub_type="approve",
            time=round(time.time()),
            user_id=uin,
        )
        await self.adapter.trigger(ev)

    @on(GroupMemberJoinedByInvite)
    async def grp_invite_join_handler(self, _client: Client, event: GroupMemberJoinedByInvite) -> None:
        logger.info(f"[Group] {event.grp_id}: member {event.uin} has joined, invited by {event.invitor_uin}")
        ev = onebot_events.GroupIncreaseEvent(
            group_id=event.grp_id,
            operator_id=event.invitor_uin,
            self_id=self.lag.client.uin,
            sub_type="invite",
            time=round(time.time()),
            user_id=event.uin,
        )
        await self.adapter.trigger(ev)

    @on(GroupMemberQuit)
    async def grp_quit_handler(self, _client: Client, event: GroupMemberQuit) -> None:
        logger.info(
            f"[Group] {event.grp_id}: member {event.uin} has left"
            f"{', kicked by ' + event.operator_uid if event.is_kicked else ''}"
        )
        opt_uin = 0
        if event.is_kicked or event.is_kicked_self:
            try:
                opt_uin = await info_mgr.uid_mgr.from_uid(event.operator_uid)
            except ValueError:
                opt_uin = 0

        if event.is_kicked:
            tp = "kick"
        elif event.is_kicked_self:
            tp = "kick_me"
        else:
            tp = "leave"
        if not await info_mgr.uid_mgr.is_exist(event.uin) and event.uin != event.grp_id:
            await info_mgr.uid_mgr.add(event.uid, event.uin)
        ev = onebot_events.GroupDecreaseEvent(
            group_id=event.grp_id,
            operator_id=opt_uin,
            self_id=self.lag.client.uin,
            sub_type=tp,
            time=round(time.time()),
            user_id=await info_mgr.uid_mgr.from_uid(event.uid),
        )
        await self.adapter.trigger(ev)

    @on(GroupNudge)
    async def poke_handler(self, _client: Client, event: GroupNudge) -> None:
        ev = onebot_events.GroupPokeEvent(
            time=round(time.time()),
            self_id=self.lag.client.uin,
            group_id=event.grp_id,
            user_id=event.sender_uin,
            target_id=event.target_uin,
        )
        await self.adapter.trigger(ev)

    @on(GroupReaction)
    async def reaction_handler(self, _client: Client, event: GroupReaction) -> None:
        try:
            if event.uid:
                uid = event.uid
                uin = await info_mgr.uid_mgr.from_uid(event.uid)
            else:
                uid = ""
                uin = 0
        except ValueError:
            if event.uid:
                uid = event.uid
                uin = 0
            else:
                uid = ""
                uin = 0
        msgid = await info_mgr.msgid_mgr.search(MsgInfo(scene_type="group", scene_id=event.grp_id, seq=event.seq))
        if not msgid:
            msgid = await info_mgr.msgid_mgr.add(
                MsgInfo(
                    scene_type="group",
                    scene_id=event.grp_id,
                    seq=event.seq,
                    uid=uid,
                    uin=uin,
                )
            )
        ev = onebot_events.ReactionEvent(
            time=round(time.time()),
            self_id=self.lag.client.uin,
            message_id=msgid,
            operator_id=uin,
            sub_type="add" if event.is_increase else "remove",
            code=event.emoji_id,
            count=event.emoji_count,
        )
        await self.adapter.trigger(ev)

    @on(GroupMemberJoinRequest)
    async def join_req_handler(self, _client: Client, event: GroupMemberJoinRequest) -> None:
        rev = await self.lag.client.fetch_grp_request()
        req = None
        for i in rev.requests:
            if i.event_type == 1 and i.group.grp_id == event.grp_id and i.target.uid == event.uid:
                req = i
                break
        assert req
        try:
            uin = await info_mgr.uid_mgr.from_uid(event.uid)
        except ValueError:
            uin = 0
        flag = await info_mgr.req_mgr.set_group(grp_id=req.group.grp_id, seq=req.seq, ev_type=req.event_type)
        ev = onebot_events.GroupRequestEvent(
            time=round(time.time()),
            self_id=self.lag.client.uin,
            sub_type="add" if not event.invitor_uid else "invite",
            group_id=req.group.grp_id,
            user_id=uin,
            comment=req.comment,
            flag=flag,
        )
        await self.adapter.trigger(ev)

    @on(GroupAdminChange)
    async def grp_admin_handler(self, _client: Client, event: GroupAdminChange) -> None:
        try:
            uin = await info_mgr.uid_mgr.from_uid(event.uid)
        except ValueError:
            uin = 0

        ev = onebot_events.GroupAdminEvent(
            time=round(time.time()),
            self_id=self.lag.client.uin,
            sub_type="set" if event.is_set else "unset",
            group_id=event.grp_id,
            user_id=uin,
        )
        await self.adapter.trigger(ev)

    @on(FriendRequest)
    async def friend_req_handler(self, _client: Client, event: FriendRequest) -> None:
        if event.from_uid == self.lag.client.uid:
            return
        flag = event.from_uid
        ev = onebot_events.FriendRequestEvent(
            time=round(time.time()),
            self_id=self.lag.client.uin,
            user_id=event.from_uin,
            comment=event.message,
            flag=flag,
        )
        await self.adapter.trigger(ev)

    @on(FriendAddNotify)
    async def friend_add_handler(self, _client: Client, event: FriendAddNotify) -> None:
        if event.status == 3:
            ev = onebot_events.FriendAddEvent(
                time=event.timestamp,
                self_id=self.lag.client.uin,
                user_id=event.from_uin if event.from_uin != self.lag.client.uin else event.to_uin,
            )
            await self.adapter.trigger(ev)
