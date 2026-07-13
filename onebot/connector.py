from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Optional, Literal, Self
import asyncio

from ..hyperogger import Logger

logger = Logger.create("euler", "INFO")


class Connector:
    def __init__(
            self, host: str, port: int,
            impls: list[Literal["http", "http_post", "forward_websocket", "reverse_websocket"]]
    ):
        self.host = host
        self.port = port
        self.impls = impls
        self.app = FastAPI()
        self.received: asyncio.Queue[str] = asyncio.Queue()
        self.active_websocket_servers: dict[Literal["root", "api", "event"], WebSocket] = dict()

    async def setup(self) -> Self:
        for i in self.impls:
            match i:
                case "http":
                    await self.set_http()
                case "http_post":
                    await self.set_http_post()
                case "forward_websocket":
                    await self.set_forward_websocket()
                case "reverse_websocket":
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
        @self.app.websocket("/")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.active_websocket_servers["root"] = websocket
            try:
                while True:
                    await self.received.put(await websocket.receive_text())
            except WebSocketDisconnect:
                logger.error("连接断开")

        @self.app.websocket("/api")
        async def api_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.active_websocket_servers["api"] = websocket
            try:
                while True:
                    await self.received.put(await websocket.receive_text())
            except WebSocketDisconnect:
                logger.error("连接断开")

        @self.app.websocket("/event")
        async def event_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.active_websocket_servers["event"] = websocket
            while True:
                await asyncio.sleep(1)

    async def set_reverse_websocket(self) -> None:
        raise NotImplementedError

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
