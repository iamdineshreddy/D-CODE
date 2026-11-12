import os
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "d_orchestrator.db"
CHECKPOINT_DIR = DATA_DIR / "checkpoints"
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_API_URL = OLLAMA_BASE_URL.rstrip("/") + "/api"
OLLAMA_OPENAI_URL = OLLAMA_BASE_URL.rstrip("/") + "/v1"

DEFAULT_LOCAL_OPTIMIZER = os.getenv("LOCAL_OPTIMIZER_MODEL", "qwen2.5-coder:7b")

# Budget defaults (USD)
DEFAULT_MONTHLY_BUDGET = float(os.getenv("MONTHLY_BUDGET_USD", "20.0"))
DEFAULT_DAILY_BUDGET = float(os.getenv("DAILY_BUDGET_USD", "5.0"))

# Approval settings
AUTO_SAFE_OPS = os.getenv("AUTO_SAFE_OPS", "true").lower() == "true"
REQUIRE_APPROVAL_DESTRUCTIVE = os.getenv("REQUIRE_APPROVAL_DESTRUCTIVE", "true").lower() == "true"
REQUIRE_APPROVAL_PAID = os.getenv("REQUIRE_APPROVAL_PAID", "true").lower() == "true"

# Resource limits
MAX_LOCAL_CONTEXT = int(os.getenv("MAX_LOCAL_CONTEXT", "8192"))
ONE_LOCAL_MODEL_AT_A_TIME = True
