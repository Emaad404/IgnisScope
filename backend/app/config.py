"""Configuration. Values can be overridden with environment variables or a .env file
(loaded manually to avoid an extra dependency)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()

DATA_DIR = Path(os.environ.get("FIF_DATA_DIR", ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
SYNTHETIC_DIR = ROOT / "data" / "synthetic"
DB_PATH = Path(os.environ.get("FIF_DB_PATH", DATA_DIR / "flame.db"))
MAX_UPLOAD_MB = int(os.environ.get("FIF_MAX_UPLOAD_MB", "25"))
CORS_ORIGINS = [o.strip() for o in os.environ.get(
    "FIF_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]

PIPELINE_VERSION = "fif-pipeline-0.1.0"
METHODOLOGY_VERSION = "fif-method-0.1.0-heuristic"
SYNTHETIC_LABEL = "SYNTHETIC - NOT NASA DATA"
