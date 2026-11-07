"""Central configuration for the urcast weather node.

Runtime settings live in the repository-root ``.env`` file. Import this module
instead of defining API URLs, tokens, node ids, or broker addresses in each
script.
"""

from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path

try:
    from dotenv import load_dotenv, set_key
except ImportError as error:
    raise SystemExit(
        "python-dotenv is required. Install the node dependencies with:\n"
        "    pip install -r requirements.txt"
    ) from error

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
ENV_EXAMPLE_PATH = PROJECT_ROOT / ".env.example"

DEFAULT_API_URL = "http://localhost:8000"
DEFAULT_MQTT_BROKER = "localhost"
DEFAULT_MQTT_PORT = 1883
DEFAULT_NODE_NAME = "pi5-outdoor"
DEFAULT_READ_INTERVAL_S = 3.0


class ConfigError(ValueError):
    """Raised when a configuration value is missing or malformed."""


load_dotenv(ENV_PATH)


def _raw(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def get_str(
    name: str,
    default: str | None = None,
    *,
    required: bool = False,
) -> str | None:
    value = _raw(name)
    if value is None:
        if required:
            raise ConfigError(f"{name} is missing from {ENV_PATH}")
        return default
    return value


def get_int(
    name: str,
    default: int | None = None,
    *,
    required: bool = False,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int | None:
    raw = get_str(name, None, required=required)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a whole number, got {raw!r}") from None
    if minimum is not None and value < minimum:
        raise ConfigError(f"{name} must be at least {minimum}, got {value}")
    if maximum is not None and value > maximum:
        raise ConfigError(f"{name} must be at most {maximum}, got {value}")
    return value


def get_float(
    name: str,
    default: float | None = None,
    *,
    required: bool = False,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float | None:
    raw = get_str(name, None, required=required)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from None
    if minimum is not None and value < minimum:
        raise ConfigError(f"{name} must be at least {minimum}, got {value}")
    if maximum is not None and value > maximum:
        raise ConfigError(f"{name} must be at most {maximum}, got {value}")
    return value


def get_optional_float(
    name: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float | None:
    raw = get_str(name)
    if raw is None:
        return None
    return get_float(name, minimum=minimum, maximum=maximum)


def ensure_env_file() -> Path:
    """Create .env from .env.example when it does not exist."""
    if not ENV_PATH.exists():
        if ENV_EXAMPLE_PATH.exists():
            shutil.copyfile(ENV_EXAMPLE_PATH, ENV_PATH)
        else:
            ENV_PATH.touch()
        load_dotenv(ENV_PATH, override=False)
        _restrict_permissions()
    return ENV_PATH


def save(values: dict[str, object]) -> None:
    """Persist values to the central .env and update the current process."""
    ensure_env_file()
    for name, value in values.items():
        text = "" if value is None else str(value)
        set_key(str(ENV_PATH), name, text)
        os.environ[name] = text
    _restrict_permissions()


def _restrict_permissions() -> None:
    try:
        ENV_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
