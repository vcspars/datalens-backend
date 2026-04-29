"""User model for MongoDB"""
from datetime import datetime
from typing import Optional
from bson import ObjectId


VALID_ROLES = ("executive", "sales", "operations")


class User:
    """User model"""
    
    def __init__(
        self,
        email: str,
        password_hash: str,
        full_name: str,
        role: str = "executive",
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        _id: Optional[ObjectId] = None
    ):
        self._id = _id or ObjectId()
        self.email = email
        self.password_hash = password_hash
        self.full_name = full_name
        self.role = role if role in VALID_ROLES else "executive"
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()
    
    def to_dict(self) -> dict:
        """Convert user to dictionary"""
        return {
            "_id": self._id,
            "email": self.email,
            "password_hash": self.password_hash,
            "full_name": self.full_name,
            "role": self.role,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "User":
        """Create user from dictionary"""
        return cls(
            _id=data.get("_id"),
            email=data["email"],
            password_hash=data["password_hash"],
            full_name=data["full_name"],
            role=data.get("role", "executive"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at")
        )

