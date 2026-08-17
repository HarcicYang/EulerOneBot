import asyncio
import hashlib
import hmac
import json
from contextlib import suppress
from typing import Any, cast

import httpx
import pytest
import websockets
from fastapi import FastAPI, Request, Response
from uvicorn import Config as UvicornConfig
from uvicorn import Server as UvicornServer

from euleronebot.config import ForwardWebsocketConfig, HTTPConfig, HTTPPostConfig, ReverseWebsocketConfig
from euleronebot.onebot import Adapter
from euleronebot.onebot.api import SendMessageResponse, SendMsgRsp


def run(coro):
    return asyncio.run(coro)


async def fake_service(adapter: Adapter):
    while True:
        call = await adapter.api_calls.get()
        rsp = SendMessageResponse(status="ok", retcode=0, data=SendMsgRsp(message_id=1), echo=call.echo)
        await adapter.report(rsp)


async def start_server(app: FastAPI, host: str = "127.0.0.1", port: int = 0) -> tuple[UvicornServer, asyncio.Task, int]:
    server = UvicornServer(UvicornConfig(app, host=host, port=port, log_config=None))
    task = asyncio.create_task(server.serve())
    for _ in range(200):
        if server.started:
            break
        await asyncio.sleep(0.01)
    assert server.started
    actual_port = server.servers[0].sockets[0].getsockname()[1]
    return server, task, actual_port


class TestHTTP:
    async def make(self, access_token: str = "") -> Adapter:
        adapter = Adapter(impls=[HTTPConfig(url="http://127.0.0.1:0")], access_token=access_token)
        await adapter.setup()
        return adapter

    def test_unknown_action_404(self):
        async def main():
            adapter = await self.make()
            app = adapter.connector.http_app
            assert app is not None
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as cli:
                rsp = await cli.post("/no_such_action", json={})
            assert rsp.status_code == 404
            assert rsp.json()["retcode"] == 1404

        run(main())

    def test_access_token(self):
        async def main():
            adapter = await self.make(access_token="secret")
            cycle = asyncio.create_task(adapter.cycle())
            service = asyncio.create_task(fake_service(adapter))
            app = adapter.connector.http_app
            assert app is not None
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as cli:
                rsp = await cli.post("/get_login_info", json={})
                assert rsp.status_code == 401
                rsp = await cli.post("/get_login_info", json={}, headers={"Authorization": "Bearer wrong"})
                assert rsp.status_code == 403
                rsp = await cli.post("/get_login_info", params={"access_token": "secret"}, json={})
                assert rsp.status_code == 200
                rsp = await cli.post("/get_login_info", json={}, headers={"Authorization": "Bearer secret"})
                assert rsp.status_code == 200
                assert rsp.json()["status"] == "ok"
                assert rsp.json()["data"]["message_id"] == 1
            service.cancel()
            cycle.cancel()
            with suppress(asyncio.CancelledError):
                await service
                await cycle
            await adapter.close()

        run(main())

    def test_unsupported_content_type_406(self):
        async def main():
            adapter = await self.make()
            app = adapter.connector.http_app
            assert app is not None
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as cli:
                rsp = await cli.post("/get_login_info", content="raw", headers={"Content-Type": "text/plain"})
            assert rsp.status_code == 406

        run(main())

    def test_malformed_json_400(self):
        async def main():
            adapter = await self.make()
            app = adapter.connector.http_app
            assert app is not None
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as cli:
                rsp = await cli.post(
                    "/get_login_info", content="{invalid", headers={"Content-Type": "application/json"}
                )
            assert rsp.status_code == 400

        run(main())

    def test_json_params_dispatched(self):
        async def main():
            adapter = await self.make()
            seen = {}

            async def service(adapter):
                while True:
                    call = await adapter.api_calls.get()
                    seen.update(call.params)
                    await adapter.report(
                        SendMessageResponse(status="ok", retcode=0, data=SendMsgRsp(message_id=1), echo=call.echo)
                    )

            service_task = asyncio.create_task(service(adapter))
            cycle = asyncio.create_task(adapter.cycle())
            app = adapter.connector.http_app
            assert app is not None
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as cli:
                rsp = await cli.post(
                    "/send_private_msg", json={"user_id": 123, "message": [{"type": "text", "data": {"text": "hi"}}]}
                )
                assert rsp.status_code == 200
                assert seen["user_id"] == 123
                rsp = await cli.post(
                    "/send_private_msg",
                    data={"user_id": "456", "message": '[{"type": "text", "data": {"text": "hi"}}]'},
                )
                assert rsp.status_code == 200
                assert seen["user_id"] == 456
                assert isinstance(seen["message"], list)
            service_task.cancel()
            cycle.cancel()
            with suppress(asyncio.CancelledError):
                await service_task
                await cycle
            await adapter.close()

        run(main())


class TestForwardWebSocket:
    def test_access_token_auth(self):
        async def main():
            adapter = Adapter(impls=[ForwardWebsocketConfig(url="ws://127.0.0.1:0")], access_token="secret")
            await adapter.setup()
            task = asyncio.create_task(adapter.connector.run())
            for _ in range(200):
                if adapter.connector._servers and adapter.connector._servers[0].started:
                    break
                await asyncio.sleep(0.01)
            assert adapter.connector._servers
            port = adapter.connector._servers[0].servers[0].sockets[0].getsockname()[1]
            with pytest.raises(websockets.exceptions.InvalidStatus):
                await websockets.connect(f"ws://127.0.0.1:{port}/api")
            async with websockets.connect(
                f"ws://127.0.0.1:{port}/api", additional_headers={"Authorization": "Bearer secret"}
            ):
                pass
            await adapter.close()
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        run(main())


