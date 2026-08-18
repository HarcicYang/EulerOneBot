import asyncio
import hashlib
import json
import os
import pickle
import random
import sqlite3
import traceback
from functools import partial
from typing import TYPE_CHECKING, Any, Literal, Self

import aiosqlite
from lagrange import Client
from pydantic import BaseModel

from ..hyperogger import Logger
from . import with_retry

if TYPE_CHECKING:
    from lagrange.client.message.types import Element
else:
    Element = Any


logger = Logger.fetch("euler").name_custom("euler.utils.infomgr")

_DB_FILE = "euleronebot.db"
_CACHE_FILE = "cache.json"


class MsgInfo(BaseModel):
    scene_type: Literal["group", "user"]
    scene_id: int
    uin: int = 0
    uid: str = ""
    timestamp: int = 0
    raw_msg: list[Element] = []
    seq: int
    rand: int = 0
    text: str = ""

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MsgInfo):
            raise NotImplementedError()
        return other.scene_type == self.scene_type and other.scene_id == self.scene_id and other.seq == self.seq


def _dump_raw(raw: list[Element]) -> bytes | None:
    if not raw:
        return None
    return pickle.dumps(raw, protocol=pickle.HIGHEST_PROTOCOL)


def _load_raw(blob: bytes | None) -> list[Element]:
    if not blob:
        return []
    try:
        return pickle.loads(blob)
    except Exception:
        logger.warning("消息原文无法解析,已丢弃")
        return []


class MsgIDPool:
    def __init__(self, mgr: "InfoManager"):
        self._mgr = mgr

    @property
    def db(self) -> aiosqlite.Connection:
        return self._mgr.require_db()

    @staticmethod
    def _gen_id(info: MsgInfo) -> int:
        key = f"{info.scene_type}_{info.scene_id}_{info.seq}".encode()
        x = hashlib.sha1(key).digest()
        return int.from_bytes(x[-4:], "big", signed=False)

    async def add(self, info: MsgInfo) -> int:
        nid = self._gen_id(info)
        await self.db.execute(
            "INSERT OR IGNORE INTO messages "
            "(message_id, scene_type, scene_id, uin, uid, timestamp, seq, rand, text, raw) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                nid,
                info.scene_type,
                info.scene_id,
                info.uin,
                info.uid,
                info.timestamp,
                info.seq,
                info.rand,
                info.text,
                _dump_raw(info.raw_msg),
            ),
        )
        await self.db.commit()
        return nid

    async def fetch(self, nid: int) -> MsgInfo:
        cur = await self.db.execute("SELECT * FROM messages WHERE message_id = ?", (nid,))
        row = await cur.fetchone()
        if row is None:
            raise KeyError(f"Unknown message_id = {nid}")
        return self._row_to_info(row)

    async def search(self, info: MsgInfo) -> int:
        cur = await self.db.execute(
            "SELECT message_id FROM messages "
            "WHERE scene_type = ? AND scene_id = ? AND seq = ? "
            "ORDER BY message_id DESC LIMIT 1",
            (info.scene_type, info.scene_id, info.seq),
        )
        row = await cur.fetchone()
        return int(row[0]) if row else 0

    @staticmethod
    def _row_to_info(row: sqlite3.Row) -> MsgInfo:
        return MsgInfo(
            scene_type=row["scene_type"],
            scene_id=row["scene_id"],
            uin=row["uin"],
            uid=row["uid"],
            timestamp=row["timestamp"],
            seq=row["seq"],
            rand=row["rand"],
            text=row["text"],
            raw_msg=_load_raw(row["raw"]),
        )


