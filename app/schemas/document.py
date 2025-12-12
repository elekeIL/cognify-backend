"""Document schemas for API validation."""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.document import DocumentStatus, FileType, ProcessingStep, StepStatus
from app.schemas.theme import ThemeResponse
from app.schemas.lesson import LessonResponse
from app.schemas.citation import CitationResponse


class DocumentCreate(BaseModel):
    """Schema for creating a document (file upload metadata)."""
    title: Optional[str] = Field(None, max_length=255)


class DocumentBase(BaseModel):
    """Base document schema with common fields."""
    id: str
    ingestion_id: str
    title: str
    file_name: str
    file_type: FileType
    file_size: int
    status: DocumentStatus
    word_count: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    processed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentResponse(DocumentBase):
    """Schema for document response (list view)."""
    themes_count: int = 0
    themes: List[ThemeResponse] = []
    has_lesson: bool = False


class DocumentListResponse(BaseModel):
    """Schema for paginated document list response."""
    items: List[DocumentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class DocumentDetailResponse(DocumentBase):
    """Schema for detailed document response with relationships."""
    themes: List[ThemeResponse] = []
    lesson: Optional[LessonResponse] = None
    citations: List[CitationResponse] = []
    error_message: Optional[str] = None


class DocumentStatusResponse(BaseModel):
    """Schema for document processing status."""
    id: str
    ingestion_id: str
    status: DocumentStatus
    progress: int = Field(ge=0, le=100)
    current_step: str
    error_message: Optional[str] = None


class ProcessingProgress(BaseModel):
    """Schema for real-time processing progress updates."""
    ingestion_id: str
    status: DocumentStatus
    progress: int
    current_step: str
    steps_completed: List[str]
    estimated_time_remaining: Optional[int] = None  # in seconds


# ===== Step-Level Processing Schemas =====

class StepInfo(BaseModel):
    """Information about a single processing step."""
    step: ProcessingStep
    status: StepStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0


class ProcessingStatusResponse(BaseModel):
    """Detailed processing status with step-level information."""
    id: str
    ingestion_id: str
    status: DocumentStatus
    current_step: Optional[ProcessingStep] = None
    failed_step: Optional[ProcessingStep] = None
    step_statuses: Dict[str, StepStatus] = {}
    error_message: Optional[str] = None
    progress_percentage: int = Field(ge=0, le=100)
    can_retry: bool = False
    retry_count: int = 0


class StepRequest(BaseModel):
    """Request to execute a specific processing step."""
    idempotency_key: Optional[str] = Field(
        None,
        description="Unique key to prevent duplicate processing",
        max_length=64
    )


class StepResponse(BaseModel):
    """Response from executing a processing step."""
    document_id: str
    step: ProcessingStep
    status: StepStatus
    message: str
    next_step: Optional[ProcessingStep] = None
    error_message: Optional[str] = None
    can_retry: bool = False
    retry_count: int = 0


class RetryStepRequest(BaseModel):
    """Request to retry a failed step."""
    step: ProcessingStep
    idempotency_key: Optional[str] = Field(
        None,
        description="Unique key to prevent duplicate processing",
        max_length=64
    )


class RetryStepResponse(BaseModel):
    """Response from retrying a failed step."""
    document_id: str
    step: ProcessingStep
    status: StepStatus
    message: str
    retry_count: int
    error_message: Optional[str] = None
