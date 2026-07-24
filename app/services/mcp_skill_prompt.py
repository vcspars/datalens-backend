"""
MCP Orchestrator Skill — system prompt builder for the unified ReAct agent.

Static rules are loaded from app/skills/orchestrator_skill.md via skill_loader
so they can be edited without touching Python code.  The dynamic parts (live
tool catalog, role-scope restriction) are spliced in at request time.
"""

from app.services.skill_loader import load_skill


def build_orchestrator_system_prompt(tool_catalog_text: str, role_scope_text: str = "") -> str:
    """Compose the full system prompt for the unified orchestrator agent.

    Components (in order):
      1. Static behavioural rules from orchestrator_skill.md
      2. Live tool catalog (MCP tool names/descriptions + query_sql_database)
      3. Optional role-based access restriction
    """
    parts = [load_skill("orchestrator_skill")]
    if tool_catalog_text:
        parts.append("\n\n## AVAILABLE MCP TOOLS (live catalog — call only these by their exact name):\n")
        parts.append(tool_catalog_text)
    if role_scope_text:
        parts.append("\n\n## ROLE RESTRICTION — do not use tools to fetch data outside this scope:\n")
        parts.append(role_scope_text)
    return "".join(parts)
