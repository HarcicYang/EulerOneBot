import asyncio
import json
from typing import Any, Literal, cast

import pytest

from euleronebot.utils.infomgr import InfoManager, MsgInfo, RequestInfo


def run(coro):
    return asyncio.run(coro)


_MANAGERS: list[InfoManager] = []


@pytest.fixture(autouse=True)
def close_managers():
    yield
    for manager in _MANAGERS:
        run(manager.close())
    _MANAGERS.clear()


def make_mgr() -> InfoManager:
    mgr = InfoManager()
    _MANAGERS.append(mgr)
    return mgr


def make_msg(scene_type: Literal["group", "user"] = "group", scene_id: int = 1, seq: int = 1, **kw) -> MsgInfo:
    return MsgInfo(scene_type=scene_type, scene_id=scene_id, seq=seq, **kw)


async def new_mgr(tmp_path) -> InfoManager:
    mgr = make_mgr()
    await mgr.init(path=str(tmp_path / "test.db"), migrate_from=str(tmp_path / "cache.json"))
    return mgr


def test_msgid_pool_deduplicates_persists_and_roundtrips_raw_messages(tmp_path):
    from lagrange.client.message import elems

    async def main():
        db = str(tmp_path / "test.db")
        mgr = make_mgr()
        await mgr.init(path=db, migrate_from=str(tmp_path / "cache.json"))
        raw = [elems.Text(text="hi"), elems.MarketFace(name="f", face_id=b"\xaa\xbb", tab_id=1, width=1, height=1)]
        info = make_msg(scene_id=42, seq=7, raw_msg=raw)

        nid = await mgr.msgid_mgr.add(info)
        duplicate = await mgr.msgid_mgr.add(info)
        other = await mgr.msgid_mgr.add(make_msg(scene_id=42, seq=8))
        fetched = await mgr.msgid_mgr.fetch(nid)

        assert duplicate == nid
        assert other != nid
        assert await mgr.msgid_mgr.search(make_msg(scene_id=42, seq=7)) == nid
        assert await mgr.msgid_mgr.search(make_msg(scene_id=42, seq=999)) == 0
        assert isinstance(fetched.raw_msg[0], elems.Text)
        assert fetched.raw_msg[0].text == "hi"
        assert isinstance(fetched.raw_msg[1], elems.MarketFace)
        assert fetched.raw_msg[1].face_id == b"\xaa\xbb"

        with pytest.raises(KeyError):
            await mgr.msgid_mgr.fetch(123456)

        await mgr.close()
        restarted = make_mgr()
        await restarted.init(path=db, migrate_from=str(tmp_path / "cache.json"))
        assert await restarted.msgid_mgr.add(info) == nid
        restored = await restarted.msgid_mgr.fetch(nid)
        assert cast(Any, restored.raw_msg[0]).text == "hi"

    run(main())


def test_uid_pool_maps_uid_and_uin_and_distinguishes_fake_entries(tmp_path):
    async def main():
        mgr = await new_mgr(tmp_path)
        await mgr.uid_mgr.add(b"u_bytes", 10002)
        await mgr.uid_mgr.add("u_real", 10001)

        assert await mgr.uid_mgr.from_uid("u_real") == 10001
        assert await mgr.uid_mgr.from_uid(b"u_bytes") == 10002
        assert await mgr.uid_mgr.from_uin(10001) == "u_real"
        assert await mgr.uid_mgr.is_exist("u_real") is True
        assert await mgr.uid_mgr.is_exist(10001) is True

        await mgr.uid_mgr.add("u_real", 20001)
        assert await mgr.uid_mgr.from_uid("u_real") == 20001

        fake_uin = await mgr.uid_mgr.add_fake("u_fake")
        assert str(fake_uin).endswith("0145")
        assert await mgr.uid_mgr.from_uid("u_fake") == fake_uin
        assert await mgr.uid_mgr.is_exist("u_fake") is False
        assert await mgr.uid_mgr.is_exist(fake_uin) is True

        with pytest.raises(ValueError):
            await mgr.uid_mgr.from_uid("missing")
        with pytest.raises(ValueError):
            await mgr.uid_mgr.from_uin(999999)

    run(main())


def test_request_pool_roundtrips_flags_and_reports_unknown_requests(tmp_path):
    async def main():
        mgr = await new_mgr(tmp_path)
        flag = await mgr.req_mgr.set_group(grp_id=100, seq=200, ev_type=1)
        info = await mgr.req_mgr.fetch(flag)

        assert info == RequestInfo(type="group", id=100, seq=200, ev_type=1)
        assert await mgr.req_mgr.has(info) is True
        assert await mgr.req_mgr.has(RequestInfo(type="group", id=1, seq=2, ev_type=3)) is False
        with pytest.raises(ValueError):
            await mgr.req_mgr.fetch("no-such-flag")

    run(main())


def _write_legacy_cache(tmp_path) -> str:
    data = {
        "uid_mgr": {"pool": {"u_real": 10001, "u_fake": 2000145}},
        "msgid_mgr": {
            "pool": {
                "12345": {
                    "scene_type": "group",
                    "scene_id": 100,
                    "uin": 10001,
                    "uid": "u_real",
                    "timestamp": 1000,
                    "seq": 5,
                    "rand": 7,
                    "text": "hello",
                }
            }
        },
        "req_mgr": {"pool": {"999": {"type": "group", "id": 100, "seq": 200, "ev_type": 1}}},
    }
    path = tmp_path / "cache.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def test_legacy_cache_migration_imports_all_pools_and_backs_up_file(tmp_path):
    async def main():
        cache = _write_legacy_cache(tmp_path)
        mgr = make_mgr()
        await mgr.init(path=str(tmp_path / "test.db"), migrate_from=cache)

        assert await mgr.uid_mgr.from_uid("u_real") == 10001
        assert await mgr.uid_mgr.is_exist("u_fake") is False
        info = await mgr.msgid_mgr.fetch(12345)
        assert (info.scene_id, info.seq, info.text, info.raw_msg) == (100, 5, "hello", [])
        request = await mgr.req_mgr.fetch("999")
        assert (request.id, request.seq, request.ev_type) == (100, 200, 1)
        assert not (tmp_path / "cache.json").exists()
        assert (tmp_path / "cache.json.bak").exists()

    run(main())


def test_corrupt_legacy_cache_is_left_untouched(tmp_path):
    async def main():
        path = tmp_path / "cache.json"
        path.write_text("not-json{{{", encoding="utf-8")
        mgr = make_mgr()
        await mgr.init(path=str(tmp_path / "test.db"), migrate_from=str(path))

        assert await mgr.msgid_mgr.search(make_msg(seq=1)) == 0
        assert path.exists()

    run(main())


def test_migration_does_not_overwrite_existing_database(tmp_path):
    async def main():
        db = str(tmp_path / "test.db")
        mgr = make_mgr()
        await mgr.init(path=db, migrate_from=str(tmp_path / "missing.json"))
        await mgr.msgid_mgr.add(make_msg(seq=1))
        await mgr.close()

        cache = _write_legacy_cache(tmp_path)
        restarted = make_mgr()
        await restarted.init(path=db, migrate_from=cache)

        with pytest.raises(KeyError):
            await restarted.msgid_mgr.fetch(12345)
        assert await restarted.msgid_mgr.search(make_msg(seq=1)) != 0
        assert (tmp_path / "cache.json").exists()

    run(main())
