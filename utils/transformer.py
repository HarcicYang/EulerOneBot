import asyncio
from typing import Literal, Union

from lagrange.client.message import elems
from lagrange.client.events.group import GroupMessage
from lagrange.client.events.friend import FriendMessage
from onebot import segments as seg
from .infomgr import MsgInfo, info_mgr


async def to_onebot_msg(event: Union[GroupMessage, FriendMessage]) -> list[seg.BaseSegment]:
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
            new.append(seg.MarketFace(data=seg.MarketFaceData(face_id=str(i.face_id), tab_id=str(i.tab_id), name=i.name)))
        elif isinstance(i, elems.File):
            pass  # TODO: As an event
        elif isinstance(i, elems.MulitMsg):
            new.append(
                seg.Forward(
                    data=seg.ForwardData(
                        id=str(i.resid),
                        content=[
                            seg.Node(data=seg.NodeData(content=[], nickname=x.sender_nick, user_id=str(x.sender_uin))) for x in i.messages
                        ]
                    )
                )
            )  # TODO: Real content
        else:
            continue
    if info_renewed:
        asyncio.create_task(info_mgr.save())
    return new
