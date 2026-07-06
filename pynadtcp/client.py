"""Asyncio client for NAD amplifiers controllable over TCP (e.g. the C338)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import inspect
import logging
from types import TracebackType
from typing import Any

from .const import (
    CMD_MAIN,
    CMD_MODEL,
    CMD_MUTE,
    CMD_POWER,
    CMD_SOURCE,
    CMD_VERSION,
    CMD_VOLUME,
    C338_CMDS,
    CMD_MIN_INTERVAL,
    DEFAULT_PORT,
    VOLUME_MAX_DB,
    VOLUME_MIN_DB,
)
from .exceptions import NadConnectionError, NadException, NadTimeoutError
from .models import NadState
from .protocol import NadProtocol, make_command

_LOGGER = logging.getLogger(__name__)

StateCallback = Callable[["NadClient"], Awaitable[None] | None]


class NadClient:
    """Manage a persistent control connection to a NAD amplifier."""

    def __init__(
        self,
        host: str,
        *,
        port: int = DEFAULT_PORT,
        connect_timeout: float = 5.0,
        reconnect_interval: float = 15.0,
    ) -> None:
        """Initialize the client. No connection is opened until ``connect``."""
        self._host = host
        self._port = port
        self._connect_timeout = connect_timeout
        self._reconnect_interval = reconnect_interval

        self._loop: asyncio.AbstractEventLoop | None = None
        self._transport: asyncio.Transport | None = None
        self._raw: dict[str, Any] = {}
        self._state = NadState()
        self._callbacks: set[StateCallback] = set()

        self._closing = False
        self._auto_reconnect = False
        self._ready = asyncio.Event()
        self._reconnect_task: asyncio.Task[None] | None = None
        self._cmd_lock = asyncio.Lock()
        self._last_cmd = 0.0

    @property
    def host(self) -> str:
        """Return the configured host."""
        return self._host

    @property
    def state(self) -> NadState:
        """Return the latest known device state."""
        return self._state

    @property
    def sources(self) -> list[str]:
        """Return the list of selectable input sources."""
        return list(C338_CMDS[CMD_SOURCE]["values"])

    def is_connected(self) -> bool:
        """Return whether a live connection to the device exists."""
        return self._transport is not None and not self._closing

    async def connect(self) -> None:
        """Open the connection and wait until the device identifies itself.

        Raises:
            NadConnectionError: if the socket cannot be opened.
            NadTimeoutError: if the device does not respond in time.
        """
        self._closing = False
        self._loop = asyncio.get_running_loop()
        await self._open()
        self._auto_reconnect = True

    async def disconnect(self) -> None:
        """Close the connection and stop reconnecting."""
        self._closing = True
        self._auto_reconnect = False
        if self._reconnect_task is not None:
            self._reconnect_task.cancel()
            self._reconnect_task = None
        if self._transport is not None:
            self._transport.close()
            self._transport = None

    async def __aenter__(self) -> NadClient:
        """Connect on entering an async context."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Disconnect on leaving an async context."""
        await self.disconnect()

    def register_state_update_callback(
        self, callback: StateCallback
    ) -> Callable[[], None]:
        """Register a callback invoked on every state or connection change.

        Returns a function that unregisters the callback.
        """
        self._callbacks.add(callback)

        def _unsubscribe() -> None:
            self._callbacks.discard(callback)

        return _unsubscribe

    def unregister_state_update_callback(self, callback: StateCallback) -> None:
        """Unregister a previously registered callback."""
        self._callbacks.discard(callback)

    async def power_on(self) -> None:
        """Turn the amplifier on."""
        await self._send(make_command(CMD_POWER, "=", True))

    async def power_off(self) -> None:
        """Turn the amplifier off."""
        await self._send(make_command(CMD_POWER, "=", False))

    async def set_mute(self, mute: bool) -> None:
        """Mute or unmute the amplifier."""
        await self._send(make_command(CMD_MUTE, "=", mute))

    async def set_volume(self, volume_db: float) -> None:
        """Set the volume in dB, clamped to the device's supported range."""
        clamped = round(max(VOLUME_MIN_DB, min(VOLUME_MAX_DB, volume_db)))
        await self._send(make_command(CMD_VOLUME, "=", clamped))

    async def volume_up(self) -> None:
        """Increase the volume by one device step."""
        await self._send(make_command(CMD_VOLUME, "+"))

    async def volume_down(self) -> None:
        """Decrease the volume by one device step."""
        await self._send(make_command(CMD_VOLUME, "-"))

    async def select_source(self, source: str) -> None:
        """Select an input source."""
        await self._send(make_command(CMD_SOURCE, "=", source))

    async def _open(self) -> None:
        """Open a single connection and wait for the device to identify."""
        assert self._loop is not None
        self._ready.clear()

        def _factory() -> NadProtocol:
            return NadProtocol(self._handle_lines, self._handle_connection_lost)

        try:
            transport, _ = await asyncio.wait_for(
                self._loop.create_connection(_factory, self._host, self._port),
                timeout=self._connect_timeout,
            )
        except TimeoutError as err:
            raise NadTimeoutError(
                f"Timed out connecting to {self._host}:{self._port}"
            ) from err
        except OSError as err:
            raise NadConnectionError(
                f"Could not connect to {self._host}:{self._port}: {err}"
            ) from err

        self._transport = transport
        await self._send(make_command(CMD_MAIN, "?"))
        try:
            async with asyncio.timeout(self._connect_timeout):
                await self._ready.wait()
        except TimeoutError as err:
            transport.close()
            raise NadTimeoutError(
                f"No response from NAD device at {self._host}:{self._port}"
            ) from err

    async def _reconnect(self) -> None:
        """Retry opening the connection until it succeeds or we close."""
        while not self._closing:
            await asyncio.sleep(self._reconnect_interval)
            if self._closing:
                return
            try:
                await self._open()
            except NadException as err:
                _LOGGER.debug("Reconnect to %s failed: %s", self._host, err)
                continue
            _LOGGER.debug("Reconnected to %s", self._host)
            return

    def _handle_lines(self, lines: list[tuple[str, Any]]) -> None:
        """Apply a batch of parsed response lines to the local state."""
        for key, value in lines:
            self._raw[key] = value
            # A volume change implicitly clears mute on the device.
            if key == CMD_VOLUME and self._raw.get(CMD_MUTE) is True:
                self._raw[CMD_MUTE] = False
        self._rebuild_state()
        if CMD_MODEL in self._raw:
            self._ready.set()
        self._schedule_notify()

    def _handle_connection_lost(self, exc: Exception | None) -> None:
        """React to the transport closing, reconnecting if appropriate."""
        self._transport = None
        self._raw.clear()
        self._rebuild_state()
        self._ready.clear()
        self._schedule_notify()
        if (
            self._auto_reconnect
            and not self._closing
            and self._loop is not None
            and (self._reconnect_task is None or self._reconnect_task.done())
        ):
            _LOGGER.debug("Connection to %s lost (%s); reconnecting", self._host, exc)
            self._reconnect_task = self._loop.create_task(self._reconnect())

    def _rebuild_state(self) -> None:
        """Recompute the public ``NadState`` from raw device values."""
        version = self._raw.get(CMD_VERSION)
        self._state = NadState(
            power=self._raw.get(CMD_POWER),
            volume_db=self._raw.get(CMD_VOLUME),
            muted=self._raw.get(CMD_MUTE),
            source=self._raw.get(CMD_SOURCE),
            model=self._raw.get(CMD_MODEL),
            version=None if version is None else str(version),
        )

    def _schedule_notify(self) -> None:
        """Schedule callback notification on the event loop."""
        if self._loop is not None:
            self._loop.create_task(self._notify())

    async def _notify(self) -> None:
        """Invoke every registered callback, awaiting async ones."""
        for callback in list(self._callbacks):
            result = callback(self)
            if inspect.isawaitable(result):
                await result

    async def _send(self, command: str) -> None:
        """Write a command to the device, throttled to the minimum interval."""
        transport = self._transport
        if transport is None:
            raise NadConnectionError("Not connected to the device")
        assert self._loop is not None
        async with self._cmd_lock:
            wait = (self._last_cmd + CMD_MIN_INTERVAL) - self._loop.time()
            if wait > 0:
                await asyncio.sleep(wait)
            transport.write(command.encode("utf-8"))
            self._last_cmd = self._loop.time()
