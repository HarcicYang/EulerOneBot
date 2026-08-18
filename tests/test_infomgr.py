import asyncio
import json
from typing import Literal

import pytest

from euleronebot.utils.infomgr import InfoManager, MsgInfo, RequestInfo


def run(coro):
    return asyncio.run(coro)


_MANAGERS: list[InfoManager] = []


@pytest.fixture(autouse=True)
def close_managers():
    yield
    for m in _MANAGERS:
        run(m.close())
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


class TestMsgIDPool:
    def test_add_and_fetch(self, tmp_path):
        async def main():
            mgr = await new_mgr(tmp_path)
            info = make_msg(seq=10)
            nid = await mgr.msgid_mgr.add(info)
            assert isinstance(nid, int)
            assert await mgr.msgid_mgr.fetch(nid) == info

        run(main())

    def test_fetch_unknown_raises(self, tmp_path):
        async def main():
            mgr = await new_mgr(tmp_path)
            with pytest.raises(KeyError):
                await mgr.msgid_mgr.fetch(123456)

        run(main())

    def test_search_hit(self, tmp_path):
        async def main():
            mgr = await new_mgr(tmp_path)
            info = make_msg(seq=10)
            nid = await mgr.msgid_mgr.add(info)
            assert await mgr.msgid_mgr.search(info) == nid

        run(main())

    def test_search_miss_returns_zero(self, tmp_path):
        async def main():
            mgr = await new_mgr(tmp_path)
            assert await mgr.msgid_mgr.search(make_msg(seq=999)) == 0

        run(main())

    def test_duplicate_add_returns_same_id(self, tmp_path):
        async def main():
            mgr = await new_mgr(tmp_path)
            first = await mgr.msgid_mgr.add(make_msg(seq=7))
            again = await mgr.msgid_mgr.add(make_msg(seq=7))
            assert first == again
            assert await mgr.msgid_mgr.search(make_msg(seq=7)) == first

        run(main())

    def test_different_seq_different_id(self, tmp_path):
        async def main():
            mgr = await new_mgr(tmp_path)
            a = await mgr.msgid_mgr.add(make_msg(seq=7))
            b = await mgr.msgid_mgr.add(make_msg(seq=8))
            assert a != b

        run(main())

    def test_stable_id_across_restart(self, tmp_path):
        async def main():
            db = str(tmp_path / "test.db")
            mgr = make_mgr()
            await mgr.init(path=db, migrate_from=str(tmp_path / "cache.json"))
            nid = await mgr.msgid_mgr.add(make_msg(scene_id=42, seq=7))
            await mgr.close()
            mgr2 = make_mgr()
            await mgr2.init(path=db, migrate_from=str(tmp_path / "cache.json"))
            nid2 = await mgr2.msgid_mgr.add(make_msg(scene_id=42, seq=7))
            assert nid == nid2

        run(main())

    def test_raw_msg_pickle_roundtrip(self, tmp_path):
        from lagrange.client.message import elems

        async def main():
            mgr = await new_mgr(tmp_path)
            raw = [elems.Text(text="hi"), elems.MarketFace(name="f", face_id=b"\xaa\xbb", tab_id=1, width=1, height=1)]
            nid = await mgr.msgid_mgr.add(make_msg(seq=3, raw_msg=raw))
            fetched = await mgr.msgid_mgr.fetch(nid)
            assert isinstance(fetched.raw_msg[0], elems.Text)
            assert fetched.raw_msg[0].text == "hi"
            assert isinstance(fetched.raw_msg[1], elems.MarketFace)
            assert fetched.raw_msg[1].face_id == b"\xaa\xbb"

        run(main())


