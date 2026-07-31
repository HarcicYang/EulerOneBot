import pytest
from pydantic import TypeAdapter, ValidationError

from euleronebot.onebot.segments import (
    At,
    Face,
    Forward,
    Image,
    Json,
    MarketFace,
    Node,
    Poke,
    Record,
    Reply,
    SegmentUnion,
    Text,
    Video,
)

segment_adapter = TypeAdapter(SegmentUnion)

CASES = [
    (Text, {"text": "hello"}),
    (At, {"qq": "12345"}),
    (Reply, {"id": "42"}),
    (Face, {"id": "1"}),
    (Poke, {"id": "1", "type": "1"}),
    (MarketFace, {"face_id": "a", "tab_id": "1", "name": "x"}),
    (
        Node,
        {"user_id": "1", "nick_name": "n", "content": [{"type": "text", "data": {"text": "hi"}}]},
    ),
    (Forward, {"id": "resid1", "content": []}),
    (Image, {"file": "abc.png", "summary": "img", "is_emoji": False}),
    (Record, {"file": "a.wav"}),
    (Video, {"file": "a.mp4"}),
    (Json, {"data": '{"k": 1}'}),
]


@pytest.mark.parametrize("seg_cls,data", CASES, ids=[c[0].__name__ for c in CASES])
def test_segment_roundtrip(seg_cls, data):
    seg = seg_cls(data=data)
    dumped = seg.model_dump()
    restored = segment_adapter.validate_python(dumped)
    assert restored == seg


def test_segment_union_serializes_as_cqcode_style_json():
    seg = Text(data={"text": "hi"})
    assert seg.model_dump() == {"type": "text", "data": {"text": "hi"}}


def test_unknown_segment_type_rejected():
    with pytest.raises(ValidationError):
        segment_adapter.validate_python({"type": "unknown", "data": {}})


def test_node_holds_nested_segments():
    node = segment_adapter.validate_python(
        {
            "type": "node",
            "data": {
                "user_id": "1",
                "nick_name": "n",
                "content": [{"type": "text", "data": {"text": "hi"}}],
            },
        }
    )
    assert node.data.content[0] == Text(data={"text": "hi"})
