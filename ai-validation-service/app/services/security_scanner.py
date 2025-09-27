import clamd
import subprocess
import os
import hashlib
import re
from typing import Dict, List, Any
import asyncio

class SecurityScanner:
    def __init__(self):
        self.clamd_socket = None
        self.initialize_clamav()
    
    def initialize_clamav(self):
        """Initialize ClamAV connection"""
        try:
            self.clamd_socket = clamd.ClamdUnixSocket()
            # Test connection
            self.clamd_socket.ping()
            print("✅ ClamAV initialized successfully")
        except Exception as e:
            print(f"⚠️ ClamAV initialization failed: {e}")
            self.clamd_socket = None
    
    def check_antivirus_status(self) -> str:
        """Check if antivirus service is running"""
        try:
            if self.clamd_socket:
                self.clamd_socket.ping()
                return "running"
            else:
                return "not_connected"
        except:
            return "error"
    
    async def scan_file(self, file_path: str, file_info: Dict) -> Dict[str, Any]:
        """
        Comprehensive security scan of a file
        """
        issues = []
        security_score = 100  # Start with perfect score, deduct for issues
        
        try:
            # 1. ClamAV virus scan
            virus_result = await self._scan_with_clamav(file_path)
            if virus_result["infected"]:
                issues.append({
                    "severity": "error",
                    "message": f"Malware detected: {virus_result['virus']}",
                    "file": file_info["name"],
                    "rule": "clamav_scan"
                })
                security_score = 0  # Critical security failure
            
            # 2. File type validation
            file_type_result = self._validate_file_type(file_path, file_info)
            if file_type_result["suspicious"]:
                issues.extend(file_type_result["issues"])
                security_score -= 20
            
            # 3. Content-based security checks
            content_result = await self._scan_file_content(file_path, file_info)
            issues.extend(content_result["issues"])
            security_score -= content_result["score_deduction"]
            
            # 4. File size and structure checks
            structure_result = self._validate_file_structure(file_path, file_info)
            issues.extend(structure_result["issues"])
            security_score -= structure_result["score_deduction"]
            
            # Ensure score doesn't go below 0
            security_score = max(0, security_score)
            
            return {
                "score": security_score,
                "issues": issues,
                "scan_completed": True
            }
            
        except Exception as e:
            issues.append({
                "severity": "error",
                "message": f"Security scan failed: {str(e)}",
                "file": file_info["name"],
                "rule": "scan_error"
            })
            
            return {
                "score": 0,
                "issues": issues,
                "scan_completed": False
            }
    
    async def _scan_with_clamav(self, file_path: str) -> Dict[str, Any]:
        """Scan file with ClamAV antivirus"""
        try:
            if not self.clamd_socket:
                return {"infected": False, "virus": None, "error": "ClamAV not available"}
            
            result = self.clamd_socket.scan(file_path)
            
            if result is None:
                return {"infected": False, "virus": None}
            
            # ClamAV returns (filename, status) if infected
            filename, status = list(result.items())[0]
            if "FOUND" in status:
                virus_name = status.replace(" FOUND", "")
                return {"infected": True, "virus": virus_name}
            
            return {"infected": False, "virus": None}
            
        except Exception as e:
            return {"infected": False, "virus": None, "error": str(e)}
    
    def _validate_file_type(self, file_path: str, file_info: Dict) -> Dict[str, Any]:
        """Validate file type and extension"""
        issues = []
        suspicious = False
        
        try:
            # Check file extension against content
            file_extension = os.path.splitext(file_info["name"])[1].lower()
            
            # Suspicious extensions that shouldn't be in research submissions
            dangerous_extensions = [
                '.exe', '.bat', '.cmd', '.scr', '.pif', '.com', '.dll',
                '.msi', '.vbs', '.ps1', '.jar', '.app', '.deb', '.rpm'
            ]
            
            if file_extension in dangerous_extensions:
                issues.append({
                    "severity": "error",
                    "message": f"Dangerous file type not allowed: {file_extension}",
                    "file": file_info["name"],
                    "rule": "file_type_validation"
                })
                suspicious = True
            
            # Check file signature (magic numbers)
            with open(file_path, 'rb') as f:
                file_signature = f.read(16)
            
            # Basic file signature validation
            if len(file_signature) >= 2:
                # Check for executable signatures
                if file_signature[:2] == b'MZ':  # Windows PE executable
                    issues.append({
                        "severity": "error",
                        "message": "Executable file detected by signature",
                        "file": file_info["name"],
                        "rule": "file_signature_check"
                    })
                    suspicious = True
            
            return {
                "suspicious": suspicious,
                "issues": issues
            }
            
        except Exception as e:
            issues.append({
                "severity": "warning",
                "message": f"File type validation failed: {str(e)}",
                "file": file_info["name"],
                "rule": "file_type_error"
            })
            
            return {
                "suspicious": True,
                "issues": issues
            }
    
    async def _scan_file_content(self, file_path: str, file_info: Dict) -> Dict[str, Any]:
        """Scan file content for suspicious patterns"""
        issues = []
        score_deduction = 0
        
        try:
            # Only scan text-based files
            text_extensions = ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.txt', '.md']
            file_extension = os.path.splitext(file_info["name"])[1].lower()
            
            if file_extension not in text_extensions:
                return {"issues": issues, "score_deduction": score_deduction}
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Suspicious patterns to look for
            suspicious_patterns = [
                (r'eval\s*\(', "Use of eval() function detected", "warning"),
                (r'exec\s*\(', "Use of exec() function detected", "warning"),
                (r'__import__\s*\(', "Dynamic import detected", "info"),
                (r'subprocess\.|os\.system|os\.popen', "System command execution detected", "warning"),
                (r'socket\.|urllib|requests', "Network operation detected", "info"),
                (r'base64\.decode|base64\.b64decode', "Base64 decoding detected", "info"),
                (r'pickle\.loads?|marshal\.loads?', "Unsafe deserialization detected", "error")
            ]
            
            for pattern, message, severity in suspicious_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    issues.append({
                        "severity": severity,
                        "message": f"{message} ({len(matches)} occurrences)",
                        "file": file_info["name"],
                        "rule": "content_pattern_scan"
                    })
                    
                    if severity == "error":
                        score_deduction += 30
                    elif severity == "warning":
                        score_deduction += 10
                    elif severity == "info":
                        score_deduction += 2
            
            return {
                "issues": issues,
                "score_deduction": min(score_deduction, 50)  # Cap deduction
            }
            
        except Exception as e:
            issues.append({
                "severity": "warning",
                "message": f"Content scan failed: {str(e)}",
                "file": file_info["name"],
                "rule": "content_scan_error"
            })
            
            return {
                "issues": issues,
                "score_deduction": 5
            }
    
    def _validate_file_structure(self, file_path: str, file_info: Dict) -> Dict[str, Any]:
        """Validate file structure and metadata"""
        issues = []
        score_deduction = 0
        
        try:
            file_stats = os.stat(file_path)
            file_size = file_stats.st_size
            
            # Check for suspiciously large files (>100MB)
            if file_size > 100 * 1024 * 1024:
                issues.append({
                    "severity": "warning",
                    "message": f"Large file size: {file_size / (1024*1024):.1f}MB",
                    "file": file_info["name"],
                    "rule": "file_size_check"
                })
                score_deduction += 5
            
            # Check for suspiciously small files that claim to be code (might be malformed)
            code_extensions = ['.py', '.js', '.java', '.cpp']
            file_extension = os.path.splitext(file_info["name"])[1].lower()
            
            if file_extension in code_extensions and file_size < 10:
                issues.append({
                    "severity": "info",
                    "message": "Very small code file detected",
                    "file": file_info["name"],
                    "rule": "file_size_check"
                })
                score_deduction += 2
            
            return {
                "issues": issues,
                "score_deduction": score_deduction
            }
            
        except Exception as e:
            issues.append({
                "severity": "info",
                "message": f"File structure validation failed: {str(e)}",
                "file": file_info["name"],
                "rule": "structure_validation_error"
            })
            
            return {
                "issues": issues,
                "score_deduction": 1
            }