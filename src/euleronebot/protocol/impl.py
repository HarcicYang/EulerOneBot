import base64
import io
import os
import time
import traceback
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    BinaryIO,
    Literal,
    NoReturn,
    Protocol,
    cast,
    runtime_checkable,
)
from urllib.parse import unquote, urlparse

import httpx
from lagrange import Lagrange
from lagrange.client.message.elems import MulitMsg
from lagrange.client.message.types import Element

from ..hyperogger import Logger
from ..onebot import Adapter as OneBotAdapter
from ..onebot import events as onebot_events
from ..onebot.api import *
from ..onebot.api_data import *
from ..onebot.models import TargetInfo
from ..onebot.segments import Node
from ..utils import with_retry
from ..utils.infomgr import MsgInfo, info_mgr
from ..utils.transformer import to_lagrange_msg, to_onebot_msg

if TYPE_CHECKING:
    from . import LagrangeProtocol
else:
    LagrangeProtocol = Any

logger = Logger.fetch("euler").name_custom("euler.protocol.impl")
APICallHandler = Callable[..., Coroutine[Any, Any, Any]]


def _process_memory_bytes() -> int:
    """返回当前进程常驻内存字节数;非 Linux 平台无法读取时返回 0。"""
    try:
        with open("/proc/self/statm", encoding="utf-8") as f:
            resident_pages = int(f.read().split()[1])
        return resident_pages * os.sysconf("SC_PAGE_SIZE")
    except (FileNotFoundError, IndexError, OSError, ValueError):
        return 0


@runtime_checkable
class RegisteredHandler(Protocol):
    call_type: type[BaseAPICall]


def on(call_type: type[BaseAPICall]) -> Callable[[APICallHandler], APICallHandler]:
    def dec(func: APICallHandler) -> APICallHandler:
        cast(RegisteredHandler, cast(object, func)).call_type = call_type
        return func

    return dec


