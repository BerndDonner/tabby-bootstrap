# ==========================================================
# ⚙️  config.py — Shared defaults for setup scripts
# ==========================================================
# Central configuration for Tabby bootstrap environment.
# Adjust paths or defaults here as needed.
# All values can be overridden via environment variables.
# ==========================================================

from pathlib import Path
import os

# --- Core directories ---
DATA_ROOT = Path(os.getenv("DATA_ROOT", "/home/ubuntu/tabbyclassmodels"))
MODEL_ROOT = Path(os.getenv("MODEL_ROOT", f"{DATA_ROOT}/models/TabbyML"))
DB_PATH = Path(os.getenv("DB_PATH", f"{DATA_ROOT}/ee/db.sqlite"))
CLASSES_DIR = Path(os.getenv("CLASSES_DIR", f"{Path(__file__).parent.parent}/classes"))

# --- Docker / Container settings ---
PORT = int(os.getenv("PORT", "8080"))
CONTAINER_NAME = os.getenv("CONTAINER_NAME", "tabby")

# --- AWS / S3 defaults ---
DEFAULT_BUCKET = os.getenv("TABBY_S3_BUCKET", "tabby-models")
DEFAULT_ENDPOINT = os.getenv("TABBY_S3_ENDPOINT", "https://fsn1.your-objectstorage.com")
DEFAULT_PROFILE = os.getenv("AWS_PROFILE", "default")

# --- Model selections ---
PROMPT_MODEL = os.getenv("PROMPT_MODEL", "DeepSeekCoder-6.7B")
CHAT_MODEL = os.getenv("CHAT_MODEL", "Qwen2.5-Coder-7B-Instruct")

# --- SMTP / Mail defaults (used by create_students.py) ---
MAIL_ENABLED = bool(int(os.getenv("MAIL_ENABLED", "0")))
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.yourschool.de")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "teacher@sabel.education")
SMTP_PASS = os.getenv("SMTP_PASS", "YOUR_SMTP_PASSWORD")
SENDER_NAME = os.getenv("SENDER_NAME", "Tabby Classroom Server")

