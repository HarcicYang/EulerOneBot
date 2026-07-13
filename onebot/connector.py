from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Optional, Literal, Self, TYPE_CHECKING, Any
from uvicorn import Config as UvicornConfig
from uvicorn import Server as UvicornServer
from urllib.parse import urlparse, ParseResult
import asyncio

from hyperogger import Logger
from config import AdapterConfig, ForwardWebsocketConfig

logger = Logger.fetch("euler")


class Connector:
    def __init__(self, impls: list[AdapterConfig]):
        self.impls = impls
        self.forward_app: FastAPI = None
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

    async def __aexit__(self) -> None:
        del self

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
            except WebSocketDisconnect:
                logger.error("连接断开")

        @self.forward_app.websocket("/api")
        async def api_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.active_websocket_servers["api"] = websocket
            try:
                while True:
                    await self.received.put(await websocket.receive_text())
            except WebSocketDisconnect:
                logger.error("连接断开")

        @self.forward_app.websocket("/event")
        async def event_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.active_websocket_servers["event"] = websocket
            while True:
                await asyncio.sleep(1)

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
                    cfg = UvicornConfig(
                        self.forward_app,
                        host=host,
                        port=port,
                    )
                    break
            assert cfg
            server = UvicornServer(cfg)
            await server.serve()



    async def report(self, data: str) -> None:
        if self.active_websocket_servers:
            if self.active_websocket_servers.get("root"):
                await self.active_websocket_servers["root"].send_text(data)
            if self.active_websocket_servers.get("api"):
                await self.active_websocket_servers["api"].send_text(data)

    async def trigger(self, data: str) -> None:
        if self.active_websocket_servers:
            if self.active_websocket_servers.get("root"):
                await self.active_websocket_servers["root"].send_text(data)
            if self.active_websocket_servers.get("event"):
                await self.active_websocket_servers["event"].send_text(data)
