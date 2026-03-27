"""
Route to the correct role-specific DB knowledge module.

Each role has its own db_knowledge_<role>.py that exports `get_system_prompt()`.
For now all three files are identical copies of the original db_knowledge.py;
the user will edit the sales and operations versions later to restrict their
schema exposure.
"""

from app.services.db_knowledge_executive import get_system_prompt as _executive_prompt
from app.services.db_knowledge_sales import get_system_prompt as _sales_prompt
from app.services.db_knowledge_operations import get_system_prompt as _operations_prompt

_PROMPT_MAP = {
    "executive": _executive_prompt,
    "sales": _sales_prompt,
    "operations": _operations_prompt,
}


def get_system_prompt_for_role(role: str) -> str:
    """Return the system prompt appropriate for the given user role."""
    getter = _PROMPT_MAP.get(role, _executive_prompt)
    return getter()
