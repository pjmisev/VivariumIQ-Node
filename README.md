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
- **Runtime Utilities:** `time`, `datetime` (UTC-enforced timestamping)

---

## Project Architecture

```text
urcast-node-pi5/
│
├── tests/
│   ├── bmp280.py         # Standalone hardware test script for BMP280 pressure sensor
│   ├── dht22.py          # Standalone hardware test script for DHT22 temp & humidity sensor
│   ├── tsl2591.py        # Standalone hardware test script for TSL2591 light sensor
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

3. Install required Adafruit CircuitPython dependencies:
```bash
pip install adafruit-circuitpython-tsl2591 adafruit-circuitpython-bmp280 adafruit-circuitpython-dht adafruit-blinka
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

## Team

- **Pijus (PM)** – Back-End, Version Control
- **Raivis** – Database, Back-End
- **Anastasija** – Front-End, UI/UX/UD, Database
- **Leonas** – Hardware, Front-End
- **Kornel** – UI/UX/UD, Testing, Hardware