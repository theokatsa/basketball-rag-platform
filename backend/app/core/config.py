import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openrouter").strip().lower()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
# The name of a Sentence Transformers model, or of a folder in backend/models made by training/.
# Changing it means running scripts/build_rag_index.py again.
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2").strip()
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "6"))
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "300"))

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

if LLM_PROVIDER != "openrouter":
    raise RuntimeError("LLM_PROVIDER must be 'openrouter'")


# Set COOKIE_SECURE=true when the site is served over HTTPS.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").strip().lower() == "true"
