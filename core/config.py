"""Central paths and settings. Resolves the supplied data pack and runtime config."""
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # dotenv is optional at runtime
    pass

# --- Paths -------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# The candidate data pack ships in a folder with spaces in its name; resolve it
# robustly rather than hard-coding, so the repo works if the folder is renamed.
def _find_pack() -> Path:
    candidates = [
        ROOT / "AI Agent Assessment - Candidate Pack",
        ROOT / "data" / "pack",
        ROOT / "candidate_pack",
    ]
    for c in candidates:
        if c.exists():
            return c
    # Fall back to any folder containing the workbook.
    for p in ROOT.rglob("ParcelPilot_Assessment_Data.xlsx"):
        return p.parent
    raise FileNotFoundError(
        "Could not locate the candidate data pack. Expected a folder containing "
        "ParcelPilot_Assessment_Data.xlsx (e.g. 'AI Agent Assessment - Candidate Pack')."
    )


PACK_DIR = _find_pack()
WORKBOOK = PACK_DIR / "ParcelPilot_Assessment_Data.xlsx"
DOC_INDEX = DATA_DIR / "doc_index.json"
ACTIONS_STORE = DATA_DIR / "actions_store.json"

# --- LLM settings (provider-agnostic, OpenAI-compatible) ---------------------
# The agent talks to any OpenAI-compatible endpoint. We accept generic LLM_* vars
# and fall back to provider-specific ones, auto-detecting sensible base URL + model
# from the API-key prefix so a pasted key "just works":
#   gsk_...  -> Groq   (https://api.groq.com/openai/v1)
#   xai-...  -> xAI Grok (https://api.x.ai/v1)
LLM_API_KEY = (os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY")
               or os.getenv("XAI_API_KEY") or "").strip()

_PROVIDER_DEFAULTS = {
    "groq": ("https://api.groq.com/openai/v1", "openai/gpt-oss-120b"),
    "xai": ("https://api.x.ai/v1", "grok-4"),
}


def _detect_provider(key: str) -> str:
    if key.startswith("gsk_"):
        return "groq"
    if key.startswith("xai-"):
        return "xai"
    return "groq"  # safe default for OpenAI-compatible hosts


_provider = _detect_provider(LLM_API_KEY)
_def_base, _def_model = _PROVIDER_DEFAULTS[_provider]

LLM_BASE_URL = (os.getenv("LLM_BASE_URL") or os.getenv("XAI_BASE_URL") or _def_base)
LLM_MODEL = (os.getenv("LLM_MODEL") or os.getenv("XAI_MODEL") or _def_model)
LLM_PROVIDER = _provider


def llm_available() -> bool:
    return bool(LLM_API_KEY)
