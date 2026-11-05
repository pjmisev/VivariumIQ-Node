# urcast Raspberry Pi 5 Weather Node README

> A Python-based telemetry collection and diagnostic script designed for the urcast weather station project running on a Raspberry Pi 5. This script validates hardware communication, independent I2C bus splitting, and continuous raw environmental data acquisition.

---

## About the Weather Node

The **urcast Weather Node** runs locally on a Raspberry Pi 5 deployed inside an outdoor protective enclosure. It simultaneously communicates with three separate environmental sensors using isolated peripheral interfaces—utilizing the Raspberry Pi 5's hardware I2C bus, a software bit-banged I2C bus, and a direct single-wire GPIO connection. Each sensor read is wrapped in fault-tolerant exception handling to guarantee that a glitch or failure in one sensor never interrupts the others.

---

## Key Features and Responsibilities

- **Isolated Multi-Bus Architecture:** Communicates with the TSL2591 light sensor via hardware I2C (Bus 1) and the BMP280 pressure sensor via software bit-banged I2C (`adafruit_bitbangio`) on separate pins, eliminating bus contention and speed interference.
- **Fault-Tolerant Error Handling:** Implements independent `try/except` boundaries around every sensor call, returning `None` on failure so the continuous sampling loop remains active.
- **Raw Telemetry Output:** Captures unadjusted base metrics (`ch0`, `ch1`, `lux`, `temperature`, `humidity`, and absolute station `pressure`), leaving derivative math like altitude, dew point, cloud index, and pressure trends to the backend application.
- **Formatted Terminal Diagnostics:** Prints structured, columnar log lines with UTC ISO timestamps and sequential sample numbering.

---

## Hardware Stack & Wiring Guide

- **Microcontroller:** Raspberry Pi 5

| Sensor | Protocol | GPIO Pins | Physical Connections |
| :--- | :--- | :--- | :--- |
| **TSL2591** (Light) | Hardware I2C (Bus 1) | GPIO 2 (SDA), GPIO 3 (SCL) | VIN $\rightarrow$ Pin 17 (3.3V)<br>GND $\rightarrow$ Pin 6<br>SCL $\rightarrow$ Pin 5<br>SDA $\rightarrow$ Pin 3 |
| **BMP280** (Pressure) | Software I2C (Bitbangio) | GPIO 17 (SDA), GPIO 27 (SCL) | VCC $\rightarrow$ Pin 1 (3.3V)<br>GND $\rightarrow$ Pin 9<br>SCL $\rightarrow$ Pin 13<br>SDA $\rightarrow$ Pin 11 |
| **DHT22** (Temp/Humidity) | Single-Wire Data | GPIO 4 | VCC $\rightarrow$ Pin 4 (5V)<br>DATA $\rightarrow$ Pin 7 *(with pull-up resistor to VCC)*<br>GND $\rightarrow$ Pin 14 |

---

## Data Fields and Backend Processing Strategy

The node focuses strictly on raw data collection to keep edge operations simple and lightweight:

| Sensor | Reported Fields | Calculated / Derived on Backend |
| :--- | :--- | :--- |
| **TSL2591** | `lux`, `ch0` (Full Spectrum), `ch1` (Infrared) | `visible` ($ch0 - ch1$), `broadband` ($ch0$), gain clipping detection |
| **DHT22** | `temperature` (°C), `humidity` (%) | Dew point, dew point spread, air comfort index |
| **BMP280** | `pressure` (hPa absolute) | Relative sea-level pressure, altitude estimation, pressure trend |

---

## Technology Stack

- **Language:** Python 3.10+
- **Peripheral Libraries:** Adafruit CircuitPython (`board`, `busio`, `bitbangio`, `adafruit_tsl2591`, `adafruit_bmp280`, `adafruit_dht`)
- **Network Libraries:** `paho-mqtt` (MQTT publishing), `urllib` (one-time REST registration)
- **Runtime Utilities:** `time`, `datetime` (UTC-enforced timestamping)

---

## Project Architecture

```text
urcast-node/
│
├── test/
│   ├── bmp280.py         # Standalone hardware test script for BMP280 pressure sensor
│   ├── dht22.py          # Standalone hardware test script for DHT22 temp & humidity sensor
│   ├── tsl2591.py        # Standalone hardware test script for TSL2591 light sensor
│   ├── register_node.py  # One-time REST registration with the owner's JWT
│   ├── mqtt_client.py    # MQTT publisher (readings, diagnostics, heartbeat)
│   └── combinedTest.py   # Main entry point script executing multi-bus setup, reading loop, and formatted output
└── README.md           # Project documentation
```

---

## Repository Commit History & Test Development

You can inspect the complete evolution of the individual sensor scripts and diagnostic code on GitHub:

