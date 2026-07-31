import asyncio

import pytest

from euleronebot.utils import with_retry


def run(coro):
    return asyncio.run(coro)


def test_success_on_first_try():
    async def factory():
        return 42

    assert run(with_retry(factory)) == 42


def test_retries_then_succeeds():
    calls = {"n": 0}

    async def factory():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("boom")
        return "ok"

    assert run(with_retry(factory)) == "ok"
    assert calls["n"] == 3


def test_exhausts_retries():
    async def factory():
        raise ValueError("always fails")

    with pytest.raises(RuntimeError, match="Max retries"):
        run(with_retry(factory))


def test_custom_maximum():
    calls = {"n": 0}

    async def factory():
        calls["n"] += 1
        raise ValueError("x")

    with pytest.raises(RuntimeError):
        run(with_retry(factory, maximum=2))
    assert calls["n"] == 2
