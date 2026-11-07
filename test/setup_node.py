"""Interactive first-run setup for the urcast weather node."""

from __future__ import annotations

import getpass
import re
import subprocess
import sys
from pathlib import Path

import auth_client
import config

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _ask(prompt, default=None, validator=None):
    while True:
        shown_default = f" [{default}]" if default not in (None, "") else ""
        raw = input(f"{prompt}{shown_default}: ").strip()
        if not raw and default is not None:
            raw = str(default)
        if not raw:
            print("This field is required.")
            continue
        try:
            return validator(raw) if validator else raw
        except ValueError as error:
            print(f"Invalid value: {error}")


def _ask_optional(prompt, default=None, validator=None):
    while True:
        shown_default = (
            f" [{default}]" if default not in (None, "") else " (optional)"
        )
        raw = input(f"{prompt}{shown_default}: ").strip()
        if not raw:
            if default is None:
                return None
            raw = str(default)
        try:
            return validator(raw) if validator else raw
        except ValueError as error:
            print(f"Invalid value: {error}")


def _ask_secret(prompt, validator=None):
    while True:
        value = getpass.getpass(f"{prompt}: ")
        if not value:
            print("This field is required.")
            continue
        if validator is None:
            return value
        try:
            return validator(value)
        except ValueError as error:
            print(f"Invalid value: {error}")


def _ask_choice(prompt, choices):
    while True:
        value = input(f"{prompt}: ").strip().lower()
        if value in choices:
            return value
        print(f"Please enter one of: {', '.join(sorted(choices))}")


def _validate_email(value):
    if len(value) > 255:
        raise ValueError("email must be at most 255 characters")
    if not EMAIL_RE.match(value):
        raise ValueError("enter a valid email address")
    return value


def _validate_username(value):
    if not 3 <= len(value) <= 100:
        raise ValueError("username must be 3-100 characters")
    return value


def _validate_password(value):
    if not 8 <= len(value) <= 72:
        raise ValueError("password must be 8-72 characters")
    if len(value.encode("utf-8")) > 72:
        raise ValueError("password must be at most 72 bytes")
    return value


def _validate_node_name(value):
    if not 1 <= len(value) <= 100:
        raise ValueError("node name must be 1-100 characters")
    return value


def _validate_location(value):
    if len(value) > 150:
        raise ValueError("location must be at most 150 characters")
    return value


def _parse_coordinate(value, label, minimum, maximum):
    try:
        number = float(value)
    except ValueError:
        raise ValueError(f"{label} must be a number") from None
    if not minimum <= number <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return number


def _validate_latitude(value):
    return _parse_coordinate(value, "latitude", -90, 90)


def _validate_longitude(value):
    return _parse_coordinate(value, "longitude", -180, 180)


def _configured_node_id():
    try:
        return config.get_int("URCAST_NODE_ID", minimum=1)
    except config.ConfigError as error:
        print(f"Ignoring URCAST_NODE_ID: {error}")
        return None


def _configured_optional_float(name, minimum, maximum):
    try:
        return config.get_optional_float(name, minimum=minimum, maximum=maximum)
    except config.ConfigError as error:
        print(f"Ignoring {name}: {error}")
        return None


def _login():
    email_default = config.get_str("URCAST_EMAIL")
    email = _ask("Email", default=email_default, validator=_validate_email)
    password = _ask_secret("Password")

    try:
        token = auth_client.login(email, password)
    except auth_client.ApiError as error:
        if error.status == 401:
            print("Login failed: invalid email or password.")
        else:
            print(f"Login failed: {error}")
            if error.status is None:
                print(
                    f"Check URCAST_API_URL in {config.ENV_PATH} "
                    "and that the API is running."
                )
        return None

    config.save(
        {
            "URCAST_EMAIL": email,
            "URCAST_PASSWORD": password,
            "URCAST_NODE_TOKEN": token,
        }
    )
    print("Logged in. Saved the JWT and account credentials to .env.")
    return token


def _register():
    username = _ask("Username", validator=_validate_username)
    email = _ask("Email", validator=_validate_email)

    while True:
        password = _ask_secret("Password", validator=_validate_password)
        confirmation = getpass.getpass("Confirm password: ")
        if password == confirmation:
            break
        print("Passwords do not match. Try again.")

    try:
        auth_client.register_user(username, email, password)
    except auth_client.ApiError as error:
        if error.status in (400, 422):
            print(f"Registration failed: {error.detail}")
        else:
            print(f"Registration failed: {error}")
            if error.status is None:
                print(
                    f"Check URCAST_API_URL in {config.ENV_PATH} "
                    "and that the API is running."
                )
        return None

    print("Account created. Logging in...")
    try:
        token = auth_client.login(email, password)
    except auth_client.ApiError as error:
        print(f"Account created, but login failed: {error}")
        print("Run setup again and choose Log in.")
        return None

    config.save(
        {
            "URCAST_EMAIL": email,
            "URCAST_PASSWORD": password,
            "URCAST_NODE_TOKEN": token,
        }
    )
    print("Logged in. Saved the JWT and account credentials to .env.")
    return token


