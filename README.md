# urcast Raspberry Pi Weather Node README

> A Python-based edge telemetry collection script designed to run on outdoor Raspberry Pi weather stations. This repository contains the hardware-interfacing code responsible for gathering environmental data from local sensors and submitting it via HTTP REST API to the centralized urcast backend.

---

## About the Weather Node

The **urcast Node** runs locally on a Raspberry Pi (such as the Raspberry Pi Zero 2 W) deployed inside an outdoor protective enclosure. Using a scheduled cron job, the script executes at regular intervals to read real-time environmental metrics, capture location and timestamp data via GPS, and securely transmit the payload to the FastAPI backend.

---

## Key Features and Responsibilities

* **Sensor Data Collection:** Interfaces with connected hardware to measure temperature, humidity, atmospheric pressure, and ambient light levels.
* **GPS Positioning and Timing:** Obtains precise latitude, longitude coordinates, and synchronized timestamps via a GPS module.
* **Automated Telemetry Transmission:** Formats sensor readings into structured JSON payloads and submits them to the backend API over HTTP.
* **Error Resilience:** Designed to handle temporary network disconnections, sensor read timeouts, or connection failures gracefully without crashing the system or corrupting local operations.

---

## Hardware Stack

* **Microcontroller:** Raspberry Pi (Zero 2 W)
* **Temperature and Humidity:** DHT22 sensor
* **Atmospheric Pressure:** BMP280 sensor
* **Light Level:** BH1750 sensor
* **Location and Time:** NEO-6M GPS module
* **Power and Housing:** Weatherproof outdoor enclosure with proper ventilation and sun-shading.

---

## Technology Stack

* **Language:** Python 3.10+
* **HTTP Client:** `requests` library for REST API communication
* **Sensor Libraries:** Adafruit CircuitPython libraries and GPIO/I2C peripheral interfaces
* **Scheduling:** Linux `cron` (crontab)

---

## Project Architecture (Node Client)

```text
urcast-node/
│
├── sensors/            # Individual sensor interface wrappers (dht22.py, bmp280.py, bh1750.py, gps.py)
├── api/                # HTTP client module for communicating with the urcast backend API
├── config.py           # Configuration loader (API endpoints, node authentication tokens, logging settings)
├── main.py             # Entry point script executing data collection and transmission
├── requirements.txt    # Python hardware and utility dependencies
└── .env.example        # Template for environment variables

```

---

## Getting Started and Installation

### Prerequisites

* A Raspberry Pi running Raspberry Pi OS with I2C and UART interfaces enabled via `sudo raspi-config`.
* Physical wiring of the DHT22, BMP280, BH1750, and NEO-6M GPS modules to the appropriate Raspberry Pi GPIO pins.

### Setup Instructions

1. Clone the repository onto your Raspberry Pi:
```bash
git clone https://github.com/your-team/urcast-node.git
cd urcast-node

```


2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate

```


3. Install dependencies:
```bash
pip install -r requirements.txt

```


4. Create your local configuration file (`.env`) based on the template:
```env
API_BASE_URL=https://api.urcast.local/v1
NODE_ID=1
NODE_SECRET_KEY=your_secure_node_token

```



---

## Configuring Automation via Crontab

To ensure the script runs automatically at fixed intervals (for example, every 10 minutes), configure a cron job.

1. Open the crontab editor:
```bash
crontab -e

```


2. Add the following entry to execute the Python script using your virtual environment interpreter every 10 minutes:
```cron
*/10 * * * * /home/pi/urcast-node/venv/bin/python /home/pi/urcast-node/main.py >> /home/pi/urcast-node/node.log 2>&1

```



---

## Testing and Manual Execution

To test data collection and ensure the script successfully communicates with the backend without waiting for the cron schedule, run the script manually:

```bash
python main.py

```

Check the generated log file (`node.log`) to verify sensor readings and inspect HTTP response codes from the backend API.

---

## Team

* **Pijus (PM)** – Back-End, Version Control
* **Raivis** – Database, Back-End
* **Anastasija** – Front-End, UI/UX/UD, Database
* **Leonas** – Hardware, Front-End
* **Kornel** – UI/UX/UD, Testing, Hardware
