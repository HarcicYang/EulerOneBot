import asyncio
import io
import base64
import httpx
from typing import Literal, Union, TYPE_CHECKING
from urllib.parse import urlparse, unquote

from lagrange import Client
from lagrange.client.message import elems
from lagrange.client.events.group import GroupMessage
from lagrange.client.events.friend import FriendMessage
from lagrange.client.message.types import Element as LgrElement

from onebot import segments as seg
from onebot import events as obev
from .infomgr import MsgInfo, info_mgr
from onebot.models import TargetInfo


async def to_onebot_msg(event: Union[GroupMessage, FriendMessage], lgrc: Client) -> list[seg.BaseSegment]:
    new: list[seg.BaseSegment] = []
    info_renewed = False
    for i in event.msg_chain:
        if isinstance(i, elems.Text):
            new.append(seg.Text(data=seg.TextData(text=i.text)))
        elif isinstance(i, elems.Quote) and isinstance(event, GroupMessage):
            info = MsgInfo(
                scene_type="group",
                scene_id=event.grp_id,
                uin=event.uin,
                uid=event.uid,
                timestamp=event.time,
                raw_msg=event.msg_chain,
                seq=event.seq
            )
            if msgid := info_mgr.msgid_mgr.search(info):
                pass
            else:
                msgid = info_mgr.msgid_mgr.add(info)
                info_renewed = True
            new.append(seg.Reply(data=seg.ReplyData(id=str(msgid))))
        elif isinstance(i, elems.AtAll):
            new.append(seg.At(data=seg.AtData(qq="all")))
        elif isinstance(i, elems.At):
            if not info_mgr.uid_mgr.is_exist(i.uid):
                info_mgr.uid_mgr.add(i.uid, i.uin)
                info_renewed = True
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
            pass  # TODO: As an event
        elif isinstance(i, elems.Poke):
            new.append(seg.Poke(data=seg.PokeData(id=str(i.id), type="")))
        elif isinstance(i, elems.MarketFace):
            new.append(
                seg.MarketFace(data=seg.MarketFaceData(face_id=str(i.face_id), tab_id=str(i.tab_id), name=i.name)))
        elif isinstance(i, elems.File):
            pass  # TODO: As an event
        elif isinstance(i, elems.MulitMsg):
            new.append(
                seg.Forward(
                    data=seg.ForwardData(
                        id=str(i.resid),
                        content=[
                            seg.Node(data=seg.NodeData(content=[], nickname=x.sender_nick, user_id=str(x.sender_uin)))
                            for x in i.messages
                        ]
                    )
                )
            )  # TODO: Real content
        else:
            continue
    if info_renewed:
        asyncio.create_task(info_mgr.save())
    return new


async def to_lagrange_msg(msg: list[seg.BaseSegment], lgrc: Client, target: TargetInfo) -> list[LgrElement]:
    new: list[LgrElement] = []
    for i in msg:
        if isinstance(i, seg.Text):
            new.append(elems.Text(text=i.data.text))
        elif isinstance(i, seg.At):
            if i.data.qq == "all":
                new.append(elems.AtAll(text="@全体成员"))
            else:
                try:
                    qq = int(i.data.qq)
                except TypeError:
                    continue
                uid = info_mgr.uid_mgr.from_uin(qq)
                info = await lgrc.get_user_info(uid)
                new.append(elems.At(text=f"@{info.name}", uin=qq, uid=uid))
        elif isinstance(i, seg.Reply):
            msgid = int(i.data.id)
            msg_info = info_mgr.msgid_mgr.fetch(msgid)
            new.append(elems.Quote(seq=msg_info.seq, uin=msg_info.uin, timestamp=msg_info.timestamp, uid=msg_info.uid,
                                   msg=msg_info.text))
        elif isinstance(i, seg.Face):
            faceid = int(i.data.id)
            new.append(elems.Emoji(id=faceid))
        elif isinstance(i, seg.Poke):
            new.append(elems.Poke(id=114514))
        elif isinstance(i, seg.MarketFace):
            new.append(elems.MarketFace(face_id=i.data.face_id.encode(), name=i.data.name, tab_id=int(i.data.tab_id),
                                        width=512, height=512))
        elif isinstance(i, seg.Node):
            new.append(elems.ForwardNode(content=await to_lagrange_msg(i.data.content, lgrc, target),  # type: ignore
                                         sender_uin=int(i.data.user_id), sender_nick=i.data.nickname))
        elif isinstance(i, seg.Forward):
            if i.data.content:
                new.append(elems.MulitMsg(messages=await to_lagrange_msg(i.data.content, lgrc, target)))  # type: ignore
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
                            uid=info_mgr.uid_mgr.from_uin(target.id),
                            is_emoji=i.data.is_emoji,
                            image=io.BytesIO(response.content)
                        )
            elif scheme == "file":
                with open(path, "rb") as f:
                    if target.target == "group":
                        img = await lgrc.upload_grp_image(grp_id=target.id, image=f)
                    else:
                        img = await lgrc.upload_friend_image(
                            uid=info_mgr.uid_mgr.from_uin(target.id),
                            is_emoji=i.data.is_emoji,
                            image=f
                        )
            elif scheme == "base64":
                data = i.data.file.removeprefix("base64://")
                img = base64.b64decode(data)
                if target.target == "group":
                    img = await lgrc.upload_grp_image(grp_id=target.id, image=io.BytesIO(img))
                else:
                    img = await lgrc.upload_friend_image(
                        uid=info_mgr.uid_mgr.from_uin(target.id),
                        is_emoji=i.data.is_emoji,
                        image=io.BytesIO(img)
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
                    response = await cli.get(url)  # type: ignore
                    if target.target == "group":
                        voice = await lgrc.upload_grp_audio(grp_id=target.id, voice=io.BytesIO(response.content))
                    else:
                        voice = await lgrc.upload_friend_audio(
                            uid=info_mgr.uid_mgr.from_uin(target.id),
                            voice=io.BytesIO(response.content)
                        )
            elif scheme == "file":
                with open(path, "rb") as f:
                    if target.target == "group":
                        voice = await lgrc.upload_grp_audio(grp_id=target.id, voice=f)
                    else:
                        voice = await lgrc.upload_friend_audio(
                            uid=info_mgr.uid_mgr.from_uin(target.id),
                            voice=f
                        )
            elif scheme == "base64":
                data = i.data.file.removeprefix("base64://")
                voice = base64.b64decode(data)
                if target.target == "group":
                    voice = await lgrc.upload_grp_audio(grp_id=target.id, voice=io.BytesIO(voice))
                else:
                    voice = await lgrc.upload_friend_audio(
                        uid=info_mgr.uid_mgr.from_uin(target.id),
                        voice=io.BytesIO(voice)
                    )
            else:
                continue
            new.append(voice)
        else:
            continue

    return new
