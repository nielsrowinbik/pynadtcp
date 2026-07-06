"""Exceptions raised by pynadtcp."""

from __future__ import annotations


class NadException(Exception):
    """Base class for all pynadtcp errors."""


class NadConnectionError(NadException):
    """Raised when the connection to the device fails or is lost."""


class NadTimeoutError(NadException):
    """Raised when the device does not respond in time."""
