import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "app.db"
DB_PATH = os.getenv("DB_PATH", str(DEFAULT_DB_PATH))

# CORS Settings — 前端開發伺服器預設 1688（見 scripts/dev.sh）
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:1688,http://localhost:5173"
    ).split(",")
    if origin.strip()
]

# Risk Management Settings
MAX_POSITION_PCT = float(os.getenv("RISK_MAX_POSITION_PCT", "0.25"))
MAX_ORDER_VALUE = float(os.getenv("RISK_MAX_ORDER_VALUE", "500000"))
MIN_CONFIDENCE = float(os.getenv("RISK_MIN_CONFIDENCE", "0.5"))
ALLOW_SHORT = os.getenv("RISK_ALLOW_SHORT", "0").lower() in ("1", "true", "yes")

# Advisor & Model Settings
USE_CODEX = os.getenv("USE_CODEX", "0") == "1"
USE_RULES = os.getenv("USE_RULES", "0") == "1"
CODEX_MODEL = os.getenv("CODEX_MODEL", "gpt-4o-mini")  # Default to gpt-4o-mini to avoid using gpt-5-codex placeholder
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Shioaji SDK Settings
USE_SHIOAJI = os.getenv("USE_SHIOAJI", "0") == "1"
SHIOAJI_API_KEY = os.getenv("SHIOAJI_API_KEY", "")
SHIOAJI_SECRET_KEY = os.getenv("SHIOAJI_SECRET_KEY", "")
