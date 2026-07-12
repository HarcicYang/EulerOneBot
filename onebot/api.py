from pydantic import BaseModel
from typing import TypeVar, Generic, Literal, Optional, Any

from .api_data import *

DataType = TypeVar('DataType')
ResponseType = TypeVar('ResponseType')


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
    ...


class SendPrivateMessageResponse(BaseAPIResponse[SendMsgRsp]):
    ...


class SendGroupMessage(BaseAPICall[SendGroupMsgData]):
    ...


class SendGroupMessageResponse(BaseAPIResponse[SendMsgRsp]):
    ...


class SendMessage(BaseAPICall[SendMsgData]):
    ...


class SendMessageResponse(BaseAPIResponse[SendMsgRsp]):
    ...


class DeleteMessage(BaseAPICall[DeleteMsgData]):
    ...


class DeleteMessageResponse(BaseAPIResponse[EmptyRsp]):
    ...


class GetMessage(BaseAPICall[GetMsgData]):
    ...


class GetMessageResponse(BaseAPIResponse[GetMsgRsp]):
    ...


class GetForwardMessage(BaseAPICall[GetForwardMsgData]):
    ...


class GetForwardMessageResponse(BaseAPIResponse[GetForwardMsgRsp]):
    ...


class SendLike(BaseAPICall[SendLikeData]):
    ...


class SendLikeResponse(BaseAPIResponse[EmptyRsp]):
    ...


class SetGroupKick(BaseAPICall[SetGroupKickData]):
    ...


class SetGroupKickResponse(BaseAPIResponse[EmptyRsp]):
    ...


class SetGroupBan(BaseAPICall[SetGroupBanData]):
    ...


class SetGroupBanResponse(BaseAPIResponse[EmptyRsp]):
    ...


class SetGroupWholeBan(BaseAPICall[SetGroupWholeBanData]):
    ...


class SetGroupWholeBanResponse(BaseAPIResponse[EmptyRsp]):
    ...


class SetGroupAdmin(BaseAPICall[SetGroupAdminData]):
    ...


class SetGroupAdminResponse(BaseAPIResponse[EmptyRsp]):
    ...


class SetGroupCard(BaseAPICall[SetGroupCardData]):
    ...


class SetGroupCardResponse(BaseAPIResponse[EmptyRsp]):
    ...


class SetGroupName(BaseAPICall[SetGroupNameData]):
    ...


class SetGroupNameResponse(BaseAPIResponse[EmptyRsp]):
    ...


class SetGroupLeave(BaseAPICall[SetGroupLeaveData]):
    ...


class SetGroupLeaveResponse(BaseAPIResponse[EmptyRsp]):
    ...


class SetGroupSpecialTitle(BaseAPICall[SetGroupSpecialTitleData]):
    ...


class SetGroupSpecialTitleResponse(BaseAPIResponse[EmptyRsp]):
    ...


class SetFriendAddRequest(BaseAPICall[SetFriendAddRequestData]):
    ...


class SetFriendAddRequestResponse(BaseAPIResponse[EmptyRsp]):
    ...


class SetGroupAddRequest(BaseAPICall[SetGroupAddRequestData]):
    ...


class SetGroupAddRequestResponse(BaseAPIResponse[EmptyRsp]):
    ...


class GetLoginInfo(BaseAPICall[GetLoginInfoData]):
    ...


class GetLoginInfoResponse(BaseAPIResponse[GetLoginInfoRsp]):
    ...


class GetStrangerInfo(BaseAPICall[GetStrangerInfoData]):
    ...


class GetStrangerInfoResponse(BaseAPIResponse[GetStrangerInfoRsp]):
    ...


class GetFriendList(BaseAPICall[GetFriendListData]):
    ...


class GetFriendListResponse(BaseAPIResponse[GetFriendListRsp]):
    ...


class GetGroupInfo(BaseAPICall[GetGroupInfoData]):
    ...


class GetGroupInfoResponse(BaseAPIResponse[GetGroupInfoRsp]):
    ...


class GetGroupList(BaseAPICall[GetGroupListData]):
    ...


class GetGroupListResponse(BaseAPIResponse[GetGroupListRsp]):
    ...


class GetGroupMemberInfo(BaseAPICall[GetGroupMemberInfoData]):
    ...


class GetGroupMemberInfoResponse(BaseAPIResponse[GetGroupMemberInfoRsp]):
    ...


class GetGroupMemberList(BaseAPICall[GetGroupMemberListData]):
    ...


class GetGroupMemberListResponse(BaseAPIResponse[GetGroupMemberListRsp]):
    ...


class GetStatus(BaseAPICall[GetStatusData]):
    ...


class GetStatusResponse(BaseAPIResponse[EmptyRsp]):
    ...


class GetVersionInfo(BaseAPICall[GetVersionInfoData]):
    ...


class GetVersionInfoResponse(BaseAPIResponse[GetVersionInfoRsp]):
    ...
