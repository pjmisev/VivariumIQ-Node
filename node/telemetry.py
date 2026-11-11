"""VivariumIQ node telemetry loop.

Reads the DHT22, BMP280, and PIR sensors on a fixed interval, prints a
formatted sample, and publishes readings, diagnostics, and heartbeats to the
MQTT broker. Run with ``python -m node``.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from . import config, mqtt_client, sensors

READ_INTERVAL_S = config.get_float(
    "VIVARIUMIQ_READ_INTERVAL_S",
    config.DEFAULT_READ_INTERVAL_S,
    minimum=0.1,
)
CELL_WIDTH = 24  # column width for the per-sensor printout


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
    i2c_sw, bmp, dht, pir = sensors.init_sensors()

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
                air = sensors.read_dht22(dht) or {}
            except Exception as e:
                print(f"DHT22 unexpected failure: {e}")
                air = {}

            try:
                press = sensors.read_bmp280(bmp) or {}
            except Exception as e:
                print(f"BMP280 unexpected failure: {e}")
                press = {}

            try:
                motion = sensors.read_pir(pir) or {}
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
        sensors.close_sensors(dht=dht, pir=pir, i2c_sw=i2c_sw)


if __name__ == "__main__":
    main()