class FakeSocket:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


class SlowSocket:
    async def send_text(self, data):
        await asyncio.sleep(10)


class TestForwardWebSocketRegistry:
    def test_register_replaces_and_closes_old_socket(self):
        async def main():
            adapter = Adapter(impls=[])
            old, new = FakeSocket(), FakeSocket()
            adapter.connector.active_websocket_servers["event"] = cast(Any, old)
            await adapter.connector._register_websocket("event", cast(Any, new))
            assert adapter.connector.active_websocket_servers["event"] is new
            assert old.closed

        run(main())

    def test_unregister_only_removes_own_socket(self):
        async def main():
            adapter = Adapter(impls=[])
            old, new = FakeSocket(), FakeSocket()
            adapter.connector.active_websocket_servers["event"] = cast(Any, new)
            adapter.connector._unregister_websocket("event", cast(Any, old))
            assert adapter.connector.active_websocket_servers.get("event") is new
            adapter.connector._unregister_websocket("event", cast(Any, new))
            assert "event" not in adapter.connector.active_websocket_servers

        run(main())

    def test_push_has_timeout(self):
        async def main():
            adapter = Adapter(impls=[])
            adapter.connector.forward_send_timeout = 0.05
            t0 = asyncio.get_running_loop().time()
            await adapter.connector._forward_websocket_push(cast(Any, SlowSocket()), "x")
            assert asyncio.get_running_loop().time() - t0 < 2

        run(main())


class TestReverseWebSocket:
    def test_separate_clients_dispatch_and_event(self):
        async def main():
            roles = []
            self_ids = []
            auths = []
            api_echo = []
            events = []

            async def handler(ws):
                headers = ws.request.headers
                roles.append(headers.get("X-Client-Role"))
                self_ids.append(headers.get("X-Self-ID"))
                auths.append(headers.get("Authorization"))
                if headers.get("X-Client-Role") == "API":
                    await ws.send(json.dumps({"action": "send_private_msg", "params": {}, "echo": "abc"}))
                    async for msg in ws:
                        api_echo.append(json.loads(msg).get("echo"))
                else:
                    async for msg in ws:
                        events.append(json.loads(msg))

            async with websockets.serve(handler, "127.0.0.1", 0) as server:
                port = server.sockets[0].getsockname()[1]
                adapter = Adapter(
                    impls=[ReverseWebsocketConfig(url=f"ws://127.0.0.1:{port}", reconnect_interval=100)],
                    access_token="tok",
                )
                adapter.connector.self_id = 12345
                await adapter.setup()
                cycle = asyncio.create_task(adapter.cycle())
                service = asyncio.create_task(fake_service(adapter))
                for _ in range(200):
                    if (
                        adapter.connector._reverse_ws["API"] is not None
                        and adapter.connector._reverse_ws["Event"] is not None
                    ):
                        break
                    await asyncio.sleep(0.01)
                await adapter.connector.trigger(
                    '{"post_type": "meta_event", "meta_event_type": "heartbeat", "time": 0, "self_id": 12345, '
                    '"status": {"online": true, "good": true}, "interval": 15000}'
                )
                for _ in range(200):
                    if api_echo and events:
                        break
                    await asyncio.sleep(0.01)
                assert set(roles) == {"API", "Event"}
                assert set(self_ids) == {"12345"}
                assert set(auths) == {"Bearer tok"}
                assert api_echo == ["abc"]
                assert events and events[0]["post_type"] == "meta_event"
                service.cancel()
                cycle.cancel()
                with suppress(asyncio.CancelledError):
                    await service
                    await cycle
                await adapter.close()

        run(main())

    def test_universal_client(self):
        async def main():
            roles = []

            async def handler(ws):
                roles.append(ws.request.headers.get("X-Client-Role"))
                async for _ in ws:
                    break

            async with websockets.serve(handler, "127.0.0.1", 0) as server:
                port = server.sockets[0].getsockname()[1]
                adapter = Adapter(
                    impls=[
                        ReverseWebsocketConfig(
                            url=f"ws://127.0.0.1:{port}", use_universal_client=True, reconnect_interval=100
                        )
                    ]
                )
                await adapter.setup()
                for _ in range(200):
                    if roles:
                        break
                    await asyncio.sleep(0.01)
                assert roles == ["Universal"]
                await adapter.close()

        run(main())


class TestHTTPPost:
    def test_push_with_signature(self):
        async def main():
            received: dict[str, str | None] = {}

            async def webhook(request: Request):
                received["raw"] = (await request.body()).decode()
                received["sig"] = request.headers.get("X-Signature")
                received["self_id"] = request.headers.get("X-Self-ID")
                return Response(status_code=204)

            app = FastAPI()
            app.post("/webhook")(webhook)
            server, server_task, port = await start_server(app)

            adapter = Adapter(
                impls=[HTTPPostConfig(url=f"http://127.0.0.1:{port}/webhook", secret="mysecret", timeout=5)],
            )
            adapter.connector.self_id = 42
            await adapter.setup()
            event = (
                '{"post_type": "meta_event", "meta_event_type": "heartbeat", "time": 0, "self_id": 42, '
                '"status": {"online": true, "good": true}, "interval": 15000}'
            )
            await adapter.connector.trigger(event)
            for _ in range(200):
                if received:
                    break
                await asyncio.sleep(0.01)
            assert received
            assert received["raw"] == event
            assert received["self_id"] == "42"
            expected = hmac.new(b"mysecret", event.encode(), hashlib.sha1).hexdigest()
            assert received["sig"] == f"sha1={expected}"
            await adapter.close()
            server.should_exit = True
            server_task.cancel()
            with suppress(asyncio.CancelledError):
                await server_task

        run(main())
