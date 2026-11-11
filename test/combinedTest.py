# Combined sensor test for Raspberry Pi 5: DHT22 + BMP280 + PIR.

# Wiring:
#   BMP280  -- software I2C: SDA GPIO17 (physical pin 11), SCL GPIO27 (pin 13)
#   DHT22   -- single-wire data on GPIO4 (physical pin 7)
#   PIR     -- single-wire digital out on GPIO22 (physical pin 15)
#
# The BMP280 runs on bitbangio (software I2C), so it does not depend on the
# hardware I2C bus or another peripheral's bus speed or pull-ups.

# Reported stats -- raw values only, the backend will derive everything else:
#   DHT22   : temp_c, rh_pct (humidity)
#   BMP280  : pressure_hpa (absolute station pressure)
#   PIR     : motion (True while movement is detected)

# Not reported as separate fields - each item below is math for the backend:
#   altitude    -- needs a real sea-level reference
#   bmp280 temp -- that is the chip die temperature, not air temperature
#   dew point, dew point spread, cloud index, pressure trend, activity index
#   -- math for these can be done on the backend / app

# Air temperature comes from the DHT22 only; the PIR reports movement on its own.

# Outline
#
#   init_sensors()  opens software I2C (BMP280) plus the DHT22 and the PIR
#                   motion sensor, returning i2c_sw, bmp, dht, pir
#
#   read_dht22()    -> {"temperature", "humidity"} or None   (air temp + humidity)
#   read_bmp280()   -> {"pressure"}                or None   (barometer/air pressure)
#   read_pir()      -> {"motion"}                  or None   (movement detected)
#
# Each read function returns None instead of raising issues, so one dead or
# glitching sensor never takes down the others. print_sample() then shows
# n/a for the missing fields with some formatting functions.

# SENSOR WIRING GUIDE (Raspberry Pi 5)
#
# BMP280 (Software I2C / Bitbangio)
#   - VCC  -> Pin 1  (3.3V Power)
#   - GND  -> Pin 9  (Ground)
#   - SCL  -> Pin 13 (GPIO 27 - Software SCL)
#   - SDA  -> Pin 11 (GPIO 17 - Software SDA)
#
# DHT22 (Single-Wire Data) (Resistor connected between VCC and Data)
#   - VCC  -> Pin 4  (5V Power)
#   - DATA -> Pin 7  (GPIO 4)
#   - GND  -> Pin 14 (Ground)
#
# PIR (Single-Wire Digital)
#   - VCC  -> Pin 4  (5V Power)
#   - OUT  -> Pin 15 (GPIO 22)
#   - GND  -> Pin 6  (Ground)

import time
from datetime import datetime, timezone

import adafruit_bmp280
import adafruit_bitbangio as bitbangio
import adafruit_dht
import board
import digitalio

import config
import mqtt_client

DHT_PIN = board.D4
BMP_SDA_PIN = board.D17  # Physical Pin 11
BMP_SCL_PIN = board.D27  # Physical Pin 13
BMP280_ADDRESS = 0x76
PIR_PIN = board.D22  # Physical Pin 15
READ_INTERVAL_S = config.get_float(
    "URCAST_READ_INTERVAL_S",
    config.DEFAULT_READ_INTERVAL_S,
    minimum=0.1,
)
CELL_WIDTH = 24  # column width for the per-sensor printout


def init_sensors():
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


def fmt(value, spec, unit=""):
    if value is None:
        return "n/a"
    return f"{format(value, spec)} {unit}".rstrip()


def fmt_motion(value):
    if value is None:
        return "n/a"
    return "yes" if value else "no"


def print_sample(ts, seq, air, press, motion):
    rows = [
        (
            "DHT22",
            [
                ("temp", fmt(air.get("temperature"), ".1f", "C")),
                ("rh (humidity)", fmt(air.get("humidity"), ".1f", "%")),
            ],
        ),
        (
            "BMP280",
            [("pressure", fmt(press.get("pressure"), ".2f", "hPa"))],
        ),
        (
            "PIR",
            [("motion", fmt_motion(motion.get("motion")))],
        ),
    ]

    print(f"{ts}   sample #{seq:05d}")
    for name, cells in rows:
        line = "".join(f"{label} {value}".ljust(CELL_WIDTH) for label, value in cells)
        print(f"  {name:<8}| {line.rstrip()}")
    print()


def main():
    i2c_sw, bmp, dht, pir = init_sensors()

    print("Press Ctrl+C to stop.\n")

    seq = 0
    try:
        while True:
            seq += 1
            ts = (
                datetime.now(timezone.utc)
                .isoformat(timespec="seconds")
                .replace("+00:00", "Z")
            )

            # Safely query each sensor independently with try/except fallbacks
            try:
                air = read_dht22(dht) or {}
            except Exception as e:
                print(f"DHT22 unexpected failure: {e}")
                air = {}

            try:
                press = read_bmp280(bmp) or {}
            except Exception as e:
                print(f"BMP280 unexpected failure: {e}")
                press = {}

            try:
                motion = read_pir(pir) or {}
            except Exception as e:
                print(f"PIR unexpected failure: {e}")
                motion = {}

            print_sample(ts, seq, air, press, motion)

            if mqtt_client.send_reading(
                temperature=air.get("temperature"),
                humidity=air.get("humidity"),
                pressure=press.get("pressure"),
                motion=motion.get("motion"),
            ):
                print(f"  sent reading #{seq}")

                if seq % 10 == 0:
                    if mqtt_client.send_heartbeat():
                        print(f"  sent heartbeat #{seq}")
                    if mqtt_client.send_diagnostic(
                        motion_ok=motion.get("motion") is not None,
                        air_ok=air.get("temperature") is not None,
                        pressure_ok=press.get("pressure") is not None,
                    ):
                        print(f"  sent diagnostic #{seq}")

            time.sleep(READ_INTERVAL_S)
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        mqtt_client.close()
        if dht is not None:
            dht.exit()
        if pir is not None:
            pir.deinit()
        if i2c_sw is not None:
            i2c_sw.deinit()


if __name__ == "__main__":
    main()
