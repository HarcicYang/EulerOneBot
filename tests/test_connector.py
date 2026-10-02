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
from euleronebot.onebot.api import SendMessageResponse
from euleronebot.onebot.api_data import SendMsgRsp


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


async def stop_tasks(*tasks: asyncio.Task):
    for task in tasks:
        task.cancel()
    for task in tasks:
        with suppress(asyncio.CancelledError):
            await task


class TestHTTP:
    @staticmethod
    async def make(access_token: str = "") -> Adapter:
        adapter = Adapter(impls=[HTTPConfig(url="http://127.0.0.1:0")], access_token=access_token)
        await adapter.setup()
        return adapter

    def test_http_contract_handles_auth_unknown_routes_and_bad_payloads(self):
        async def main():
            adapter = await self.make(access_token="secret")
            app = adapter.connector.http_app
            assert app is not None
            transport = httpx.ASGITransport(app=app)
            auth = {"Authorization": "Bearer secret"}
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                rsp = await client.post("/no_such_action", json={})
                assert (rsp.status_code, rsp.json()["retcode"]) == (401, 1401)

                rsp = await client.post("/no_such_action", json={}, headers={"Authorization": "Bearer wrong"})
                assert (rsp.status_code, rsp.json()["retcode"]) == (403, 1403)

                rsp = await client.post("/no_such_action", json={}, headers=auth)
                assert (rsp.status_code, rsp.json()["retcode"]) == (404, 1404)

                rsp = await client.post(
                    "/get_login_info", content="raw", headers={**auth, "Content-Type": "text/plain"}
                )
                assert rsp.status_code == 406

                rsp = await client.post(
                    "/get_login_info", content="{invalid", headers={**auth, "Content-Type": "application/json"}
                )
                assert rsp.status_code == 400
            await adapter.close()

        run(main())

    def test_http_dispatches_json_and_form_params_and_returns_echo(self):
        async def main():
            adapter = await self.make()
            seen = []

            async def service():
                for _ in range(2):
                    data = await adapter.connector.received.get()
                    call = adapter.api_validation.validate_json(data)
                    seen.append((call.params.model_dump(), call.echo))
                    await adapter.report(
                        SendMessageResponse(status="ok", retcode=0, data=SendMsgRsp(message_id=1), echo=call.echo)
                    )

            service_task = asyncio.create_task(service())
            app = adapter.connector.http_app
            assert app is not None
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                rsp = await client.post(
                    "/send_private_msg",
                    json={"user_id": 123, "message": [{"type": "text", "data": {"text": "hi"}}], "echo": "json"},
                )
                assert rsp.json()["echo"] == "json"
                rsp = await client.post(
                    "/send_private_msg",
                    data={
                        "user_id": "456",
                        "message": '[{"type": "text", "data": {"text": "hi"}}]',
                        "echo": "form",
                    },
                )
                assert rsp.json()["echo"] == "form"

            assert seen[0][0]["user_id"] == 123
            assert seen[1][0]["user_id"] == 456
            assert isinstance(seen[1][0]["message"], list)
            await stop_tasks(service_task)
            await adapter.close()

        run(main())


class TestForwardWebSocket:
    def test_forward_websocket_enforces_access_token(self):
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
            await stop_tasks(task)

        run(main())

    def test_forward_websocket_registry_replaces_old_socket_and_only_unregisters_current(self):
        async def main():
            adapter = Adapter(impls=[])
            old, new = FakeSocket(), FakeSocket()
            adapter.connector.active_websocket_servers["event"] = cast(Any, new)
            adapter.connector._unregister_websocket("event", cast(Any, old))
            assert adapter.connector.active_websocket_servers.get("event") is new

            await adapter.connector._register_websocket("event", cast(Any, old))
            assert adapter.connector.active_websocket_servers["event"] is old
            assert new.closed is True
            adapter.connector._unregister_websocket("event", cast(Any, old))
            assert "event" not in adapter.connector.active_websocket_servers

        run(main())

    def test_forward_websocket_push_has_timeout(self):
        async def main():
            adapter = Adapter(impls=[])
            adapter.connector.forward_send_timeout = 0.05
            started = asyncio.get_running_loop().time()
            await adapter.connector._forward_websocket_push(cast(Any, SlowSocket()), "x")
            assert asyncio.get_running_loop().time() - started < 2

        run(main())


