"""Async client library for NAD amplifiers controllable over TCP (e.g. C338)."""

from __future__ import annotations

from .client import NadClient
from .const import DEFAULT_PORT, VOLUME_MAX_DB, VOLUME_MIN_DB
from .exceptions import NadConnectionError, NadException, NadTimeoutError
from .models import NadState

__all__ = [
    "DEFAULT_PORT",
    "VOLUME_MAX_DB",
    "VOLUME_MIN_DB",
    "NadClient",
    "NadConnectionError",
    "NadException",
    "NadState",
    "NadTimeoutError",
]

__version__ = "1.0.0"
