from pydantic import BaseModel


class BaseSegment(BaseModel):
    ...


class Text(BaseSegment):
    text: str


class At(BaseSegment):
    qq: str

class Reply(BaseSegment):
    id: str

class Face(BaseSegment):
    id: str

class Poke(BaseSegment):
    id: str
    type: str

class MarketFace(BaseSegment):
    face_id: str
    tab_id: str
    name: str

class Node(BaseSegment):
    user_id: str
    nickname: str
    content: list[BaseSegment]

class Forward(BaseSegment):
    id: str
    content: list[Node]


class MediaBase(BaseSegment):
    file: str
    url: str


class Image(MediaBase):
    summary: str


class Record(MediaBase):
    ...

class Video(BaseSegment):
    ...