def _ensure_authenticated():
    try:
        user = auth_client.check_authentication()
    except auth_client.ApiError as error:
        print(f"Could not check the saved login: {error}")
        print(
            f"Check URCAST_API_URL in {config.ENV_PATH} "
            "and that the API is running."
        )
        raise SystemExit(1) from error

    if user:
        print(f"Authenticated as {user.get('username')} ({user.get('email')}).")
        return user

    print("No valid urcast login found.")
    while True:
        choice = _ask_choice(
            "Log in or register a new account? [l/r/q]",
            {"l", "r", "q"},
        )
        if choice == "q":
            print("Setup cancelled.")
            raise SystemExit(1)

        token = _login() if choice == "l" else _register()
        if token is None:
            continue

        try:
            user = auth_client.check_authentication(token)
        except auth_client.ApiError as error:
            print(f"Could not verify the new login: {error}")
            continue

        if user:
            print(f"Authenticated as {user.get('username')} ({user.get('email')}).")
            return user

        print("The API rejected the new token. Please try again.")


def _ensure_node(user):
    node_id = _configured_node_id()
    if node_id is not None:
        try:
            node = auth_client.get_node(node_id)
        except auth_client.ApiError as error:
            if error.status == 404:
                print(f"Node {node_id} does not exist; registering a new node.")
            else:
                print(f"Could not check node {node_id}: {error}")
                raise SystemExit(1) from error
        else:
            if node and node.get("user_id") == user.get("user_id"):
                print(f"Using existing node {node_id} ({node.get('node_name')}).")
                return node_id
            if node:
                print(
                    f"Node {node_id} belongs to a different account; "
                    "registering a new node."
                )
            else:
                print(f"Could not load node {node_id}; registering a new node.")

    node_name_default = config.get_str("URCAST_NODE_NAME", config.DEFAULT_NODE_NAME)
    node_name = _ask(
        "Node name",
        default=node_name_default,
        validator=_validate_node_name,
    )

    location_default = config.get_str("URCAST_NODE_LOCATION")
    location = _ask_optional(
        "Location",
        default=location_default,
        validator=_validate_location,
    )

    latitude_default = _configured_optional_float("URCAST_NODE_LATITUDE", -90, 90)
    latitude = _ask_optional(
        "Latitude",
        default=latitude_default,
        validator=_validate_latitude,
    )

    longitude_default = _configured_optional_float("URCAST_NODE_LONGITUDE", -180, 180)
    longitude = _ask_optional(
        "Longitude",
        default=longitude_default,
        validator=_validate_longitude,
    )

    try:
        token = auth_client.get_token()
    except auth_client.AuthError as error:
        print(f"Could not prepare a JWT: {error}")
        raise SystemExit(1) from error

    try:
        node = auth_client.register_node(
            token,
            node_name,
            location,
            latitude,
            longitude,
        )
    except auth_client.ApiError as error:
        if error.status == 401:
            print("Node registration failed: the JWT is invalid or expired.")
            print("Run setup again and log in.")
        else:
            print(f"Node registration failed: {error}")
        raise SystemExit(1) from error

    new_node_id = node.get("node_id")
    if new_node_id is None:
        print("The API did not return a node_id.")
        raise SystemExit(1)

    config.save(
        {
            "URCAST_NODE_ID": new_node_id,
            "URCAST_NODE_NAME": node_name,
            "URCAST_NODE_LOCATION": location,
            "URCAST_NODE_LATITUDE": latitude,
            "URCAST_NODE_LONGITUDE": longitude,
        }
    )
    print(f"Registered node {new_node_id} and saved it to .env.")
    return new_node_id


def _start_service():
    script = Path(__file__).resolve().with_name("combinedTest.py")
    print("Starting the sensor service. Press Ctrl+C to stop.")
    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(script.parent),
        )
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0
    return result.returncode


def main(setup_only=False):
    config.ensure_env_file()
    print(f"Using settings from {config.ENV_PATH}")
    print(f"API: {auth_client.api_url()}")

    user = _ensure_authenticated()
    _ensure_node(user)

    if setup_only:
        print("Setup complete. Run test/combinedTest.py to start the service.")
        return 0

    return _start_service()


if __name__ == "__main__":
    try:
        sys.exit(main(setup_only="--setup-only" in sys.argv[1:]))
    except config.ConfigError as error:
        print(f"Configuration error: {error}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(1)