class UIDPool:
    def __init__(self, mgr: "InfoManager"):
        self._mgr = mgr

    @property
    def db(self) -> aiosqlite.Connection:
        return self._mgr.require_db()

    async def add(self, uid: str | bytes, uin: int) -> int:
        if isinstance(uid, bytes):
            uid = uid.decode()
        await self.db.execute(
            "INSERT OR REPLACE INTO uid_map (uid, uin, fake) VALUES (?, ?, 0)",
            (uid, uin),
        )
        await self.db.commit()
        return uin

    async def add_fake(self, uid: str) -> int:
        while True:
            x = random.randint(1 << 15, (1 << 16) - 1)
            uin = int(str(x) + "0145")
            if not await self.is_exist(uin):
                break
        await self.db.execute(
            "INSERT OR REPLACE INTO uid_map (uid, uin, fake) VALUES (?, ?, 1)",
            (uid, uin),
        )
        await self.db.commit()
        return uin

    async def load_all_grps(self, client: Client) -> int:
        count = 0
        grps = (await with_retry(client.get_grp_list)).grp_list
        for i in grps:
            try:
                mbrs = await with_retry(partial(client.get_grp_members, i.grp_id))
                mbr_list = mbrs.body
                next_key = mbrs.next_key
                while next_key:
                    mbrs = await with_retry(partial(client.get_grp_members, i.grp_id, next_key.decode()))
                    mbr_list += mbrs.body
                    next_key = mbrs.next_key
                for j in mbr_list:
                    if j.account.uin == i.grp_id:
                        continue
                    if j.account.uin and not (
                        await self.is_exist(j.account.uid) and await self.is_exist(j.account.uin)
                    ):
                        await self.add(j.account.uid, j.account.uin)
                        count += 1
            except Exception:
                logger.warning(f"群 {i.grp_id} 成员列表加载失败,已跳过")
                logger.trace(traceback.format_exc())

        return count

    async def load_all_users(self, client: Client) -> int:
        count = 0
        users = await with_retry(client.get_friend_list)
        for i in users:
            if i.uid and not (await self.is_exist(i.uid) and await self.is_exist(i.uin)):
                await self.add(i.uid, i.uin)
                count += 1

        return count

    async def load_all(self, client: Client) -> None:
        t1 = asyncio.create_task(self.load_all_users(client))
        t2 = asyncio.create_task(self.load_all_grps(client))
        results = await asyncio.gather(t1, t2, return_exceptions=True)
        c1 = results[0] if not isinstance(results[0], BaseException) else 0
        c2 = results[1] if not isinstance(results[1], BaseException) else 0
        for r in results:
            if isinstance(r, BaseException) and not isinstance(r, asyncio.CancelledError):
                logger.error(f"load_all 子任务异常: {r!r}")
        count = c1 + c2
        if count != 0:
            logger.info(f"Newly cached {count} user(s)")

    async def from_uid(self, uid: str | bytes) -> int:
        if isinstance(uid, bytes):
            uid = uid.decode()
        cur = await self.db.execute("SELECT uin FROM uid_map WHERE uid = ?", (uid,))
        row = await cur.fetchone()
        if row is None:
            raise ValueError(f"Unknown uid = {uid}")
        return int(row[0])

    async def from_uin(self, uin: int) -> str:
        cur = await self.db.execute("SELECT uid FROM uid_map WHERE uin = ?", (uin,))
        row = await cur.fetchone()
        if row is None:
            raise ValueError(f"Unknown uin = {uin}")
        return str(row[0])

    async def is_exist(self, uid_or_uin: int | str | bytes) -> bool:
        if isinstance(uid_or_uin, bytes):
            uid_or_uin = uid_or_uin.decode()
        if isinstance(uid_or_uin, str):
            cur = await self.db.execute("SELECT fake FROM uid_map WHERE uid = ?", (uid_or_uin,))
            row = await cur.fetchone()
            return bool(row and not row["fake"])
        cur = await self.db.execute("SELECT 1 FROM uid_map WHERE uin = ? LIMIT 1", (uid_or_uin,))
        row = await cur.fetchone()
        return row is not None


class RequestInfo(BaseModel):
    type: Literal["friend", "group"] = "group"
    id: int
    seq: int
    ev_type: int


class RequestPool:
    def __init__(self, mgr: "InfoManager"):
        self._mgr = mgr

    @property
    def db(self) -> aiosqlite.Connection:
        return self._mgr.require_db()

    async def _get_flag(self) -> str:
        while True:
            x = random.randint(1 << 15, (1 << 18) - 1)
            flag = str(x)
            cur = await self.db.execute("SELECT 1 FROM requests WHERE flag = ?", (flag,))
            if await cur.fetchone() is None:
                return flag

    async def set_group(self, grp_id: int, seq: int, ev_type: int) -> str:
        flag = await self._get_flag()
        await self.db.execute(
            "INSERT INTO requests (flag, type, id, seq, ev_type) VALUES (?, 'group', ?, ?, ?)",
            (flag, grp_id, seq, ev_type),
        )
        await self.db.commit()
        return flag

    async def has(self, info: RequestInfo) -> bool:
        cur = await self.db.execute(
            "SELECT 1 FROM requests WHERE type = ? AND id = ? AND seq = ? AND ev_type = ? LIMIT 1",
            (info.type, info.id, info.seq, info.ev_type),
        )
        return await cur.fetchone() is not None

    async def fetch(self, flag: str) -> RequestInfo:
        cur = await self.db.execute("SELECT * FROM requests WHERE flag = ?", (flag,))
        row = await cur.fetchone()
        if row is None:
            raise ValueError(f"Unknown flag: {flag}")
        return RequestInfo(type=row["type"], id=row["id"], seq=row["seq"], ev_type=row["ev_type"])


