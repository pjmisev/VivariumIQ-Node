# One-time registration for the urcast weather node.
#
# A node can only be created by a logged-in user. This script sends
# POST /api/node with the owner's JWT in the Authorization header, then saves
# the returned node id to the repository-root .env as URCAST_NODE_ID.
#
# Settings are read from .env:
#   URCAST_API_URL        -- address of the urcast API
#   URCAST_NODE_TOKEN     -- the JWT from /api/auth/login
#   URCAST_NODE_NAME      -- a name for this node (1-100 characters)
#   URCAST_NODE_LOCATION  -- optional human-readable location
#   URCAST_NODE_LATITUDE  -- optional decimal latitude
#   URCAST_NODE_LONGITUDE -- optional decimal longitude
#
# The JWT expires 24 hours after login. If the API returns HTTP 401, run the
# login step again or use setup_node.py to refresh the token automatically.

import json
import sys
import urllib.error
import urllib.request

import config

PLACEHOLDER_TOKEN = "paste-your-jwt-token-here"


def _error_detail(body):
    try:
        return json.loads(body).get("detail", body)
    except json.JSONDecodeError:
        return body


def register_node():
    api_url = config.get_str("URCAST_API_URL", config.DEFAULT_API_URL).rstrip("/")
    node_token = config.get_str("URCAST_NODE_TOKEN", required=True)
    node_name = config.get_str("URCAST_NODE_NAME", config.DEFAULT_NODE_NAME)
    node_location = config.get_str("URCAST_NODE_LOCATION")
    latitude = config.get_optional_float(
        "URCAST_NODE_LATITUDE", minimum=-90, maximum=90
    )
    longitude = config.get_optional_float(
        "URCAST_NODE_LONGITUDE", minimum=-180, maximum=180
    )

    if node_token == PLACEHOLDER_TOKEN:
        print("Registration failed: URCAST_NODE_TOKEN is still the placeholder.")
        print("Run setup_node.py or log in and update URCAST_NODE_TOKEN in .env.")
        return None

    if not 1 <= len(node_name) <= 100:
        print("Registration failed: node name must be 1-100 characters.")
        return None

    payload = {"node_name": node_name}
    if node_location is not None:
        payload["location_name"] = node_location
    if latitude is not None:
        payload["latitude"] = latitude
    if longitude is not None:
        payload["longitude"] = longitude

    request = urllib.request.Request(
        f"{api_url}/api/node",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {node_token}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
            print(f"Node registered (HTTP {response.status}).")
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8")
        detail = _error_detail(body)
        if error.code == 401:
            print("Registration failed: invalid or expired token (HTTP 401).")
            print(f"API detail: {detail}")
            print("Run setup_node.py or log in again to refresh URCAST_NODE_TOKEN.")
        elif error.code == 422:
            print("Registration failed: validation error (HTTP 422).")
            print(f"API detail: {detail}")
        else:
            print(f"Registration failed (HTTP {error.code}).")
            print(f"API detail: {detail}")
        return None
    except urllib.error.URLError as error:
        print(f"Could not reach the API at {api_url}: {error.reason}")
        return None

    try:
        node = json.loads(body)
    except json.JSONDecodeError:
        print("Could not read the API response as JSON.")
        print(f"API response: {body}")
        return None

    node_id = node.get("node_id")
    if node_id is None:
        print("Registration succeeded but the API response did not include node_id.")
        print(f"API response: {body}")
        return None

    config.save({"URCAST_NODE_ID": node_id})
    print(f"node_name: {node.get('node_name', node_name)}")
    print(f"node_id:   {node_id}")
    print()
    print("Saved URCAST_NODE_ID to .env.")
    return node_id


def main():
    try:
        if register_node() is None:
            sys.exit(1)
    except config.ConfigError as error:
        print(f"Registration failed: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
