from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class FileInfo(BaseModel):
    ipfs_hash: Optional[str] = None
    file_type: str
    file_name: str
    size_bytes: Optional[int] = None

class ValidationRequest(BaseModel):
    submission_id: str = Field(..., description="Unique submission identifier")
    researcher_type: str = Field(..., description="Type of researcher: coder, researcher, data_scientist")
    files: List[FileInfo] = Field(..., description="List of files to validate")
    milestone_requirements: Dict[str, Any] = Field(default={}, description="Milestone-specific requirements")

class ValidationIssue(BaseModel):
    severity: str = Field(..., description="Issue severity: error, warning, info")
    message: str = Field(..., description="Human-readable issue description")
    file: str = Field(..., description="File where issue was found")
    line: Optional[int] = Field(None, description="Line number if applicable")
    rule: Optional[str] = Field(None, description="Validation rule that triggered")

class ValidationResponse(BaseModel):
    validation_id: str = Field(..., description="Unique validation result identifier")
    overall_confidence: int = Field(..., ge=0, le=100, description="Overall confidence score (0-100)")
    security_passed: bool = Field(..., description="Whether security checks passed")
    detailed_scores: Dict[str, float] = Field(..., description="Breakdown of scores by category")
    issues_found: List[ValidationIssue] = Field(..., description="List of issues found during validation")
    recommendation: str = Field(..., description="approve, human_review, or reject")
    processing_time_ms: float = Field(..., description="Time taken to process validation")
    files_processed: int = Field(..., description="Number of files processed")