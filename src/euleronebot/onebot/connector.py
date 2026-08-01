import asyncio
from typing import Literal, Self, cast
from urllib.parse import urlparse

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from uvicorn import Config as UvicornConfig
from uvicorn import Server as UvicornServer

from ..config import AdapterConfig, ForwardWebsocketConfig
from ..hyperogger import Logger

logger = Logger.fetch("euler").name_custom("euler.onebot.connector")


class Connector:
    def __init__(self, impls: list[AdapterConfig]):
        self.impls = impls
        self.forward_app: FastAPI = cast(FastAPI, cast(object, None))
        self.received: asyncio.Queue[str] = asyncio.Queue()
        self.active_websocket_servers: dict[Literal["root", "api", "event"], WebSocket] = dict()

    async def setup(self) -> Self:
        for i in self.impls:
            match i.type:
                case "HTTP":
                    await self.set_http()
                case "HTTPPost":
                    await self.set_http_post()
                case "ForwardWebSocket":
                    await self.set_forward_websocket()
                case "ReverseWebSocket":
                    await self.set_reverse_websocket()
                case _:
                    raise RuntimeError(f"Unknown implementation: {i}")
        return self

    async def __aenter__(self) -> Self:
        return await self.setup()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.forward_app is not None and self.active_websocket_servers:
            for socket in self.active_websocket_servers.values():
                if socket.client_state != socket.client_state.DISCONNECTED:
                    await socket.close()

    async def set_http(self) -> None:
        raise NotImplementedError

    async def set_http_post(self) -> None:
        raise NotImplementedError

    async def set_forward_websocket(self) -> None:
        self.forward_app = FastAPI()

        @self.forward_app.websocket("/")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.active_websocket_servers["root"] = websocket
            try:
                while True:
                    await self.received.put(await websocket.receive_text())
            except (WebSocketDisconnect, RuntimeError):
                logger.error("Connection lost")
                self.active_websocket_servers.pop("root", None)

        @self.forward_app.websocket("/api")
        async def api_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.active_websocket_servers["api"] = websocket
            try:
                while True:
                    await self.received.put(await websocket.receive_text())
            except (WebSocketDisconnect, RuntimeError):
                logger.error("Connection lost")
                self.active_websocket_servers.pop("api", None)

        @self.forward_app.websocket("/event")
        async def event_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.active_websocket_servers["event"] = websocket
            try:
                while True:
                    await asyncio.sleep(1)
            except (WebSocketDisconnect, RuntimeError):
                logger.error("Connection lost")
                self.active_websocket_servers.pop("event", None)

    async def set_reverse_websocket(self) -> None:
        raise NotImplementedError

    async def run(self):
        if self.forward_app:
            cfg = None
            for i in self.impls:
                if isinstance(i, ForwardWebsocketConfig):
                    url = urlparse(i.url)
                    host = url.hostname
                    port = url.port
                    assert host is not None and port is not None
                    cfg = UvicornConfig(self.forward_app, host=host, port=port, log_config=None)
                    break
            assert cfg
            server = UvicornServer(cfg)
            await server.serve()

    async def report(self, data: str) -> None:
        logger.trace(f"API report: {data}")
        if not self.active_websocket_servers:
            return
        for key in ("root", "api"):
            socket = self.active_websocket_servers.get(key)
            if socket is None or socket.client_state == socket.client_state.DISCONNECTED:
                continue
            await socket.send_text(data)

    async def trigger(self, data: str) -> None:
        logger.trace(f"Event trigger: {data}")
        if self.active_websocket_servers:
            if self.active_websocket_servers.get("root"):
                socket = self.active_websocket_servers["root"]
                if socket.client_state == socket.client_state.DISCONNECTED:
                    logger.warning("Unable to trigger")
                    return
                await socket.send_text(data)
            if self.active_websocket_servers.get("event"):
                socket = self.active_websocket_servers["event"]
                if socket.client_state == socket.client_state.DISCONNECTED:
                    logger.warning("Unable to trigger")
                    return
                await socket.send_text(data)
