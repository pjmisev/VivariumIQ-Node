"""Hardware access for the VivariumIQ node: DHT22, BMP280, and PIR.

Wiring (Raspberry Pi 5):
    BMP280  -- software I2C: SDA GPIO17 (physical pin 11), SCL GPIO27 (pin 13)
    DHT22   -- single-wire data on GPIO4 (physical pin 7)
    PIR     -- single-wire digital out on GPIO22 (physical pin 15)

The BMP280 runs on bitbangio (software I2C), so it does not depend on the
hardware I2C bus or another peripheral's bus speed or pull-ups.

Every read function returns a dict of raw values, or None when that sensor
fails, so one dead or glitching sensor never takes down the others.
"""

from __future__ import annotations

import adafruit_bmp280
import adafruit_bitbangio as bitbangio
import adafruit_dht
import board
import digitalio

DHT_PIN = board.D4
BMP_SDA_PIN = board.D17  # Physical Pin 11
BMP_SCL_PIN = board.D27  # Physical Pin 13
BMP280_ADDRESS = 0x76
PIR_PIN = board.D22  # Physical Pin 15


def init_sensors():
    """Open every sensor, returning ``(i2c_sw, bmp, dht, pir)``.

    Any sensor that fails to initialise is returned as ``None`` so the loop
    keeps running with the rest.
    """
    # Software I2C for BMP280 (Physical Pins 11 & 13)
    i2c_sw = None
    bmp = None
    try:
        i2c_sw = bitbangio.I2C(BMP_SCL_PIN, BMP_SDA_PIN)
        bmp = adafruit_bmp280.Adafruit_BMP280_I2C(i2c_sw, address=BMP280_ADDRESS)
    except Exception as e:
        print(f"BMP280 init failed: {e}")

    # DHT22 on GPIO 4 (Physical Pin 7)
    dht = None
    try:
        dht = adafruit_dht.DHT22(DHT_PIN, use_pulseio=False)
    except Exception as e:
        print(f"DHT22 init failed: {e}")

    # PIR motion sensor on GPIO 22 (Physical Pin 15)
    pir = None
    try:
        pir = digitalio.DigitalInOut(PIR_PIN)
        pir.direction = digitalio.Direction.INPUT
    except Exception as e:
        print(f"PIR init failed: {e}")

    return i2c_sw, bmp, dht, pir


def read_dht22(device):
    try:
        return {
            "temperature": device.temperature,
            "humidity": device.humidity,
        }
    except Exception as error:
        # Catches RuntimeErrors and any hardware dropouts gracefully
        print(f"DHT22 read error: {error}")
        return None


def read_bmp280(sensor):
    try:
        return {"pressure": sensor.pressure}
    except (RuntimeError, ValueError) as error:
        print(f"BMP280 read error: {error}")
        return None


def read_pir(sensor):
    try:
        return {"motion": bool(sensor.value)}
    except Exception as error:
        print(f"PIR read error: {error}")
        return None


def close_sensors(*, dht=None, pir=None, i2c_sw=None):
    """Release hardware handles on shutdown."""
    if dht is not None:
        dht.exit()
    if pir is not None:
        pir.deinit()
    if i2c_sw is not None:
        i2c_sw.deinit()
