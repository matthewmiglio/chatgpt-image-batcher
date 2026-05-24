import json
import re
from pathlib import Path
from typing import List


def load_prompts(path: str) -> List[str]:
    """Load prompts from a JSON file.

    Accepts either:
      - {"prompt1": "...", "prompt2": "..."}   (dict — values used in key order)
      - ["...", "..."]                          (list of strings)
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"prompts file not found: {path}")
    # utf-8-sig transparently handles a leading BOM if present
    data = json.loads(p.read_text(encoding="utf-8-sig"))

    if isinstance(data, dict):
        prompts = [str(v) for v in data.values()]
    elif isinstance(data, list):
        prompts = [str(v) for v in data]
    else:
        raise ValueError(
            f"prompts file must be a dict or list, got {type(data).__name__}"
        )

    prompts = [s.strip() for s in prompts if s and str(s).strip()]
    if not prompts:
        raise ValueError(f"no prompts found in {path}")
    return prompts


def slugify(text: str, max_len: int = 60) -> str:
    """Mirror the extension's slugifyPrompt — lowercase, kebab, trim."""
    s = text.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    s = s[:max_len]
    s = s.rstrip("-")
    return s or "image"
