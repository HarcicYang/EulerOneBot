import asyncio
import time
import traceback
from typing import NoReturn, Optional

from lagrange import Lagrange
from lagrange.client.client import Client
from lagrange.client.events.service import ClientOnline, ServerKick
from lagrange.client.events.friend import FriendMessage, FriendRecall
from lagrange.client.events.group import (
    GroupMessage,
    GroupRecall,
    GroupMuteMember,
    GroupMemberJoined,
    GroupMemberJoinedByInvite,
    GroupMemberQuit, GroupNudge, GroupReaction
)

from .config import load_config
from .onebot.api_data import *
from .onebot.models import TargetInfo
from .utils.infomgr import MsgInfo, info_mgr
from .utils.transformer import to_onebot_msg, to_lagrange_msg
from .onebot import events as onebot_events
from .onebot import Adapter as OneBotAdapter
from .onebot.api import *
from .hyperogger import Logger

appconfig = load_config("./appconfig.json")
logger = Logger.fetch("euler").name_custom("euler.protocol")


class LagrangeProtocol:
    def __init__(self, onebot_adapter: OneBotAdapter):
        self.adapter = onebot_adapter
        self.lag = Lagrange(
            appconfig.login.uin,
            "linux",
            (appconfig.login.signer_url + "/api/sign/sec-sign") \
                .replace("https://", f"https://{appconfig.login.signer_token}@") \
                .replace("http://", f"http://{appconfig.login.signer_token}@"),
        )

        self.lag.log.set_level("DEBUG")

        self.info_updated = False

    async def run(self) -> None:
        self.lag.subscribe(GroupMessage, self.grp_msg_handler)
        self.lag.subscribe(FriendMessage, self.pri_msg_handler)
        self.lag.subscribe(GroupRecall, self.grp_recall_handler)
        self.lag.subscribe(FriendRecall, self.pri_recall_handler)
        self.lag.subscribe(GroupMuteMember, self.grp_mute_handler)
        self.lag.subscribe(GroupMemberJoined, self.grp_join_handler)
        self.lag.subscribe(GroupMemberJoinedByInvite, self.grp_invite_join_handler)
        self.lag.subscribe(GroupNudge, self.poke_handler)
        self.lag.subscribe(GroupReaction, self.reaction_handler)

        try:
            await self.adapter.setup()
            asyncio.create_task(self.adapter.cycle())
            asyncio.create_task(self.api_service())
            asyncio.create_task(self.heartbeat())
            await self.lag.run()
        except KeyboardInterrupt:
            self.lag.client._task_clear()
            logger.info("Program exited by user")
        else:
            logger.info("Program exited normally")

    async def heartbeat(self) -> NoReturn:
        while True:
            await asyncio.sleep(appconfig.heartbeat.interval / 1000)
            try:
                await self.adapter.trigger(
                    onebot_events.HeartbeatEvent(
                        interval=appconfig.heartbeat.interval,
                        self_id=self.lag.client.uin,
                        status=onebot_events.BotStatus(good=True, online=True),
                        time=round(time.time())
                    )
                )
            except:
                pass

    async def api_service(self) -> NoReturn:
        while True:
            call = await self.adapter.api_calls.get()
            try:
                if isinstance(call, SendMessage):  # Do it ahead
                    if call.params.group_id:
                        call = SendGroupMessage(
                            params=SendGroupMsgData(
                                group_id=call.params.group_id,
                                message=call.params.message
                            ),
                            echo=call.echo
                        )
                    else:
                        call = SendPrivateMessage(
                            params=SendPrivateMsgData(
                                user_id=call.params.user_id,
                                message=call.params.message
                            ),
                            echo=call.echo
                        )

                if isinstance(call, SendPrivateMessage):
                    new_msg = await to_lagrange_msg(
                        msg=call.params.message,
                        lgrc=self.lag.client,
                        target=(TargetInfo(target="user", id=call.params.user_id))
                    )
                    seq = await self.lag.client.send_friend_msg(
                        uid=info_mgr.uid_mgr.from_uin(call.params.user_id),
                        msg_chain=new_msg
                    )
                    text = ""
                    for i in new_msg:
                        text += i.display
                    msgid = info_mgr.msgid_mgr.add(
                        MsgInfo(
                            raw_msg=new_msg,
                            scene_type="user",
                            scene_id=call.params.user_id,
                            seq=seq,
                            timestamp=round(time.time()),
                            uid=self.lag.client.uid,
                            uin=self.lag.client.uin,
                            text=text
                        )
                    )
                    rsp = SendPrivateMessageResponse(
                        status="ok",
                        retcode=0,
                        data=SendMsgRsp(message_id=msgid),
                        echo=call.echo
                    )

                elif isinstance(call, SendGroupMessage):
                    new_msg = await to_lagrange_msg(
                        msg=call.params.message,
                        lgrc=self.lag.client,
                        target=(TargetInfo(target="group", id=call.params.group_id))
                    )
                    seq = await self.lag.client.send_grp_msg(
                        grp_id=call.params.group_id,
                        msg_chain=new_msg
                    )
                    text = ""
                    for i in new_msg:
                        text += i.display
                    msgid = info_mgr.msgid_mgr.add(
                        MsgInfo(
                            raw_msg=new_msg,
                            scene_type="group",
                            scene_id=call.params.group_id,
                            seq=seq,
                            timestamp=round(time.time()),
                            uid=self.lag.client.uid,
                            uin=self.lag.client.uin,
                            text=text
                        )
                    )
                    rsp = SendGroupMessageResponse(
                        status="ok",
                        retcode=0,
                        data=SendMsgRsp(message_id=msgid),
                        echo=call.echo
                    )

                elif isinstance(call, DeleteMessage):
                    msgid = call.params.message_id
                    msg_info = info_mgr.msgid_mgr.fetch(msgid)
                    if msg_info.scene_type == "user":
                        pass
                    else:
                        await self.lag.client.recall_grp_msg(grp_id=msg_info.scene_id, seq=msg_info.seq)
                    rsp = DeleteMessageResponse(
                        status="ok",
                        retcode=0,
                        data=EmptyRsp(),
                        echo=call.echo
                    )

                elif isinstance(call, GetVersionInfo):
                    rsp = GetVersionInfoResponse(
                        status="ok",
                        retcode=0,
                        data=GetVersionInfoRsp(),
                        echo=call.echo
                    )


                elif isinstance(call, GetMessage):
                    rsp = ActionFailedResponse(
                        status="failed",
                        retcode=1400,
                        data=EmptyRsp(),
                        echo=call.echo
                    )
                    msg = info_mgr.msgid_mgr.fetch(call.params.message_id)
                    if msg.uid:
                        user_info = await self.lag.client.get_user_info(msg.uid)
                    elif msg.uin:
                        user_info = await self.lag.client.get_user_info(msg.uin)[0]
                    else:
                        user_info = None
                    rsp = GetMessageResponse(
                        status="ok",
                        retcode=0,
                        data=GetMsgRsp(
                            message=await to_onebot_msg(msg=msg, lgrc=self.lag.client),
                            time=msg.timestamp,
                            message_id=call.params.message_id,
                            message_type="private" if msg.scene_type == "user" else "group",
                            real_id=msg.seq,
                            sender=onebot_events.PrivateSender(
                                user_id=msg.uin,
                                nickname="" if not user_info else user_info.name,
                                sex=user_info.sex.name if user_info.sex.name != "notset" else "unknown",
                                age=0 if not user_info else user_info.age,
                            ) if msg.scene_type == "user" else onebot_events.GroupSender(
                                user_id=msg.uin,
                                title="",
                                sex=user_info.sex.name if user_info.sex.name != "notset" else "unknown",
                                role="member",
                                age=0 if not user_info else user_info.age,
                                area="" if not user_info else f"{user_info.country} {user_info.province} {user_info.city}",
                                card="",
                                level="",
                                nickname="" if not user_info else user_info.name,
                            )
                        ),
                        echo=call.echo
                    )


                elif isinstance(call, GetGroupInfo):
                    grps = await self.lag.client.get_grp_list()
                    info = list(filter(lambda x: x.grp_id == call.params.group_id, grps.grp_list))[0]
                    rsp = GetGroupInfoResponse(
                        status="ok",
                        retcode=0,
                        data=GetGroupInfoRsp(
                            group_id=call.params.group_id,
                            member_count=info.info.now_members,
                            max_member_count=info.info.max_members,
                            group_name=info.info.grp_name
                        ),
                        echo=call.echo
                    )


                elif isinstance(call, GetStrangerInfo):
                    try:
                        uid = info_mgr.uid_mgr.from_uin(call.params.user_id)
                    except ValueError:
                        uid = None
                    info = await self.lag.client.get_user_info(uid or call.params.user_id)
                    rsp = GetStrangerInfoResponse(
                        status="ok",
                        retcode=0,
                        data=GetStrangerInfoRsp(
                            age=info.age,
                            nickname=info.name,
                            sex=info.sex.name if info.sex.name != "notset" else "unknown",
                            user_id=call.params.user_id
                        ),
                        echo=call.echo
                    )
                else:
                    rsp = ActionFailedResponse(
                        status="failed",
                        retcode=1404,
                        data=EmptyRsp(),
                        echo=call.echo
                    )
                await self.adapter.report(rsp)
            except Exception as e:
                logger.error(repr(e))
                logger.error(traceback.format_exc())
                rsp = ActionFailedResponse(
                    status="failed",
                    retcode=1400,
                    data=EmptyRsp(),
                    echo=call.echo
                )
                await self.adapter.report(rsp)

    async def online_handler(self, client: Client, event: Optional[ClientOnline] = None) -> None:
        if self.info_updated:
            return
        grps = await client.get_grp_list()
        for i in grps.grp_list:
            gid = i.grp_id
            members = await client.get_grp_members(grp_id=gid)
            for j in members.body:
                if j.account.uin and not info_mgr.uid_mgr.is_exist(j.account.uin):
                    info_mgr.uid_mgr.add(j.account.uid, j.account.uin)

        users = await client.get_friend_list()
        for i in users:
            if i.uid and not info_mgr.uid_mgr.is_exist(i.uin):
                info_mgr.uid_mgr.add(i.uid, i.uin)

        self.info_updated = True

    @staticmethod
    async def kick_handler(client: Client, event: ServerKick) -> None:
        logger.error(f"下线通知：{event.title} {event.tips}")

    async def grp_msg_handler(self, client: Client, event: GroupMessage) -> None:
        if event.uin == self.lag.client.uin:
            return
        logger.info(f"[Group] {event.grp_name}({event.grp_id}): @{event.nickname}({event.uin}): {event.msg}")
        if not info_mgr.uid_mgr.is_exist(event.uid):
            info_mgr.uid_mgr.add(event.uid, event.uin)
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
            message_id=info_mgr.msgid_mgr.add(
                MsgInfo(
                    raw_msg=event.msg_chain,
                    scene_type="group",
                    scene_id=event.grp_id,
                    seq=event.seq,
                    timestamp=event.time,
                    uin=event.uin,
                    uid=event.uid,
                    text=event.msg
                )
            ),
            user_id=event.uin,
            message=await to_onebot_msg(event=event, lgrc=self.lag.client),
            group_id=event.grp_id,
            raw_message=event.msg,
            sender=onebot_events.GroupSender(
                age=user_info.age,
                area=f"{user_info.country} {user_info.province} {user_info.city}",
                card="" if not guser_info.name else guser_info.name.string,
                level="" if not guser_info.level else str(guser_info.level.num),
                nickname=user_info.name,
                role=role,  # type: ignore
                sex="unknown",
                title="",
                user_id=event.uin
            )
        )
        await self.adapter.trigger(ev)

    async def pri_msg_handler(self, client: Client, event: FriendMessage) -> None:
        if event.from_uin == self.lag.client.uin:
            return
        logger.info(f"[Friend] {event.from_uin} -> {event.to_uin}: {event.msg}")
        if not info_mgr.uid_mgr.is_exist(event.from_uid):
            info_mgr.uid_mgr.add(event.from_uid, event.from_uin)
        user_info = await client.get_user_info(event.from_uid)
        ev = onebot_events.PrivateMessageEvent(
            time=event.timestamp,
            self_id=self.lag.client.uin,
            message_id=info_mgr.msgid_mgr.add(
                MsgInfo(
                    raw_msg=event.msg_chain,
                    scene_type="user",
                    scene_id=event.from_uin,
                    seq=event.seq,
                    timestamp=event.timestamp,
                    uin=event.from_uin,
                    uid=event.from_uid,
                    text=event.msg
                )
            ),
            user_id=event.from_uin,
            message=await to_onebot_msg(event=event, lgrc=self.lag.client),
            raw_message=event.msg,
            sender=onebot_events.PrivateSender(
                age=user_info.age,
                nickname=user_info.name,
                sex=user_info.sex.name if user_info.sex.name != "notset" else "unknown",  # type: ignore
                user_id=event.from_uin
            )
        )
        await self.adapter.trigger(ev)

    async def grp_recall_handler(self, client: Client, event: GroupRecall) -> None:
        logger.info(f"[Group] {event.grp_id}: message {event.seq} had been deleted")
        msgid = info_mgr.msgid_mgr.search(
            MsgInfo(
                scene_id=event.grp_id,
                scene_type="group",
                seq=event.seq
            )
        )
        if not msgid:
            return
        real_info = info_mgr.msgid_mgr.fetch(msgid)
        ev = onebot_events.GroupRecallEvent(
            group_id=event.grp_id,
            message_id=msgid,
            operator_id=0,
            self_id=self.lag.client.uin,
            time=event.time,
            user_id=real_info.uin
        )
        await self.adapter.trigger(ev)

    async def pri_recall_handler(self, client: Client, event: FriendRecall) -> None:
        if event.from_uin == self.lag.client.uin:
            return
        logger.info(f"[Friend] {event.from_uin} -> {event.to_uin}: message {event.seq} had been deleted")
        msgid = info_mgr.msgid_mgr.search(
            MsgInfo(
                scene_id=event.from_uin,
                scene_type="user",
                seq=event.seq
            )
        )
        if not msgid:
            return
        ev = onebot_events.FriendRecallEvent(
            message_id=msgid,
            self_id=self.lag.client.uin,
            time=event.timestamp,
            user_id=event.from_uin
        )
        await self.adapter.trigger(ev)

    async def grp_mute_handler(self, client: Client, event: GroupMuteMember) -> None:
        logger.info(
            f"[Group] {event.grp_id}: member {event.target_uid} had been muted by {event.operator_uid} for {event.duration}s")
        try:
            opt_uin = info_mgr.uid_mgr.from_uid(event.operator_uid)
            uin = 0 if not event.target_uid else info_mgr.uid_mgr.from_uid(event.target_uid)
        except ValueError:
            return
        ev = onebot_events.GroupMuteEvent(
            duration=event.duration,
            group_id=event.grp_id,
            operator_id=opt_uin,
            self_id=self.lag.client.uin,
            sub_type="lift_ban" if event.duration == 0 else "ban",
            time=round(time.time()),
            user_id=uin
        )
        await self.adapter.trigger(ev)

    async def grp_join_handler(self, client: Client, event: GroupMemberJoined) -> None:
        logger.info(f"[Group] {event.grp_id}: member {event.uid} has joined")
        try:
            uin = info_mgr.uid_mgr.from_uid(event.uid)
        except ValueError:
            rs = await client.get_grp_member_info(grp_id=event.grp_id, uid=event.uid)
            uin = rs.body[0].account.uin or 0
            if uin:
                info_mgr.uid_mgr.add(event.uid, uin)
        ev = onebot_events.GroupIncreaseEvent(
            group_id=event.grp_id,
            operator_id=0,
            self_id=self.lag.client.uin,
            sub_type="approve",
            time=round(time.time()),
            user_id=uin
        )
        await self.adapter.trigger(ev)

    async def grp_invite_join_handler(self, client: Client, event: GroupMemberJoinedByInvite) -> None:
        logger.info(f"[Group] {event.grp_id}: member {event.uin} has joined, invited by {event.invitor_uin}")
        ev = onebot_events.GroupIncreaseEvent(
            group_id=event.grp_id,
            operator_id=event.invitor_uin,
            self_id=self.lag.client.uin,
            sub_type="invite",
            time=round(time.time()),
            user_id=event.uin
        )
        await self.adapter.trigger(ev)

    async def grp_quit_handler(self, client: Client, event: GroupMemberQuit) -> None:
        logger.info(
            f"[Group] {event.grp_id}: member {event.uin} has left{', kicked by ' + str(event.operator_uid) if event.is_kicked else ''}")
        opt_uin = 0
        if event.is_kicked or event.is_kicked_self:
            try:
                opt_uin = info_mgr.uid_mgr.from_uid(event.operator_uid)
            except ValueError:
                opt_uin = 0
        if event.is_kicked_self:
            tp = "kick_me"
        elif event.is_kicked:
            tp = "kick"
        else:
            tp = "leave"
        if not info_mgr.uid_mgr.is_exist(event.uin):
            info_mgr.uid_mgr.add(event.uid, event.uin)
        ev = onebot_events.GroupDecreaseEvent(
            group_id=event.grp_id,
            operator_id=opt_uin,
            self_id=self.lag.client.uin,
            sub_type=tp,  # type: ignore
            time=round(time.time()),
            user_id=event.uin
        )
        await self.adapter.trigger(ev)

    async def poke_handler(self, client: Client, event: GroupNudge) -> None:
        ev = onebot_events.GroupPokeEvent(
            time=round(time.time()),
            self_id=self.lag.client.uin,
            group_id=event.grp_id,
            user_id=event.sender_uin,
            target_id=event.target_uin
        )
        await self.adapter.trigger(ev)

    async def reaction_handler(self, client: Client, event: GroupReaction) -> None:
        try:
            if event.uid:
                uid = event.uid
                uin = info_mgr.uid_mgr.from_uid(event.uid)
            else:
                uid = info_mgr.uid_mgr.from_uin(event.uin)
                uin = event.uin
        except ValueError:
            if event.uid:
                uid = event.uid
                uin = 0
            else:
                uid = ""
                uin = event.uin
        try:
            msgid = info_mgr.msgid_mgr.search(MsgInfo(scene_type="group", scene_id=event.grp_id, seq=event.seq))
        except IndexError:
            msgid = info_mgr.msgid_mgr.add(
                MsgInfo(scene_type="group", scene_id=event.grp_id, seq=event.seq, uid=uid, uin=uin))
        ev = onebot_events.ReactionEvent(
            time=round(time.time()),
            self_id=self.lag.client.uin,
            message_id=msgid,
            operator_id=uin,
            sub_type="add" if event.is_increase else "remove",
            code=event.emoji_id,
            count=event.emoji_count
        )
        await self.adapter.trigger(ev)
