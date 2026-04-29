"""
Read-only SQL enforcement for Chat with Database.
The application MUST never execute DDL (CREATE/ALTER/DROP) or DML (INSERT/UPDATE/DELETE)
against the database — only SELECT (and WITH ... SELECT) is allowed.
"""

import re


# Forbidden SQL keywords (whole-word, case-insensitive). Any occurrence => not read-only.
_FORBIDDEN_KEYWORDS = [
    "CREATE", "ALTER", "DROP", "INSERT", "UPDATE", "DELETE", "TRUNCATE",
    "EXEC", "EXECUTE", "MERGE", "GRANT", "REVOKE", "BACKUP", "RESTORE",
    "BULK", "WRITETEXT", "UPDATETEXT", "READTEXT",
    "SHUTDOWN", "DBCC", "KILL", "RECONFIGURE", "DENY",
    "ENABLE", "DISABLE",
]
_FORBIDDEN_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _FORBIDDEN_KEYWORDS) + r")\b",
    re.IGNORECASE,
)

# Matches single-quoted string literals (handles escaped '' inside)
_STRING_LITERAL_PATTERN = re.compile(r"'(?:[^']|'')*'")


def _strip_string_literals(sql: str) -> str:
    """Replace all single-quoted string literals with a placeholder so their
    contents are never scanned for forbidden keywords.
    e.g. 'AMAZON (DROP SHIP)' → '' so 'DROP' inside a value never matches.
    """
    return _STRING_LITERAL_PATTERN.sub("''", sql)


def is_read_only_sql(sql: str) -> bool:
    """
    Return True only if the SQL appears to be read-only (SELECT/WITH or DECLARE+SELECT).
    Rejects any DDL/DML so the app never modifies the database.

    IMPORTANT: string literal contents are stripped before checking forbidden keywords
    so that values like 'AMAZON (DROP SHIP)' or 'DELETE ME' inside a WHERE IN (...)
    do not cause a valid SELECT to be rejected.
    """
    if not sql or not sql.strip():
        return False
    s = sql.strip()
    # Remove single-line comments (-- ...) and block comments (/* ... */)
    s = re.sub(r"--[^\n]*", "", s)
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.DOTALL)
    # Strip string literal contents BEFORE keyword scanning so values like
    # 'AMAZON (DROP SHIP)' don't trigger the DROP forbidden-keyword check.
    s = _strip_string_literals(s)
    s = " ".join(s.split()).upper()
    # Forbidden keywords anywhere in the structural SQL => not read-only
    if _FORBIDDEN_PATTERN.search(s):
        return False
    # Allow batches that start with DECLARE (used by _ensure_mssql_batch); rest must be SELECT
    while s.startswith("DECLARE"):
        # Strip one DECLARE ... ; block
        rest = re.sub(r"^DECLARE\s+[^;]+;\s*", "", s, count=1, flags=re.IGNORECASE)
        if rest == s:
            break
        s = rest.strip()
    # Main statement must start with SELECT, WITH, or ( (subquery)
    if s.startswith("SELECT") or s.startswith("WITH") or s.startswith("("):
        return True
    if "SELECT" in s and "FROM" in s:
        return True
    return False
