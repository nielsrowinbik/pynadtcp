"""Low-level command grammar and asyncio transport for the NAD TCP protocol."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
import socket
from typing import Any

from .const import C338_CMDS, EOL
from .exceptions import NadException

_LOGGER = logging.getLogger(__name__)


def make_command(key: str, operator: str, value: Any = None) -> str:
    """Build a raw protocol command string such as ``Main.Volume=-40``.

    Raises:
        NadException: if the key/operator combination is invalid.
    """
    try:
        cmd_desc = C338_CMDS[key]
    except KeyError:
        raise NadException(f"Unknown command: {key}") from None
    if operator not in cmd_desc["supported_operators"]:
        raise NadException(f"Operator {operator!r} is not valid for {key}")
    if operator == "=" and value is None:
        raise NadException(f"Operator '=' for {key} requires a value")
    if operator in ("?", "+", "-") and value is not None:
        raise NadException(f"Operator {operator!r} cannot take a value")
    if value is None:
        return f"{key}{operator}"
    if cmd_desc.get("type") is bool:
        value = cmd_desc["values"][int(bool(value))]
    return f"{key}{operator}{value}"


def parse_line(line: str) -> tuple[str, Any] | None:
    """Parse a single ``key=value`` response line.

    Returns ``None`` for lines without a value or keys we do not understand,
    so unexpected output never crashes the parser.
    """
    key, sep, raw = line.partition("=")
    if not sep:
        return None
    cmd_desc = C338_CMDS.get(key)
    if cmd_desc is None:
        return None
    value_type = cmd_desc.get("type")
    try:
        if value_type is bool:
            return key, bool(cmd_desc["values"].index(raw))
        if value_type is not None:
            return key, value_type(raw)
    except (ValueError, KeyError):
        return None
    return key, raw


class NadProtocol(asyncio.Protocol):
    """asyncio protocol that frames the device's line-based output."""

    def __init__(
        self,
        on_lines: Callable[[list[tuple[str, Any]]], None],
        on_connection_lost: Callable[[Exception | None], None],
    ) -> None:
        """Initialize the protocol with line and disconnect callbacks."""
        self._on_lines = on_lines
        self._on_connection_lost = on_connection_lost
        self._buffer = ""
        self.transport: asyncio.Transport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        """Store the transport and enable TCP keepalive (best effort)."""
        assert isinstance(transport, asyncio.Transport)
        self.transport = transport
        sock: socket.socket | None = transport.get_extra_info("socket")
        if sock is not None:
            _enable_keepalive(sock)

    def data_received(self, data: bytes) -> None:
        """Split incoming bytes into complete lines and hand them off."""
        self._buffer += data.decode("utf-8", "ignore").replace("\x00", "")
        parsed: list[tuple[str, Any]] = []
        while EOL in self._buffer:
            line, self._buffer = self._buffer.split(EOL, 1)
            if not line:
                continue
            result = parse_line(line)
            if result is not None:
                parsed.append(result)
        if parsed:
            self._on_lines(parsed)

    def connection_lost(self, exc: Exception | None) -> None:
        """Notify the client that the transport was closed."""
        self.transport = None
        self._on_connection_lost(exc)


def _enable_keepalive(sock: socket.socket) -> None:
    """Turn on TCP keepalive, tuning the timers where the platform allows."""
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    for name, value in (
        ("TCP_KEEPIDLE", 60),
        ("TCP_KEEPINTVL", 10),
        ("TCP_KEEPCNT", 3),
    ):
        option = getattr(socket, name, None)
        if option is None:
            continue
        try:
            sock.setsockopt(socket.IPPROTO_TCP, option, value)
        except OSError:  # noqa: PERF203 - best effort per option
            _LOGGER.debug("Could not set socket option %s", name)
