import os
import re

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
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "45"))  # then the answer is made without the model
# The season the pages and answers are about. Fixed, not "the latest loaded", so that loading another
# season changes nothing until the code asks for it (and the frozen evaluations keep their meaning).
ACTIVE_SEASON = os.getenv("ACTIVE_SEASON", "2024-25").strip()
if not re.fullmatch(r"\d{4}-\d{2}", ACTIVE_SEASON):
    raise RuntimeError("ACTIVE_SEASON must look like 2024-25")
ACTIVE_SEASON_SQL = f"'{ACTIVE_SEASON}'"  # safe to put in SQL: checked above

# "llm": with a key, a language model reads questions into a StatQuery; "rules": the word-matching reader only.
QUESTION_READER = os.getenv("QUESTION_READER", "llm").strip().lower()
# Marks logged questions and feedback, e.g. "study" while other people use the site; "local" otherwise.
ASK_LOG_SOURCE = os.getenv("ASK_LOG_SOURCE", "local").strip() or "local"

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

if LLM_PROVIDER != "openrouter":
    raise RuntimeError("LLM_PROVIDER must be 'openrouter'")


# Set COOKIE_SECURE=true when the site is served over HTTPS.
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").strip().lower() == "true"
