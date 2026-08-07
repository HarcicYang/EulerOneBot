import asyncio
import hashlib
import hmac
import json
import uuid
from contextlib import suppress
from typing import TYPE_CHECKING, Literal, Self
from urllib.parse import urlparse

import httpx
import websockets
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from uvicorn import Config as UvicornConfig
from uvicorn import Server as UvicornServer
from websockets.asyncio.client import ClientConnection

from ..config import AdapterConfig, ForwardWebsocketConfig, HTTPConfig, HTTPPostConfig, ReverseWebsocketConfig
from ..hyperogger import Logger

if TYPE_CHECKING:
    from . import Adapter as OneBotAdapter

logger = Logger.fetch("euler").name_custom("euler.onebot.connector")

ReverseRole = Literal["API", "Event", "Universal"]


def _convert_str(value: object) -> object:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except ValueError:
        return value


class Connector:
    def __init__(
        self,
        adapter: "OneBotAdapter",
        impls: list[AdapterConfig],
        access_token: str = "",
    ):
        self.adapter = adapter
        self.impls = impls
        self.access_token = access_token
        self.self_id: int = 0
        self.forward_app: FastAPI | None = None
        self.http_app: FastAPI | None = None
        self.received: asyncio.Queue[str] = asyncio.Queue()
        self.active_websocket_servers: dict[Literal["root", "api", "event"], WebSocket] = dict()
        self._servers: list[UvicornServer] = []
        self._reverse_ws: dict[ReverseRole, ClientConnection | None] = {
            "API": None,
            "Event": None,
            "Universal": None,
        }
        self._reverse_ws_tasks: list[asyncio.Task[None]] = []
        self._http_post: HTTPPostConfig | None = None

    async def setup(self) -> Self:
        for i in self.impls:
            match i.type:
                case "HTTP":
                    await self.set_http(i)
                case "HTTPPost":
                    await self.set_http_post(i)
                case "ForwardWebSocket":
                    await self.set_forward_websocket(i)
                case "ReverseWebSocket":
                    await self.set_reverse_websocket(i)
                case _:
                    raise RuntimeError(f"Unknown implementation: {i}")
        return self

    async def close(self) -> None:
        for server in self._servers:
            server.should_exit = True
        for task in self._reverse_ws_tasks:
            task.cancel()
        for socket in self.active_websocket_servers.values():
            if socket.client_state != socket.client_state.DISCONNECTED:
                await socket.close()

    def _ws_authorized(self, websocket: WebSocket) -> bool:
        if not self.access_token:
            return True
        return (
            websocket.headers.get("authorization") == f"Bearer {self.access_token}"
            or websocket.query_params.get("access_token") == self.access_token
        )

    async def set_http(self, _cfg: HTTPConfig) -> None:
        self.http_app = FastAPI()

        @self.http_app.api_route("/{action:path}", methods=["GET", "POST"])
        async def http_endpoint(request: Request, action: str):
            if self.access_token:
                auth = request.headers.get("authorization", "")
                authorized = (
                    auth == f"Bearer {self.access_token}"
                    or request.query_params.get("access_token") == self.access_token
                )
                if not authorized:
                    if not auth and "access_token" not in request.query_params:
                        return JSONResponse({"status": "failed", "retcode": 1401, "data": None, "echo": None}, 401)
                    return JSONResponse({"status": "failed", "retcode": 1403, "data": None, "echo": None}, 403)
            if action not in self.adapter.api_actions:
                return JSONResponse({"status": "failed", "retcode": 1404, "data": None, "echo": None}, 404)
            content_type = request.headers.get("content-type", "")
            params: dict = {}
            if request.method == "POST" and content_type:
                if "application/json" in content_type:
                    try:
                        body = await request.json()
                    except ValueError:
                        return JSONResponse({"status": "failed", "retcode": 1400, "data": None, "echo": None}, 400)
                    if not isinstance(body, dict):
                        return JSONResponse({"status": "failed", "retcode": 1400, "data": None, "echo": None}, 400)
                    params.update(body)
                elif "application/x-www-form-urlencoded" in content_type:
                    params.update({k: _convert_str(v) for k, v in (await request.form()).items()})
                else:
                    return JSONResponse({"status": "failed", "retcode": 1400, "data": None, "echo": None}, 406)
            params.update({k: _convert_str(v) for k, v in request.query_params.items()})
            params.pop("access_token", None)
            echo = params.pop("echo", "") or f"e{uuid.uuid4().hex[:8]}"
            future = self.adapter.register_awaiter(echo)
            await self.received.put(json.dumps({"action": action, "params": params, "echo": echo}))
            try:
                rsp = await asyncio.wait_for(future, timeout=30)
            except TimeoutError:
                return JSONResponse({"status": "failed", "retcode": 1, "data": None, "echo": echo}, 503)
            return JSONResponse(rsp.model_dump(), 404 if rsp.retcode == 1404 else 200)

    async def set_http_post(self, cfg: HTTPPostConfig) -> None:
        self._http_post = cfg

    async def set_forward_websocket(self, _cfg: ForwardWebsocketConfig) -> None:
        self.forward_app = FastAPI()

        @self.forward_app.websocket("/")
        async def websocket_endpoint(websocket: WebSocket):
            if not self._ws_authorized(websocket):
                await websocket.close(code=1008)
                return
            await websocket.accept()
            self.active_websocket_servers["root"] = websocket
            try:
                while True:
                    await self.received.put(await websocket.receive_text())
            except (WebSocketDisconnect, RuntimeError):
                logger.error("Connection lost")
                self.active_websocket_servers.pop("root", None)

        @self.forward_app.websocket("/api")
        @self.forward_app.websocket("/api/")
        async def api_endpoint(websocket: WebSocket):
            if not self._ws_authorized(websocket):
                await websocket.close(code=1008)
                return
            await websocket.accept()
            self.active_websocket_servers["api"] = websocket
            try:
                while True:
                    await self.received.put(await websocket.receive_text())
            except (WebSocketDisconnect, RuntimeError):
                logger.error("Connection lost")
                self.active_websocket_servers.pop("api", None)

        @self.forward_app.websocket("/event")
        @self.forward_app.websocket("/event/")
        async def event_endpoint(websocket: WebSocket):
            if not self._ws_authorized(websocket):
                await websocket.close(code=1008)
                return
            await websocket.accept()
            self.active_websocket_servers["event"] = websocket
            try:
                while True:
                    await websocket.receive_text()
            except (WebSocketDisconnect, RuntimeError):
                logger.error("Connection lost")
                self.active_websocket_servers.pop("event", None)

    async def set_reverse_websocket(self, cfg: ReverseWebsocketConfig) -> None:
        api_url = cfg.api_url or cfg.url
        event_url = cfg.event_url or cfg.url
        interval = cfg.reconnect_interval / 1000

        async def run_client(url: str, role: ReverseRole, *, consume: bool) -> None:
            headers = {"X-Client-Role": role, "X-Self-ID": str(self.self_id)}
            if self.access_token:
                headers["Authorization"] = f"Bearer {self.access_token}"
            while True:
                try:
                    async with websockets.connect(url, additional_headers=headers) as ws:
                        self._reverse_ws[role] = ws
                        if consume:
                            async for raw in ws:
                                await self.received.put(raw.decode() if isinstance(raw, bytes) else raw)
                        else:
                            await ws.wait_closed()
                except Exception as e:  # noinspection PyBroadException
                    logger.warning(f"ReverseWS[{role}] failed to connect: {e!r}")
                finally:
                    self._reverse_ws[role] = None
                await asyncio.sleep(interval)

        if cfg.use_universal_client:
            self._reverse_ws_tasks.append(asyncio.create_task(run_client(api_url, "Universal", consume=True)))
        else:
            self._reverse_ws_tasks.append(asyncio.create_task(run_client(api_url, "API", consume=True)))
            self._reverse_ws_tasks.append(asyncio.create_task(run_client(event_url, "Event", consume=False)))

    async def run(self) -> None:
        tasks: list[asyncio.Task[None]] = [*self._reverse_ws_tasks]
        for i in self.impls:
            app = None
            if isinstance(i, ForwardWebsocketConfig):
                app = self.forward_app
            elif isinstance(i, HTTPConfig):
                app = self.http_app
            if app is None:
                continue
            url = urlparse(i.url)
            host = url.hostname
            port = url.port
            assert host is not None and port is not None
            server = UvicornServer(UvicornConfig(app, host=host, port=port, log_config=None))
            self._servers.append(server)
            tasks.append(asyncio.create_task(server.serve()))
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, BaseException) and not isinstance(r, asyncio.CancelledError):
                    logger.error(f"Connector subtask error: {r!r}")
        else:
            await asyncio.Event().wait()

    async def _send_reverse_ws(self, data: str, *roles: ReverseRole) -> None:
        for role in roles:
            ws = self._reverse_ws.get(role)
            if ws is None:
                continue
            with suppress(Exception):
                await ws.send(data)

    async def report(self, data: str) -> None:
        logger.trace(f"API report: {data}")
        await self._send_reverse_ws(data, "API", "Universal")
        for key in ("root", "api"):
            socket = self.active_websocket_servers.get(key)
            if socket is None or socket.client_state == socket.client_state.DISCONNECTED:
                continue
            with suppress(Exception):
                await socket.send_text(data)

    async def trigger(self, data: str) -> None:
        tasks = []
        logger.trace(f"Event trigger: {data}")
        if self._http_post is not None:
            tasks.append(asyncio.create_task(self._http_post_push(data)))
        tasks.append(asyncio.create_task(self._send_reverse_ws(data, "Event", "Universal")))
        for key in ("root", "event"):
            socket = self.active_websocket_servers.get(key)
            if socket is None or socket.client_state == socket.client_state.DISCONNECTED:
                continue
            tasks.append(asyncio.create_task(self._forward_websocket_push(socket, data)))

        event = asyncio.Event()
        excute = asyncio.create_task(self._push_excute(tasks, event))
        timed = 0
        while not event.is_set():
            await asyncio.sleep(0.02)
            timed += 0.02
            if timed >= 10:
                logger.warning("event trigger timed out, giving up")
                excute.cancel()
                break

    async def _push_excute(self, tasks: list[asyncio.Task], event: asyncio.Event) -> None:
        try:
            await asyncio.gather(*tasks)
            event.set()
        except asyncio.CancelledError:
            return

    async def _forward_websocket_push(self, socket: WebSocket, data: str) -> None:
        with suppress(Exception):
            await socket.send_text(data)

    async def _http_post_push(self, data: str) -> None:
        cfg = self._http_post
        assert cfg is not None
        headers = {"Content-Type": "application/json", "X-Self-ID": str(self.self_id)}
        if cfg.secret:
            sig = hmac.new(cfg.secret.encode(), data.encode(), hashlib.sha1).hexdigest()
            headers["X-Signature"] = f"sha1={sig}"
        try:
            timeout = None if cfg.timeout == 0 else cfg.timeout
            async with httpx.AsyncClient(timeout=timeout) as cli:
                rsp = await cli.post(cfg.url, content=data, headers=headers)
            if rsp.text:
                logger.trace(f"Webhook response: {rsp.text}")
        except Exception as e:  # noinspection PyBroadException
            logger.warning(f"Webhook push failed: {e!r}")
