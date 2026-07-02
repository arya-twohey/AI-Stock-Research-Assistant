import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = PROJECT_ROOT / "web"
DEFAULT_BASE_URL = "https://paper-api.alpaca.markets/v2"


def load_env_file() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def require_alpaca_credentials() -> tuple[str, str]:
    load_env_file()
    key_id = os.environ.get("APCA_API_KEY_ID")
    secret_key = os.environ.get("APCA_API_SECRET_KEY")
    if not key_id or not secret_key:
        raise RuntimeError(
            "Missing Alpaca paper credentials. Set APCA_API_KEY_ID and "
            "APCA_API_SECRET_KEY in your environment or .env."
        )
    return key_id, secret_key


def public_demo_enabled() -> bool:
    return os.environ.get("PUBLIC_DEMO", "").lower() in {"1", "true", "yes", "on"}


def trade_submit_enabled() -> bool:
    return os.environ.get("ALLOW_TRADE_SUBMIT", "").lower() in {"1", "true", "yes", "on"}
