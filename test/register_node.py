# One-time registration for the urcast weather node.
#
# A node can only be created by a logged-in user. This script sends
# POST /api/node with the owner's JWT in the Authorization header, then prints
# the node_id returned by the API. Put that id and the same token into
# mqtt_client.py, then run combinedTest.py normally.
#
# The JWT expires 24 hours after login. If the API returns HTTP 401, log in
# again, paste the new token into NODE_TOKEN, and run this script again.
#
# Edit the settings below:
#   API_URL       -- address of the urcast API
#   NODE_TOKEN    -- the JWT from /api/auth/login
#   NODE_NAME     -- a name for this node (1-100 characters)
#   NODE_LOCATION -- optional human-readable location
#   NODE_LATITUDE -- optional decimal latitude
#   NODE_LONGITUDE-- optional decimal longitude

import json
import sys
import urllib.error
import urllib.request

API_URL = "http://localhost:8000"
NODE_TOKEN = "paste-your-jwt-token-here"
NODE_NAME = "pi5-outdoor"
NODE_LOCATION = "Dublin, Ireland"
NODE_LATITUDE = None
NODE_LONGITUDE = None


def _error_detail(body):
    try:
        return json.loads(body).get("detail", body)
    except json.JSONDecodeError:
        return body


def register_node():
    payload = {"node_name": NODE_NAME, "location_name": NODE_LOCATION}
    if NODE_LATITUDE is not None:
        payload["latitude"] = NODE_LATITUDE
    if NODE_LONGITUDE is not None:
        payload["longitude"] = NODE_LONGITUDE

    request = urllib.request.Request(
        f"{API_URL.rstrip('/')}/api/node",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {NODE_TOKEN}",
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
            print("Log in again and paste the new token into NODE_TOKEN.")
        elif error.code == 422:
            print("Registration failed: validation error (HTTP 422).")
            print(f"API detail: {detail}")
        else:
            print(f"Registration failed (HTTP {error.code}).")
            print(f"API detail: {detail}")
        return None
    except urllib.error.URLError as error:
        print(f"Could not reach the API at {API_URL}: {error.reason}")
        return None

    try:
        node = json.loads(body)
    except json.JSONDecodeError:
        print("Could not read the API response as JSON.")
        print(f"API response: {body}")
        return None

    node_id = node.get("node_id")
    print(f"node_name: {node.get('node_name', NODE_NAME)}")
    print(f"node_id:   {node_id}")
    print()
    print("Put this node_id into NODE_ID in mqtt_client.py.")
    return node_id


def main():
    if NODE_TOKEN == "paste-your-jwt-token-here":
        print("Edit register_node.py and paste your JWT into NODE_TOKEN first.")
        sys.exit(1)

    if register_node() is None:
        sys.exit(1)


if __name__ == "__main__":
    main()
