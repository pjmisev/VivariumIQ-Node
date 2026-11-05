# Combined sensor test for Raspberry Pi 5: TSL2591 + DHT22 + BMP280.

# Wiring:
#   TSL2591 -- hardware I2C bus 1: SDA GPIO2 (physical pin 3), SCL GPIO3 (pin 5)
#   BMP280  -- software I2C: SDA GPIO17 (physical pin 11), SCL GPIO27 (pin 13)
#   DHT22   -- single-wire data on GPIO23 (physical pin 8)
#
# The two I2C sensors are on separate buses: hardware I2C for the TSL2591, and
# bitbangio (software I2C) for the BMP280, so neither depends on the other's
# bus speed or pull-ups.

# Reported stats -- raw values only, the backend will derive everything else:
#   TSL2591 : lux, ch0 (all light: visible + IR counts), ch1 (infrared counts)
#   DHT22   : temp_c, rh_pct(humidity)
#   BMP280  : pressure_hpa (absolute station pressure)

# Not reported as separate fields - each item below is either another name
# for a number already printed above, or math for the backend:
#   visible     = ch0 - ch1   (one subtraction)
#   broadband   = ch0         (same number as ch0, already printed)
#   IR          = ch1         (same number as ch1, already printed)
#   altitude    -- needs a real sea-level reference
#   bmp280 temp -- that is the chip die temperature, not air temperature
#   dew point, dew point spread, cloud index, pressure trend -- math for these
#   can be done on the backend / app

# Air temperature comes from the DHT22 only. ch0/ch1 are kept for now because
# they show whether lux is clipping because of too much brightness at the selected gain.

# Outline
#
#   init_sensors()  opens hardware I2C (TSL2591) and software I2C (BMP280) plus
#                   the DHT22, returning i2c_hw, i2c_sw, tsl, bmp, dht
#
#   read_tsl2591()  -> {"lux", "ch0", "ch1"}       or None   (light)
#   read_dht22()    -> {"temperature", "humidity"} or None   (air temp + humidity)
#   read_bmp280()   -> {"pressure"}                or None   (barometer/air pressure)
#
# Each read function returns None instead of raising issues, so one dead or
# glitching sensor never takes down the other two. print_sample() then shows
# n/a for the missing fields with some formatting functions.

# SENSOR WIRING GUIDE (Raspberry Pi 5)
#
# TSL2591 (Hardware I2C Bus 1)
#   - VIN  -> Pin 17 (3.3V Power)
#   - GND  -> Pin 6  (Ground)
#   - SCL  -> Pin 5  (GPIO 3 - Hardware SCL)
#   - SDA  -> Pin 3  (GPIO 2 - Hardware SDA)
#
# BMP280 (Software I2C / Bitbangio)
#   - VCC  -> Pin 1  (3.3V Power)
#   - GND  -> Pin 9  (Ground)
#   - SCL  -> Pin 13 (GPIO 27 - Software SCL)
#   - SDA  -> Pin 11 (GPIO 17 - Software SDA)
# 
# DHT22 (Single-Wire Data) (Resistor connectected between VCC and Data)
#   - VCC  -> Pin 4  (5V Power)
#   - DATA -> Pin 7  (GPIO 4)
#   - GND  -> Pin 14 (Ground)

import time
from datetime import datetime, timezone

import adafruit_bmp280
import adafruit_bitbangio as bitbangio
import adafruit_dht
import adafruit_tsl2591
import board
import busio

import config
import mqtt_client

DHT_PIN = board.D4
BMP_SDA_PIN = board.D17  # Physical Pin 11
BMP_SCL_PIN = board.D27  # Physical Pin 13
BMP280_ADDRESS = 0x76
READ_INTERVAL_S = config.get_float(
    "URCAST_READ_INTERVAL_S",
    config.DEFAULT_READ_INTERVAL_S,
    minimum=0.1,
)
CELL_WIDTH = 24  # column width for the per-sensor printout

TSL_GAIN = adafruit_tsl2591.GAIN_LOW
TSL_INTEGRATION_TIME = adafruit_tsl2591.INTEGRATIONTIME_100MS

_GAIN_MULTIPLIERS = {
    adafruit_tsl2591.GAIN_LOW: 1,
    adafruit_tsl2591.GAIN_MED: 25,
    adafruit_tsl2591.GAIN_HIGH: 428,
    adafruit_tsl2591.GAIN_MAX: 9876,
}


def init_sensors():
    # Bus 1: Hardware I2C for TSL2591 (Physical Pins 3 & 5)
    i2c_hw = None
    tsl = None
    try:
        i2c_hw = busio.I2C(board.SCL, board.SDA)
        tsl = adafruit_tsl2591.TSL2591(i2c_hw)
        tsl.gain = TSL_GAIN
        tsl.integration_time = TSL_INTEGRATION_TIME
    except Exception as e:
        print(f"TSL2591 init failed: {e}")

    # Bus 2: Software I2C for BMP280 (Physical Pins 11 & 13)
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

    return i2c_hw, i2c_sw, tsl, bmp, dht


def read_tsl2591(sensor):
    try:
        ch0, ch1 = sensor.raw_luminosity
    except (RuntimeError, ValueError) as error:
        print(f"TSL2591 read error: {error}")
        return None

    try:
        lux = sensor.lux
    except RuntimeError:
        lux = None

    return {"lux": lux, "ch0": ch0, "ch1": ch1}


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


def fmt(value, spec, unit=""):
    if value is None:
        return "n/a"
    return f"{format(value, spec)} {unit}".rstrip()


def print_sample(ts, seq, light, air, press):
    rows = [
        (
            "TSL2591",
            [
                ("lux", fmt(light.get("lux"), ".2f", "lx")),
                ("ch0 (all light)", fmt(light.get("ch0"), "d")),
                ("ch1 (infrared)", fmt(light.get("ch1"), "d")),
            ],
        ),
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
    ]

    print(f"{ts}   sample #{seq:05d}")
    for name, cells in rows:
        line = "".join(f"{label} {value}".ljust(CELL_WIDTH) for label, value in cells)
        print(f"  {name:<8}| {line.rstrip()}")
    print()


def main():
    i2c_hw, i2c_sw, tsl, bmp, dht = init_sensors()

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
                light = read_tsl2591(tsl) or {}
            except Exception as e:
                print(f"TSL2591 unexpected failure: {e}")
                light = {}

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

            print_sample(ts, seq, light, air, press)

            if mqtt_client.send_reading(
                temperature=air.get("temperature"),
                humidity=air.get("humidity"),
                pressure=press.get("pressure"),
                light_level=light.get("lux"),
            ):
                # every 10th sample also report sensor health and heartbeat
                if seq % 10 == 0:
                    mqtt_client.send_heartbeat()
                    mqtt_client.send_diagnostic(
                        light_ok=light.get("lux") is not None
                        or light.get("ch0") is not None,
                        air_ok=air.get("temperature") is not None,
                        pressure_ok=press.get("pressure") is not None,
                    )

            time.sleep(READ_INTERVAL_S)
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        mqtt_client.close()
        if dht is not None:
            dht.exit()
        if i2c_hw is not None:
            i2c_hw.deinit()
        if i2c_sw is not None:
            i2c_sw.deinit()


if __name__ == "__main__":
    main()