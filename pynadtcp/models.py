"""Data models for pynadtcp."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class NadState:
    """Snapshot of the amplifier's state.

    Every field is ``None`` until the device has reported a value for it.
    """

    power: bool | None = None
    volume_db: float | None = None
    muted: bool | None = None
    source: str | None = None
    model: str | None = None
    version: str | None = None
