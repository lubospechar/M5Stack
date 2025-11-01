"""Driver for the QMP6988 pressure sensor (pressure-only)."""


import time
import random

from dataclasses import dataclass
from typing import Callable, Any, Protocol, runtime_checkable

from smbus2 import SMBus

from m5stack.qmp6988_codec import parse_pressure_frame
from m5stack.conversion_utils import raw_to_pascal
from m5stack.exceptions import QMP6988Error


@runtime_checkable
class IQMP6988(Protocol):
    """Interface for reading pressure from a QMP6988 sensor."""

    bus_number: int
    address: int

    def read_pressure(self) -> float:
        """Return the pressure in Pascals (Pa)."""
        ...


# --- Internal QMP6988 register/configuration ----------------------------------

_DEFAULT_ADDRESS: int = 0x70

# Register map (BMP280/QMP6988 compatible for data path)
_REG_STATUS     = 0xF3
_REG_CTRL_MEAS  = 0xF4
_REG_PRESS_MSB  = 0xF7  # LSB=0xF8, XLSB=0xF9

# CTRL_MEAS bits: [7:5]=osrs_t, [4:2]=osrs_p, [1:0]=mode
_OSRS_T_SKIP = 0b000 << 5
_OSRS_P_X4   = 0b011 << 2
_MODE_FORCED = 0b01

_READ_FRAME_LENGTH: int   = 3   # 3 data bytes (no CRC)
_MEASUREMENT_DELAY_S: float = 0.010
_POLL_SLEEP_S: float        = 0.003
_POLL_TIMEOUT_S: float      = 0.150


# --- QMP6988 Driver Implementation --------------------------------------------

@dataclass(slots=True)
class QMP6988:
    """Minimal QMP6988 single-shot pressure reader with simple raw->Pa scaling."""

    bus_number: int = 1
    address: int = _DEFAULT_ADDRESS
    measurement_delay_seconds: float = _MEASUREMENT_DELAY_S
    bus_factory: Callable[[int], Any] = SMBus

    coef_a: float = 0.01
    coef_b: float = 0.0

    # --- Internal helpers -----------------------------------------------------

    def _trigger_forced_measure(self, bus) -> None:
        """Configure oversampling and start a single forced measurement."""
        ctrl = _OSRS_T_SKIP | _OSRS_P_X4 | _MODE_FORCED
        bus.write_i2c_block_data(self.address, _REG_CTRL_MEAS, [ctrl])

    def _wait_measurement(self, bus) -> None:
        """Wait until measurement is finished or timeout occurs."""
        deadline = time.monotonic() + _POLL_TIMEOUT_S
        while True:
            status = bus.read_byte_data(self.address, _REG_STATUS)
            measuring = (status & 0x08) != 0  # measuring bit
            if not measuring:
                return
            if time.monotonic() > deadline:
                raise QMP6988Error("Timeout waiting for measurement ready")
            time.sleep(_POLL_SLEEP_S)

    def _read_frame(self) -> bytes:
        """Read 3 bytes of pressure data (MSB..XLSB) starting from 0xF7."""
        try:
            with self.bus_factory(self.bus_number) as bus:
                self._trigger_forced_measure(bus)
                time.sleep(self.measurement_delay_seconds)
                self._wait_measurement(bus)
                data = bus.read_i2c_block_data(self.address, _REG_PRESS_MSB, _READ_FRAME_LENGTH)
                return bytes(data)
        except OSError as error:
            raise QMP6988Error(f"I2C communication failed: {error}") from error


    def read_pressure(self) -> float:
        """Read and return pressure in Pascals (Pa)."""
        frame = self._read_frame()
        raw = parse_pressure_frame(frame)  # 3-byte frame -> 24-bit raw
        return raw_to_pascal(raw, self.coef_a, self.coef_b)


@dataclass(slots=True)
class QMP6988Fake:
    """Fake QMP6988 sensor for testing."""

    def read_pressure(self) -> float:
        """Read and return pressure in Pascals (Pa)."""
        return random.uniform(98_000.0, 103_000.0)
