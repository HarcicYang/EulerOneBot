import asyncio
import os
import time
import traceback
from typing import NoReturn
from urllib import response

from fastapi import params
from pydantic import ValidationError

from lagrange import Lagrange
from lagrange.client.client import Client
from lagrange.client.events.friend import FriendMessage
from lagrange.client.events.group import GroupMessage

from config import load_config
from onebot.api_data import SendMsgRsp, EmptyRsp
from onebot.models import TargetInfo
from utils.infomgr import MsgInfo, info_mgr
from utils.transformer import to_onebot_msg, to_lagrange_msg
import onebot.events
from onebot import Adapter as OneBotAdapter
from onebot.api import *
from hyperogger import Logger

appconfig = load_config("appconfig.json")
logger = Logger.fetch("euler")


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

    async def run(self) -> None:
        self.lag.subscribe(GroupMessage, self.grp_msg_handler)
        self.lag.subscribe(FriendMessage, self.pri_msg_handler)

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
                    onebot.events.HeartbeatEvent(
                        interval=appconfig.heartbeat.interval,
                        self_id=appconfig.login.uin,
                        status=onebot.events.BotStatus(good=True, online=True),
                        time=round(time.time())
                    )
                )
            except:
                pass

    async def api_service(self) -> NoReturn:
        while True:
            call = await self.adapter.api_calls.get()
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
                await self.adapter.report(rsp)
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
                await self.adapter.report(rsp)
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
                await self.adapter.report(rsp)

    async def grp_msg_handler(self, client: Client, event: GroupMessage) -> None:
        logger.info(event)
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
        ev = onebot.events.GroupMessageEvent(
            time=event.time,
            self_id=appconfig.login.uin,
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
            message=await to_onebot_msg(event, lgrc=client),
            group_id=event.grp_id,
            raw_message=event.msg,
            sender=onebot.events.GroupSender(
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
        logger.info(event)
        if not info_mgr.uid_mgr.is_exist(event.from_uid):
            info_mgr.uid_mgr.add(event.from_uid, event.from_uin)
        user_info = await client.get_user_info(event.from_uid)
        ev = onebot.events.PrivateMessageEvent(
            time=event.timestamp,
            self_id=appconfig.login.uin,
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
            message=await to_onebot_msg(event, lgrc=client),
            raw_message=event.msg,
            sender=onebot.events.PrivateSender(
                age=user_info.age,
                nickname=user_info.name,
                sex=user_info.sex.name,  # type: ignore
                user_id=event.from_uin
            )
        )
        await self.adapter.trigger(ev)
