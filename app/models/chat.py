"""Chat session and message models for MongoDB"""
from datetime import datetime
from typing import Optional, Any
from bson import ObjectId


class ChatSession:
    """
    One session per user — auto-created on login/signup.

    Persisted fields beyond identity:
    - db_summary:   AI-generated markdown overview of the database (str)
    - db_questions: AI-generated suggested questions list (list[str])
    - db_report:    AI-generated database analysis report (str)
    - bookmarks:    list of bookmarked questions
    - graphs:       list of Graphs tab instances [{id, table_data, table_columns, graph_type, xKey, yKey, source_label}]
    """

    def __init__(
        self,
        user_id: str,
        db_summary: str = "",
        db_questions: Optional[list] = None,
        db_report: str = "",
        bookmarks: Optional[list] = None,
        graphs: Optional[list] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        _id: Optional[ObjectId] = None,
    ):
        self._id = _id or ObjectId()
        self.user_id = user_id
        self.db_summary = db_summary
        self.db_questions: list[str] = db_questions or []
        self.db_report = db_report
        # Each bookmark: {"id": str, "question": str, "created_at": datetime}
        self.bookmarks: list[dict] = bookmarks or []
        # Graphs tab instances: [{id, table_data, table_columns, graph_type, xKey, yKey, source_label}]
        self.graphs: list = graphs or []
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "_id": self._id,
            "user_id": self.user_id,
            "db_summary": self.db_summary,
            "db_questions": self.db_questions,
            "db_report": self.db_report,
            "bookmarks": self.bookmarks,
            "graphs": self.graphs,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChatSession":
        return cls(
            _id=data.get("_id"),
            user_id=data["user_id"],
            db_summary=data.get("db_summary", ""),
            db_questions=data.get("db_questions", []),
            db_report=data.get("db_report", ""),
            bookmarks=data.get("bookmarks", []),
            graphs=data.get("graphs", []),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


class ChatMessage:
    """Individual Q/A message stored in MongoDB"""

    def __init__(
        self,
        session_id: str,
        user_id: str,
        role: str,  # 'user' | 'assistant'
        content: str,
        has_table: bool = False,
        table_data: Optional[list] = None,
        table_columns: Optional[list] = None,
        tables: Optional[list] = None,
        created_at: Optional[datetime] = None,
        _id: Optional[ObjectId] = None,
    ):
        self._id = _id or ObjectId()
        self.session_id = session_id
        self.user_id = user_id
        self.role = role
        self.content = content
        self.has_table = has_table
        self.table_data = table_data or []
        self.table_columns = table_columns or []
        # All tables found in the response [{columns, data}, ...]
        self.tables: list = tables or []
        self.created_at = created_at or datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "_id": self._id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "role": self.role,
            "content": self.content,
            "has_table": self.has_table,
            "table_data": self.table_data,
            "table_columns": self.table_columns,
            "tables": self.tables,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChatMessage":
        return cls(
            _id=data.get("_id"),
            session_id=data["session_id"],
            user_id=data["user_id"],
            role=data["role"],
            content=data["content"],
            has_table=data.get("has_table", False),
            table_data=data.get("table_data", []),
            table_columns=data.get("table_columns", []),
            tables=data.get("tables", []),
            created_at=data.get("created_at"),
        )
