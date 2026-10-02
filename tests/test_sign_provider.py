import asyncio
import importlib.util
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

VECTORS = [
    (bytes.fromhex("00"), "93a1f04712ec636afacdc8b5de7bfd0e135349ba0db46c0298dee6de4454874c"),
    (bytes.fromhex("01"), "eb79babe6c4efa49d7e14f645b32f7b616b5b73f558f5670419155253a94cfb5"),
    (b"hello", "31408282c1640790bb51efd07dedfa6270ce9ffff9534e3f6a96589b0174d98c"),
]
ROOT_PROVIDER = Path(__file__).resolve().parent.parent / "sign_provider.py"


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


@pytest.mark.skipif(not ROOT_PROVIDER.exists(), reason="root sign_provider.py is untracked and local-only")
def test_root_provider_has_stable_vectors_and_command_domain_separation():
    spec = importlib.util.spec_from_file_location("euleronebot.test_root_provider", str(ROOT_PROVIDER))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for body, expected in VECTORS:
        assert module.compute_sign(body, nonce_time=1700000000).hex() == expected
    assert module.compute_sign(b"hello", "wtlogin.login", nonce_time=1700000000) != module.compute_sign(
        b"hello", "MessageSvc.PbSendMsg", nonce_time=1700000000
    )

    get_sign = load_sign_provider(str(ROOT_PROVIDER), "sign_provider")(
        None, 1, "00" * 16, "V1_LNX_NQ_3.2.26_46494_GW_B"
    )
    result = asyncio.run(get_sign("MessageSvc.PbSendMsg", 1, VECTORS[0][0]))
    assert result["token"] == ""
    assert bytes.fromhex(result["extra"]) == b"\x12\x1b" + b"V1_LNX_NQ_3.2.26_46494_GW_B"
    assert len(bytes.fromhex(result["sign"])) == 32


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


def test_url_mode_uses_hiroqq_signer_when_no_custom_provider_is_configured(monkeypatch):
    captured: dict[str, Any] = {}
    monkeypatch.setattr("lagrange.Client", FakeClient)
    monkeypatch.setattr("lagrange.InfoManager", FakeInfoManager)
    lag = Lagrange(
        3672492480,
        "linux",
        "https://sign.example.com/api/sign/sec-sign",
        device_info_path="./unused.json",
        signinfo_path="./unused.bin",
    )

    async def fake_login(client):
        captured["sign"] = client.sign
        return True

    lag.login = fake_login  # type: ignore[method-assign]
    asyncio.run(lag.run())
    assert captured["sign"].__name__ == "get_sign"
