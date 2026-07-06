"""Constants and the command table for the NAD TCP protocol."""

from __future__ import annotations

from typing import Any

#: TCP port the NAD amplifier listens on for the control protocol.
DEFAULT_PORT = 30001

#: Minimum interval (seconds) between commands sent to the device.
CMD_MIN_INTERVAL = 0.15

#: Line terminator used by the protocol.
EOL = "\r\n"

# Command keys used by the protocol.
CMD_MAIN = "Main"
CMD_BRIGHTNESS = "Main.Brightness"
CMD_BASS_EQ = "Main.Bass"
CMD_CONTROL_STANDBY = "Main.ControlStandby"
CMD_AUTO_STANDBY = "Main.AutoStandby"
CMD_VERSION = "Main.Version"
CMD_MODEL = "Main.Model"
CMD_MUTE = "Main.Mute"
CMD_POWER = "Main.Power"
CMD_AUTO_SENSE = "Main.AutoSense"
CMD_SOURCE = "Main.Source"
CMD_VOLUME = "Main.Volume"

MSG_ON = "On"
MSG_OFF = "Off"

#: Description of every command the C338 supports: which operators are valid,
#: the accepted values, and the Python type each value maps to. This table
#: drives both command formatting and response parsing.
C338_CMDS: dict[str, dict[str, Any]] = {
    "Main": {"supported_operators": ["?"]},
    "Main.AnalogGain": {
        "supported_operators": ["+", "-", "=", "?"],
        "type": int,
    },
    "Main.Brightness": {
        "supported_operators": ["+", "-", "=", "?"],
        "values": range(0, 4),
        "type": int,
    },
    "Main.Mute": {
        "supported_operators": ["+", "-", "=", "?"],
        "values": [MSG_OFF, MSG_ON],
        "type": bool,
    },
    "Main.Power": {
        "supported_operators": ["+", "-", "=", "?"],
        "values": [MSG_OFF, MSG_ON],
        "type": bool,
    },
    "Main.Volume": {
        "supported_operators": ["+", "-", "=", "?"],
        "values": range(-80, 1),
        "type": float,
    },
    "Main.Bass": {
        "supported_operators": ["+", "-", "=", "?"],
        "values": [MSG_OFF, MSG_ON],
        "type": bool,
    },
    "Main.ControlStandby": {
        "supported_operators": ["+", "-", "=", "?"],
        "values": [MSG_OFF, MSG_ON],
        "type": bool,
    },
    "Main.AutoStandby": {
        "supported_operators": ["+", "-", "=", "?"],
        "values": [MSG_OFF, MSG_ON],
        "type": bool,
    },
    "Main.AutoSense": {
        "supported_operators": ["+", "-", "=", "?"],
        "values": [MSG_OFF, MSG_ON],
        "type": bool,
    },
    "Main.Source": {
        "supported_operators": ["+", "-", "=", "?"],
        "values": [
            "Stream",
            "Wireless",
            "TV",
            "Phono",
            "Coax1",
            "Coax2",
            "Opt1",
            "Opt2",
        ],
    },
    "Main.Version": {"supported_operators": ["?"]},
    "Main.Model": {"supported_operators": ["?"]},
}

#: Lowest volume the device accepts, in dB.
VOLUME_MIN_DB = -80.0
#: Highest volume the device accepts, in dB.
VOLUME_MAX_DB = 0.0
