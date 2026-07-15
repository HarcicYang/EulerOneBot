from pydantic import BaseModel
from typing import TypeVar, Generic, Literal, Optional

from .api_data import *

DataType = TypeVar('DataType')
ResponseType = TypeVar('ResponseType')

__all__ = [
    "BaseAPICall",
    "BaseAPIResponse",
    "SendPrivateMessage",
    "SendPrivateMsgData",
    "SendPrivateMessageResponse",
    "SendGroupMessage",
    "SendGroupMsgData",
    "SendGroupMessageResponse",
    "SendMessage",
    "SendMessageResponse",
    "DeleteMessage",
    "DeleteMessageResponse",
    "GetMessage",
    "GetMessageResponse",
    "GetForwardMessage",
    "GetForwardMessageResponse",
    "SendLike",
    "SendLikeResponse",
    "SetGroupKick",
    "SetGroupKickResponse",
    "SetGroupBan",
    "SetGroupBanResponse",
    "SetGroupWholeBan",
    "SetGroupWholeBanResponse",
    "SetGroupAdmin",
    "SetGroupAdminResponse",
    "SetGroupCard",
    "SetGroupCardResponse",
    "SetGroupName",
    "SetGroupNameResponse",
    "SetGroupLeave",
    "SetGroupLeaveResponse",
    "SetGroupSpecialTitle",
    "SetGroupSpecialTitleResponse",
    "SetFriendAddRequest",
    "SetFriendAddRequestResponse",
    "SetGroupAddRequest",
    "SetGroupAddRequestResponse",
    "GetLoginInfo",
    "GetLoginInfoResponse",
    "GetStrangerInfo",
    "GetStrangerInfoResponse",
    "GetFriendList",
    "GetFriendListResponse",
    "GetGroupInfo",
    "GetGroupInfoResponse",
    "GetGroupList",
    "GetGroupListResponse",
    "GetGroupMemberInfo",
    "GetGroupMemberInfoResponse",
    "GetGroupMemberList",
    "GetGroupMemberListResponse",
    "GetStatus",
    "GetStatusResponse",
    "GetVersionInfo",
    "GetVersionInfoResponse",
    "ActionFailedResponse"
]


class BaseAPICall(BaseModel, Generic[DataType]):
    action: str
    params: DataType
    echo: str = ""


class BaseAPIResponse(BaseModel, Generic[ResponseType]):
    status: Literal["ok", "failed"]
    retcode: int
    data: Optional[ResponseType]
    echo: str = ""


class SendPrivateMessage(BaseAPICall[SendPrivateMsgData]):
    action: Literal["send_private_msg"] = "send_private_msg"


class SendPrivateMessageResponse(BaseAPIResponse[SendMsgRsp]):
    ...


class SendGroupMessage(BaseAPICall[SendGroupMsgData]):
    action: Literal["send_group_msg"] = "send_group_msg"


class SendGroupMessageResponse(BaseAPIResponse[SendMsgRsp]):
    ...


class SendMessage(BaseAPICall[SendMsgData]):
    action: Literal["send_msg"] = "send_msg"


class SendMessageResponse(BaseAPIResponse[SendMsgRsp]):
    ...


class DeleteMessage(BaseAPICall[DeleteMsgData]):
    action: Literal["delete_msg"] = "delete_msg"


class DeleteMessageResponse(BaseAPIResponse[EmptyRsp]):
    ...


class GetMessage(BaseAPICall[GetMsgData]):
    action: Literal["get_msg"] = "get_msg"


class GetMessageResponse(BaseAPIResponse[GetMsgRsp]):
    ...


class GetForwardMessage(BaseAPICall[GetForwardMsgData]):
    action: Literal["get_forward_msg"] = "get_forward_msg"


class GetForwardMessageResponse(BaseAPIResponse[GetForwardMsgRsp]):
    ...


class SendLike(BaseAPICall[SendLikeData]):
    action: Literal["send_like"] = "send_like"


class SendLikeResponse(BaseAPIResponse[EmptyRsp]):
    ...


class SetGroupKick(BaseAPICall[SetGroupKickData]):
    action: Literal["set_group_kick"] = "set_group_kick"


class SetGroupKickResponse(BaseAPIResponse[EmptyRsp]):
    ...


class SetGroupBan(BaseAPICall[SetGroupBanData]):
    action: Literal["set_group_ban"] = "set_group_ban"


