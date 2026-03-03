import json
import logging
from pathlib import Path

logger = logging.getLogger("aloware.config")

CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config() -> dict:
    """Load agent configuration from config.json.

    Called on every new connection so that config changes made via the API
    are picked up without restarting the worker process.
    """
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    logger.info("Config loaded: agent_name=%s", config.get("agent_name"))
    return config


def read_config() -> dict:
    """Read config.json and return its contents as a dict.

    Raises FileNotFoundError if config.json does not exist.
    """
    if not CONFIG_PATH.exists():
        raise FileNotFoundError("config.json not found")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def write_config(data: dict) -> None:
    """Overwrite config.json with the provided dict."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info("config.json updated")
