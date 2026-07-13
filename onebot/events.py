from pydantic import BaseModel
from typing import Literal, TYPE_CHECKING, Any, Union

from .models import BotStatus

if TYPE_CHECKING:
    from .segments import BaseSegment

    SEGMENT = BaseSegment
else:
    SEGMENT = Any

__all__ = [
    "BaseEvent",
    "PrivateSender",
    "GroupSender",
    "MessageEvent",
    "GroupMessageEvent",
    "PrivateMessageEvent",
    "NoticeEvent",
    "FileInfo",
    "GroupFileUploadEvent",
    "GroupAdminEvent",
    "GroupDecreaseEvent",
    "GroupIncreaseEvent",
    "GroupMuteEvent",
    "FriendAddEvent",
    "GroupRecallEvent",
    "FriendRecallEvent",
    "GroupPokeEvent",
    "RequestEvent",
    "FriendRequestEvent",
    "GroupRequestEvent",
    "MateEvent",
    "LifecycleEvent",
    "HeartbeatEvent",
]


class BaseEvent(BaseModel):
    time: int
    self_id: int
    post_type: Literal["message", "notice", "request", "meta_event"]


class PrivateSender(BaseModel):
    user_id: int
    nickname: str
    sex: Literal["male", "female", "unknown"]
    age: int


class GroupSender(BaseModel):
    user_id: int
    nickname: str
    sex: Literal["male", "female", "unknown"]
    age: int
    card: str
    area: str
    level: str
    role: Literal["owner", "admin", "member"]
    title: str


class MessageEvent(BaseEvent):
    post_type: Literal["message"] = "message"
    message_type: Literal["private", "group"]
    sub_type: Literal["friend", "group", "other"]
    message_id: int
    user_id: int
    message: list[SEGMENT]
    raw_message: str
    font: int = 0
    sender: Union[PrivateSender, GroupSender]


class GroupMessageEvent(MessageEvent):
    message_type: Literal["group"] = "group"
    anonymous: None = None
    sender: Union[GroupSender]
    group_id: int


class PrivateMessageEvent(MessageEvent):
    message_type: Literal["private"] = "private"
    sender: Union[PrivateSender]


class NoticeEvent(BaseEvent):
    notice_type: Literal[
        "group_upload", "group_admin", "group_decrease", "group_increase", "group_ban", "friend_add", "group_recall", "friend_recall", "notify"]


class FileInfo(BaseModel):
    id: str
    name: str
    size: int
    busid: int


class GroupFileUploadEvent(NoticeEvent):
    notice_type: Literal["group_upload"] = "group_upload"
    group_id: int
    user_id: int
    file: FileInfo


class GroupAdminEvent(NoticeEvent):
    notice_type: Literal["group_admin"] = "group_admin"
    sub_type: Literal["set", "unset"]
    group_id: int
    user_id: int


class GroupDecreaseEvent(NoticeEvent):
    notice_type: Literal["group_decrease"] = "group_decrease"
    sub_type: Literal["leave", "kick", "kick_me"]
    group_id: int
    operator_id: int
    user_id: int


class GroupIncreaseEvent(NoticeEvent):
    notice_type: Literal["group_increase"] = "group_increase"
    sub_type: Literal["approve", "invite"]
    group_id: int
    operator_id: int
    user_id: int


class GroupMuteEvent(NoticeEvent):
    notice_type: Literal["group_ban"] = "group_ban"
    sub_type: Literal["ban", "lift_ban"]
    group_id: int
    operator_id: int
    user_id: int
    duration: int


class FriendAddEvent(NoticeEvent):
    notice_type: Literal["friend_add"] = "friend_add"
    user_id: int


class GroupRecallEvent(NoticeEvent):
    notice_type: Literal["group_recall"] = "group_recall"
    group_id: int
    operator_id: int
    user_id: int
    message_id: int


class FriendRecallEvent(NoticeEvent):
    notice_type: Literal["friend_recall"] = "friend_recall"
    user_id: int
    message_id: int


class GroupPokeEvent(NoticeEvent):
    notice_type: Literal["notify"] = "notify"
    sub_type: Literal["poke"]
    group_id: int
    operator_id: int
    group_id: int
    target_id: int
    user_id: int


class RequestEvent(BaseEvent):
    request_type: Literal["friend", "group"]


class FriendRequestEvent(RequestEvent):
    request_type: Literal["friend"] = "friend"
    user_id: int
    comment: str
    flag: str


class GroupRequestEvent(RequestEvent):
    request_type: Literal["group"] = "group"
    sub_type: Literal["add", "invite"]
    group_id: int
    user_id: int
    comment: str
    flag: str


class MateEvent(BaseEvent):
    request_type: Literal["mate"] = "mate"
    mate_event_type: Literal["lifecycle", "heartbeat"]


class LifecycleEvent(MateEvent):
    mate_event_type: Literal["lifecycle"] = "lifecycle"
    sub_type: Literal["enable", "disable", "connect"]


class HeartbeatEvent(MateEvent):
    mate_event_type: Literal["heartbeat"] = "heartbeat"
    status: BotStatus
    interval: int
