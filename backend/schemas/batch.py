"""
Pydantic schemas for batch operations
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from models.batch import ReviewerMode, BatchStatus

class BatchCreate(BaseModel):
    mode: ReviewerMode = Field(..., description="UGC or AICTE mode")
    new_university: Optional[bool] = Field(False, description="True if new university (UGC only), False for renewal")
    # Department-wise hierarchy (MANDATORY for platform)
    institution_name: Optional[str] = Field(None, description="Institution name (will be extracted from documents if not provided)")
    department_name: Optional[str] = Field(None, description="Department name (e.g., 'Computer Science', 'Mechanical Engineering')")
    academic_year: Optional[str] = Field(None, description="Academic year (e.g., '2024-25', '2025-26')")
    institution_code: Optional[str] = None  # Legacy field

class BatchResponse(BaseModel):
    batch_id: str
    mode: str  # Changed from ReviewerMode to str for compatibility
    status: str  # Changed from BatchStatus to str for compatibility
    created_at: str
    updated_at: str
    total_documents: int
    processed_documents: int
    institution_name: Optional[str] = None
    data_source: Optional[str] = "user"  # "user" = uploaded, "system" = pre-seeded
    
    class Config:
        from_attributes = True

class BatchListResponse(BaseModel):
    batches: List[BatchResponse]
    total: int

