"""
DevMind Configuration
All settings are read from environment variables with sensible defaults.
Copy .env.example → .env and fill in your values.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

# ── Endee ────────────────────────────────────────────────────────────────────
ENDEE_HOST = os.getenv("ENDEE_HOST", "http://localhost:8080")
ENDEE_AUTH_TOKEN = os.getenv("ENDEE_AUTH_TOKEN", "")
INDEX_NAME = os.getenv("INDEX_NAME", "devmind_code")

# ── Embedding ────────────────────────────────────────────────────────────────
# Dimension must match the model: all-MiniLM-L6-v2 → 384
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))

# ── Chunking ─────────────────────────────────────────────────────────────────
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "40"))       # lines per chunk
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "8"))  # overlap between chunks
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "64"))        # upsert batch size

# ── Retrieval ─────────────────────────────────────────────────────────────────
TOP_K = int(os.getenv("TOP_K", "5"))

# ── LLM (Google Gemini) ──────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", GEMINI_API_KEY)  # fallback
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-1.5-flash")  # free tier model

# ── File filtering ────────────────────────────────────────────────────────────
SUPPORTED_EXTENSIONS = set(
    os.getenv(
        "SUPPORTED_EXTENSIONS",
        ".py,.js,.ts,.jsx,.tsx,.go,.java,.rs,.cpp,.c,.h,.cs,.rb,.php,.swift,.kt,.scala",
    ).split(",")
)

EXCLUDE_DIRS = set(
    os.getenv(
        "EXCLUDE_DIRS",
        "node_modules,.git,__pycache__,.venv,venv,dist,build,.next,.cache,vendor",
    ).split(",")
)
