"""
SQL Server connection for the MCP server.
Reads credentials from the backend .env file (one level up).
Exposes a single execute_query() helper used by all MCP tools.
"""

import os
import logging
from pathlib import Path
from typing import Any

import pyodbc
from dotenv import load_dotenv

# Load from backend/.env (parent of this mcp/ folder)
_env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)

logger = logging.getLogger(__name__)

# ── Connection settings ────────────────────────────────────────────────────────
_SERVER   = os.getenv("SQL_SERVER", "")
_DATABASE = os.getenv("SQL_DATABASE", "")
_USER     = os.getenv("SQL_USER", "")
_PASSWORD = os.getenv("SQL_PASSWORD", "")
_DRIVER   = os.getenv("SQL_DRIVER", "ODBC Driver 17 for SQL Server")

_CONNECTION_STRING = (
    f"DRIVER={{{_DRIVER}}};"
    f"SERVER={_SERVER};"
    f"DATABASE={_DATABASE};"
    f"UID={_USER};"
    f"PWD={_PASSWORD};"
    "TrustServerCertificate=yes;"
)


def _get_connection() -> pyodbc.Connection:
    """Open and return a new pyodbc connection."""
    return pyodbc.connect(_CONNECTION_STRING, timeout=30)


def execute_query(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    """
    Execute a parameterised SQL query and return rows as a list of dicts.

    Args:
        sql:    Parameterised T-SQL string (use ? placeholders).
        params: Tuple of parameter values matching the ? placeholders.

    Returns:
        List of dicts keyed by column name.
    """
    conn = None
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        columns = [col[0] for col in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        logger.debug(f"execute_query returned {len(rows)} row(s)")
        return rows
    except pyodbc.Error as exc:
        logger.error(f"Database error: {exc}")
        raise
    finally:
        if conn:
            conn.close()
