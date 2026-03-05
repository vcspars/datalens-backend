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

Output ONLY valid JSON with exactly these keys (no markdown, no code fence):
{
  "resolved_question": "<the self-contained question string>",
  "intent": "sql" or "simple",
  "is_followup": true or false
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


def resolve_question(question: str, chat_history: list[dict]) -> dict[str, Any]:
    """
    Resolve the user's question using conversation history and classify intent.

    Args:
        question: The current user message.
        chat_history: List of {"role": "user"|"assistant", "content": str, optional "sql_query": str}.

    Returns:
        {
            "resolved_question": str,  # self-contained question to send to agent
            "intent": "sql" | "simple",
            "is_followup": bool
        }
    """
    print(f"[QuestionResolver] resolve_question called | question_len={len(question)} | history_len={len(chat_history)}")
    question_stripped = (question or "").strip()
    if not question_stripped:
        print("[QuestionResolver] Empty question -> simple, resolved as-is")
        return {"resolved_question": question_stripped, "intent": "simple", "is_followup": False}

    context_block = _build_context_block(chat_history)
    user_prompt = f"""Recent conversation:
{context_block}

Current user message: {question_stripped}

Output the JSON object only (resolved_question, intent, is_followup):"""

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

        if not resolved:
            resolved = question_stripped

        print(f"[QuestionResolver] resolved_question={resolved[:80]!r} | intent={intent!r} | is_followup={is_followup}")
        return {"resolved_question": resolved, "intent": intent, "is_followup": is_followup}
    except json.JSONDecodeError as e:
        print(f"[QuestionResolver] JSON parse error: {e}, defaulting to original question and intent from keywords")
        question_lower = question_stripped.lower()
        intent = "sql" if any(
            w in question_lower for w in (
                "how many", "what are", "which", "list", "show", "total", "count", "sum",
                "sales", "customer", "order", "product", "table", "tables", "database"
            )
        ) else "simple"
        return {"resolved_question": question_stripped, "intent": intent, "is_followup": False}
    except Exception as e:
        print(f"[QuestionResolver] Error: {e}, defaulting to original question, intent=sql")
        return {"resolved_question": question_stripped, "intent": "sql", "is_followup": False}
