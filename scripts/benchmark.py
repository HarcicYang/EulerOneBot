#!/usr/bin/env python3
"""Euler OneBot 性能基准测试。

覆盖 6 层:
  1. 模型层    —— API 请求 JSON 校验、事件序列化、消息段校验
  2. 转换层    —— to_onebot_msg / to_lagrange_msg 消息段双向转换
  3. 数据层    —— SQLite 持久化(msgid 池、uid 映射)读写
  4. 分发链路  —— Adapter 队列 + API 分发(含/不含 JSON 校验)
  5. HTTP     —— uvicorn + httpx 真实网络端到端
  6. WebSocket —— 正向 WS 请求-响应流水线与事件推送

lagrange 客户端使用 Stub 替换,不需要真实 QQ 登录,被测代码路径与线上一致。
用法:uv run python scripts/benchmark.py
"""

import asyncio
import faulthandler
import json
import math
import os
import platform
import sys
import tempfile
import time
from collections.abc import Callable
from contextlib import suppress
from functools import reduce
from types import SimpleNamespace
from typing import Any, cast

import httpx
import websockets
from lagrange.client.message import elems
from pydantic import TypeAdapter

from euleronebot.config import ForwardWebsocketConfig, HTTPConfig
from euleronebot.hyperogger import Logger
from euleronebot.onebot import API_CALL_TYPES, Adapter
from euleronebot.onebot import events as onebot_events
from euleronebot.onebot.api import SendGroupMessage, SendPrivateMessage
from euleronebot.onebot.api_data import SendGroupMsgData, SendPrivateMsgData
from euleronebot.onebot.models import TargetInfo
from euleronebot.onebot.segments import (
    At,
    AtData,
    Face,
    FaceData,
    Image,
    ImageData,
    Reply,
    ReplyData,
    SegmentUnion,
    Text,
    TextData,
)
from euleronebot.protocol.impl import LagrangeImpl
from euleronebot.utils import infomgr as im
from euleronebot.utils.transformer import to_lagrange_msg, to_onebot_msg

# ---------------------------------------------------------------- 统计工具


def pct(sorted_xs: list[float], p: float) -> float:
    if not sorted_xs:
        return 0.0
    k = (len(sorted_xs) - 1) * p
    f, c = math.floor(k), math.ceil(k)
    if f == c:
        return sorted_xs[int(k)]
    return sorted_xs[f] * (c - k) + sorted_xs[c] * (k - f)


def fmt_rt(ms: float) -> str:
    if ms >= 1000:
        return f"{ms / 1000:.2f}s"
    if ms >= 1:
        return f"{ms:.2f}ms"
    return f"{ms * 1000:.1f}µs"


def show(name: str, n: int, wall_ms: float, lat: list[float]) -> None:
    s = sorted(lat)
    print(
        f"  {name:<40}{n:>7}  {n / (wall_ms / 1000):>9.0f}/s"
        f"  avg {fmt_rt(sum(lat) / len(lat)):>9}"
        f"  p50 {fmt_rt(pct(s, 0.50)):>9}"
        f"  p95 {fmt_rt(pct(s, 0.95)):>9}"
        f"  p99 {fmt_rt(pct(s, 0.99)):>9}"
        f"  min {fmt_rt(s[0]):>9}"
        f"  max {fmt_rt(s[-1]):>9}"
    )


async def bench(
    name: str,
    n: int,
    fn: Callable[[int], Any],
    workers: int = 1,
    *,
    sync: bool = False,
) -> None:
    assert not (sync and workers > 1), "sync 基准不支持并发 worker"
    loop = asyncio.get_running_loop()
    lat: list[float] = []

    async def worker(start: int) -> None:
        for i in range(start, n, workers):
            t0 = loop.time()
            if sync:
                fn(i)
            else:
                await fn(i)
            lat.append((loop.time() - t0) * 1000)

    t0 = loop.time()
    await asyncio.gather(*(worker(s) for s in range(workers)))
    wall = (loop.time() - t0) * 1000
    show(name, n, wall, lat)


