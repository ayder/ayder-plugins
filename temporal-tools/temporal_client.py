"""Lazy Temporal SDK client adapter."""

from __future__ import annotations

import asyncio
import inspect
import logging
import socket
from typing import Any, Awaitable, Callable, cast

from ayder_cli.core.config import Config, load_config

logger = logging.getLogger(__name__)

try:
    from ayder_cli.tools.plugin_status import set_status as _set_status
except ImportError:  # older ayder without the badge registry
    def _set_status(name: str, label: str, color: str) -> None:  # no-op fallback
        pass


class TemporalClientUnavailableError(RuntimeError):
    """Raised when Temporal client cannot be initialized."""


def _import_temporal_client_class() -> type:
    """Import temporalio Client lazily."""
    from temporalio.client import Client  # type: ignore

    return Client


def _default_connector(client_cls: type, host: str, namespace: str) -> Any:
    """Create Temporal client using SDK connect entrypoint."""
    connect_fn = getattr(client_cls, "connect", None)
    if connect_fn is None:
        raise TemporalClientUnavailableError("Temporal Client.connect is unavailable")

    result = connect_fn(host, namespace=namespace)
    if inspect.isawaitable(result):
        async_result = cast(Awaitable[Any], result)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            async def _resolve() -> Any:
                return await async_result

            return asyncio.run(_resolve())
        raise TemporalClientUnavailableError(
            "Cannot run synchronous temporal connect while event loop is active"
        )
    return result


class TemporalClientAdapter:
    """Lazily initialized Temporal client adapter with caching."""

    def __init__(
        self,
        config: Config | None = None,
        connector: Callable[[type, str, str], Any] | None = None,
    ) -> None:
        self._config = config or load_config()
        self._connector = connector or _default_connector
        self._client: Any | None = None

    @property
    def enabled(self) -> bool:
        """Whether Temporal runtime is enabled in config."""
        return self._config.temporal.enabled

    def get_client(self) -> Any:
        """Get cached Temporal client, initializing lazily when needed."""
        if not self.enabled:
            raise TemporalClientUnavailableError(
                "Temporal runtime is disabled in config"
            )

        if self._client is not None:
            return self._client

        try:
            client_cls = _import_temporal_client_class()
        except ImportError as e:
            raise TemporalClientUnavailableError(
                "temporalio package is not installed. "
                "Install optional dependency: uv pip install -e '.[temporal]'"
            ) from e

        self._client = self._connector(
            client_cls,
            self._config.temporal.host,
            self._config.temporal.namespace,
        )
        return self._client

    def clear_cache(self) -> None:
        """Clear cached Temporal client (mainly for tests)."""
        self._client = None


# --- status badge ----------------------------------------------------------
#
# Publish a "TMP" badge to ayder's status bar (via the shared plugin_status
# registry), mirroring the mcp-tool "MCP" badge: green when the configured
# Temporal server is reachable, red when it isn't.


def set_green(detail: str = "connected") -> None:
    """Publish a green Temporal status badge (e.g. 'TMP: connected')."""
    _set_status("temporal", f"TMP: {detail}", "green")


def set_red(detail: str = "unreachable") -> None:
    """Publish a red Temporal status badge (e.g. 'TMP: unreachable')."""
    _set_status("temporal", f"TMP: {detail}", "red")


def probe_reachable(host: str, timeout: float = 1.0) -> bool:
    """Best-effort TCP reachability check for a ``host:port`` address.

    A lightweight liveness probe — it does NOT perform a Temporal handshake, only
    confirms the port accepts a TCP connection, so it can't hang ayder's startup.
    """
    head, sep, port_str = host.rpartition(":")
    if not sep:  # no port specified
        target_host, port = host, 7233
    else:
        target_host = head
        try:
            port = int(port_str)
        except ValueError:
            return False
    try:
        with socket.create_connection((target_host, port), timeout=timeout):
            return True
    except OSError:
        return False


def publish_status() -> None:
    """Publish the Temporal status badge at plugin load.

    No badge when Temporal is disabled in config; green when the configured host
    is reachable, red otherwise. Never raises — a status probe must not break
    plugin import.
    """
    try:
        cfg = load_config()
        if not cfg.temporal.enabled:
            return
        if probe_reachable(cfg.temporal.host):
            set_green()
        else:
            set_red()
    except Exception as exc:  # defensive: status must never break loading
        logger.debug("temporal status probe failed: %s", exc)
