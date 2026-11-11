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
├── .dockerignore         # Files excluded from the Docker build context
├── .env.example          # Template for the central .env configuration
├── .gitignore            # Keeps .env and local Python files out of git
├── Dockerfile            # Image definition for running the node in a container
├── docker-compose.yml    # Compose service (privileged, mounts .env)
├── requirements.txt      # Python dependencies for the node
│
├── node/                 # The node application (importable package)
│   ├── __init__.py
│   ├── __main__.py       # Entry point for `python -m node`
│   ├── config.py         # Loads and saves the central .env values
│   ├── auth_client.py    # Login, registration, auth checks, and JWT refresh
│   ├── mqtt_client.py    # MQTT publisher (readings, diagnostics, heartbeat)
│   ├── sensors.py        # Opens and reads the DHT22, BMP280, and PIR
│   ├── telemetry.py      # Main sampling and publishing loop
│   ├── setup_node.py     # Interactive setup (`python -m node.setup_node`)
│   └── register_node.py  # Non-interactive registration with an existing JWT
│
├── tools/                # Standalone hardware test scripts
│   ├── bmp280.py         # Quick BMP280 check
│   ├── dht22.py          # Quick DHT22 check
│   └── pir.py            # Quick PIR check
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
- Optional: Docker with the Compose plugin, to run the node in a container (see [Running with Docker](#running-with-docker)).

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

5. Run the interactive setup from the repository root:

```bash
python -m node.setup_node
```

The setup script will:

- check the saved JWT with `GET /api/auth/me`;
- ask whether to log in or register if no valid login exists;
- register the node when it is missing;
- save the JWT, account credentials, and node id to `.env`;
- start the sensor service in the foreground.

To configure without starting the service, run:

```bash
python -m node.setup_node --setup-only
```

`.env` is created with owner-only permissions and is ignored by git. Keep it private: it contains the account password and node JWT.

---

## Running and Testing

The recommended entry point is the setup script, which checks the login, registers the node, and starts the service:

```bash
python -m node.setup_node
```

After `.env` is configured, the sensor loop can also be started on its own:

```bash
python -m node
```

The standalone hardware checks in `tools/` are handy while wiring a sensor:

```bash
python tools/dht22.py
python tools/bmp280.py
python tools/pir.py
```

Press `Ctrl+C` at any time to safely terminate the execution loop and release hardware interfaces.

---

## Running with Docker

The node ships with a `Dockerfile` and a `docker-compose.yml`, so it can run on any Raspberry Pi without installing Python or the sensor libraries on the host. The image is based on `python:3.11-slim-bookworm`, installs `libgpiod` for GPIO access, and runs the service with `python -m node`.

| File | Purpose |
| :--- | :--- |
| `Dockerfile` | Builds the node image: system libraries, Python dependencies, and the `node/` and `tools/` code. |
| `docker-compose.yml` | Runs the image `privileged`, mounts `./.env`, and restarts the node automatically. |
| `.dockerignore` | Keeps `.env`, git data, and Python caches out of the build context. |

### 1. Prerequisites

- Docker Engine with the Compose plugin:

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"   # log out and back in afterwards
```

- I2C enabled on the host (`sudo raspi-config` → Interface Options → I2C), since the container uses the host kernel drivers.
- A populated `./.env` file (created in step 3).

### 2. Build the image

```bash
docker compose build
```

Build on the Pi itself so the image matches its CPU architecture (`arm64` on Pi 4/5, `armv7` on older boards). For cross-architecture builds use `docker buildx build --platform linux/arm64`.

### 3. Provision the node (once)

`.env` must exist before Compose starts, because it is bind-mounted and rewritten in place whenever the JWT is refreshed:

```bash
cp .env.example .env
docker compose run --rm -it node python -m node.setup_node --setup-only
```

The `--setup-only` flag stops after login/registration instead of starting the service inside this throwaway container. It writes `VIVARIUMIQ_NODE_TOKEN` and `VIVARIUMIQ_NODE_ID` back to `./.env` on the host.

### 4. Start the service

```bash
docker compose up -d --build
```

### Common commands

```bash
docker compose logs -f node      # follow the sample log
docker compose ps                # check that it is running
docker compose down              # stop and remove the container
docker compose up -d --build     # rebuild and restart after a code change
```

### Hardware access

The container drives the GPIO and I2C peripherals directly, so `docker-compose.yml` runs it `privileged`. That grants access to the host devices the node needs: `/dev/gpiochip*` for the PIR and the software-I2C BMP280, and `/dev/i2c-*` if you use the hardware I2C bus. To avoid `privileged`, replace it with an explicit device allow-list plus the `gpio`/`i2c` groups:

```yaml
    devices:
      - /dev/gpiochip4:/dev/gpiochip4   # Pi 5 40-pin header
      - /dev/i2c-1:/dev/i2c-1
    group_add:
      - gpio
      - i2c
```

### Auto-start on boot

`restart: unless-stopped` brings the node back whenever the Pi reboots or the process exits, so `docker compose up -d` is only needed once. Ensure Docker itself starts on boot with `sudo systemctl enable docker`.

### Docker troubleshooting

| Symptom | Fix |
| :--- | :--- |
| `permission denied` on `/dev/gpiochip0` | Keep `privileged: true`, or use the explicit `devices`/`group_add` list above. |
| `import gpiod` fails / `libgpiod` error | The container's `libgpiod` must match the pip `gpiod` version. Align the `gpiod` pin in `requirements.txt` with the base image's `libgpiod`, or base the `Dockerfile` on the same Raspberry Pi OS release as the host. |
| `.env` appears as a directory | `.env` must exist as a file before `docker compose up`; run `cp .env.example .env` first. |
| `exec format error` when starting | The image was built for the wrong architecture; rebuild it on the Pi. |
| Readings never arrive | Check `docker compose logs -f node`, confirm I2C is enabled on the host, and verify `VIVARIUMIQ_MQTT_BROKER` in `.env`. |

---

## Connecting to the VivariumIQ Backend

`setup_node.py` performs the REST steps for you. The manual steps below are for debugging or for provisioning a node without the interactive setup.

### Automatic setup (recommended)

Run from the repository root:

```bash
python -m node.setup_node
```

The script:

1. Loads `.env`.
2. Calls `GET /api/auth/me` with `VIVARIUMIQ_NODE_TOKEN`.
3. If the token is missing or expired, asks whether to log in, register, or quit.
4. On login, validates the email and password, then writes `VIVARIUMIQ_EMAIL`, `VIVARIUMIQ_PASSWORD`, and `VIVARIUMIQ_NODE_TOKEN` to `.env`.
5. On registration, validates the username, email, and password, creates the account with `POST /api/user`, then logs in and saves the same values.
6. Checks `VIVARIUMIQ_NODE_ID`; if it is missing or owned by another account, asks for the node name, location, and optional coordinates, then creates it with `POST /api/node`.
7. Saves `VIVARIUMIQ_NODE_ID` and the node details to `.env`.
8. Starts the telemetry loop (`python -m node`).

Use `python -m node.setup_node --setup-only` to stop before step 8.

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
python -m node.register_node
```

The script sends `POST /api/node` with `Authorization: Bearer <token>` and saves the returned `node_id` to `.env`. This path does not prompt and does not refresh the token; use `setup_node.py` for the normal setup.

The API endpoints used are:

- `POST /api/user` with `username`, `email`, `password`
- `POST /api/auth/login` with `email`, `password`; returns `access_token`
- `GET /api/auth/me` with `Authorization: Bearer <token>`
- `POST /api/node` with `Authorization: Bearer <token>` and `node_name`, `location_name`, `latitude`, and `longitude`

### MQTT topics

The telemetry loop (`node/telemetry.py`) prints samples to the terminal and additionally publishes:

| Topic | When | Payload |
| :--- | :--- | :--- |
| `vivariumiq/<node_id>/reading` | every sample (~3 s) | `temperature`, `humidity`, `pressure`, `motion`, `token` |
| `vivariumiq/<node_id>/diagnostic` | every 10th successful reading | `uptime`, `motion_sensor_status`, `dht22_status`, `pressure_sensor_status`, `token` |
| `vivariumiq/<node_id>/heartbeat` | every 10th successful reading | `token` |

Sensor failures are sent as `null` (or omitted) rather than a made-up value, and the loop keeps running if the broker is unreachable. The terminal will show `could not send reading (TLS connection to broker failed): ...` and retry on the next sample.

### Troubleshooting

| Symptom | Fix |
| :--- | :--- |
| `No valid vivariumiq login found` | Run `python -m node.setup_node` and choose login or register. |
| Login returns `401` | Check `VIVARIUMIQ_EMAIL` and `VIVARIUMIQ_PASSWORD`; the API reports `Invalid email or password`. |
| Registration returns `400` | The username or email already exists. Choose login instead, or use a different email. |
| Registration returns `422` | The API validation failed; check the printed detail (for example, a password under 8 characters). |
| `Could not reach the API at ...` | Check `VIVARIUMIQ_API_URL` in `.env` and that the API is running. Use the server's LAN IP, not `localhost`, when the API is on another machine. |
| Backend drops readings with `token is missing or wrong for node <id>` | Run `python -m node.setup_node` so the token belongs to the account that registered `VIVARIUMIQ_NODE_ID`. |
| Backend drops readings with `node <id> does not exist` | Run `python -m node.setup_node` to register the node; do not use an id from another node. |
| `could not send reading (TLS connection to broker failed)` | Check `VIVARIUMIQ_MQTT_BROKER` (must be `vivariumiq.pjmisev.com`, kept as a grey-cloud DNS record) and that Mosquitto is listening with TLS on `VIVARIUMIQ_MQTT_PORT` (8883). |
| Nothing arrives after 24 hours | Check that `VIVARIUMIQ_EMAIL` and `VIVARIUMIQ_PASSWORD` are still valid; the node refreshes the JWT one hour before expiry. |
| `VIVARIUMIQ_NODE_TOKEN` or `VIVARIUMIQ_NODE_ID` missing from `.env` | Run `python -m node.setup_node` again. It reuses existing values and fills in missing ones. |

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