class InfoManager:
    def __init__(self):
        self.db: aiosqlite.Connection | None = None
        self.msgid_mgr = MsgIDPool(self)
        self.uid_mgr = UIDPool(self)
        self.req_mgr = RequestPool(self)

    def require_db(self) -> aiosqlite.Connection:
        if self.db is None:
            raise RuntimeError("InfoManager 尚未初始化,请先 await info_mgr.init()")
        return self.db

    async def init(self, path: str | None = None, migrate_from: str = _CACHE_FILE) -> Self:
        if self.db is not None:
            return self
        self.db = await aiosqlite.connect(path or _DB_FILE)
        self.db.row_factory = sqlite3.Row
        await self._create_tables()
        await self._migrate_from_json(migrate_from)
        return self

    async def _create_tables(self) -> None:
        db = self.require_db()
        await db.execute(
            "CREATE TABLE IF NOT EXISTS messages ("
            "message_id INTEGER PRIMARY KEY,"
            "scene_type TEXT NOT NULL,"
            "scene_id INTEGER NOT NULL,"
            "uin INTEGER NOT NULL DEFAULT 0,"
            "uid TEXT NOT NULL DEFAULT '',"
            "timestamp INTEGER NOT NULL DEFAULT 0,"
            "seq INTEGER NOT NULL,"
            "rand INTEGER NOT NULL DEFAULT 0,"
            "text TEXT NOT NULL DEFAULT '',"
            "raw BLOB"
            ")"
        )
        await db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_scene ON messages (scene_type, scene_id, seq)")
        await db.execute(
            "CREATE TABLE IF NOT EXISTS uid_map ("
            "uid TEXT PRIMARY KEY,"
            "uin INTEGER NOT NULL,"
            "fake INTEGER NOT NULL DEFAULT 0"
            ")"
        )
        await db.execute("CREATE INDEX IF NOT EXISTS idx_uid_map_uin ON uid_map (uin)")
        await db.execute(
            "CREATE TABLE IF NOT EXISTS requests ("
            "flag TEXT PRIMARY KEY,"
            "type TEXT NOT NULL,"
            "id INTEGER NOT NULL,"
            "seq INTEGER NOT NULL,"
            "ev_type INTEGER NOT NULL"
            ")"
        )
        await db.commit()

    async def _migrate_from_json(self, cache_file: str) -> None:
        if not os.path.exists(cache_file):
            return
        db = self.require_db()
        cur = await db.execute("SELECT COUNT(*) FROM messages")
        row = await cur.fetchone()
        if row and row[0]:
            return
        try:
            with open(cache_file, encoding="utf-8") as f:
                raw = f.read()
            if not raw.strip():
                return
            data = json.loads(raw)
        except (OSError, ValueError):
            logger.warning(f"{cache_file} 为空或已损坏,跳过迁移")
            return

        for uid, uin in (data.get("uid_mgr") or {}).get("pool", {}).items():
            fake = 1 if str(uin).endswith("0145") else 0
            await db.execute(
                "INSERT OR IGNORE INTO uid_map (uid, uin, fake) VALUES (?, ?, ?)",
                (uid, uin, fake),
            )

        # 旧 raw_msg 为无类型标记的 dict,无法还原为 Element,仅保留元数据
        for nid, info in (data.get("msgid_mgr") or {}).get("pool", {}).items():
            await db.execute(
                "INSERT OR IGNORE INTO messages "
                "(message_id, scene_type, scene_id, uin, uid, timestamp, seq, rand, text) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    int(nid),
                    info.get("scene_type"),
                    info.get("scene_id"),
                    info.get("uin", 0),
                    info.get("uid", ""),
                    info.get("timestamp", 0),
                    info.get("seq"),
                    info.get("rand", 0),
                    info.get("text", ""),
                ),
            )

        for flag, info in (data.get("req_mgr") or {}).get("pool", {}).items():
            await db.execute(
                "INSERT OR IGNORE INTO requests (flag, type, id, seq, ev_type) VALUES (?, ?, ?, ?, ?)",
                (flag, info.get("type"), info.get("id"), info.get("seq"), info.get("ev_type")),
            )

        await db.commit()
        os.replace(cache_file, f"{cache_file}.bak")
        logger.info(f"已将 {cache_file} 迁移至数据库,原文件备份为 {cache_file}.bak")

    async def close(self) -> None:
        if self.db is not None:
            await self.db.close()
            self.db = None


info_mgr = InfoManager()
