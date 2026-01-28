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
    summary: Optional[str] = None
    questions: Optional[list[str]] = None
    report: Optional[str] = None
    summary_generated: bool = False
    questions_generated: bool = False
    report_generated: bool = False
    uploaded_at: datetime
    size: str  # Human-readable size
    
    class Config:
        from_attributes = True


class DatasetListResponse(BaseModel):
    """Dataset list response schema"""
    datasets: list[DatasetResponse]
    total: int


class ColumnCalculationRequest(BaseModel):
    """Column calculation request schema"""
    column_name: str
    operation: str


class SaveChangesRequest(BaseModel):
    """Save changes request schema"""
    columns: list[str]  # List of column names in order
    data: list[dict]  # List of row data as dictionaries