class SetGroupBanResponse(BaseAPIResponse[EmptyRsp]):
    ...


class SetGroupWholeBan(BaseAPICall[SetGroupWholeBanData]):
    action: Literal["set_group_whole_ban"] = "set_group_whole_ban"


class SetGroupWholeBanResponse(BaseAPIResponse[EmptyRsp]):
    ...


class SetGroupAdmin(BaseAPICall[SetGroupAdminData]):
    action: Literal["set_group_admin"] = "set_group_admin"


class SetGroupAdminResponse(BaseAPIResponse[EmptyRsp]):
    ...


class SetGroupCard(BaseAPICall[SetGroupCardData]):
    action: Literal["set_group_card"] = "set_group_card"


class SetGroupCardResponse(BaseAPIResponse[EmptyRsp]):
    ...


class SetGroupName(BaseAPICall[SetGroupNameData]):
    action: Literal["set_group_name"] = "set_group_name"


class SetGroupNameResponse(BaseAPIResponse[EmptyRsp]):
    ...


class SetGroupLeave(BaseAPICall[SetGroupLeaveData]):
    action: Literal["set_group_leave"] = "set_group_leave"


class SetGroupLeaveResponse(BaseAPIResponse[EmptyRsp]):
    ...


class SetGroupSpecialTitle(BaseAPICall[SetGroupSpecialTitleData]):
    action: Literal["set_group_special_title"] = "set_group_special_title"


class SetGroupSpecialTitleResponse(BaseAPIResponse[EmptyRsp]):
    ...


class SetFriendAddRequest(BaseAPICall[SetFriendAddRequestData]):
    action: Literal["set_friend_add_request"] = "set_friend_add_request"


class SetFriendAddRequestResponse(BaseAPIResponse[EmptyRsp]):
    ...


class SetGroupAddRequest(BaseAPICall[SetGroupAddRequestData]):
    action: Literal["set_group_add_request"] = "set_group_add_request"


class SetGroupAddRequestResponse(BaseAPIResponse[EmptyRsp]):
    ...


class GetLoginInfo(BaseAPICall[GetLoginInfoData]):
    action: Literal["get_login_info"] = "get_login_info"


class GetLoginInfoResponse(BaseAPIResponse[GetLoginInfoRsp]):
    ...


class GetStrangerInfo(BaseAPICall[GetStrangerInfoData]):
    action: Literal["get_stranger_info"] = "get_stranger_info"


class GetStrangerInfoResponse(BaseAPIResponse[GetStrangerInfoRsp]):
    ...


class GetFriendList(BaseAPICall[GetFriendListData]):
    action: Literal["get_friend_list"] = "get_friend_list"


class GetFriendListResponse(BaseAPIResponse[GetFriendListRsp]):
    ...


class GetGroupInfo(BaseAPICall[GetGroupInfoData]):
    action: Literal["get_group_info"] = "get_group_info"


class GetGroupInfoResponse(BaseAPIResponse[GetGroupInfoRsp]):
    ...


class GetGroupList(BaseAPICall[GetGroupListData]):
    action: Literal["get_group_list"] = "get_group_list"


class GetGroupListResponse(BaseAPIResponse[GetGroupListRsp]):
    ...


class GetGroupMemberInfo(BaseAPICall[GetGroupMemberInfoData]):
    action: Literal["get_group_member_info"] = "get_group_member_info"


class GetGroupMemberInfoResponse(BaseAPIResponse[GetGroupMemberInfoRsp]):
    ...


class GetGroupMemberList(BaseAPICall[GetGroupMemberListData]):
    action: Literal["get_group_member_list"] = "get_group_member_list"


class GetGroupMemberListResponse(BaseAPIResponse[GetGroupMemberListRsp]):
    ...


class GetStatus(BaseAPICall[GetStatusData]):
    action: Literal["get_status"] = "get_status"


class GetStatusResponse(BaseAPIResponse[EmptyRsp]):
    ...


class GetVersionInfo(BaseAPICall[GetVersionInfoData]):
    action: Literal["get_version_info"] = "get_version_info"


class GetVersionInfoResponse(BaseAPIResponse[GetVersionInfoRsp]):
    ...

class ActionFailedResponse(BaseAPIResponse[EmptyRsp]):
    ...