class TestUIDPool:
    def test_add_and_from_uid(self, tmp_path):
        async def main():
            mgr = await new_mgr(tmp_path)
            await mgr.uid_mgr.add("u_abc", 10001)
            assert await mgr.uid_mgr.from_uid("u_abc") == 10001

        run(main())

    def test_add_bytes_uid(self, tmp_path):
        async def main():
            mgr = await new_mgr(tmp_path)
            await mgr.uid_mgr.add(b"u_byte", 10002)
            assert await mgr.uid_mgr.from_uid("u_byte") == 10002

        run(main())

    def test_from_uid_unknown_raises(self, tmp_path):
        async def main():
            mgr = await new_mgr(tmp_path)
            with pytest.raises(ValueError):
                await mgr.uid_mgr.from_uid("u_none")

        run(main())

    def test_from_uin(self, tmp_path):
        async def main():
            mgr = await new_mgr(tmp_path)
            await mgr.uid_mgr.add("u_abc", 10001)
            assert await mgr.uid_mgr.from_uin(10001) == "u_abc"

        run(main())

    def test_from_uin_unknown_raises(self, tmp_path):
        async def main():
            mgr = await new_mgr(tmp_path)
            with pytest.raises(ValueError):
                await mgr.uid_mgr.from_uin(99999)

        run(main())

    def test_is_exist_uid_and_uin(self, tmp_path):
        async def main():
            mgr = await new_mgr(tmp_path)
            await mgr.uid_mgr.add("u_abc", 10001)
            assert await mgr.uid_mgr.is_exist("u_abc")
            assert await mgr.uid_mgr.is_exist(10001)
            assert not await mgr.uid_mgr.is_exist("u_none")

        run(main())

    def test_is_exist_fake_uid_returns_false(self, tmp_path):
        async def main():
            mgr = await new_mgr(tmp_path)
            fake_uin = await mgr.uid_mgr.add_fake("u_fake")
            assert await mgr.uid_mgr.is_exist("u_fake") is False
            assert await mgr.uid_mgr.from_uid("u_fake") == fake_uin

        run(main())

    def test_add_fake_uin_ends_with_0145(self, tmp_path):
        async def main():
            mgr = await new_mgr(tmp_path)
            uin = await mgr.uid_mgr.add_fake("u_fake")
            assert str(uin).endswith("0145")

        run(main())

    def test_add_overwrites_existing(self, tmp_path):
        async def main():
            mgr = await new_mgr(tmp_path)
            await mgr.uid_mgr.add("u_abc", 10001)
            await mgr.uid_mgr.add("u_abc", 10002)
            assert await mgr.uid_mgr.from_uid("u_abc") == 10002

        run(main())


class TestRequestPool:
    def test_set_and_fetch(self, tmp_path):
        async def main():
            mgr = await new_mgr(tmp_path)
            flag = await mgr.req_mgr.set_group(grp_id=100, seq=200, ev_type=1)
            info = await mgr.req_mgr.fetch(flag)
            assert info.type == "group"
            assert info.id == 100
            assert info.seq == 200

        run(main())

    def test_fetch_unknown_raises(self, tmp_path):
        async def main():
            mgr = await new_mgr(tmp_path)
            with pytest.raises(ValueError):
                await mgr.req_mgr.fetch("no-such-flag")

        run(main())

    def test_has(self, tmp_path):
        async def main():
            mgr = await new_mgr(tmp_path)
            flag = await mgr.req_mgr.set_group(grp_id=100, seq=200, ev_type=1)
            info = await mgr.req_mgr.fetch(flag)
            assert await mgr.req_mgr.has(info)
            assert not await mgr.req_mgr.has(RequestInfo(type="group", id=1, seq=2, ev_type=3))

        run(main())


class TestMigration:
    @staticmethod
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

    def test_migrate_imports_all_pools(self, tmp_path):
        async def main():
            cache = self._write_legacy_cache(tmp_path)
            mgr = make_mgr()
            await mgr.init(path=str(tmp_path / "test.db"), migrate_from=cache)
            assert await mgr.uid_mgr.from_uid("u_real") == 10001
            assert await mgr.uid_mgr.is_exist("u_fake") is False
            nid = await mgr.msgid_mgr.search(make_msg(scene_id=100, seq=5))
            assert nid == 12345
            info = await mgr.msgid_mgr.fetch(nid)
            assert info.text == "hello"
            assert info.raw_msg == []
            flag = await mgr.req_mgr.set_group(grp_id=100, seq=200, ev_type=1)
            assert flag != "999"

        run(main())

    def test_migrate_backs_up_legacy_file(self, tmp_path):
        async def main():
            cache = self._write_legacy_cache(tmp_path)
            mgr = make_mgr()
            await mgr.init(path=str(tmp_path / "test.db"), migrate_from=cache)
            assert not (tmp_path / "cache.json").exists()
            assert (tmp_path / "cache.json.bak").exists()

        run(main())

    def test_corrupt_legacy_file_skipped(self, tmp_path):
        async def main():
            path = tmp_path / "cache.json"
            path.write_text("not-json{{{", encoding="utf-8")
            mgr = make_mgr()
            await mgr.init(path=str(tmp_path / "test.db"), migrate_from=str(path))
            assert await mgr.msgid_mgr.search(make_msg(seq=1)) == 0
            assert path.exists()

        run(main())

    def test_no_migration_without_file(self, tmp_path):
        async def main():
            mgr = await new_mgr(tmp_path)
            assert await mgr.msgid_mgr.search(make_msg(seq=1)) == 0

        run(main())

    def test_migrate_skipped_when_db_not_empty(self, tmp_path):
        async def main():
            db = str(tmp_path / "test.db")
            mgr = make_mgr()
            await mgr.init(path=db, migrate_from=str(tmp_path / "cache.json"))
            await mgr.msgid_mgr.add(make_msg(seq=1))
            await mgr.close()
            cache = self._write_legacy_cache(tmp_path)
            mgr2 = make_mgr()
            await mgr2.init(path=db, migrate_from=cache)
            assert await mgr2.msgid_mgr.search(make_msg(seq=1)) != 0
            assert (tmp_path / "cache.json").exists()

        run(main())
