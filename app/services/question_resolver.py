"""
Question Resolver for chat-with-database: resolves follow-up questions into
self-contained questions and classifies intent (sql vs simple) in a single LLM call.
"""

import json
import time
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
            model="gpt-4.1",
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
5. Classify intent — read ALL rules carefully before deciding:

   ALWAYS classify as "simple" (NO database query needed):
   - Greetings, thanks, goodbyes, small talk (e.g. "hi", "thanks", "bye", "great").
   - Requests to explain, clarify, or interpret something already shown (e.g. "explain that", "what does this mean", "what do you mean", "can you clarify").
   - Advisory / strategic questions about how data can be used, even if they mention data or business topics. Examples:
       • "how can this data help me take business decisions"
       • "what decisions can I make from this"
       • "how should I act on this"
       • "what does this tell me about my business"
       • "what insights can I draw from this"
       • "how can I use this information"
       • "what action should I take based on this"
       • "is this good or bad for my business"
       • "what does this result mean"
   - Questions about what the assistant can do, its capabilities, or the chat itself.
   - Questions about the conversation history itself (e.g. "what were my last N questions", "what did I ask before", "show my previous questions", "what have we discussed", "recap our conversation"). The chat history is available in the conversation context — no database query is needed.
   - Any follow-up that asks for interpretation, recommendation, or opinion on data already presented — no new database fetch is needed.
   - CRITICAL — Re-analysis of already-returned data: If the previous assistant message already contains a table or results,
     AND the user is asking to reorganize, re-group, re-arrange, categorize, label, summarize, or analyze THAT data,
     classify as "simple". The LLM can re-analyze the data already in the conversation — no new DB query is needed.
     Examples of this pattern:
       • "group this data logically"
       • "arrange these results by category"
       • "categorize these reasons"
       • "can you label these into groups"
       • "summarize this into themes"
       • "organize these items"
       • "cluster these by type"
       • "now sort this differently" (when referring to data already shown)
     KEY TEST: Ask yourself — does answering this require fetching NEW data from the database?
     If the data is already in the previous response and the user just wants a different view of it → "simple".

   ALWAYS classify as "sql" (database query IS needed):
   - Requests for counts, totals, lists, reports, summaries that require fetching fresh data (e.g. "how many", "what are the top", "show me sales for", "list all customers", "give me a summary of").
   - Schema / structure questions (e.g. "what tables exist", "what columns does X have").
   - Comparisons or trends that require new data (e.g. "compare last year vs this year", "show monthly breakdown").
   - Requests for a DIFFERENT time period, different filter, or different dimension not present in the previous result.

   DECISION RULE: If the question is asking the assistant to THINK, ADVISE, or RE-ANALYZE data already shown (not fetch new data), it is "simple". If it is asking the assistant to FETCH or COUNT or LIST fresh data from the database, it is "sql".

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
    t_start = time.time()
    print(f"[QuestionResolver] -- resolve_question START --------------------------")
    print(f"[QuestionResolver] question       : {question!r}")
    print(f"[QuestionResolver] question_len   : {len(question)}")
    print(f"[QuestionResolver] history_len    : {len(chat_history)}")
    print(f"[QuestionResolver] role           : {role!r}")

    question_stripped = (question or "").strip()
    if not question_stripped:
        print("[QuestionResolver] Empty question -> returning simple intent immediately")
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
        print(f"[QuestionResolver] Calling LLM (model=gpt-4.1-mini) ...")
        result = llm.invoke(messages)
        raw = (result.content or "").strip()
        elapsed = time.time() - t_start
        print(f"[QuestionResolver] LLM response received | {elapsed:.2f}s | raw_len={len(raw)}")
        print(f"[QuestionResolver] LLM raw output: {raw}")

        # Strip markdown code block if present
        if raw.startswith("```"):
            lines = raw.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            raw = "\n".join(lines)
            print(f"[QuestionResolver] Stripped markdown fences from LLM output")

        data = json.loads(raw)
        resolved = (data.get("resolved_question") or question_stripped).strip()
        intent = (data.get("intent") or "simple").lower()
        if intent not in ("sql", "simple"):
            print(f"[QuestionResolver] WARNING: unexpected intent value {intent!r} -> defaulting to 'simple'")
            intent = "simple"
        is_followup = bool(data.get("is_followup", False))
        access_denied = bool(data.get("access_denied", False))
        denial_reason = (data.get("denial_reason") or "").strip()

        if not resolved:
            resolved = question_stripped

        print(f"[QuestionResolver] -- RESULT --------------------------------------------")
        print(f"[QuestionResolver] resolved_question : {resolved!r}")
        print(f"[QuestionResolver] intent            : {intent!r}")
        print(f"[QuestionResolver] is_followup       : {is_followup}")
        print(f"[QuestionResolver] access_denied     : {access_denied}")
        if denial_reason:
            print(f"[QuestionResolver] denial_reason     : {denial_reason!r}")
        print(f"[QuestionResolver] total_elapsed     : {elapsed:.2f}s")
        print(f"[QuestionResolver] -------------------------------------------------")

        return {"resolved_question": resolved, "intent": intent, "is_followup": is_followup, "access_denied": access_denied, "denial_reason": denial_reason}

    except json.JSONDecodeError as e:
        elapsed = time.time() - t_start
        print(f"[QuestionResolver] ERROR: JSON parse failed after {elapsed:.2f}s | error={e}")
        print(f"[QuestionResolver] Falling back to keyword-based intent detection")
        question_lower = question_stripped.lower()
        # Advisory patterns should always fall back to simple, not sql
        advisory_keywords = (
            "how can", "how should", "what can i do", "what action", "help me decide",
            "help me take", "business decision", "what does this mean", "what does this tell",
            "insights", "advise", "recommend", "suggestion", "what should i",
            # chat-history questions — never need a DB query
            "last question", "previous question", "what did i ask", "what have we discussed",
            "what were my", "recap", "our conversation",
            # re-analysis of already-returned data — never need a new DB query
            "group this", "group these", "arrange this", "arrange these",
            "categorize this", "categorize these", "organize this", "organize these",
            "cluster this", "cluster these", "label this", "label these",
            "summarize this", "summarize these", "sort this differently",
        )
        data_keywords = (
            "how many", "what are", "which", "list", "show", "total", "count", "sum",
            "sales", "customer", "order", "product", "table", "tables", "database",
        )
        if any(w in question_lower for w in advisory_keywords):
            intent = "simple"
            print(f"[QuestionResolver] Fallback: matched advisory keyword -> intent=simple")
        elif any(w in question_lower for w in data_keywords):
            intent = "sql"
            print(f"[QuestionResolver] Fallback: matched data keyword -> intent=sql")
        else:
            intent = "simple"
            print(f"[QuestionResolver] Fallback: no keyword matched -> defaulting to intent=simple")
        return {"resolved_question": question_stripped, "intent": intent, "is_followup": False, "access_denied": False, "denial_reason": ""}

    except Exception as e:
        elapsed = time.time() - t_start
        print(f"[QuestionResolver] ERROR: unexpected exception after {elapsed:.2f}s | {type(e).__name__}: {e}")
        print(f"[QuestionResolver] Defaulting to original question with intent=sql")
        return {"resolved_question": question_stripped, "intent": "sql", "is_followup": False, "access_denied": False, "denial_reason": ""}
