import asyncio
import hashlib
import os.path
import random
from functools import partial
from typing import TYPE_CHECKING, Any, Literal

from lagrange import Client
from pydantic import BaseModel
from pydantic_core import PydanticSerializationError

from ..hyperogger import Logger
from . import with_retry

if TYPE_CHECKING:
    from lagrange.client.message.types import Element
else:
    Element = Any


logger = Logger.fetch("euler").name_custom("euler.utils.infomgr")


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


class MsgIDPool(BaseModel):
    pool: dict[str, MsgInfo] = {}

    def _gen_id(self, info: MsgInfo) -> int:
        key = f"{info.scene_type}_{info.scene_id}_{info.seq}_{len(list(self.pool.keys()))}".encode()
        x = hashlib.sha1(key).digest()
        return int.from_bytes(x[-4:], "big", signed=False)

    def add(self, info: MsgInfo) -> int:
        nid = self._gen_id(info)
        self.pool[str(nid)] = info
        return nid

    def fetch(self, nid: int) -> MsgInfo:
        if str(nid) in list(self.pool.keys()):
            return self.pool[str(nid)]
        else:
            raise KeyError(f"Unknown message_id = {nid} ")

    def search(self, info: MsgInfo) -> int:
        for nid, pool_info in reversed(self.pool.items()):
            if pool_info == info:
                return int(nid)
        return 0


class UIDPool(BaseModel):
    pool: dict[str, int] = {}

    def add(self, uid: str | bytes, uin: int) -> int:
        if isinstance(uid, bytes):
            uid = uid.decode()
        self.pool[uid] = uin
        return uin

    def add_fake(self, uid: str) -> int:
        x = 0
        while not x or str(x) + "0145" in list(self.pool.keys()):
            x = random.randint(1 << 15, (1 << 16) - 1)
        self.add(uid, int(str(x) + "0145"))
        return int(str(x) + "0145")

    async def load_all_grps(self, client: Client) -> int:
        count = 0
        grps = (await with_retry(client.get_grp_list)).grp_list
        for i in grps:
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
                if j.account.uin and not (self.is_exist(j.account.uid) and self.is_exist(j.account.uin)):
                    self.add(j.account.uid, j.account.uin)
                    count += 1

        return count

    async def load_all_users(self, client: Client) -> int:
        count = 0
        users = await with_retry(client.get_friend_list)
        for i in users:
            if i.uid and not (self.is_exist(i.uid) and self.is_exist(i.uin)):
                self.add(i.uid, i.uin)
                count += 1

        return count

    async def load_all(self, client: Client) -> None:
        t1 = asyncio.create_task(self.load_all_users(client))
        t2 = asyncio.create_task(self.load_all_grps(client))
        await asyncio.gather(t1, t2)
        c1 = t1.result()
        c2 = t2.result()
        count = c1 + c2
        if count != 0:
            logger.info(f"Newly cached {count} user(s)")

    def from_uid(self, uid: str | bytes) -> int:
        if isinstance(uid, bytes):
            uid = uid.decode()
        if uid in list(self.pool.keys()):
            return self.pool[uid]
        else:
            raise ValueError(f"Unknown uid = {uid}")

    def from_uin(self, uin: int) -> str:
        for uid, pool_uin in self.pool.items():
            if pool_uin == uin:
                return uid
        raise ValueError(f"Unknown uin = {uin}")

    def is_exist(self, uid_or_uin: int | str | bytes) -> bool:
        if isinstance(uid_or_uin, bytes):
            uid_or_uin = uid_or_uin.decode()
        if isinstance(uid_or_uin, str) and uid_or_uin in self.pool and str(self.from_uid(uid_or_uin)).endswith("0145"):
            return False
        return uid_or_uin in self.pool or uid_or_uin in self.pool.values()


class RequestInfo(BaseModel):
    type: Literal["friend", "group"] = "group"
    id: int
    seq: int
    ev_type: int


class RequestPool(BaseModel):
    pool: dict[str, RequestInfo] = {}

    def _get_flag(self) -> str:
        x = 0
        while not x or str(x) in list(self.pool.keys()):
            x = random.randint(1 << 15, (1 << 18) - 1)
        return str(x)

    def set_group(self, grp_id: int, seq: int, ev_type: int) -> str:
        flag = self._get_flag()
        self.pool[flag] = RequestInfo(type="group", id=grp_id, seq=seq, ev_type=ev_type)
        return flag

    def has(self, info: RequestInfo) -> bool:
        return info in list(self.pool.values())

    def fetch(self, flag: str) -> RequestInfo:
        if flag in list(self.pool.keys()):
            return self.pool[flag]
        else:
            raise ValueError(f"Unknown flag: {flag}")


class InfoManager(BaseModel):
    msgid_mgr: MsgIDPool = MsgIDPool()
    uid_mgr: UIDPool = UIDPool()
    req_mgr: RequestPool = RequestPool()

    def _dump(self) -> str:
        try:
            return self.model_dump_json(indent=2)
        except (PydanticSerializationError, TypeError, ValueError):
            logger.warning(f"{_CACHE_FILE} 包含无法序列化的消息，已清空对应消息原文")
            for msg in reversed(self.msgid_mgr.pool.values()):
                try:
                    msg.model_dump_json()
                except (PydanticSerializationError, TypeError, ValueError):
                    msg.raw_msg = []
            return self.model_dump_json(indent=2)

    async def save(self) -> None:
        self.save_sync()

    def save_sync(self) -> None:
        data = self._dump()
        tmp = f"{_CACHE_FILE}.tmp"
        with open(tmp, "w", encoding="utf-8") as f_:
            f_.write(data)
        os.replace(tmp, _CACHE_FILE)


_CACHE_FILE = "cache.json"


def _load_cache() -> InfoManager:
    if not os.path.exists(_CACHE_FILE):
        return InfoManager()
    try:
        with open(_CACHE_FILE, encoding="utf-8") as f:
            raw = f.read()
        if not raw.strip():
            return InfoManager()
        return InfoManager.model_validate_json(raw)
    except (OSError, ValueError):
        logger.warning(f"{_CACHE_FILE} 为空或已损坏，已重置")
        return InfoManager()


info_mgr = _load_cache()
if not os.path.exists(_CACHE_FILE):
    info_mgr.save_sync()