class FakeSocket:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


class SlowSocket:
    @staticmethod
    async def send_text(data):
        await asyncio.sleep(10)


class TestReverseWebSocket:
    def test_reverse_websocket_separate_api_and_event_clients(self):
        async def main():
            roles = []
            echo = []
            events = []

            async def handler(ws):
                role = ws.request.headers.get("X-Client-Role")
                roles.append(role)
                assert ws.request.headers.get("X-Self-ID") == "12345"
                assert ws.request.headers.get("Authorization") == "Bearer tok"
                if role == "API":
                    await ws.send(json.dumps({"action": "send_private_msg", "params": {}, "echo": "abc"}))
                    async for msg in ws:
                        echo.append(json.loads(msg)["echo"])
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
                    if adapter.connector._reverse_ws["API"] and adapter.connector._reverse_ws["Event"]:
                        break
                    await asyncio.sleep(0.01)

                await adapter.connector.trigger(
                    '{"post_type": "meta_event", "meta_event_type": "heartbeat", "time": 0, "self_id": 12345, '
                    '"status": {"online": true, "good": true}, "interval": 15000}'
                )
                for _ in range(200):
                    if echo and events:
                        break
                    await asyncio.sleep(0.01)

                assert set(roles) == {"API", "Event"}
                assert echo == ["abc"]
                assert events and events[0]["post_type"] == "meta_event"
                await stop_tasks(cycle, service)
                await adapter.close()

        run(main())

    def test_reverse_websocket_universal_client_carries_events_and_api_responses(self):
        async def main():
            roles = []
            echo = []
            events = []

            async def handler(ws):
                roles.append(ws.request.headers.get("X-Client-Role"))
                await ws.send(json.dumps({"action": "send_private_msg", "params": {}, "echo": "abc"}))
                async for msg in ws:
                    payload = json.loads(msg)
                    if payload.get("echo"):
                        echo.append(payload["echo"])
                    else:
                        events.append(payload)

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
                cycle = asyncio.create_task(adapter.cycle())
                service = asyncio.create_task(fake_service(adapter))
                for _ in range(200):
                    if adapter.connector._reverse_ws["Universal"]:
                        break
                    await asyncio.sleep(0.01)

                await adapter.connector.trigger(
                    '{"post_type": "meta_event", "meta_event_type": "heartbeat", "time": 0, "self_id": 1, '
                    '"status": {"online": true, "good": true}, "interval": 15000}'
                )
                for _ in range(200):
                    if echo and events:
                        break
                    await asyncio.sleep(0.01)

                assert roles == ["Universal"]
                assert echo == ["abc"]
                assert events and events[0]["post_type"] == "meta_event"
                await stop_tasks(cycle, service)
                await adapter.close()

        run(main())


def test_http_post_pushes_hmac_signed_event_with_self_id():
    async def main():
        received: dict[str, str | None] = {}

        async def webhook(request: Request):
            received["raw"] = (await request.body()).decode()
            received["signature"] = request.headers.get("X-Signature")
            received["self_id"] = request.headers.get("X-Self-ID")
            return Response(status_code=204)

        app = FastAPI()
        app.post("/webhook")(webhook)
        server, server_task, port = await start_server(app)
        adapter = Adapter(impls=[HTTPPostConfig(url=f"http://127.0.0.1:{port}/webhook", secret="mysecret", timeout=5)])
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

        assert received["raw"] == event
        assert received["self_id"] == "42"
        expected = hmac.new(b"mysecret", event.encode(), hashlib.sha1).hexdigest()
        assert received["signature"] == f"sha1={expected}"
        await adapter.close()
        server.should_exit = True
        await stop_tasks(server_task)

    run(main())
