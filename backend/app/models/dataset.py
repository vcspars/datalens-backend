"""Dataset model for MongoDB"""
from datetime import datetime
from typing import Optional
from bson import ObjectId


class Dataset:
    """Dataset model"""
    
    def __init__(
        self,
        user_id: str,
        name: str,
        dataset_type: str,  # 'pdf', 'csv', 'database'
        google_drive_file_id: str,
        file_name: str,
        file_size: int,
        description: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        _id: Optional[ObjectId] = None
    ):
        self._id = _id or ObjectId()
        self.user_id = user_id
        self.name = name
        self.dataset_type = dataset_type
        self.google_drive_file_id = google_drive_file_id
        self.file_name = file_name
        self.file_size = file_size
        self.description = description
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()
    
    def to_dict(self) -> dict:
        """Convert dataset to dictionary"""
        return {
            "_id": self._id,
            "user_id": self.user_id,
            "name": self.name,
            "dataset_type": self.dataset_type,
            "google_drive_file_id": self.google_drive_file_id,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "description": self.description,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Dataset":
        """Create dataset from dictionary"""
        return cls(
            _id=data.get("_id"),
            user_id=data["user_id"],
            name=data["name"],
            dataset_type=data["dataset_type"],
            google_drive_file_id=data["google_drive_file_id"],
            file_name=data["file_name"],
            file_size=data["file_size"],
            description=data.get("description"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at")
        )

