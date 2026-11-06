# MQTT publisher for the urcast weather node.
#
# Every message is published to urcast/<node_id>/<kind> and carries the owner's
# JWT in the "token" field. The backend drops anything with a missing, expired,
# or wrong token, so keep the node account in sync with the account that
# registered this node.
#
# Settings are read from the repository-root .env:
#   URCAST_MQTT_BROKER -- the machine running the urcast API and Mosquitto
#   URCAST_MQTT_PORT   -- the Mosquitto port
#   URCAST_NODE_ID     -- the id returned by registration
#   URCAST_NODE_TOKEN  -- the JWT from /api/auth/login; auth_client refreshes it
#                        automatically before it expires

import json
import time

import paho.mqtt.client as mqtt

import auth_client
import config

_STARTED_AT = time.monotonic()
_client = None


def _settings():
    broker = config.get_str("URCAST_MQTT_BROKER", config.DEFAULT_MQTT_BROKER)
    port = config.get_int(
        "URCAST_MQTT_PORT",
        config.DEFAULT_MQTT_PORT,
        minimum=1,
        maximum=65535,
    )
    node_id = config.get_int("URCAST_NODE_ID", required=True, minimum=1)
    return broker, port, node_id


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


def _get_client(broker, port):
    global _client
    if _client is not None and _client.is_connected():
        return _client

    _drop_client()
    _client = _new_client()
    _client.connect(broker, port)
    _client.loop_start()
    return _client


def _publish(kind, fields):
    try:
        broker, port, node_id = _settings()
        token = auth_client.get_token()
    except (config.ConfigError, auth_client.AuthError) as error:
        print(f"could not send {kind}: {error}")
        return False

    payload = dict(fields)
    payload["token"] = token
    topic = f"urcast/{node_id}/{kind}"

    try:
        client = _get_client(broker, port)
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
