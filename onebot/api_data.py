from pydantic import BaseModel, RootModel
from typing import Any, TYPE_CHECKING, Literal, Union

from ..versions import NAME, VERSION

if TYPE_CHECKING:
    from .segments import BaseSegment, Node
    from .events import GroupSender, PrivateSender

    SEGMENT = BaseSegment
    NODE = Node
    GROUP_SENDER = GroupSender
    PRIVATE_SENDER = PrivateSender
else:
    SEGMENT = Any
    NODE = Any
    GROUP_SENDER = Any
    PRIVATE_SENDER = Any


__all__ = [
    "SendPrivateMsgData",
    "SendGroupMsgData",
    "SendMsgData",
    "SendMsgRsp",
    "DeleteMsgData",
    "EmptyRsp",
    "GetMsgData",
    "GetMsgRsp",
    "GetForwardMsgData",
    "GetForwardMsgRsp",
    "SendLikeData",
    "SetGroupKickData",
    "SetGroupBanData",
    "SetGroupWholeBanData",
    "SetGroupAdminData",
    "SetGroupCardData",
    "SetGroupNameData",
    "SetGroupLeaveData",
    "SetGroupSpecialTitleData",
    "SetFriendAddRequestData",
    "SetGroupAddRequestData",
    "GetLoginInfoData",
    "GetLoginInfoRsp",
    "GetStrangerInfoData",
    "GetStrangerInfoRsp",
    "GetFriendListData",
    "FriendElem",
    "GetFriendListRsp",
    "GetGroupInfoData",
    "GetGroupInfoRsp",
    "GetGroupListData",
    "GetGroupListRsp",
    "GetGroupMemberInfoData",
    "GetGroupMemberInfoRsp",
    "GetGroupMemberListData",
    "GetGroupMemberListRsp",
    "GetStatusData",
    "GetVersionInfoData",
    "GetVersionInfoRsp",
]


class SendPrivateMsgData(BaseModel):
    user_id: int
    message: list[SEGMENT]


class SendGroupMsgData(BaseModel):
    group_id: int
    message: list[SEGMENT]


class SendMsgData(BaseModel):
    message_type: Literal["private", "group"]
    user_id: int = 0
    group_id: int = 0
    message: list[SEGMENT]


class SendMsgRsp(BaseModel):
    message_id: int


class DeleteMsgData(BaseModel):
    message_id: int


class EmptyRsp(BaseModel):
    ...


class GetMsgData(BaseModel):
    message_id: int


class GetMsgRsp(BaseModel):
    time: int
    message_type: Literal["private", "group"]
    message_id: int
    real_id: int
    sender: Union[PRIVATE_SENDER, GROUP_SENDER]
    message: list[SEGMENT]


class GetForwardMsgData(BaseModel):
    id: str


class GetForwardMsgRsp(BaseModel):
    message: list[NODE]


class SendLikeData(BaseModel):
    user_id: int
    times: int = 1


class SetGroupKickData(BaseModel):
    user_id: int
    group_id: int
    reject_add_request: bool = False


class SetGroupBanData(BaseModel):
    user_id: int
    group_id: int
    duration: int = 30 * 60


class SetGroupWholeBanData(BaseModel):
    group_id: int
    enable: bool = True


class SetGroupAdminData(BaseModel):
    user_id: int
    group_id: int
    enable: bool = True


class SetGroupCardData(BaseModel):
    user_id: int
    group_id: int
    card: str


class SetGroupNameData(BaseModel):
    group_id: int
    group_name: str


class SetGroupLeaveData(BaseModel):
    group_id: int
    is_dismiss: bool = False


class SetGroupSpecialTitleData(BaseModel):
    group_id: int
    user_id: int
    special_title: str
    duration: int = -1


class SetFriendAddRequestData(BaseModel):
    flag: str
    approve: bool = True
    remark: str


class SetGroupAddRequestData(BaseModel):
    flag: str
    sub_type: Literal["add", "invite"]
    approve: bool = True
    reason: str


class GetLoginInfoData(BaseModel):
    ...


class GetLoginInfoRsp(BaseModel):
    user_id: int
    nickname: str


class GetStrangerInfoData(BaseModel):
    user_id: int
    no_cache: bool = False


class GetStrangerInfoRsp(BaseModel):
    user_id: int
    nickname: str
    sex: Literal["male", "female", "unknown"]
    age: int


class GetFriendListData(BaseModel):
    ...


class FriendElem(BaseModel):
    user_id: int
    nickname: str
    remark: str


class GetFriendListRsp(RootModel[list[FriendElem]]):
    ...


class GetGroupInfoData(BaseModel):
    group_id: int
    no_cache: bool = False


class GetGroupInfoRsp(BaseModel):
    group_id: int
    group_name: str
    member_count: int
    max_member_count: int


class GetGroupListData(BaseModel):
    ...


class GetGroupListRsp(RootModel[list[GetGroupInfoRsp]]):
    ...


class GetGroupMemberInfoData(BaseModel):
    group_id: int
    user_id: int
    no_cache: bool = False


class GetGroupMemberInfoRsp(BaseModel):
    group_id: int
    user_id: int
    nickname: str
    card: str
    sex: Literal["male", "female", "unknown"]
    age: int
    area: str
    join_time: int
    last_sent_time: int
    level: str
    role: str
    unfriendly: bool = False
    title: str
    title_expire_time: int = -1
    card_changeable: bool = True


class GetGroupMemberListData(BaseModel):
    group_id: int


class GetGroupMemberListRsp(RootModel[list[GetGroupMemberInfoRsp]]):
    ...


class GetStatusData(BaseModel):
    ...


class GetVersionInfoData(BaseModel):
    ...


class GetVersionInfoRsp(BaseModel):
    app_name: str = NAME
    app_version: str = VERSION
    protocol_version: str = "v11"
