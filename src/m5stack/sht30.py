"""Driver for the Sensirion SHT30 temperature and humidity sensor."""
import random
import time
from dataclasses import dataclass
from typing import Callable, Any, Protocol, runtime_checkable

from smbus2 import SMBus

from m5stack.sht30_codec import parse_measurement_frame
from m5stack.conversion_utils import raw_to_celsius, raw_to_humidity
from m5stack.exceptions import SHT30Error


@runtime_checkable
class ISHT30(Protocol):
    """Protocol (interface) for reading data from an SHT30 sensor."""

    bus_number: int
    address: int

    def read(self) -> tuple[float, float]:
        """Return a tuple (temperature °C, relative humidity %RH)."""
        ...

    def read_temperature(self) -> float:
        """Return the temperature in Celsius."""
        ...

    def read_humidity(self) -> float:
        """Return the relative humidity in percent."""
        ...


# --- Internal SHT30 command configuration --------------------------------------

_DEFAULT_ADDRESS: int = 0x44
# Single-shot measurement, high repeatability, no clock-stretching
_COMMAND_SINGLE_HIGH = (0x24, 0x00)
_READ_FRAME_LENGTH: int = 6


# --- SHT30 Driver Implementation ----------------------------------------------

@dataclass(slots=True)
class SHT30:
    """Minimal SHT30 single-shot reader with CRC validation.

    Parameters
    ----------
    bus_number : int
        I2C bus number (Raspberry Pi typically 1; for testing with i2c-stub use stub bus).
    address : int
        7-bit I2C address (ENV-III default: 0x44).
    measurement_delay_seconds : float
        Wait time after triggering measurement (datasheet recommends ~15 ms).
    bus_factory : Callable[[int], Any]
        Factory that returns an I2C bus instance (default: smbus2.SMBus).
        Can be replaced with a fake bus for unit testing.
    """

    bus_number: int = 1
    address: int = _DEFAULT_ADDRESS
    measurement_delay_seconds: float = 0.020
    bus_factory: Callable[[int], Any] = SMBus

    def _measure_raw(self) -> tuple[int, int]:
        """Trigger a single-shot measurement and return raw (temperature, humidity)."""
        try:
            with self.bus_factory(self.bus_number) as bus:
                # 1. Trigger measurement
                bus.write_i2c_block_data(
                    self.address, _COMMAND_SINGLE_HIGH[0], [_COMMAND_SINGLE_HIGH[1]]
                )
                # 2️. Wait for the sensor to complete measurement
                time.sleep(self.measurement_delay_seconds)
                # 3️. Read 6-byte measurement frame
                frame = bytes(bus.read_i2c_block_data(self.address, 0x00, _READ_FRAME_LENGTH))
        except OSError as error:
            raise SHT30Error(f"I2C communication failed: {error}") from error

        # 4️. Parse and validate the frame
        return parse_measurement_frame(frame)

    def read(self) -> tuple[float, float]:
        """Read both temperature (°C) and relative humidity (%RH)."""
        temperature_raw, humidity_raw = self._measure_raw()
        return raw_to_celsius(temperature_raw), raw_to_humidity(humidity_raw)

    def read_temperature(self) -> float:
        """Read only temperature in Celsius."""
        temperature_raw, _ = self._measure_raw()
        return raw_to_celsius(temperature_raw)

    def read_humidity(self) -> float:
        """Read only relative humidity in percent."""
        _, humidity_raw = self._measure_raw()
        return raw_to_humidity(humidity_raw)


@dataclass(slots=True)
class SHT30Fake:
    """Fake SHT30 sensor"""


    temperature: float = 25.0
    humidity: float = 50.0
    temperature_sigma: float = 0.2
    humidity_sigma: float = 1.0

    def _rand_temperature(self) -> float:
        t = random.gauss(self.temperature, self.temperature_sigma)
        return max(-40.0, min(125.0, t))

    def _rand_humidity(self) -> float:
        h = random.gauss(self.humidity, self.humidity_sigma)
        return max(0.0, min(100.0, h))

    def read(self) -> tuple[float, float]:
        return self._rand_temperature(), self._rand_humidity()

    def read_temperature(self) -> float:
        return self._rand_temperature()

    def read_humidity(self) -> float:
        return self._rand_humidity()

