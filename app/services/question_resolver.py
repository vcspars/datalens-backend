"""
Question Resolver for chat-with-database: resolves follow-up questions into
self-contained questions and classifies intent (sql vs simple) in a single LLM call.
"""

import json
from typing import Any

from app.config import settings
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

print("[QuestionResolver] Module loaded")

_RESOLVER_LLM = None


def _get_resolver_llm() -> ChatOpenAI:
    global _RESOLVER_LLM
    if _RESOLVER_LLM is None:
        _RESOLVER_LLM = ChatOpenAI(
            model="gpt-4.1-mini",
            temperature=0,
            max_tokens=500,
            openai_api_key=settings.OPENAI_API_KEY,
        )
    return _RESOLVER_LLM


# ---------------------------------------------------------------------------
# Role-based access scope — defines what each role is allowed to ask about
# ---------------------------------------------------------------------------

_ROLE_SCOPE: dict[str, str] = {
    "executive": "",  # no restriction
    "sales": (
        "ALLOWED topics for this user: sales figures, customer analytics, inventory levels, pricing, and backorder status. "
        "RESTRICTED topics: profitability, profit margins, unit costs, vendor analytics, vendor payments, vendor returns, and any cost/financial data. "
        "If the resolved question touches a restricted topic, set access_denied=true and write denial_reason as a short, "
        "natural, first-person assistant message. Do NOT mention 'role', 'not allowed', or any table names. "
        "Example tone: 'I can help with sales, customers, inventory and pricing — I'm not set up to look up profitability or margin data, though.'"
    ),
    "operations": (
        "ALLOWED topics for this user: inventory monitoring (stock levels, warehouse quantities) and backorder information. "
        "RESTRICTED topics: sales data, customer data, revenue, pricing, profitability, margins, vendor data, purchase orders, payments, and credit memos. "
        "If the resolved question touches a restricted topic, set access_denied=true and write denial_reason as a short, "
        "natural, first-person assistant message. Do NOT mention 'role', 'not allowed', or any table names. "
        "Example tone: 'I can only help with inventory and backorder questions — I'm not able to pull up sales or financial data from here.'"
    ),
}

SYSTEM_PROMPT = """You are a question resolver for a chat-with-database app. The database contains business data: sales, customers, products, vendors, purchases, inventory, tables/schema.

Your task:
1. Look at the recent conversation (User and Assistant messages, and any SQL that was run).
2. Determine if the CURRENT user message is a follow-up (e.g. "yes", "no", "show me all", "continue", "break it down by month", "only last year", "explain that") that only makes sense in context of the previous exchange.
3. If it IS a follow-up: produce a single self-contained question that captures what the user really wants. Preserve the original intent; do not change the meaning.
   - CRITICAL: If the assistant had offered to show "the full list", "all of them", "the rest", or "more" and the user said "yes", "yeah", "sure", "show all", or "show me all", the resolved question MUST ask for the COMPLETE list (e.g. "List all table names in the database"), NOT "How many tables" or a repeat of the count/summary question. The user is accepting the offer to see everything.
4. If it is NOT a follow-up (standalone question): use the user's message as-is with minimal changes (fix typos only if obvious; preserve their wording).
5. Classify intent:
   - sql: The (resolved) question requires querying the business database to answer (counts, lists, totals, reports, schema info, "how many tables", "list all X", etc.).
   - simple: Greetings, thanks, goodbyes, "explain that", "what do you mean", questions about the chat itself, or anything that does NOT need fresh data from the database.
6. If a ROLE RESTRICTION block is provided below, check whether the resolved question falls outside the user's allowed scope. If it does, set "access_denied" to true and write "denial_reason" as a short, warm, first-person assistant message. Never mention the word "role", never say "not allowed", and never reference internal table names. Write it as if naturally explaining what you can help with instead.

Output ONLY valid JSON with exactly these keys (no markdown, no code fence):
{
  "resolved_question": "<the self-contained question string>",
  "intent": "sql" or "simple",
  "is_followup": true or false,
  "access_denied": true or false,
  "denial_reason": "<reason string or empty>"
}"""


