from typing import Literal, TypeVar, Generic

from pydantic import BaseModel

__all__ = [
    "BaseSegmentData",
    "Text",
    "At",
    "Reply",
    "Face",
    "Poke",
    "MarketFace",
    "Node",
    "Forward",
    "Image",
    "Record",
    "Video",
]


SegmentType = TypeVar("SegmentType")


class BaseSegmentData(BaseModel):
    ...


class BaseSegment(BaseModel, Generic[SegmentType]):
    type: Literal["text", "at", "reply", "face", "poke", "mface", "node", "forward", "image", "record", "video"]
    data: SegmentType


class TextData(BaseSegmentData):
    text: str


class Text(BaseSegment[TextData]):
    type: Literal["text"] = "text"
    data: TextData


class AtData(BaseSegmentData):
    qq: str


class At(BaseSegment[AtData]):
    type: Literal["at"] = "at"
    data: AtData


class ReplyData(BaseSegmentData):
    id: str


class Reply(BaseSegment[ReplyData]):
    type: Literal["reply"] = "reply"
    data: ReplyData


class FaceData(BaseSegmentData):
    id: str


class Face(BaseSegment[FaceData]):
    type: Literal["face"] = "face"
    data: FaceData


class PokeData(BaseSegmentData):
    id: str
    type: str


class Poke(BaseSegment[PokeData]):
    type: Literal["poke"] = "poke"
    data: PokeData


class MarketFaceData(BaseSegmentData):
    face_id: str
    tab_id: str
    name: str


class MarketFace(BaseSegment[MarketFaceData]):
    type: Literal["mface"] = "mface"
    data: MarketFaceData


class NodeData(BaseSegmentData):
    user_id: str
    nickname: str
    content: list[BaseSegmentData]


class Node(BaseSegment[NodeData]):
    type: Literal["node"] = "node"
    data: NodeData


class ForwardData(BaseSegmentData):
    id: str
    content: list[Node]


class Forward(BaseSegment[ForwardData]):
    type: Literal["forward"] = "forward"
    data: ForwardData


class MediaBaseData(BaseSegmentData):
    file: str
    url: str


class ImageData(MediaBaseData):
    summary: str
    is_emoji: bool = False


class Image(BaseSegment[ImageData]):
    type: Literal["image"] = "image"
    data: ImageData


class RecordData(MediaBaseData):
    ...


class Record(BaseSegment[RecordData]):
    type: Literal["record"] = "record"
    data: RecordData


class VideoData(MediaBaseData):
    ...


class Video(BaseSegment[VideoData]):
    type: Literal["video"] = "video"
    data: VideoData
