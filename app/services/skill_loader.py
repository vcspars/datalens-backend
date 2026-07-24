"""
skill_loader — lightweight in-memory cache for static `.md` skill files.

Skill files live in `app/skills/<name>.md` (relative to this file's package
root). They are read once on first access and cached for the lifetime of the
process — they never change at runtime, so no TTL or invalidation is needed.
"""

import os
from pathlib import Path
from functools import lru_cache

_SKILLS_DIR = Path(__file__).parent.parent / "skills"


@lru_cache(maxsize=None)
def load_skill(name: str) -> str:
    """Return the full text of `app/skills/<name>.md`.

    Results are cached in-process after the first read.  The file is resolved
    relative to this module's package root so it works regardless of the
    working directory the server is started from.

    Raises FileNotFoundError if the skill file does not exist.
    """
    path = _SKILLS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(
            f"Skill file not found: {path}. "
            f"Available skills: {[f.stem for f in _SKILLS_DIR.glob('*.md')]}"
        )
    return path.read_text(encoding="utf-8")
