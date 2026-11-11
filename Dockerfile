# VivariumIQ node image -- runs the enclosure telemetry loop.
#
# The node talks to real hardware (DHT22, BMP280 over software I2C, and a PIR),
# so the container must run with access to the Pi's GPIO and I2C devices. See
# docker-compose.yml, which runs it privileged and mounts ./.env.

FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# libgpiod backs Blinka's GPIO access on the Pi; i2c-tools helps with debugging.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgpiod2 \
        i2c-tools \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY .env.example ./
COPY node ./node
COPY tools ./tools

CMD ["python", "-m", "node"]
