# MQTT publisher for the urcast weather node.
#
# Every message is published to urcast/<node_id>/<kind> and carries the owner's
# JWT in the "token" field. The backend drops anything with a missing, expired,
# or wrong token, so keep NODE_TOKEN in sync with the account that registered
# this node.
#
# Edit the settings below:
#   NODE_ID     -- the id printed by register_node.py
#   NODE_TOKEN  -- the JWT from /api/auth/login (it expires after 24 hours)
#   MQTT_BROKER -- the machine running the urcast API and Mosquitto

import json
import time

import paho.mqtt.client as mqtt

MQTT_BROKER = "localhost"
MQTT_PORT = 1883
NODE_ID = 1
NODE_TOKEN = "paste-your-jwt-token-here"

_STARTED_AT = time.monotonic()
_client = None


def _new_client():
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except AttributeError:
        # paho-mqtt older than 2.0 has no CallbackAPIVersion
        return mqtt.Client()


def _drop_client():
    global _client
    if _client is not None:
        try:
            _client.loop_stop()
            _client.disconnect()
        except Exception:
            pass
        _client = None


def _get_client():
    global _client
    if _client is not None and _client.is_connected():
        return _client

    _drop_client()
    _client = _new_client()
    _client.connect(MQTT_BROKER, MQTT_PORT)
    _client.loop_start()
    return _client


def _publish(kind, fields):
    payload = dict(fields)
    payload["token"] = NODE_TOKEN
    topic = f"urcast/{NODE_ID}/{kind}"

    try:
        client = _get_client()
        result = client.publish(topic, json.dumps(payload))
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"publish returned code {result.rc}")
        return True
    except Exception as error:
        _drop_client()
        print(f"could not send {kind} (no connection to broker): {error}")
        return False


def send_reading(temperature, humidity, pressure, light_level):
    return _publish(
        "reading",
        {
            "temperature": temperature,
            "humidity": humidity,
            "pressure": pressure,
            "light_level": light_level,
        },
    )


def send_diagnostic(light_ok, air_ok, pressure_ok):
    return _publish(
        "diagnostic",
        {
            "uptime": int(time.monotonic() - _STARTED_AT),
            "light_sensor_status": light_ok,
            "dht22_status": air_ok,
            "pressure_sensor_status": pressure_ok,
        },
    )


def send_heartbeat():
    return _publish("heartbeat", {})


def close():
    _drop_client()
