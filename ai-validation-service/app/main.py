from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import asyncio
import json
import tempfile
import os
import subprocess
import time
from pathlib import Path

from app.services.security_scanner import SecurityScanner
from app.services.code_validator import CodeValidator
from app.services.confidence_scorer import ConfidenceScorer
from app.models.validation_models import ValidationRequest, ValidationResponse
from app.utils.file_handler import FileHandler

app = FastAPI(
    title="Viera Protocol - AI Validation Service",
    description="Local AI validation service for research submissions",
    version="1.0.0"
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
security_scanner = SecurityScanner()
code_validator = CodeValidator()
confidence_scorer = ConfidenceScorer()
file_handler = FileHandler()

@app.get("/")
async def root():
    return {
        "service": "Viera Protocol AI Validation Engine",
        "status": "running",
        "version": "1.0.0",
        "supported_domains": ["code"],
        "supported_languages": ["python", "javascript"],
        "timestamp": int(time.time())
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check if ClamAV is running
        clamav_status = security_scanner.check_antivirus_status()
        
        return {
            "status": "healthy",
            "services": {
                "clamav": clamav_status,
                "api": "running"
            },
            "timestamp": int(time.time())
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

@app.post("/validate", response_model=ValidationResponse)
async def validate_submission(
    submission_id: str = Form(...),
    researcher_type: str = Form(...),
    milestone_description: str = Form(...),
    files: List[UploadFile] = File(...)
):
    """
    Validate a research submission
    """
    validation_start_time = time.time()
    
    try:
        # Input validation
        if researcher_type not in ["coder", "researcher", "data_scientist"]:
            raise HTTPException(status_code=400, detail="Invalid researcher type")
        
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")
        
        # Process files
        processed_files = []
        overall_scores = {"security": 0, "technical_quality": 0, "originality": 0, "completeness": 0}
        all_issues = []
        
        for file in files:
            file_result = await process_single_file(file, researcher_type)
            processed_files.append(file_result)
            
            # Aggregate scores
            for key in overall_scores:
                overall_scores[key] += file_result["scores"][key]
            
            all_issues.extend(file_result["issues"])
        
        # Average scores across files
        num_files = len(processed_files)
        for key in overall_scores:
            overall_scores[key] = round(overall_scores[key] / num_files, 2)
        
        # Calculate overall confidence
        overall_confidence = confidence_scorer.calculate_overall_confidence(overall_scores)
        
        # Determine recommendation
        recommendation = get_recommendation(overall_confidence, all_issues)
        
        processing_time = round((time.time() - validation_start_time) * 1000, 2)
        
        return ValidationResponse(
            validation_id=f"val_{submission_id}_{int(time.time())}",
            overall_confidence=overall_confidence,
            security_passed=overall_scores["security"] >= 70,
            detailed_scores=overall_scores,
            issues_found=all_issues,
            recommendation=recommendation,
            processing_time_ms=processing_time,
            files_processed=num_files
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")

async def process_single_file(file: UploadFile, researcher_type: str) -> Dict[str, Any]:
    """Process a single uploaded file"""
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as temp_file:
        try:
            # Save uploaded file
            content = await file.read()
            temp_file.write(content)
            temp_file.flush()
            
            file_path = temp_file.name
            file_info = {
                "name": file.filename,
                "size": len(content),
                "type": file.content_type or "unknown"
            }
            
            # Security scan
            security_result = await security_scanner.scan_file(file_path, file_info)
            
            # Code validation (if applicable)
            validation_result = {"score": 0, "issues": []}
            if researcher_type == "coder":
                validation_result = await code_validator.validate_code_file(file_path, file_info)
            
            # Calculate scores
            scores = {
                "security": security_result["score"],
                "technical_quality": validation_result["score"],
                "originality": 85,  # Placeholder - would integrate plagiarism check
                "completeness": 80   # Placeholder - would check against milestone requirements
            }
            
            # Combine issues
            issues = security_result["issues"] + validation_result["issues"]
            
            return {
                "file_info": file_info,
                "scores": scores,
                "issues": issues
            }
            
        finally:
            # Cleanup temp file
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)

def get_recommendation(confidence: int, issues: List[Dict]) -> str:
    """Determine validation recommendation based on confidence and issues"""
    
    critical_issues = [issue for issue in issues if issue["severity"] == "error"]
    
    if critical_issues:
        return "reject"
    elif confidence >= 85:
        return "approve"
    elif confidence >= 70:
        return "human_review"
    else:
        return "reject"

@app.post("/validate/code")
async def validate_code_only(
    code_content: str = Form(...),
    language: str = Form(...),
    filename: str = Form(...)
):
    """Validate code content directly without file upload"""
    
    try:
        if language not in ["python", "javascript"]:
            raise HTTPException(status_code=400, detail="Unsupported language")
        
        # Create temporary file with code content
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=f".{get_extension(language)}") as temp_file:
            temp_file.write(code_content)
            temp_file.flush()
            
            file_info = {
                "name": filename,
                "size": len(code_content),
                "type": f"text/{language}"
            }
            
            try:
                # Security scan
                security_result = await security_scanner.scan_file(temp_file.name, file_info)
                
                # Code validation
                validation_result = await code_validator.validate_code_file(temp_file.name, file_info)
                
                scores = {
                    "security": security_result["score"],
                    "technical_quality": validation_result["score"],
                    "originality": 85,
                    "completeness": 80
                }
                
                overall_confidence = confidence_scorer.calculate_overall_confidence(scores)
                issues = security_result["issues"] + validation_result["issues"]
                
                return {
                    "confidence": overall_confidence,
                    "scores": scores,
                    "issues": issues,
                    "recommendation": get_recommendation(overall_confidence, issues)
                }
                
            finally:
                if os.path.exists(temp_file.name):
                    os.unlink(temp_file.name)
                    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Code validation failed: {str(e)}")

def get_extension(language: str) -> str:
    """Get file extension for programming language"""
    extensions = {
        "python": "py",
        "javascript": "js",
        "typescript": "ts",
        "java": "java",
        "cpp": "cpp"
    }
    return extensions.get(language, "txt")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)