# VivariumIQ Node

VivariumIQ is a full-stack IoT remote monitoring and behavioral tracking system designed for exotic pet enclosures. This repository contains the **Raspberry Pi node (telemetry gateway)** that sits inside the enclosure, captures microclimate telemetry, atmospheric pressure, and motion, and streams it securely over an MQTT pub-sub broker to the cloud-hosted FastAPI backend, which computes a biological activity index and presents it through the web dashboard.

The node focuses strictly on raw data collection to keep edge operations simple and lightweight. The Python script validates hardware communication, isolates each sensor read, and performs continuous raw environmental data acquisition. Derivative math such as altitude, dew point, cloud index, and pressure trends is left to the backend application.

The companion web application lives in the [VivariumIQ](https://github.com/pjmisev/VivariumIQ) repository.

---

## System Architecture and Hardware

**Controller:** Raspberry Pi 400 in Custom 3D Printed Enclosure

**Sensor Array:**

- **DHT22** temperature and humidity sensor for microclimate monitoring
- **BMP280** barometer for atmospheric pressure and seasonal trend analysis
- **PIR** motion sensor for animal movement and tank-intrusion detection

**Communication Protocol:** MQTTS (TLS on port 8883) for telemetry, HTTPS for the API and front-end webpages

**Backend and Frontend:** FastAPI, HTML templates with TailwindCSS styling

**Database:** MySQL

**Cloud Infrastructure:** Deployed on AWS

The node talks to the backend over two transports:

- **REST over HTTP(S)** is used to log in, register the account and node, and verify the saved JWT.
- **MQTT over TLS (port 8883)** carries every reading, diagnostic, and heartbeat. `mqtt_client.py` enables TLS with the Pi's system CA store, so the broker's Let's Encrypt certificate and hostname are verified on every connection. The broker accepts anonymous connections, but the backend reads the JWT from a `token` field inside each payload and drops anything with a missing, expired, or mismatched token.

---

## Key Features

- **Software Bit-Banged Barometer Bus:** Drives the BMP280 pressure sensor over a software I2C bus (`adafruit_bitbangio`) on its own pins, keeping it independent of the hardware I2C bus and any future peripherals.
- **Fault-Tolerant Error Handling:** Implements independent `try/except` boundaries around every sensor call, returning `None` on failure so the continuous sampling loop remains active.
- **Motion and Intrusion Detection:** Reads a PIR motion sensor over a single GPIO to report animal movement and tank-intrusion events.
- **Raw Telemetry Output:** Captures unadjusted base metrics (`temperature`, `humidity`, absolute station `pressure`, and `motion`), leaving derivative math to the backend application.
- **Formatted Terminal Diagnostics:** Prints structured, columnar log lines with UTC ISO timestamps and sequential sample numbering.
- **Seamless Provisioning and Token Refresh:** `setup_node.py` checks the saved login, guides the user through login or registration, registers the node, stores the JWT and credentials in `.env`, and the MQTT publisher renews the JWT automatically before it expires.

---

## Hardware Stack & Wiring Guide

- **Microcontroller:** Raspberry Pi 5

| Sensor | Protocol | GPIO Pins | Physical Connections |
| :--- | :--- | :--- | :--- |
| **BMP280** (Pressure) | Software I2C (Bitbangio) | GPIO 17 (SDA), GPIO 27 (SCL) | VCC $\rightarrow$ Pin 1 (3.3V)<br>GND $\rightarrow$ Pin 9<br>SCL $\rightarrow$ Pin 13<br>SDA $\rightarrow$ Pin 11 |
| **DHT22** (Temp/Humidity) | Single-Wire Data | GPIO 4 | VCC $\rightarrow$ Pin 4 (5V)<br>DATA $\rightarrow$ Pin 7 *(with pull-up resistor to VCC)*<br>GND $\rightarrow$ Pin 14 |
| **PIR** (Motion) | Single-Wire Digital | GPIO 22 | VCC $\rightarrow$ Pin 4 (5V)<br>OUT $\rightarrow$ Pin 15 (GPIO 22)<br>GND $\rightarrow$ Pin 6 |

> **Pin conflict:** The PIR module's documentation suggests wiring `OUT` to physical pin 11 (GPIO 17), but that pin is already used by the BMP280 software I2C `SDA` line. Wire `OUT` to a free GPIO such as GPIO 22 (physical pin 15) instead, and set the matching pin in the sensor loop.

---

## Data Fields and Backend Processing Strategy

The node focuses strictly on raw data collection; the backend derives everything else:

| Sensor | Reported Fields | Calculated / Derived on Backend |
| :--- | :--- | :--- |
| **DHT22** | `temperature` (°C), `humidity` (%) | Dew point, dew point spread, air comfort index |
| **BMP280** | `pressure` (hPa absolute) | Relative sea-level pressure, altitude estimation, pressure trend |
| **PIR** | `motion` (boolean) | Activity/occupancy events, intrusion alerts, biological activity index inputs |

---

## Technology Stack

- **Language:** Python 3.10+
- **Peripheral Libraries:** Adafruit CircuitPython (`board`, `busio`, `bitbangio`, `adafruit_bmp280`, `adafruit_dht`) with `gpiod` as the Raspberry Pi 5 GPIO backend for the PIR motion sensor
- **Network Libraries:** `paho-mqtt` (MQTT publishing), `urllib` (REST login, registration, and auth checks)
- **Configuration:** `python-dotenv` (loads the central `.env`)
- **Runtime Utilities:** `getpass` (password prompts), `time`, `datetime` (UTC-enforced timestamping)

---

## Project Architecture

```text
VivariumIQ-Node/
│
├── .env.example          # Template for the central .env configuration
├── .gitignore            # Keeps .env and local Python files out of git
├── requirements.txt      # Python dependencies for the node
│
├── test/
│   ├── config.py         # Loads and saves the central .env values
│   ├── auth_client.py    # Login, registration, auth checks, and JWT refresh
│   ├── setup_node.py     # Interactive first-run setup and service launcher
│   ├── register_node.py  # Non-interactive node registration with an existing JWT
│   ├── mqtt_client.py    # MQTT publisher (readings, diagnostics, heartbeat)
│   ├── combinedTest.py   # Main sensor loop (also started by setup_node.py)
│   ├── bmp280.py         # Standalone hardware test script for BMP280
│   └── dht22.py          # Standalone hardware test script for DHT22
│
└── README.md             # Project documentation
```

---

## Security Implementation

To adhere strictly to project safety and security guidelines:

- **Authentication:** Every MQTT payload carries the node's JWT in a `token` field. The backend drops any message with a missing, expired, or mismatched token, so the node account must match the account that registered the node. Account passwords are hashed by the API.
- **Data in Transit:** The node publishes telemetry over MQTTS (TLS on port 8883) with certificate and hostname verification, and uses HTTPS for REST provisioning. Web traffic uses HTTPS with a custom domain.
- **Data at Rest:** All secret keys, account credentials, and the node JWT are stored exclusively in the gitignored `.env` file, which is written with owner-only permissions (`600`). Nothing sensitive is hard-coded.
- **Automatic Token Rotation:** The JWT is an HS256 token valid for 24 hours and is refreshed automatically before expiry, limiting the lifetime of any leaked credential.

---

## Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/pjmisev/VivariumIQ-Node.git
cd VivariumIQ-Node
```

### 2. Prerequisites

- A Raspberry Pi 5 running Raspberry Pi OS with I2C interfaces enabled via `sudo raspi-config`.
- Python 3.10 or newer.
- Physical wiring of the DHT22, BMP280, and PIR motion sensor modules according to the hardware stack pinout table above.
- Access to the VivariumIQ API and MQTT broker. Their addresses go in the central `.env` file.

### 3. Setup Instructions

1. Install the MQTT broker and local client tools, start the services, and set them to start on boot:

```bash
sudo apt install -y mosquitto mosquitto-clients
sudo systemctl enable --now mosquitto
sudo systemctl enable mosquitto
```

2. Create and activate a virtual environment in `VivariumIQ-Node/`:

```bash
python -m venv venv
source venv/bin/activate
```

3. Install the Python dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

`requirements.txt` installs Adafruit Blinka (`board`, `busio`, `bitbangio`), the BMP280 and DHT22 sensor drivers, `gpiod` for Raspberry Pi 5 GPIO (also used for the PIR motion sensor), `paho-mqtt`, and `python-dotenv`. If pip cannot find a `gpiod` wheel for your Python version, install the matching libgpiod development package from Raspberry Pi OS and retry.

On Raspberry Pi OS, make sure your user can access GPIO:

```bash
sudo usermod -aG gpio "$USER"
```

Log out and back in after changing groups.

4. Create the central `.env` from the template:

```bash
cp .env.example .env
```

Our default API:

```dotenv
VIVARIUMIQ_API_URL=https://vivariumiq.pjmisev.com
VIVARIUMIQ_MQTT_BROKER=vivariumiq.pjmisev.com
VIVARIUMIQ_MQTT_PORT=8883
```

Leave `VIVARIUMIQ_NODE_ID`, `VIVARIUMIQ_NODE_TOKEN`, `VIVARIUMIQ_EMAIL`, and `VIVARIUMIQ_PASSWORD` empty. `setup_node.py` fills them in.

If the node runs on the Pi and the API runs on your laptop, use the laptop's LAN IP, not `localhost`.

5. Run the interactive setup:

```bash
cd test
python setup_node.py
```

The setup script will:

- check the saved JWT with `GET /api/auth/me`;
- ask whether to log in or register if no valid login exists;
- register the node when it is missing;
- save the JWT, account credentials, and node id to `.env`;
- start the sensor service in the foreground.

To configure without starting the service, run:

```bash
python setup_node.py --setup-only
```

`.env` is created with owner-only permissions and is ignored by git. Keep it private: it contains the account password and node JWT.

---

## Running and Testing

The recommended entry point is the setup script, which also starts the service:

```bash
cd test
python setup_node.py
```

After `.env` is configured, the sensor loop can also be started directly:

```bash
cd test
python combinedTest.py
```

Press `Ctrl+C` at any time to safely terminate the execution loop and release hardware interfaces.

---

## Connecting to the VivariumIQ Backend

`setup_node.py` performs the REST steps for you. The manual steps below are for debugging or for provisioning a node without the interactive setup.

### Automatic setup (recommended)

Run from `test/`:

```bash
python setup_node.py
```

The script:

1. Loads `.env`.
2. Calls `GET /api/auth/me` with `VIVARIUMIQ_NODE_TOKEN`.
3. If the token is missing or expired, asks whether to log in, register, or quit.
4. On login, validates the email and password, then writes `VIVARIUMIQ_EMAIL`, `VIVARIUMIQ_PASSWORD`, and `VIVARIUMIQ_NODE_TOKEN` to `.env`.
5. On registration, validates the username, email, and password, creates the account with `POST /api/user`, then logs in and saves the same values.
6. Checks `VIVARIUMIQ_NODE_ID`; if it is missing or owned by another account, asks for the node name, location, and optional coordinates, then creates it with `POST /api/node`.
7. Saves `VIVARIUMIQ_NODE_ID` and the node details to `.env`.
8. Starts `combinedTest.py`.

Use `python setup_node.py --setup-only` to stop before step 8.

### What the setup writes to .env

| Key | Source |
| :--- | :--- |
| `VIVARIUMIQ_API_URL` | you |
| `VIVARIUMIQ_MQTT_BROKER` | you |
| `VIVARIUMIQ_MQTT_PORT` | you |
| `VIVARIUMIQ_EMAIL` | login/register prompt |
| `VIVARIUMIQ_PASSWORD` | login/register prompt |
| `VIVARIUMIQ_NODE_TOKEN` | `/api/auth/login` response |
| `VIVARIUMIQ_NODE_ID` | `POST /api/node` response |
| `VIVARIUMIQ_NODE_NAME`, `VIVARIUMIQ_NODE_LOCATION`, `VIVARIUMIQ_NODE_LATITUDE`, `VIVARIUMIQ_NODE_LONGITUDE` | information for database to be filled in manually |
| `VIVARIUMIQ_READ_INTERVAL_S` | you (optional, defaults to `60.0`) |

`.env` is gitignored and is set to owner-only permissions (`600`) on Linux. Do not share it: it contains the account password and node JWT.

### JWT lifetime and automatic refresh

The token is an HS256 JWT and is valid for **24 hours**. The node renews it automatically through `auth_client.py`:

- the token expiry is checked before every MQTT publish;
- when less than one hour remains, the node logs in again with `VIVARIUMIQ_EMAIL` and `VIVARIUMIQ_PASSWORD`;
- the new token is written back to `VIVARIUMIQ_NODE_TOKEN` in `.env`;
- if the API is temporarily unreachable, the old token keeps being used while it is still valid and the refresh is retried every 60 seconds.

This requires the API to be reachable around the refresh time and the stored credentials to remain valid. If the password changes, run `setup_node.py` and log in again to update `.env`.

### Manual registration (optional)

If you already have a JWT and want to register the node non-interactively, set `VIVARIUMIQ_API_URL`, `VIVARIUMIQ_NODE_TOKEN`, and the `VIVARIUMIQ_NODE_*` fields in `.env`, then run:

```bash
cd test
python register_node.py
```

The script sends `POST /api/node` with `Authorization: Bearer <token>` and saves the returned `node_id` to `.env`. This path does not prompt and does not refresh the token; use `setup_node.py` for the normal setup.

The API endpoints used are:

- `POST /api/user` with `username`, `email`, `password`
- `POST /api/auth/login` with `email`, `password`; returns `access_token`
- `GET /api/auth/me` with `Authorization: Bearer <token>`
- `POST /api/node` with `Authorization: Bearer <token>` and `node_name`, `location_name`, `latitude`, and `longitude`

### MQTT topics

`combinedTest.py` continues to print samples to the terminal and additionally publishes:

| Topic | When | Payload |
| :--- | :--- | :--- |
| `vivariumiq/<node_id>/reading` | every sample (~3 s) | `temperature`, `humidity`, `pressure`, `motion`, `token` |
| `vivariumiq/<node_id>/diagnostic` | every 10th successful reading | `uptime`, `motion_sensor_status`, `dht22_status`, `pressure_sensor_status`, `token` |
| `vivariumiq/<node_id>/heartbeat` | every 10th successful reading | `token` |

Sensor failures are sent as `null` (or omitted) rather than a made-up value, and the loop keeps running if the broker is unreachable. The terminal will show `could not send reading (TLS connection to broker failed): ...` and retry on the next sample.

### Troubleshooting

| Symptom | Fix |
| :--- | :--- |
| `No valid vivariumiq login found` | Run `setup_node.py` and choose login or register. |
| Login returns `401` | Check `VIVARIUMIQ_EMAIL` and `VIVARIUMIQ_PASSWORD`; the API reports `Invalid email or password`. |
| Registration returns `400` | The username or email already exists. Choose login instead, or use a different email. |
| Registration returns `422` | The API validation failed; check the printed detail (for example, a password under 8 characters). |
| `Could not reach the API at ...` | Check `VIVARIUMIQ_API_URL` in `.env` and that the API is running. Use the server's LAN IP, not `localhost`, when the API is on another machine. |
| Backend drops readings with `token is missing or wrong for node <id>` | Run `setup_node.py` so the token belongs to the account that registered `VIVARIUMIQ_NODE_ID`. |
| Backend drops readings with `node <id> does not exist` | Run `setup_node.py` to register the node; do not use an id from another node. |
| `could not send reading (TLS connection to broker failed)` | Check `VIVARIUMIQ_MQTT_BROKER` (must be `vivariumiq.pjmisev.com`, kept as a grey-cloud DNS record) and that Mosquitto is listening with TLS on `VIVARIUMIQ_MQTT_PORT` (8883). |
| Nothing arrives after 24 hours | Check that `VIVARIUMIQ_EMAIL` and `VIVARIUMIQ_PASSWORD` are still valid; the node refreshes the JWT one hour before expiry. |
| `VIVARIUMIQ_NODE_TOKEN` or `VIVARIUMIQ_NODE_ID` missing from `.env` | Run `setup_node.py` again. It reuses existing values and fills in missing ones. |

---

## Team

- **Pijus (PM)** – Back-End, Version Control
- **Raivis** – Database, Back-End
- **Anastasija** – Front-End, UI/UX/UD, Database
- **Leonas** – Hardware, Front-End
- **Kornel** – UI/UX/UD, Testing, Hardware

---

## Screencast and Demo Link

A complete video walkthrough detailing the system architecture, security implementations, live end-to-end functionality demo, and known issues will be available below:

- [Link to Screencast/Demo]
