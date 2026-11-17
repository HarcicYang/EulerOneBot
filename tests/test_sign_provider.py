import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from lagrange import Lagrange
from lagrange.info.app import app_list

from euleronebot.utils.sign_provider import _MODULE_NAME, load_sign_provider

PROVIDER_SOURCE = "\n".join(
    [
        "def make_sign_provider(sign_url, uin, guid, qua):",
        "    async def get_sign(cmd, seq, buf):",
        '        return {"sign": "ab" * 32, "token": "", "extra": "cd" * 8}',
        "",
        "    return get_sign",
    ]
)


def write_provider(tmp_path: Path) -> str:
    path = tmp_path / "provider.py"
    path.write_text(PROVIDER_SOURCE, encoding="utf-8")
    return str(path)


def test_loader_returns_factory_and_reloads_module_under_fixed_name(tmp_path):
    path = write_provider(tmp_path)
    factory = load_sign_provider(path, "make_sign_provider")
    assert sys.modules[_MODULE_NAME].__file__ == path

    get_sign = factory(None, 123, "00" * 16, "V1_LNX_NQ_3.2.26_46494_GW_B")
    assert asyncio.run(get_sign("MessageSvc.PbSendMsg", 1, b"\x00")) == {
        "sign": "ab" * 32,
        "token": "",
        "extra": "cd" * 8,
    }

    Path(path).write_text(PROVIDER_SOURCE.replace("def make_sign_provider", "def other"), encoding="utf-8")
    first = sys.modules[_MODULE_NAME]
    with pytest.raises(AttributeError):
        load_sign_provider(path, "make_sign_provider")
    assert sys.modules[_MODULE_NAME] is not first


def test_loader_surfaces_missing_file_entry_and_syntax_errors(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_sign_provider(str(tmp_path / "nope.py"), "make_sign_provider")

    path = write_provider(tmp_path)
    with pytest.raises(AttributeError):
        load_sign_provider(path, "does_not_exist")

    broken = tmp_path / "broken.py"
    broken.write_text("this is not python(", encoding="utf-8")
    with pytest.raises(SyntaxError):
        load_sign_provider(str(broken), "make_sign_provider")


class FakeClient:
    def __init__(self, *args: Any):
        self.sign = args[4]

    def connect(self):
        return None

    async def wait_closed(self):
        return None


class FakeInfoManager:
    def __init__(self, *args: Any):
        self.device = SimpleNamespace(guid="ab" * 16)
        self.sig_info = SimpleNamespace(d2="ticket")

    def __enter__(self):
        return self

    def __exit__(self, *args: Any):
        return False


def drive_hiroqq(monkeypatch, factory, sign_url):
    captured: dict[str, Any] = {}
    seen: dict[str, Any] = {}

    def recording_factory(url, uin, guid, qua):
        seen["args"] = (url, uin, guid, qua)
        getter = factory(url, uin, guid, qua)

        async def traced(cmd, seq, buf):
            seen["sign_call"] = (cmd, seq, buf)
            return await getter(cmd, seq, buf)

        return traced

    monkeypatch.setattr("lagrange.Client", FakeClient)
    monkeypatch.setattr("lagrange.InfoManager", FakeInfoManager)
    lag = Lagrange(
        3672492480,
        "linux",
        sign_url,
        device_info_path="./unused.json",
        signinfo_path="./unused.bin",
        custom_sign_provider=recording_factory,
    )

    async def fake_login(client):
        captured["client"] = client
        return True

    lag.login = fake_login  # type: ignore[method-assign]
    asyncio.run(lag.run())
    return seen, captured


def test_custom_provider_receives_live_context_and_reaches_client(monkeypatch):
    def factory(url, uin, guid, qua):
        async def get_sign(cmd, seq, buf):
            return {"sign": "00" * 32, "token": "", "extra": "11" * 8}

        return get_sign

    seen, captured = drive_hiroqq(monkeypatch, factory, "https://sign.example.com/api/sign/sec-sign")
    url, uin, guid, qua = seen["args"]

    assert url == "https://sign.example.com/api/sign/sec-sign"
    assert uin == 3672492480
    assert guid == "ab" * 16
    assert qua == app_list["linux"].qua
    assert asyncio.run(captured["client"].sign("MessageSvc.PbSendMsg", 9, b"\x00")) == {
        "sign": "00" * 32,
        "token": "",
        "extra": "11" * 8,
    }
    assert seen["sign_call"] == ("MessageSvc.PbSendMsg", 9, b"\x00")