def _build_context_block(chat_history: list[dict], max_assistant_chars: int = 1200) -> str:
    """Build conversation context for the resolver, including SQL when available."""
    if not chat_history:
        return "(no prior messages)"
    parts = []
    for i, msg in enumerate(chat_history, 1):
        role = "User" if msg.get("role") == "user" else "Assistant"
        content = (msg.get("content") or "").strip()
        if msg.get("role") == "assistant" and len(content) > max_assistant_chars:
            content = content[:max_assistant_chars] + "... [truncated]"
        parts.append(f"{role}: {content}")
        sql_query = msg.get("sql_query") or ""
        if sql_query and msg.get("role") == "assistant":
            parts.append(f"(SQL that was run: {sql_query[:300]}{'...' if len(sql_query) > 300 else ''})")
    return "\n".join(parts)


def resolve_question(question: str, chat_history: list[dict], role: str = "executive") -> dict[str, Any]:
    """
    Resolve the user's question using conversation history and classify intent.

    Args:
        question: The current user message.
        chat_history: List of {"role": "user"|"assistant", "content": str, optional "sql_query": str}.
        role: User role – "executive", "sales", or "operations".

    Returns:
        {
            "resolved_question": str,  # self-contained question to send to agent
            "intent": "sql" | "simple",
            "is_followup": bool,
            "access_denied": bool,
            "denial_reason": str
        }
    """
    print(f"[QuestionResolver] resolve_question called | question_len={len(question)} | history_len={len(chat_history)} | role={role}")
    question_stripped = (question or "").strip()
    if not question_stripped:
        print("[QuestionResolver] Empty question -> simple, resolved as-is")
        return {"resolved_question": question_stripped, "intent": "simple", "is_followup": False, "access_denied": False, "denial_reason": ""}

    context_block = _build_context_block(chat_history)

    # Build role restriction addendum
    role_restriction = _ROLE_SCOPE.get(role, "")
    role_block = f"\n\nROLE RESTRICTION:\n{role_restriction}" if role_restriction else ""

    user_prompt = f"""Recent conversation:
{context_block}

Current user message: {question_stripped}{role_block}

Output the JSON object only (resolved_question, intent, is_followup, access_denied, denial_reason):"""

    try:
        llm = _get_resolver_llm()
        messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_prompt)]
        result = llm.invoke(messages)
        raw = (result.content or "").strip()

        # Strip markdown code block if present
        if raw.startswith("```"):
            lines = raw.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            raw = "\n".join(lines)

        data = json.loads(raw)
        resolved = (data.get("resolved_question") or question_stripped).strip()
        intent = (data.get("intent") or "simple").lower()
        if intent not in ("sql", "simple"):
            intent = "simple"
        is_followup = bool(data.get("is_followup", False))
        access_denied = bool(data.get("access_denied", False))
        denial_reason = (data.get("denial_reason") or "").strip()

        if not resolved:
            resolved = question_stripped

        print(f"[QuestionResolver] resolved_question={resolved[:80]!r} | intent={intent!r} | is_followup={is_followup} | access_denied={access_denied}")
        return {"resolved_question": resolved, "intent": intent, "is_followup": is_followup, "access_denied": access_denied, "denial_reason": denial_reason}
    except json.JSONDecodeError as e:
        print(f"[QuestionResolver] JSON parse error: {e}, defaulting to original question and intent from keywords")
        question_lower = question_stripped.lower()
        intent = "sql" if any(
            w in question_lower for w in (
                "how many", "what are", "which", "list", "show", "total", "count", "sum",
                "sales", "customer", "order", "product", "table", "tables", "database"
            )
        ) else "simple"
        return {"resolved_question": question_stripped, "intent": intent, "is_followup": False, "access_denied": False, "denial_reason": ""}
    except Exception as e:
        print(f"[QuestionResolver] Error: {e}, defaulting to original question, intent=sql")
        return {"resolved_question": question_stripped, "intent": "sql", "is_followup": False, "access_denied": False, "denial_reason": ""}
