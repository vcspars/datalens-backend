"""Dashboard item and report models for MongoDB"""
from datetime import datetime
from typing import Optional, Any
from bson import ObjectId


class DashboardItem:
    """Saved table, graph, or report on a user's dashboard"""

    def __init__(
        self,
        user_id: str,
        item_type: str,          # 'table' | 'graph' | 'report'
        name: str,
        # table fields
        table_data: Optional[list] = None,
        table_columns: Optional[list] = None,
        # graph fields
        graph_type: Optional[str] = None,   # 'bar' | 'line' | 'pie' | 'area' | 'scatter'
        graph_config: Optional[dict] = None,
        # report fields
        report_content: Optional[str] = None,  # markdown
        report_template: Optional[str] = None,
        # shared metadata
        source_question: Optional[str] = None,
        metadata: Optional[dict] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        _id: Optional[ObjectId] = None,
    ):
        self._id = _id or ObjectId()
        self.user_id = user_id
        self.item_type = item_type
        self.name = name
        self.table_data = table_data or []
        self.table_columns = table_columns or []
        self.graph_type = graph_type
        self.graph_config = graph_config or {}
        self.report_content = report_content or ""
        self.report_template = report_template or ""
        self.source_question = source_question or ""
        self.metadata = metadata or {}
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "_id": self._id,
            "user_id": self.user_id,
            "item_type": self.item_type,
            "name": self.name,
            "table_data": self.table_data,
            "table_columns": self.table_columns,
            "graph_type": self.graph_type,
            "graph_config": self.graph_config,
            "report_content": self.report_content,
            "report_template": self.report_template,
            "source_question": self.source_question,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DashboardItem":
        return cls(
            _id=data.get("_id"),
            user_id=data["user_id"],
            item_type=data["item_type"],
            name=data["name"],
            table_data=data.get("table_data", []),
            table_columns=data.get("table_columns", []),
            graph_type=data.get("graph_type"),
            graph_config=data.get("graph_config", {}),
            report_content=data.get("report_content", ""),
            report_template=data.get("report_template", ""),
            source_question=data.get("source_question", ""),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )
