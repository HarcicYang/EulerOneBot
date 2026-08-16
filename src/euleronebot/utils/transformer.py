import base64
import io
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import unquote, urlparse

import httpx
from lagrange import Client
from lagrange.client.events.friend import FriendMessage
from lagrange.client.events.group import GroupMessage
from lagrange.client.message import elems
from lagrange.client.message.types import Element as LgrElement

from ..hyperogger import Logger
from ..onebot import events as onebot_events
from ..onebot import segments as seg
from ..onebot.events import FileInfo
from ..onebot.models import TargetInfo
from ..onebot.segments import JsonData, Node
from .infomgr import MsgInfo, info_mgr

if TYPE_CHECKING:
    from ..protocol import LagrangeProtocol
else:
    LagrangeProtocol = Any

logger = Logger.fetch("euler").name_custom("euler.transformer")


async def to_onebot_msg(
    adp: LagrangeProtocol,
    event: GroupMessage | FriendMessage | None = None,
    msg: MsgInfo | None = None,
) -> list[seg.SegmentUnion]:
    new: list[seg.SegmentUnion] = []
    if event:
        msgc = event.msg_chain
    elif msg:
        msgc = msg.raw_msg
    else:
        return []  # 特喵的泥啥也不给我
    for i in msgc:
        if isinstance(i, elems.Text):
            new.append(seg.Text(data=seg.TextData(text=i.text)))
        elif isinstance(i, elems.Quote):
            if event and isinstance(event, GroupMessage):
                info = MsgInfo(
                    scene_type="group",
                    scene_id=event.grp_id,
                    uin=i.uin,
                    uid=i.uid,
                    timestamp=i.timestamp,
                    seq=i.seq,
                )
                msgid = await info_mgr.msgid_mgr.search(info)
                if not msgid:
                    msgid = await info_mgr.msgid_mgr.add(info)
            else:
                assert msg
                msgid = await info_mgr.msgid_mgr.search(
                    MsgInfo(
                        scene_type=msg.scene_type,
                        scene_id=msg.scene_id,
                        uin=i.uin,
                        uid=i.uid,
                        timestamp=i.timestamp,
                        seq=i.seq,
                    )
                )
            new.append(seg.Reply(data=seg.ReplyData(id=str(msgid))))

        elif isinstance(i, elems.AtAll):
            new.append(seg.At(data=seg.AtData(qq="all")))
        elif isinstance(i, elems.At):
            if not await info_mgr.uid_mgr.is_exist(i.uid):
                await info_mgr.uid_mgr.add(i.uid, i.uin)
            new.append(seg.At(data=seg.AtData(qq=str(i.uin))))
        elif isinstance(i, elems.Image):
            new.append(seg.Image(data=seg.ImageData(file=i.url, url=i.url, summary=i.text, is_emoji=i.is_emoji)))
        elif isinstance(i, elems.Video):
            new.append(seg.Video(data=seg.VideoData(file=i.url, url=i.url)))
        elif isinstance(i, elems.Audio):
            new.append(seg.Record(data=seg.RecordData(file=i.url, url=i.url)))
        elif isinstance(i, elems.Emoji):
            new.append(seg.Face(data=seg.FaceData(id=str(i.id))))
        elif isinstance(i, elems.Reaction):
            pass
        elif isinstance(i, elems.Poke):
            new.append(seg.Poke(data=seg.PokeData(id=str(i.id), type="")))
        elif isinstance(i, elems.MarketFace):
            new.append(
                seg.MarketFace(data=seg.MarketFaceData(face_id=str(i.face_id), tab_id=str(i.tab_id), name=i.name))
            )
        elif isinstance(i, elems.File) and event:
            if isinstance(event, GroupMessage):
                ev = onebot_events.GroupFileUploadEvent(
                    time=event.time,
                    self_id=adp.lag.client.uin,
                    group_id=event.grp_id,
                    user_id=event.uin,
                    file=FileInfo(id=i.file_id or "", name=i.file_name, size=i.file_size, busid=0),
                )
                await adp.adapter.trigger(ev)
            elif isinstance(event, FriendMessage):
                ev = onebot_events.FriendFileUploadEvent(
                    time=event.timestamp,
                    self_id=adp.lag.client.uin,
                    user_id=event.from_uin,
                    file=FileInfo(
                        id=i.file_uuid or "",
                        name=i.file_name,
                        size=i.file_size,
                        busid=0,
                        hash=i.file_hash or "",
                    ),
                )
                await adp.adapter.trigger(ev)
            new.append(seg.Text(data=seg.TextData(text="")))
        elif isinstance(i, elems.MulitMsg):
            new.append(
                seg.Forward(
                    data=seg.ForwardData(
                        id=i.resid or "",
                        content=cast(
                            list[Node],
                            await to_onebot_msg(
                                adp,
                                msg=MsgInfo(
                                    scene_type="user",
                                    scene_id=0,
                                    seq=0,
                                    raw_msg=i.messages,  # type: ignore
                                ),
                            ),
                        ),
                    )
                )
            )
        elif isinstance(i, elems.ForwardNode):
            new.append(
                seg.Node(
                    data=seg.NodeData(
                        content=await to_onebot_msg(
                            adp,
                            msg=MsgInfo(
                                scene_type="user",
                                scene_id=i.sender_uin,
                                seq=0,
                                raw_msg=i.content,  # type: ignore
                            ),
                        ),
                        user_id=str(i.sender_uin),
                        nickname=i.sender_nick,
                    )
                )
            )
        elif isinstance(i, elems.Json):
            new.append(seg.Json(data=JsonData(data=i.raw.decode())))
        else:
            continue
    if len(new) == 0:
        logger.warning(f"Empty message: {msgc}")
    return new


async def to_lagrange_msg(
    msg: list[seg.SegmentUnion], lgrc: Client, target: TargetInfo
) -> list[LgrElement | elems.ForwardNode]:
    new: list[LgrElement | elems.ForwardNode] = []
    for i in msg:
        if isinstance(i, seg.Text):
            new.append(elems.Text(text=i.data.text))
        elif isinstance(i, seg.At):
            if i.data.qq == "all":
                new.append(elems.AtAll(text="@全体成员"))
            else:
                try:
                    qq = int(i.data.qq)
                except ValueError:
                    continue
                try:
                    uid = await info_mgr.uid_mgr.from_uin(qq)
                except ValueError:
                    logger.warning(f"未知 uin {qq},已跳过 at 段")
                    continue
                try:
                    info = await lgrc.get_user_info(uid)
                except AttributeError:
                    info = await lgrc.get_user_info(qq)
                new.append(elems.At(text=f"@{info.name}", uin=qq, uid=uid))
        elif isinstance(i, seg.Reply):
            msgid = int(i.data.id)
            msg_info = await info_mgr.msgid_mgr.fetch(msgid)
            new.append(
                elems.Quote(
                    seq=msg_info.seq,
                    uin=msg_info.uin,
                    timestamp=msg_info.timestamp,
                    uid=msg_info.uid,
                    msg=msg_info.text,
                )
            )
        elif isinstance(i, seg.Face):
            faceid = int(i.data.id)
            new.append(elems.Emoji(id=faceid))
        elif isinstance(i, seg.Poke):
            pass
        elif isinstance(i, seg.MarketFace):
            new.append(
                elems.MarketFace(
                    face_id=i.data.face_id.encode(),
                    name=i.data.name,
                    tab_id=int(i.data.tab_id),
                    width=512,
                    height=512,
                )
            )
        elif isinstance(i, seg.Node):
            new.append(
                elems.ForwardNode(
                    content=await to_lagrange_msg(i.data.content, lgrc, target),  # type: ignore
                    sender_uin=int(i.data.user_id),
                    sender_nick=i.data.nickname,
                )
            )
        elif isinstance(i, seg.Forward):
            if i.data.content:
                content = cast("list[seg.SegmentUnion]", i.data.content)
                new.append(
                    elems.MulitMsg(
                        messages=cast(
                            list[elems.ForwardNode],
                            cast(object, await to_lagrange_msg(content, lgrc, target)),
                        )
                    )
                )
            elif i.data.id:
                new.append(elems.MulitMsg(resid=i.data.id))
            else:
                continue
        elif isinstance(i, seg.Image):
            url = urlparse(i.data.file)
            scheme = url.scheme
            path = unquote(url.path)
            if scheme in ["http", "https"]:
                async with httpx.AsyncClient() as cli:
                    retried = 0
                    while retried < 3:
                        response = await cli.get(url.geturl())
                        if response.status_code != 200:
                            retried += 1
                            continue
                        else:
                            break
                    if retried == 3:
                        continue
                    if target.target == "group":
                        img = await lgrc.upload_grp_image(grp_id=target.id, image=io.BytesIO(response.content))
                    else:
                        img = await lgrc.upload_friend_image(
                            uid=await info_mgr.uid_mgr.from_uin(target.id),
                            is_emoji=i.data.is_emoji,
                            image=io.BytesIO(response.content),
                        )
            elif scheme == "file":
                with open(path, "rb") as f:
                    if target.target == "group":
                        img = await lgrc.upload_grp_image(grp_id=target.id, image=f)
                    else:
                        img = await lgrc.upload_friend_image(
                            uid=await info_mgr.uid_mgr.from_uin(target.id),
                            is_emoji=i.data.is_emoji,
                            image=f,
                        )
            elif scheme == "base64":
                data = i.data.file.removeprefix("base64://")
                img = base64.b64decode(data)
                if target.target == "group":
                    img = await lgrc.upload_grp_image(grp_id=target.id, image=io.BytesIO(img))
                else:
                    img = await lgrc.upload_friend_image(
                        uid=await info_mgr.uid_mgr.from_uin(target.id),
                        is_emoji=i.data.is_emoji,
                        image=io.BytesIO(img),
                    )
            else:
                continue
            new.append(img)
        elif isinstance(i, seg.Record):
            url = urlparse(i.data.file)
            scheme = url.scheme
            path = unquote(url.path)
            if scheme in ["http", "https"]:
                async with httpx.AsyncClient() as cli:
                    response = await cli.get(url.geturl())
                    if target.target == "group":
                        voice = await lgrc.upload_grp_audio(grp_id=target.id, voice=io.BytesIO(response.content))
                    else:
                        voice = await lgrc.upload_friend_audio(
                            uid=await info_mgr.uid_mgr.from_uin(target.id),
                            voice=io.BytesIO(response.content),
                        )
            elif scheme == "file":
                with open(path, "rb") as f:
                    if target.target == "group":
                        voice = await lgrc.upload_grp_audio(grp_id=target.id, voice=f)
                    else:
                        voice = await lgrc.upload_friend_audio(uid=await info_mgr.uid_mgr.from_uin(target.id), voice=f)
            elif scheme == "base64":
                data = i.data.file.removeprefix("base64://")
                voice = base64.b64decode(data)
                if target.target == "group":
                    voice = await lgrc.upload_grp_audio(grp_id=target.id, voice=io.BytesIO(voice))
                else:
                    voice = await lgrc.upload_friend_audio(
                        uid=await info_mgr.uid_mgr.from_uin(target.id), voice=io.BytesIO(voice)
                    )
            else:
                continue
            new.append(voice)
        else:
            continue

    return new
