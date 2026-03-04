"""
Intent classifier for chat-with-database: routes user questions to SQL agent or simple LLM.
Returns "sql" when the question requires running a database query; "simple" otherwise.
"""

from app.config import settings
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

print("[IntentClassifier] Module loaded")

# Fast, cheap model for classification only
_CLASSIFIER_LLM = None


def _get_classifier_llm():
    global _CLASSIFIER_LLM
    if _CLASSIFIER_LLM is None:
        _CLASSIFIER_LLM = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            max_tokens=10,
            openai_api_key=settings.OPENAI_API_KEY,
        )
    return _CLASSIFIER_LLM


SYSTEM_PROMPT = """You classify the user's message into exactly one word: sql or simple.

This is a chat-with-database app. The database contains business data: sales, customers, products, vendors, purchases, inventory. Classify based on whether we need to run a SQL query against that business database.

- sql: The question requires querying the BUSINESS DATABASE to answer (e.g. sales totals, customer lists, product counts, revenue reports, inventory levels, purchase orders, "show me sales", "how many customers", "top 10 products", "sales by month").
- simple: Everything else — greetings ("hi", "hello"), thanks ("thank you", "thanks"), goodbyes, follow-ups about a previous answer ("explain that", "what do you mean", "can you clarify", "summarize the above"), questions about the chat itself ("what did I ask", "my last questions", "repeat that"), general knowledge questions, or any message that does NOT need fresh data from the business database.

Examples:
- "What are the total sales this month?" -> sql
- "Show me top 10 customers by revenue" -> sql  
- "How many products do we have?" -> sql
- "Hi" -> simple
- "Thanks!" -> simple
- "What was my last question?" -> simple
- "Explain that in simpler terms" -> simple
- "What tables are in the database?" -> sql
- "Can you clarify the numbers above?" -> simple
- "No" -> simple
- "Yes, show me the breakdown" -> sql

Reply with only the single word: sql or simple. No other text."""


def classify_intent(question: str, chat_history: list[dict]) -> str:
    """
    Classify whether the user question needs the SQL agent (sql) or a simple LLM response (simple).
    Uses last 2 history pairs for context. Returns "sql" or "simple".
    """
    print(f"[IntentClassifier] classify_intent called | question_len={len(question)} | history_len={len(chat_history)}")
    question_stripped = (question or "").strip()
    if not question_stripped:
        print("[IntentClassifier] Empty question -> simple")
        return "simple"
    question_lower = question_stripped.lower()

    # Build minimal context from last 2 pairs
    context_parts = []
    recent = chat_history[-4:] if len(chat_history) > 4 else chat_history  # last 2 pairs
    for msg in recent:
        role = "User" if msg.get("role") == "user" else "Assistant"
        content = (msg.get("content") or "")[:200]
        context_parts.append(f"{role}: {content}")
    context_block = "\n".join(context_parts) if context_parts else "(no prior messages)"

    user_prompt = f"Recent conversation:\n{context_block}\n\nCurrent user message: {question_stripped}\n\nClassification (sql or simple):"

    try:
        llm = _get_classifier_llm()
        messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user_prompt)]
        result = llm.invoke(messages)
        raw = (result.content or "").strip().lower()
        if "sql" in raw and "simple" not in raw:
            intent = "sql"
        elif "simple" in raw:
            intent = "simple"
        else:
            # Default: if it looks like a question with data intent, use sql
            intent = "sql" if any(w in question_lower for w in ("how many", "what are", "which", "list", "show", "total", "count", "sum", "sales", "customer", "order", "product")) else "simple"
        print(f"[IntentClassifier] classified intent={intent!r} (raw={raw!r})")
        return intent
    except Exception as e:
        print(f"[IntentClassifier] Classifier error: {e}, defaulting to sql")
        return "sql"
