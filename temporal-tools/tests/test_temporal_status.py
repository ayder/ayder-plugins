"""Tests for the temporal-tools status badge.

The plugin publishes a green/red "TMP" badge to ayder's status bar based on
whether a configured Temporal server is reachable, mirroring the mcp-tool badge.
"""

import socket
from types import SimpleNamespace

import temporal_client
from ayder_cli.tools import plugin_status


def _cfg(enabled: bool, host: str = "localhost:7233"):
    return SimpleNamespace(
        temporal=SimpleNamespace(enabled=enabled, host=host, namespace="default")
    )


class _FakeConn:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


# --- badge writers ---------------------------------------------------------


def test_set_green_writes_green_badge():
    temporal_client.set_green()
    assert plugin_status.get_all()["temporal"] == ("TMP: connected", "green")


def test_set_red_writes_red_badge():
    temporal_client.set_red()
    assert plugin_status.get_all()["temporal"] == ("TMP: unreachable", "red")


# --- reachability probe ----------------------------------------------------


def test_probe_reachable_false_when_connection_refused(monkeypatch):
    def boom(*a, **k):
        raise OSError("refused")

    monkeypatch.setattr(socket, "create_connection", boom)
    assert temporal_client.probe_reachable("localhost:7233") is False


def test_probe_reachable_true_when_connects(monkeypatch):
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: _FakeConn())
    assert temporal_client.probe_reachable("localhost:7233") is True


def test_probe_parses_host_and_port(monkeypatch):
    captured = {}

    def fake(addr, timeout=None):
        captured["addr"] = addr
        return _FakeConn()

    monkeypatch.setattr(socket, "create_connection", fake)
    temporal_client.probe_reachable("example.com:1234")
    assert captured["addr"] == ("example.com", 1234)


# --- publish_status integration -------------------------------------------


def test_publish_status_disabled_sets_no_badge(monkeypatch):
    monkeypatch.setattr(temporal_client, "load_config", lambda: _cfg(enabled=False))
    temporal_client.publish_status()
    assert "temporal" not in plugin_status.get_all()


def test_publish_status_enabled_unreachable_is_red(monkeypatch):
    monkeypatch.setattr(temporal_client, "load_config", lambda: _cfg(enabled=True))
    monkeypatch.setattr(
        temporal_client, "probe_reachable", lambda host, timeout=1.0: False
    )
    temporal_client.publish_status()
    assert plugin_status.get_all()["temporal"] == ("TMP: unreachable", "red")


def test_publish_status_enabled_reachable_is_green(monkeypatch):
    monkeypatch.setattr(temporal_client, "load_config", lambda: _cfg(enabled=True))
    monkeypatch.setattr(
        temporal_client, "probe_reachable", lambda host, timeout=1.0: True
    )
    temporal_client.publish_status()
    assert plugin_status.get_all()["temporal"] == ("TMP: connected", "green")


def test_publish_status_never_raises(monkeypatch):
    """A status probe must never break plugin import."""
    def boom():
        raise RuntimeError("config blew up")

    monkeypatch.setattr(temporal_client, "load_config", boom)
    temporal_client.publish_status()  # should swallow
    assert "temporal" not in plugin_status.get_all()