class LagrangeImpl:
    def __init__(self, onebot_adapter: OneBotAdapter, lag: Lagrange, protocol: LagrangeProtocol):
        self.adapter = onebot_adapter
        self.lag = lag
        self.protocol = protocol
        self.subscriptions: dict[str, APICallHandler] = {}

    def subscribe(self) -> None:
        for i in dir(self):
            attr = getattr(self, i)
            func = getattr(attr, "__func__", attr)
            if isinstance(func, RegisteredHandler):
                self.subscriptions[func.call_type.model_fields["action"].default] = attr

    async def _open_upload_file(self, file: str, name: str | None = None) -> tuple[BinaryIO, str]:
        """解析 Lagrange.OneBot 风格的上传文件字段,返回可读流和文件名。"""
        if file.startswith("base64://"):
            data = base64.b64decode(file.removeprefix("base64://"))
            return io.BytesIO(data), name or "file"

        parsed = urlparse(file)
        if parsed.scheme in ("http", "https"):
            async with httpx.AsyncClient() as cli:
                rsp = await cli.get(parsed.geturl())
                rsp.raise_for_status()
                data = rsp.content
            filename = name or unquote(Path(parsed.path).name) or "file"
            return io.BytesIO(data), filename

        path = unquote(parsed.path) if parsed.scheme == "file" else file
        filename = name or Path(path).name
        return open(path, "rb"), filename

    async def api_service(self) -> NoReturn:
        while True:
            call = await self.adapter.api_calls.get()
            try:
                if handler := self.subscriptions.get(call.action, None):
                    rsp = await with_retry(lambda c=call: handler(c.params))
                    rsp.echo = call.echo
                else:
                    rsp = ActionFailedResponse(status="failed", retcode=1404, data=EmptyRsp(), echo=call.echo)
                await self.adapter.report(rsp)
            except Exception as e:  # noinspection PyBroadException
                logger.error(repr(e))
                logger.trace(traceback.format_exc())
                rsp = ActionFailedResponse(status="failed", retcode=1400, data=EmptyRsp(), echo=call.echo)
                try:
                    await self.adapter.report(rsp)
                except Exception:
                    logger.error("error in handler, can't deliver")

    @on(SendMessage)
    async def send_message(self, data: SendMsgData) -> SendMessageResponse:
        if data.group_id:
            return await self.send_group_message(SendGroupMsgData(group_id=data.group_id, message=data.message))
        else:
            return await self.send_private_message(SendPrivateMsgData(user_id=data.user_id, message=data.message))

    @on(SendPrivateMessage)
    async def send_private_message(self, data: SendPrivateMsgData) -> SendMessageResponse:
        new_msg = await to_lagrange_msg(
            msg=data.message,
            lgrc=self.lag.client,
            target=(TargetInfo(target="user", id=data.user_id)),
        )
        uid = await info_mgr.uid_mgr.from_uin(data.user_id)
        if len(new_msg) == 1 and isinstance(new_msg[0], MulitMsg):
            seq = await self.lag.client.send_friend_forward_msg(new_msg[0], uid)
        else:
            new_msg = cast(list[Element], new_msg)
            seq = await self.lag.client.send_friend_msg(uid=uid, msg_chain=new_msg)
        text = ""
        for i in new_msg:
            text += i.display
        msgid = await info_mgr.msgid_mgr.add(
            MsgInfo(
                raw_msg=new_msg,
                scene_type="user",
                scene_id=data.user_id,
                seq=seq,
                timestamp=round(time.time()),
                uid=self.lag.client.uid,
                uin=self.lag.client.uin,
                text=text,
            )
        )
        return SendMessageResponse(status="ok", retcode=0, data=SendMsgRsp(message_id=msgid))

    @on(SendGroupMessage)
    async def send_group_message(self, data: SendGroupMsgData) -> SendMessageResponse:
        new_msg = await to_lagrange_msg(
            msg=data.message,
            lgrc=self.lag.client,
            target=(TargetInfo(target="group", id=data.group_id)),
        )
        if len(new_msg) == 1 and isinstance(new_msg[0], MulitMsg):
            seq = await self.lag.client.send_grp_forward_msg(new_msg[0], data.group_id)  # type: ignore
        else:
            new_msg = cast(list[Element], new_msg)
            seq = await self.lag.client.send_grp_msg(grp_id=data.group_id, msg_chain=new_msg)
        try:
            rand = (
                await self.lag.client.get_grp_msg(grp_id=data.group_id, start=seq, end=seq, filter_deleted_msg=False)
            )[0].rand
        except (AttributeError, IndexError, KeyError):
            rand = 0
        text = ""
        for i in new_msg:
            text += i.display
        msgid = await info_mgr.msgid_mgr.add(
            MsgInfo(
                raw_msg=new_msg,
                scene_type="group",
                scene_id=data.group_id,
                seq=seq,
                timestamp=round(time.time()),
                uid=self.lag.client.uid,
                uin=self.lag.client.uin,
                text=text,
                rand=rand,
            )
        )
        return SendMessageResponse(status="ok", retcode=0, data=SendMsgRsp(message_id=msgid))

    @on(DeleteMessage)
    async def delete_message(self, data: DeleteMsgData) -> DeleteMessageResponse:
        msgid = data.message_id
        msg_info = await info_mgr.msgid_mgr.fetch(msgid)
        if msg_info.scene_type == "user":
            uid = await info_mgr.uid_mgr.from_uin(msg_info.scene_id)
            await self.lag.client.recall_friend_msg(uid=uid, seq=msg_info.seq)
        else:
            await self.lag.client.recall_grp_msg(grp_id=msg_info.scene_id, seq=msg_info.seq)
        return DeleteMessageResponse(status="ok", retcode=0, data=EmptyRsp())

    @on(GetVersionInfo)
    async def get_version_info(self, _data: GetVersionInfoData) -> GetVersionInfoResponse:
        return GetVersionInfoResponse(status="ok", retcode=0, data=GetVersionInfoRsp())

    @on(GetStatus)
    async def get_status(self, _data: GetStatusData) -> GetStatusResponse:
        return GetStatusResponse(
            status="ok",
            retcode=0,
            data=GetStatusRsp(
                app_initialized=True,
                app_enabled=True,
                plugins_good=None,
                app_good=True,
                online=self.protocol.status.online,
                good=self.protocol.status.good,
                memory=_process_memory_bytes(),
            ),
        )

    @on(GetMessage)
    async def get_message(self, data: GetMsgData) -> GetMessageResponse:
        msg = await info_mgr.msgid_mgr.fetch(data.message_id)
        user_info = None
        try:
            if msg.uid:
                user_info = await self.lag.client.get_user_info(msg.uid)
            elif msg.uin:
                user_info = await self.lag.client.get_user_info(msg.uin)
        except (AttributeError, ValueError):
            logger.warning(f"get_user_info 失败,user_info 置空: uid={msg.uid!r} uin={msg.uin}")
        if isinstance(user_info, list):
            user_info = user_info[0] if user_info else None

        sex: Literal["male", "female", "unknown"] = "unknown"
        if user_info is not None:
            sex = user_info.sex.name if user_info.sex.name != "notset" else "unknown"  # type: ignore
        nickname = "" if not user_info else user_info.name
        age = 0 if not user_info else user_info.age
        area = "" if not user_info else f"{user_info.country} {user_info.province} {user_info.city}"

        return GetMessageResponse(
            status="ok",
            retcode=0,
            data=GetMsgRsp(
                message=await to_onebot_msg(msg=msg, adp=self.protocol),
                time=msg.timestamp,
                message_id=data.message_id,
                message_type="private" if msg.scene_type == "user" else "group",
                real_id=msg.seq,
                sender=onebot_events.PrivateSender(
                    user_id=msg.uin,
                    nickname=nickname,
                    sex=sex,
                    age=age,
                )
                if msg.scene_type == "user"
                else onebot_events.GroupSender(
                    user_id=msg.uin,
                    title="",
                    sex=sex,
                    role="member",
                    age=age,
                    area=area,
                    card="",
                    level="",
                    nickname=nickname,
                ),
            ),
        )

    @on(GetGroupInfo)
    async def get_group_info(self, data: GetGroupInfoData) -> GetGroupInfoResponse:
        grps = await self.lag.client.get_grp_list()
        info = next(x for x in grps.grp_list if x.grp_id == data.group_id)
        return GetGroupInfoResponse(
            status="ok",
            retcode=0,
            data=GetGroupInfoRsp(
                group_id=data.group_id,
                member_count=info.info.now_members,
                max_member_count=info.info.max_members,
                group_name=info.info.grp_name,
            ),
        )

    @on(GetStrangerInfo)
    async def get_stranger_info(self, data: GetStrangerInfoData) -> GetStrangerInfoResponse:
        try:
            uid = await info_mgr.uid_mgr.from_uin(data.user_id)
        except ValueError:
            uid = None
        try:
            info = await self.lag.client.get_user_info(uid or data.user_id)
        except AttributeError:
            info = await self.lag.client.get_user_info(data.user_id)
        return GetStrangerInfoResponse(
            status="ok",
            retcode=0,
            data=GetStrangerInfoRsp(
                age=info.age,
                nickname=info.name,
                sex=info.sex.name if info.sex.name != "notset" else "unknown",  # type: ignore
                user_id=data.user_id,
            ),
        )

    @on(GetForwardMessage)
    async def get_forward_msg(self, data: GetForwardMsgData) -> GetForwardMessageResponse:
        res_id = data.id
        msg = await self.lag.client.get_forward_msg(res_id)
        return GetForwardMessageResponse(
            status="ok",
            retcode=0,
            data=GetForwardMsgRsp(
                message=cast(
                    list[Node],
                    await to_onebot_msg(
                        adp=self.protocol,
                        msg=MsgInfo(scene_type="user", scene_id=0, seq=0, raw_msg=msg.messages),  # type: ignore
                    ),
                )
            ),
        )

    @on(SetGroupKick)
    async def set_group_kick(self, data: SetGroupKickData) -> SetGroupKickResponse:
        await self.lag.client.kick_grp_member(grp_id=data.group_id, uin=data.user_id, permanent=data.reject_add_request)
        return SetGroupKickResponse(status="ok", retcode=0, data=EmptyRsp())

    @on(SetGroupBan)
    async def set_group_ban(self, data: SetGroupBanData) -> SetGroupBanResponse:
        await self.lag.client.set_mute_member(grp_id=data.group_id, uin=data.user_id, duration=data.duration)
        return SetGroupBanResponse(status="ok", retcode=0, data=EmptyRsp())

    @on(SetGroupWholeBan)
    async def set_group_whole_ban(self, data: SetGroupWholeBanData) -> SetGroupWholeBanResponse:
        await self.lag.client.set_mute_grp(grp_id=data.group_id, enable=data.enable)
        return SetGroupWholeBanResponse(status="ok", retcode=0, data=EmptyRsp())

    @on(SetGroupCard)
    async def set_group_card(self, data: SetGroupCardData) -> SetGroupCardResponse:
        await self.lag.client.rename_grp_member(
            grp_id=data.group_id, target_uid=await info_mgr.uid_mgr.from_uin(data.user_id), name=data.card
        )
        return SetGroupCardResponse(status="ok", retcode=0, data=EmptyRsp())

    @on(SetGroupName)
    async def set_group_name(self, data: SetGroupNameData) -> SetGroupNameResponse:
        await self.lag.client.rename_grp_name(grp_id=data.group_id, name=data.group_name)
        return SetGroupNameResponse(status="ok", retcode=0, data=EmptyRsp())

    @on(SendPoke)
    async def send_poke(self, data: SendPokeData) -> SendPokeResponse:
        await self.lag.client.send_nudge(uin=data.user_id, grp_id=data.group_id)
        return SendPokeResponse(status="ok", retcode=0, data=EmptyRsp())

    @on(SetGroupLeave)
    async def set_group_leave(self, data: SetGroupLeaveData) -> SetGroupLeaveResponse:
        await self.lag.client.leave_grp(grp_id=data.group_id)
        return SetGroupLeaveResponse(status="ok", retcode=0, data=EmptyRsp())

    @on(SetGroupAddRequest)
    async def set_group_add_request(self, data: SetGroupAddRequestData) -> SetGroupAddRequestResponse:
        info = await info_mgr.req_mgr.fetch(data.flag)
        if info.type == "group":
            await self.lag.client.set_grp_request(
                grp_id=info.id,
                grp_req_seq=info.seq,
                ev_type=info.ev_type,
                action=1 if data.approve else 2,
            )
            return SetGroupAddRequestResponse(status="ok", retcode=0, data=EmptyRsp())
        raise NotImplementedError()

    @on(SetFriendAddRequest)
    async def set_friend_add_request(self, data: SetFriendAddRequestData) -> SetFriendAddRequestResponse:
        await self.lag.client.set_friend_request(target_uid=data.flag, accept=data.approve)
        return SetFriendAddRequestResponse(status="ok", retcode=0, data=EmptyRsp())

    @on(GetLoginInfo)
    async def get_login_info(self, _data: GetLoginInfoData) -> GetLoginInfoResponse:
        info = await self.lag.client.get_user_info(self.lag.client.uin)
        return GetLoginInfoResponse(
            status="ok",
            retcode=0,
            data=GetLoginInfoRsp(user_id=self.lag.client.uin, nickname=info.name),
        )

    @on(GetGroupMemberInfo)
    async def get_group_member_info(self, data: GetGroupMemberInfoData) -> GetGroupMemberInfoResponse:
        uid = await info_mgr.uid_mgr.from_uin(data.user_id)
        info = (await self.lag.client.get_grp_member_info(data.group_id, uid)).body[0]
        user_info = await self.lag.client.get_user_info(data.user_id)
        role = "member"
        if info.is_owner:
            role = "owner"
        elif info.is_admin:
            role = "admin"
        return GetGroupMemberInfoResponse(
            status="ok",
            retcode=0,
            data=GetGroupMemberInfoRsp(
                group_id=data.group_id,
                user_id=data.user_id,
                nickname=info.nickname,
                card="" if not info.name else info.name.string,
                sex=user_info.sex.name if user_info.sex.name != "notset" else "unknown",  # type: ignore
                age=user_info.age,
                area=f"{user_info.country} {user_info.province} {user_info.city}",
                join_time=info.joined_time,
                last_sent_time=info.last_seen,
                level="" if not info.level else str(info.level.num),
                role=role,
                title="",
            ),
        )

    @on(GetCookie)
    async def get_cookie(self, data: GetCookieData) -> GetCookieResponse:
        cookie = (await self.lag.client.get_cookies([data.domain]))[0]
        return GetCookieResponse(status="ok", retcode=0, data=GetCookieRsp(cookies=cookie))

    @on(GetCSRFToken)
    async def get_csrf_token(self, _data: GetCSRFTokenData) -> GetCSRFTokenResponse:
        token = await self.lag.client.get_csrf_token()
        return GetCSRFTokenResponse(status="ok", retcode=0, data=GetCSRFTokenRsp(token=token))

    @on(SendLike)
    async def send_like(self, data: SendLikeData) -> SendLikeResponse:
        uid = await info_mgr.uid_mgr.from_uin(data.user_id)
        await self.lag.client.friend_like(uid, data.times)
        return SendLikeResponse(status="ok", retcode=0, data=EmptyRsp())

    @on(SetGroupAdmin)
    async def set_group_admin(self, data: SetGroupAdminData) -> SetGroupAdminResponse:
        uid = await info_mgr.uid_mgr.from_uin(data.user_id)
        await self.lag.client.set_grp_admin(grp_id=data.group_id, uid=uid, is_set=data.enable)
        return SetGroupAdminResponse(status="ok", retcode=0, data=EmptyRsp())

    @on(GetFriendList)
    async def get_friend_list(self, _data: GetFriendListData) -> GetFriendListResponse:
        friends = await self.lag.client.get_friend_list()
        return GetFriendListResponse(
            status="ok",
            retcode=0,
            data=GetFriendListRsp.model_validate(
                [FriendElem(user_id=i.uin, nickname=i.nickname or "", remark=i.remark or "") for i in friends]
            ),
        )

    @on(GetGroupList)
    async def get_group_list(self, _data: GetGroupListData) -> GetGroupListResponse:
        groups = await self.lag.client.get_grp_list()
        return GetGroupListResponse(
            status="ok",
            retcode=0,
            data=GetGroupListRsp.model_validate(
                [
                    GetGroupInfoRsp(
                        group_id=i.grp_id,
                        group_name=i.info.grp_name,
                        member_count=i.info.now_members,
                        max_member_count=i.info.max_members,
                    )
                    for i in groups.grp_list
                ]
            ),
        )

    @on(GetGroupMemberList)
    async def get_group_member_list(self, data: GetGroupMemberListData) -> GetGroupMemberListResponse:
        members = await self.lag.client.get_grp_members(grp_id=data.group_id)
        result = []
        for i in members.body:
            if not i.account.uin:
                try:
                    uin = await info_mgr.uid_mgr.from_uid(i.account.uid)
                except ValueError:
                    continue
            else:
                uin = i.account.uin
            result.append(
                (await self.get_group_member_info(GetGroupMemberInfoData(group_id=data.group_id, user_id=uin))).data
            )
        return GetGroupMemberListResponse(status="ok", retcode=0, data=GetGroupMemberListRsp.model_validate(result))

    @on(GroupReaction)
    async def group_reaction(self, data: GroupReactionData) -> GroupReactionResponse:
        msg_info = await info_mgr.msgid_mgr.fetch(data.message_id or 0)
        await self.lag.client.send_grp_reaction(
            grp_id=data.group_id, msg_seq=msg_info.seq, content=data.emoji or data.code or 0, is_cancel=not data.is_add
        )
        return GroupReactionResponse(status="ok", retcode=0, data=EmptyRsp())

    @on(SetGroupSpecialTitle)
    async def set_group_special_title(self, data: SetGroupSpecialTitleData) -> SetGroupSpecialTitleResponse:
        uid = await info_mgr.uid_mgr.from_uin(data.user_id)
        await self.lag.client.set_grp_special_title(data.group_id, uid, data.special_title)
        return SetGroupSpecialTitleResponse(status="ok", retcode=0, data=EmptyRsp())

    @on(UploadGroupFile)
    async def upload_group_file(self, data: UploadGroupFileData) -> UploadGroupFileResponse:
        source, filename = await self._open_upload_file(data.file, data.name)
        try:
            await self.lag.client.upload_grp_file(source, data.group_id, data.folder or "/", filename)
        finally:
            source.close()
        return UploadGroupFileResponse(status="ok", retcode=0, data=EmptyRsp())

    @on(UploadPrivateFile)
    async def upload_private_file(self, data: UploadPrivateFileData) -> UploadPrivateFileResponse:
        uid = await info_mgr.uid_mgr.from_uin(data.user_id)
        source, filename = await self._open_upload_file(data.file, data.name)
        try:
            await self.lag.client.upload_friend_file(source, uid, filename)
        finally:
            source.close()
        return UploadPrivateFileResponse(status="ok", retcode=0, data=EmptyRsp())

    @on(GetGroupFileUrl)
    async def get_group_file_url(self, data: GetGroupFileUrlData) -> GetGroupFileUrlResponse:
        url = await self.lag.client.fetch_grp_file_url(data.group_id, data.file_id)
        return GetGroupFileUrlResponse(status="ok", retcode=0, data=GetGroupFileUrlRsp(url=url))

    @on(GetPrivateFileUrl)
    async def get_private_file_url(self, data: GetPrivateFileUrlData) -> GetPrivateFileUrlResponse:
        uid = await info_mgr.uid_mgr.from_uin(data.user_id)
        url = await self.lag.client.fetch_friend_file_url(data.file_id, data.file_hash, uid)
        return GetPrivateFileUrlResponse(status="ok", retcode=0, data=GetPrivateFileUrlRsp(url=url))