- **Repository:** [leonas-stanis/udp-pi-test-code](https://github.com/leonas-stanis/udp-pi-test-code)
- **Commit History:** Track incremental updates, bug fixes, and bus isolation testing across individual commits via the [GitHub Commit Log](https://github.com/leonas-stanis/udp-pi-test-code/commits/main/).


## Getting Started and Installation

### Prerequisites

- A Raspberry Pi 5 running Raspberry Pi OS with I2C interfaces enabled via `sudo raspi-config`.
- Physical wiring of the TSL2591, BMP280, and DHT22 modules according to the hardware stack pinout table above.

### Setup Instructions

1. Clone or download this repository to your Raspberry Pi 5:
```bash
git clone https://github.com/urcast/urcast-node/tree/main
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate
```

3. Install required Adafruit CircuitPython dependencies and the MQTT client:
```bash
pip install adafruit-circuitpython-tsl2591 adafruit-circuitpython-bmp280 adafruit-circuitpython-dht adafruit-blinka paho-mqtt
```

---

## Running and Testing

To execute the data collection loop and monitor sensor readings directly in your terminal:

```bash
cd test
python combinedTest.py
```

Press `Ctrl+C` at any time to safely terminate the execution loop and release hardware interfaces.

---

## Connecting to the urcast API

The node talks to the backend over two transports:

- **HTTPS REST** is used once, to create the node. It requires the owner's JWT.
- **MQTT** carries every reading, diagnostic, and heartbeat. The broker accepts anonymous connections, but the backend reads the JWT from a `token` field inside each payload and drops anything with a missing, expired, or mismatched token.

A node can only be created by a logged-in user, so run the registration step once with that user's token.

### 1. Get a JWT

Create a user if you do not have one yet:

```bash
curl -X POST http://<api-host>:8000/api/user \
  -H "Content-Type: application/json" \
  -d '{"username": "pijus", "email": "pijus@example.com", "password": "S3curePass!"}'
```

Log in and copy the `access_token` from the response:

```bash
curl -X POST http://<api-host>:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "pijus@example.com", "password": "S3curePass!"}'
```

The token is an HS256 JWT and is valid for **24 hours**. When it expires, log in again and replace `NODE_TOKEN` in `test/mqtt_client.py`. Registration only has to be done once, so `register_node.py` does not need to be re-run for a token refresh.

### 2. Register the node (once)

Edit the settings at the top of `test/register_node.py`:

```python
API_URL = "http://localhost:8000"   # the API server
NODE_TOKEN = "paste-your-jwt-token-here"
NODE_NAME = "pi5-outdoor"
NODE_LOCATION = "Dublin, Ireland"
NODE_LATITUDE = None                # optional decimal latitude
NODE_LONGITUDE = None               # optional decimal longitude
```

Then run it:

```bash
cd test
python register_node.py
```

The script sends `POST /api/node` with `Authorization: Bearer <token>` and prints the returned `node_id`. If the API returns `401`, the token is missing, malformed, or expired: log in again, paste the new token, and re-run the script. A `422` response means the request failed validation (for example, an empty node name); the API's error detail is printed.

### 3. Configure MQTT

Edit the settings at the top of `test/mqtt_client.py`:

```python
MQTT_BROKER = "localhost"   # on the Pi, put the server's IP here
MQTT_PORT = 1883
NODE_ID = 1                 # the id printed by register_node.py
NODE_TOKEN = "paste-your-jwt-token-here"
```

- `MQTT_BROKER` must point at the machine running Mosquitto.
- `NODE_ID` must match the id returned by registration. A different id publishes on a topic the token does not own, and the backend silently drops the message.
- `NODE_TOKEN` must belong to the user who registered the node.

### 4. Run the loop

```bash
cd test
python combinedTest.py
```

`combinedTest.py` continues to print samples to the terminal and additionally publishes:

| Topic | When | Payload |
| :--- | :--- | :--- |
| `urcast/<node_id>/reading` | every sample (~3 s) | `temperature`, `humidity`, `pressure`, `light_level`, `token` |
| `urcast/<node_id>/diagnostic` | every 10th successful reading | `uptime`, `light_sensor_status`, `dht22_status`, `pressure_sensor_status`, `token` |
| `urcast/<node_id>/heartbeat` | every 10th successful reading | `token` |

Sensor failures are sent as `null` (or omitted) rather than a made-up value, and the loop keeps running if the broker is unreachable. The terminal will show `could not send reading (no connection to broker): ...` and retry on the next sample.

### Troubleshooting

| Symptom | Fix |
| :--- | :--- |
| Registration returns `401` | The JWT is missing or expired. Log in again and paste the new token into `NODE_TOKEN`. |
| Backend drops readings with `token is missing or wrong for node <id>` | Check that `NODE_TOKEN` in `mqtt_client.py` is the current token for the user who registered the node. |
| Backend drops readings with `node <id> does not exist` | Run `register_node.py` first, then copy its `node_id` into `mqtt_client.py`. |
| Readings land on the wrong node or disappear | `NODE_ID` must be the id printed by registration, not an id copied from another node. |
| `could not send reading (no connection to broker)` | Check `MQTT_BROKER` and that Mosquitto is running on port `1883`. |
| Nothing arrives after 24 hours | The JWT expired. Log in again and update `NODE_TOKEN` in `mqtt_client.py`. |

---

## Team

- **Pijus (PM)** – Back-End, Version Control
- **Raivis** – Database, Back-End
- **Anastasija** – Front-End, UI/UX/UD, Database
- **Leonas** – Hardware, Front-End
- **Kornel** – UI/UX/UD, Testing, Hardware