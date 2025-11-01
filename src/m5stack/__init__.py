"""Public API for the M5Stack sensor library."""

from .exceptions import SensorError, SHT30Error, QMP6988Error
from .sht30 import SHT30, SHT30Fake
from .qmp6988 import QMP6988, QMP6988Fake

__all__ = [
    "SHT30",
    "SHT30Error",
    "SHT30Fake",
    "QMP6988",
    "QMP6988Error",
    "QMP6988Fake",
    "SensorError",
]