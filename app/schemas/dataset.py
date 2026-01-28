"""Dataset schemas"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class DatasetCreate(BaseModel):
    """Dataset creation schema"""
    name: str
    description: Optional[str] = None


class DatasetResponse(BaseModel):
    """Dataset response schema"""
    id: str
    name: str
    dataset_type: str
    file_name: str
    file_size: int
    description: Optional[str] = None
    uploaded_at: datetime
    size: str  # Human-readable size
    
    class Config:
        from_attributes = True


class DatasetListResponse(BaseModel):
    """Dataset list response schema"""
    datasets: list[DatasetResponse]
    total: int