def section(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


# ---------------------------------------------------------------- Stub lagrange 客户端


class StubClient:
    uin = 10001
    uid = "u_bot"

    def __init__(self) -> None:
        self._seq = 0

    def _next(self) -> int:
        self._seq += 1
        return self._seq

    # 发消息
    async def send_grp_msg(self, grp_id: int, msg_chain: Any) -> int:
        return self._next()

    async def send_friend_msg(self, uid: str, msg_chain: Any) -> int:
        return self._next()

    async def send_grp_forward_msg(self, msg: Any, grp_id: int) -> int:
        return self._next()

    async def send_friend_forward_msg(self, msg: Any, uid: str) -> int:
        return self._next()

    # 查消息
    @staticmethod
    async def get_grp_msg(**kw: Any) -> list[Any]:
        return [SimpleNamespace(rand=1)]

    # 用户信息
    @staticmethod
    async def get_user_info(_x: Any) -> Any:
        return SimpleNamespace(
            name="stub",
            age=20,
            country="CN",
            province="GD",
            city="SZ",
            sex=SimpleNamespace(name="male"),
        )

    # 上传素材(transformer 调用)
    @staticmethod
    async def upload_grp_image(grp_id: int, image: Any) -> Any:
        return SimpleNamespace(display="[图片]")

    @staticmethod
    async def upload_friend_image(uid: str, is_emoji: bool, image: Any) -> Any:
        return SimpleNamespace(display="[图片]")

    @staticmethod
    async def upload_grp_audio(grp_id: int, voice: Any) -> Any:
        return SimpleNamespace(display="[语音]")

    @staticmethod
    async def upload_friend_audio(uid: str, voice: Any) -> Any:
        return SimpleNamespace(display="[语音]")


class StubLag:
    def __init__(self) -> None:
        self.client = StubClient()


def make_impl(adapter: Adapter) -> LagrangeImpl:
    impl = LagrangeImpl(adapter, cast(Any, StubLag()), cast(Any, None))
    impl.subscribe()
    return impl


# ---------------------------------------------------------------- 测试数据

# 1x1 PNG,base64:// 形式,避免转换基准走网络下载
_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="

LGR_TEXT_CHAIN = [elems.Text("hello world,性能测试")]

LGR_MIXED_CHAIN = [
    elems.Text("hello world,性能测试"),
    elems.At(text="@someone", uin=90000001, uid="u_90000001"),
    elems.Emoji(id=14),
    elems.Image(
        name="a.png",
        size=100,
        url="http://example.com/a.png",
        id=1,
        md5=b"\x00" * 16,
        qmsg=None,
        width=100,
        height=100,
        is_emoji=False,
        display_name="a",
    ),
    elems.Json(raw=b'{"app":"com.tencent.miniapp"}'),
]

OB_TEXT_MSG: list[SegmentUnion] = [Text(data=TextData(text="hello world,性能测试"))]

OB_MIXED_MSG: list[SegmentUnion] = [
    Text(data=TextData(text="hello ")),
    At(data=AtData(qq="90000001")),
    Face(data=FaceData(id="14")),
    Image(data=ImageData(file=f"base64://{_PNG_B64}", url="", summary="", is_emoji=False)),
]

EV_FIXTURE = onebot_events.GroupMessageEvent(
    time=1700000000,
    self_id=10001,
    message_id=12345,
    user_id=90000001,
    message=[
        Text(data=TextData(text="hi")),
        At(data=AtData(qq="90000002")),
    ],
    raw_message="hi",
    group_id=500000001,
    sender=onebot_events.GroupSender(
        user_id=90000001,
        nickname="a",
        sex="unknown",
        age=20,
        card="",
        area="",
        level="",
        role="member",
        title="",
    ),
)


def ob_dump(msg: list[SegmentUnion]) -> list[dict]:
    return [s.model_dump() for s in msg]


def group_call(i: int, echo: str) -> SendGroupMessage:
    return SendGroupMessage(params=SendGroupMsgData(group_id=500000000, message=OB_TEXT_MSG), echo=echo)


def private_call(i: int, echo: str) -> SendPrivateMessage:
    return SendPrivateMessage(
        params=SendPrivateMsgData(user_id=90000000 + (i % 1000), message=OB_TEXT_MSG),
        echo=echo,
    )


# ---------------------------------------------------------------- 各层基准


async def section_model() -> None:
    section("1. 模型层(纯 CPU)")
    api_payload = json.dumps(
        {"action": "send_group_msg", "params": {"group_id": 1, "message": ob_dump(OB_TEXT_MSG)}, "echo": ""},
        ensure_ascii=False,
    )
    validator = TypeAdapter(reduce(lambda a, b: a | b, API_CALL_TYPES))  # type: ignore

    seg_validator = TypeAdapter(list[SegmentUnion])
    seg_payload = json.dumps([s.model_dump() for s in OB_MIXED_MSG], ensure_ascii=False)

    await bench("API 请求 JSON 校验 (TypeAdapter)", 30000, lambda _: validator.validate_json(api_payload), sync=True)
    await bench("事件序列化 model_dump_json", 30000, lambda _: EV_FIXTURE.model_dump_json(), sync=True)
    await bench(
        "消息段列表校验 (list[SegmentUnion])",
        30000,
        lambda _: seg_validator.validate_json(seg_payload),
        sync=True,
    )


async def section_transform() -> None:
    section("2. 转换层(lagrange Element <-> OneBot 消息段)")
    lgrc = StubClient()

    async def onebot_text(i: int) -> None:
        await to_onebot_msg(
            adp=cast(Any, None),
            msg=im.MsgInfo(
                scene_type="group",
                scene_id=400000000 + i,
                seq=1,
                raw_msg=LGR_TEXT_CHAIN,
            ),
        )

    async def onebot_mixed(i: int) -> None:
        await to_onebot_msg(
            adp=cast(Any, None),
            msg=im.MsgInfo(
                scene_type="group",
                scene_id=400000000 + i,
                seq=1,
                raw_msg=LGR_MIXED_CHAIN,
            ),
        )

    async def onebot_quote(i: int) -> None:
        chain = [
            elems.Quote(seq=1, uin=90000001, timestamp=1700000000, uid="u_90000001", msg="原消息"),
            *LGR_MIXED_CHAIN,
        ]
        await to_onebot_msg(
            adp=cast(Any, None),
            msg=im.MsgInfo(scene_type="group", scene_id=400100000 + i, seq=1, raw_msg=chain),
        )

    async def lgr_mixed(i: int) -> None:
        await to_lagrange_msg(OB_MIXED_MSG, lgrc=cast(Any, lgrc), target=TargetInfo(target="group", id=1))

    await bench("to_onebot_msg 纯文本链", 10000, onebot_text)
    await bench("to_onebot_msg 混合链(text/at/face/image/json)", 5000, onebot_mixed)
    await bench("to_onebot_msg 含引用段(带 DB 反查)", 5000, onebot_quote)
    await bench("to_lagrange_msg 混合链(含 base64 图片上传)", 3000, lgr_mixed)


async def section_db() -> None:
    section("3. 数据层(SQLite,磁盘 /tmp)")
    mgr = im.info_mgr

    async def add_msg(i: int) -> None:
        await mgr.msgid_mgr.add(
            im.MsgInfo(
                scene_type="group",
                scene_id=400000000 + i,
                seq=1,
                timestamp=1700000000,
                text="hello",
                raw_msg=LGR_TEXT_CHAIN,
            )
        )

    async def search_msg(i: int) -> None:
        await mgr.msgid_mgr.search(im.MsgInfo(scene_type="group", scene_id=400000000 + i, seq=1))

    async def fetch_msg(i: int) -> None:
        await mgr.msgid_mgr.fetch(
            im.MsgIDPool._gen_id(im.MsgInfo(scene_type="group", scene_id=400000000 + (i % 5000), seq=1))
        )

    async def add_uid(i: int) -> None:
        await mgr.uid_mgr.add(f"f{i}", 800000000 + i)

    async def from_uin(i: int) -> None:
        await mgr.uid_mgr.from_uin(90000000 + (i % 1000))

    async def from_uid(i: int) -> None:
        await mgr.uid_mgr.from_uid(f"u_{90000000 + (i % 1000)}")

    await bench("msgid_pool.add (单条 commit + pickle)", 5000, add_msg)
    await bench("msgid_pool.search (场景+seq 索引)", 10000, search_msg)
    await bench("msgid_pool.fetch (主键查询)", 10000, fetch_msg)
    await bench("uid_pool.add (单条 commit)", 5000, add_uid)
    await bench("uid_pool.from_uin (索引查询)", 10000, from_uin)
    await bench("uid_pool.from_uid (主键查询)", 10000, from_uid)


async def section_dispatch() -> None:
    section("4. API 分发链路(Adapter 队列 -> LagrangeImpl)")
    logger = Logger.fetch("euler")
    logger.set_level("WARNING")

    def _task_died(t: asyncio.Task) -> None:
        if not t.cancelled():
            print(f"!!! api_service 异常退出: {t.exception()!r}", flush=True)

    async def queue_bench(name: str, n: int, factory: Callable[[int, str], Any]) -> None:
        adapter = Adapter(impls=[])
        impl = make_impl(adapter)
        task = asyncio.create_task(impl.api_service())
        task.add_done_callback(_task_died)
        try:

            async def one(i: int) -> None:
                echo = f"e{i}"
                fut = adapter.register_awaiter(echo)
                await adapter.api_calls.put(factory(i, echo))
                await fut

            await bench(name, n, one)
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    await queue_bench("队列分发 send_group_msg (含入库)", 3000, group_call)
    await queue_bench("队列分发 send_private_msg (含 uid 反查)", 3000, private_call)

    # 日志开销对比(默认 INFO 下每次响应打印一行)
    adapter = Adapter(impls=[])
    impl = make_impl(adapter)
    task = asyncio.create_task(impl.api_service())
    logger.set_level("INFO")
    try:

        async def one_info(i: int) -> None:
            echo = f"i{i}"
            fut = adapter.register_awaiter(echo)
            await adapter.api_calls.put(group_call(i, echo))
            await fut

        await bench("send_group_msg (INFO 日志,逐条打印)", 500, one_info)
    finally:
        logger.set_level("WARNING")
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    # 完整 JSON 链路(含 TypeAdapter 校验与 cycle 队列)
    adapter = Adapter(impls=[])
    cycle = asyncio.create_task(adapter.cycle())
    impl = make_impl(adapter)
    service = asyncio.create_task(impl.api_service())
    try:

        async def full(i: int) -> None:
            echo = f"e{i}"
            fut = adapter.register_awaiter(echo)
            payload = json.dumps(
                {
                    "action": "send_group_msg",
                    "params": {"group_id": 500000000, "message": ob_dump(OB_TEXT_MSG)},
                    "echo": echo,
                },
                ensure_ascii=False,
            )
            await adapter.connector.received.put(payload)
            await fut

        await bench("完整 JSON 链路 send_group_msg (校验+分发+入库)", 3000, full)

        async def unknown(i: int) -> None:
            echo = f"e{i}"
            fut = adapter.register_awaiter(echo)
            await adapter.connector.received.put(json.dumps({"action": "no_such_action", "params": {}, "echo": echo}))
            await fut

        await bench("未知 action 快速失败 (1404)", 3000, unknown)
    finally:
        service.cancel()
        cycle.cancel()
        with suppress(asyncio.CancelledError):
            await service
            await cycle

    # 事件触发吞吐(无连接,纯序列化+分发)
    adapter = Adapter(impls=[])
    try:
        ev = onebot_events.HeartbeatEvent(
            interval=15000,
            self_id=10001,
            status=onebot_events.BotStatus(good=True, online=True),
            time=1700000000,
        )

        async def trigger(i: int) -> None:
            await adapter.trigger(ev)

        await bench("事件触发 trigger (序列化+传输) 无连接", 10000, trigger)
    finally:
        await adapter.close()


async def section_http() -> None:
    section("5. HTTP 端到端(uvicorn + httpx 真实网络)")
    adapter = Adapter(impls=[HTTPConfig(url="http://127.0.0.1:0")])
    await adapter.setup()
    cycle = asyncio.create_task(adapter.cycle())
    impl = make_impl(adapter)
    service = asyncio.create_task(impl.api_service())
    conn = asyncio.create_task(adapter.connector.run())
    for _ in range(400):
        if adapter.connector._servers and adapter.connector._servers[0].started:
            break
        await asyncio.sleep(0.01)
    assert adapter.connector._servers and adapter.connector._servers[0].started
    port = adapter.connector._servers[0].servers[0].sockets[0].getsockname()[1]
    base = f"http://127.0.0.1:{port}"

    try:
        async with httpx.AsyncClient(timeout=30, limits=httpx.Limits(max_connections=16)) as cli:

            async def http_send(i: int) -> None:
                rsp = await cli.post(
                    f"{base}/send_group_msg",
                    json={"group_id": 500000000, "message": ob_dump(OB_TEXT_MSG)},
                )
                assert rsp.status_code == 200

            async def http_unknown(i: int) -> None:
                rsp = await cli.post(f"{base}/no_such_action", json={})
                assert rsp.status_code == 404

            await bench("HTTP send_group_msg 串行 1 连接", 500, http_send, workers=1)
            await bench("HTTP send_group_msg 并发 8 连接", 2000, http_send, workers=8)
            await bench("HTTP 未知 action 并发 8 连接", 1000, http_unknown, workers=8)
    finally:
        service.cancel()
        cycle.cancel()
        conn.cancel()
        with suppress(asyncio.CancelledError):
            await service
            await cycle
            await conn
        await adapter.close()


async def section_ws() -> None:
    section("6. 正向 WebSocket 端到端(真实网络)")
    adapter = Adapter(impls=[ForwardWebsocketConfig(url="ws://127.0.0.1:0")])
    await adapter.setup()
    cycle = asyncio.create_task(adapter.cycle())
    impl = make_impl(adapter)
    service = asyncio.create_task(impl.api_service())
    conn = asyncio.create_task(adapter.connector.run())
    for _ in range(400):
        if adapter.connector._servers and adapter.connector._servers[0].started:
            break
        await asyncio.sleep(0.01)
    assert adapter.connector._servers and adapter.connector._servers[0].started
    port = adapter.connector._servers[0].servers[0].sockets[0].getsockname()[1]

    async with websockets.connect(f"ws://127.0.0.1:{port}/") as ws:
        loop = asyncio.get_running_loop()

        # 请求-响应流水线:一次发完,逐个收
        n = 1500
        send_at: dict[str, float] = {}
        rtt: list[float] = []
        t0 = loop.time()
        for i in range(n):
            send_at[f"w{i}"] = loop.time()
            await ws.send(
                json.dumps(
                    {
                        "action": "send_group_msg",
                        "params": {"group_id": 500000000, "message": ob_dump(OB_TEXT_MSG)},
                        "echo": f"w{i}",
                    }
                )
            )
        send_wall = (loop.time() - t0) * 1000
        for _ in range(n):
            raw = await ws.recv()
            echo = json.loads(raw).get("echo", "")
            rtt.append((loop.time() - send_at.get(echo, loop.time())) * 1000)
        wall = (loop.time() - t0) * 1000
        show("WS 流水线 send_group_msg 请求-响应", n, wall, rtt)
        print(f"    其中发送端耗时 {fmt_rt(send_wall)},服务端处理吞吐 {n / (wall / 1000):.0f} 请求/s")

        # 事件推送:服务端触发,客户端并行收取
        n_ev = 1500
        ev = onebot_events.HeartbeatEvent(
            interval=15000,
            self_id=10001,
            status=onebot_events.BotStatus(good=True, online=True),
            time=1700000000,
        )
        got = 0

        async def recv_loop() -> None:
            nonlocal got
            while got < n_ev:
                await ws.recv()
                got += 1

        recv_task = asyncio.create_task(recv_loop())
        t0 = loop.time()
        for _ in range(n_ev):
            await adapter.trigger(ev)
        await recv_task
        wall = (loop.time() - t0) * 1000
        print(f"  WS 事件推送(服务端 trigger -> 客户端收齐) {n_ev} 条,{fmt_rt(wall)},{n_ev / (wall / 1000):.0f} 条/s")

    service.cancel()
    cycle.cancel()
    conn.cancel()
    with suppress(asyncio.CancelledError):
        await service
        await cycle
        await conn
    await adapter.close()


# ---------------------------------------------------------------- 入口


class ResourceSampler:
    """每 0.5s 从 /proc 采样本进程 CPU/RSS/线程/fd,按区段时间窗聚合。"""

    def __init__(self) -> None:
        self.samples: list[tuple[float, float, int, int, int]] = []  # (wall, cpu%, rss_kb, threads, fds)
        self._last_wall: float | None = None
        self._last_ticks: int | None = None

    @staticmethod
    def _cpu_ticks() -> int | None:
        try:
            with open(f"/proc/{os.getpid()}/stat", encoding="utf-8") as f:
                raw = f.read()
            _, _, rest = raw.rpartition(")")  # 进程名可能含空格,按最后一个 ')' 切
            fields = rest.split()
            return int(fields[10]) + int(fields[11])  # utime + stime
        except OSError:
            return None

    def sample(self) -> None:
        now = time.perf_counter()
        ticks = self._cpu_ticks()
        cpu = 0.0
        if ticks is not None and self._last_ticks is not None and self._last_wall is not None:
            hz = os.sysconf("SC_CLK_TCK")
            cpu = (ticks - self._last_ticks) / hz / (now - self._last_wall) * 100.0  # 相对单核,可 >100%
        self._last_wall, self._last_ticks = now, ticks
        rss = threads = fds = 0
        try:
            with open(f"/proc/{os.getpid()}/status", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        rss = int(line.split()[1])  # kB
                    elif line.startswith("Threads:"):
                        threads = int(line.split()[1])
        except OSError:
            pass
        with suppress(OSError):
            fds = len(os.listdir(f"/proc/{os.getpid()}/fd"))
        self.samples.append((now, cpu, rss, threads, fds))

    @staticmethod
    def report(samples: list[tuple[float, float, int, int, int]], db_path: str) -> None:
        print("\n=== 资源占用报告(相对单核 CPU%,可超 100%) ===")
        if not samples:
            print("  (无采样数据)")
            return
        cpu = [s[1] for s in samples]
        rss = [s[2] for s in samples]
        threads = [s[3] for s in samples]
        fds = [s[4] for s in samples]
        db_mb = os.path.getsize(db_path) / 1024 / 1024
        print(
            f"  全进程: avg CPU {sum(cpu) / len(cpu):.1f}% | max CPU {max(cpu):.1f}% | "
            f"avg RSS {sum(rss) / len(rss) / 1024:.1f}MB | max RSS {max(rss) / 1024:.1f}MB | "
            f"线程 {min(threads)}~{max(threads)} | fd {min(fds)}~{max(fds)}"
        )
        print(f"  SQLite 库文件: {db_mb:.1f}MB")


async def stack_dumper() -> None:
    """每 10s 打印所有 asyncio 任务栈,用于定位卡死点。"""
    while True:
        await asyncio.sleep(10)
        print("\n=== asyncio 任务栈 ===", flush=True)
        cur = asyncio.current_task()
        for t in asyncio.all_tasks():
            if t is cur:
                continue
            print(f"--- {t.get_name()} done={t.done()} ---", flush=True)
            for frame in t.get_stack():
                print(f"    {frame.f_code.co_filename}:{frame.f_lineno} {frame.f_code.co_name}", flush=True)


async def _sampler_loop(sampler: ResourceSampler) -> None:
    sampler.sample()
    while True:
        await asyncio.sleep(0.5)
        sampler.sample()


def _guard_tmp_path(path: str, *, suffix: str) -> str:
    """仅允许 /tmp 下的基准专用文件,防止误写项目目录的真实数据。"""
    ap = os.path.realpath(path)
    if not ap.startswith("/tmp/") or not ap.endswith(suffix):
        raise RuntimeError(f"基准拒绝使用危险路径: {ap} (仅允许 /tmp 下的 {suffix} 文件)")
    return ap


async def main() -> None:
    faulthandler.dump_traceback_later(60, repeat=True)  # 卡死时每 60s 打印所有协程栈
    print(f"Euler OneBot 性能基准  |  Python {sys.version.split()[0]}  |  {platform.platform()}", flush=True)
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("model name"):
                    print(f"CPU: {line.split(':')[1].strip()}")
                    break
    except OSError:
        pass
    print(f"CPU 核心数: {os.cpu_count()}")

    Logger.create("euler", "WARNING", use_nf=False)  # 基准默认 WARNING,避免日志干扰
    tmpdir = tempfile.mkdtemp(prefix="eulerob_bench_")
    db_path = _guard_tmp_path(os.path.join(tmpdir, "bench.db"), suffix=".db")
    cache_path = _guard_tmp_path(os.path.join(tmpdir, "cache.json"), suffix=".json")
    await im.info_mgr.init(path=db_path, migrate_from=cache_path)
    # 预置 1000 个 uid<->uin 映射与一条消息(供 reply/私聊基准使用)
    for i in range(1000):
        await im.info_mgr.uid_mgr.add(f"u_{90000000 + i}", 90000000 + i)
    await im.info_mgr.msgid_mgr.add(
        im.MsgInfo(scene_type="group", scene_id=999, seq=999, uin=90000001, uid="u_90000001", timestamp=1, text="seed")
    )
    OB_MIXED_MSG.insert(
        3, Reply(data=ReplyData(id=str(im.MsgIDPool._gen_id(im.MsgInfo(scene_type="group", scene_id=999, seq=999)))))
    )
    print(f"临时数据库: {db_path}")

    dump_task = asyncio.create_task(stack_dumper())
    sampler = ResourceSampler()
    sampler_task = asyncio.create_task(_sampler_loop(sampler))
    bounds: list[tuple[str, float, float]] = []
    loop = asyncio.get_running_loop()
    try:
        only = 0
        if len(sys.argv) > 1 and sys.argv[1] == "--only":
            only = int(sys.argv[2])
        sections = [
            ("模型层", section_model),
            ("转换层", section_transform),
            ("数据层", section_db),
            ("分发链路", section_dispatch),
            ("HTTP", section_http),
            ("WebSocket", section_ws),
        ]
        for i, (label, fn) in enumerate(sections, 1):
            if only and i != only:
                continue
            print(f"\n>>> 运行区段 {i}/{len(sections)}: {label}", flush=True)
            t0 = loop.time()
            await fn()
            bounds.append((label, t0, loop.time()))
    finally:
        dump_task.cancel()
        sampler_task.cancel()
        with suppress(asyncio.CancelledError):
            await dump_task
            await sampler_task
        await im.info_mgr.close()
        sampler.sample()
        ResourceSampler.report(sampler.samples, db_path)
        print("\n基准完成。")


if __name__ == "__main__":
    asyncio.run(main())
