"""Tests for the pynadtcp client and protocol."""

from __future__ import annotations

import asyncio
import socket

import pytest

from pynadtcp import NadClient, NadConnectionError, NadTimeoutError
from pynadtcp.exceptions import NadException
from pynadtcp.protocol import make_command, parse_line

STATE_DUMP = (
    "Main.Model=NADC338\r\n"
    "Main.Version=1.53\r\n"
    "Main.Power=On\r\n"
    "Main.Volume=-40\r\n"
    "Main.Mute=Off\r\n"
    "Main.Source=Stream\r\n"
)


class FakeNad:
    """A minimal fake NAD device speaking the port-30001 protocol."""

    def __init__(self) -> None:
        """Initialize the fake device."""
        self.received: list[str] = []
        self._server: asyncio.AbstractServer | None = None
        self._writers: list[asyncio.StreamWriter] = []
        self.port = 0

    async def start(self) -> None:
        """Start listening on an ephemeral local port."""
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]

    async def _handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        self._writers.append(writer)
        while not reader.at_eof():
            data = await reader.read(1024)
            if not data:
                break
            text = data.decode()
            self.received.append(text)
            if "Main?" in text:
                writer.write(STATE_DUMP.encode())
                await writer.drain()
        writer.close()

    async def push(self, text: str) -> None:
        """Send unsolicited output to every connected client."""
        for writer in self._writers:
            writer.write(text.encode())
            await writer.drain()

    async def stop(self) -> None:
        """Stop the server if it is still running."""
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None


@pytest.fixture
async def fake_nad() -> FakeNad:
    """Provide a running fake NAD device."""
    device = FakeNad()
    await device.start()
    yield device
    await device.stop()


async def test_connect_populates_state(fake_nad: FakeNad) -> None:
    """Connecting queries the device and fills in the state."""
    client = NadClient("127.0.0.1", port=fake_nad.port)
    await client.connect()

    assert client.is_connected()
    assert client.state.model == "NADC338"
    assert client.state.version == "1.53"
    assert client.state.power is True
    assert client.state.volume_db == -40.0
    assert client.state.muted is False
    assert client.state.source == "Stream"
    assert client.sources[0] == "Stream"

    await client.disconnect()
    assert not client.is_connected()


async def test_context_manager(fake_nad: FakeNad) -> None:
    """The client works as an async context manager."""
    async with NadClient("127.0.0.1", port=fake_nad.port) as client:
        assert client.is_connected()
    assert not client.is_connected()


async def test_callbacks_fire(fake_nad: FakeNad) -> None:
    """Registered callbacks receive state updates."""
    client = NadClient("127.0.0.1", port=fake_nad.port)
    powers: list[bool | None] = []

    async def _cb(c: NadClient) -> None:
        powers.append(c.state.power)

    unsubscribe = client.register_state_update_callback(_cb)
    await client.connect()
    await asyncio.sleep(0.05)

    assert True in powers
    unsubscribe()
    await client.disconnect()


async def test_unparseable_lines_keep_connection(fake_nad: FakeNad) -> None:
    """Bad lines are skipped; later valid lines still apply on the same connection."""
    client = NadClient("127.0.0.1", port=fake_nad.port)
    await client.connect()

    await fake_nad.push("garbage\r\nMain.Unknown=1\r\nMain.Volume=-20\r\n")
    await asyncio.sleep(0.05)

    assert client.state.volume_db == -20.0
    assert client.is_connected()
    await client.disconnect()


@pytest.mark.parametrize(
    ("requested", "expected"),
    [(-30, "Main.Volume=-30"), (-200, "Main.Volume=-80"), (10, "Main.Volume=0")],
)
async def test_set_volume_clamped(
    fake_nad: FakeNad, requested: float, expected: str
) -> None:
    """Volume is clamped to the device range before sending."""
    client = NadClient("127.0.0.1", port=fake_nad.port)
    await client.connect()
    fake_nad.received.clear()

    await client.set_volume(requested)
    await asyncio.sleep(0.05)

    assert expected in "".join(fake_nad.received)
    await client.disconnect()


async def test_power_and_source_commands(fake_nad: FakeNad) -> None:
    """Power and source commands are encoded correctly on the wire."""
    client = NadClient("127.0.0.1", port=fake_nad.port)
    await client.connect()
    fake_nad.received.clear()

    await client.power_on()
    await client.select_source("Phono")
    await client.set_mute(True)
    await asyncio.sleep(0.05)

    sent = "".join(fake_nad.received)
    assert "Main.Power=On" in sent
    assert "Main.Source=Phono" in sent
    assert "Main.Mute=On" in sent
    await client.disconnect()


async def test_connect_refused() -> None:
    """Connecting to a closed port raises NadConnectionError."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    client = NadClient("127.0.0.1", port=port, connect_timeout=1)
    with pytest.raises((NadConnectionError, NadTimeoutError)):
        await client.connect()
    assert not client.is_connected()


async def test_no_response_times_out() -> None:
    """A device that accepts but never answers raises NadTimeoutError."""

    async def _silent(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        await reader.read(1024)
        await asyncio.sleep(5)
        # Without this, wait_closed() below hangs on Python 3.12.
        writer.close()

    server = await asyncio.start_server(_silent, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]

    client = NadClient("127.0.0.1", port=port, connect_timeout=0.3)
    with pytest.raises(NadTimeoutError):
        await client.connect()

    server.close()
    await server.wait_closed()


def test_make_command() -> None:
    """Commands are formatted per the protocol grammar."""
    assert make_command("Main", "?") == "Main?"
    assert make_command("Main.Power", "=", True) == "Main.Power=On"
    assert make_command("Main.Power", "=", False) == "Main.Power=Off"
    assert make_command("Main.Volume", "=", -40) == "Main.Volume=-40"
    assert make_command("Main.Volume", "+") == "Main.Volume+"


def test_make_command_invalid() -> None:
    """Invalid keys and operator/value combinations raise."""
    with pytest.raises(NadException):
        make_command("Unknown.Key", "?")
    with pytest.raises(NadException):
        make_command("Main.Power", "!")
    with pytest.raises(NadException):
        make_command("Main.Volume", "?", -40)
    with pytest.raises(NadException):
        make_command("Main.Power", "=")


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("Main.Power=On", ("Main.Power", True)),
        ("Main.Power=Off", ("Main.Power", False)),
        ("Main.Volume=-40", ("Main.Volume", -40.0)),
        ("Main.Source=Stream", ("Main.Source", "Stream")),
        ("Main.Model=NADC338", ("Main.Model", "NADC338")),
        ("Unknown.Key=1", None),
        ("garbage", None),
        ("Main.Mute=Weird", None),
    ],
)
def test_parse_line(line: str, expected: tuple[str, object] | None) -> None:
    """Response lines parse to typed values, bad input to None."""
    assert parse_line(line) == expected
