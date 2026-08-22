import asyncio
import traceback
from collections.abc import Callable
from typing import Any, Never

from lagrange.client.base import BaseClient

from euleronebot.hyperogger import Logger

_HEARTBEAT_TIMEOUT = 10
_heartbeat_timeout_patched = False
logger = Logger.fetch("euler").name_custom("euler.patches")


def patch_lagrange_heartbeat_timeout() -> None:
    """
    This patch is here due to an unsure bug that lagrange event emitting might be dead unexpectedly without any logs.
    """
    global _heartbeat_timeout_patched
    if _heartbeat_timeout_patched:
        return

    original_sso_heartbeat = BaseClient.sso_heartbeat

    async def sso_heartbeat_with_total_timeout(self: BaseClient, *args: Any, **kwargs: Any) -> float:
        try:
            return await asyncio.wait_for(
                original_sso_heartbeat(self, *args, **kwargs),
                timeout=_HEARTBEAT_TIMEOUT,
            )
        except TimeoutError:
            raise
        except asyncio.CancelledError as exc:
            task = asyncio.current_task()
            if task is not None and task.cancelling():
                raise
            raise TimeoutError("Lagrange heartbeat response cancelled") from exc
        except Exception as exc:
            logger.error(f"Lagrange heartbeat failed: {exc!r}")
            logger.trace(traceback.format_exc())
            raise TimeoutError("Lagrange heartbeat unexpected failure") from exc

    BaseClient.sso_heartbeat = sso_heartbeat_with_total_timeout
    _heartbeat_timeout_patched = True


def patch_lagrange_heartbeat_recovery() -> None:
    """
    Lagrange only recovers from asyncio.TimeoutError here. Any other exception kills
    the heartbeat task silently while the TCP connection may remain half-open.
    """
    async def resilient_heartbeat_task(self: BaseClient) -> Never:
        error_count = 0
        while True:
            await self.online.wait()
            if not error_count:
                await asyncio.sleep(self._heartbeat_interval)
            try:
                latency = await self.sso_heartbeat(True, 5)
                logger.trace(f"Lagrange heartbeat {latency * 1000:.2f}ms")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                error_count += 1
                if error_count < 3:
                    logger.warning(f"Lagrange heartbeat failed ({error_count}/3): {exc!r}")
                    continue
                logger.error(f"Lagrange heartbeat failed {error_count} times, reconnecting: {exc!r}")
                logger.trace(traceback.format_exc())
                self.destroy_network()
                await asyncio.sleep(_HEARTBEAT_TIMEOUT)
                continue
            error_count = 0

    BaseClient._heartbeat_task = resilient_heartbeat_task


def apply_patches() -> None:
    patches: list[Callable[[], None]] = [
        patch_lagrange_heartbeat_timeout,
        patch_lagrange_heartbeat_recovery,
    ]
    for pt in patches:
        logger.trace(f"Applying patch for {pt.__name__}")
        pt()
