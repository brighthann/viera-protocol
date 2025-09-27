import os
import hashlib
import tempfile
import aiofiles
from typing import Dict, Any, Optional
from pathlib import Path

class FileHandler:
    def __init__(self):
        self.max_file_size = 100 * 1024 * 1024  # 100MB
        self.temp_dir = Path(tempfile.gettempdir()) / "viera_validation"
        self.temp_dir.mkdir(exist_ok=True)
    
    async def save_uploaded_file(self, file_content: bytes, filename: str) -> str:
        """
        Save uploaded file to temporary location and return path
        """
        # Validate file size
        if len(file_content) > self.max_file_size:
            raise ValueError(f"File too large: {len(file_content)} bytes (max: {self.max_file_size})")
        
        # Generate unique filename
        file_hash = hashlib.md5(file_content).hexdigest()[:8]
        safe_filename = self._sanitize_filename(filename)
        temp_filename = f"{file_hash}_{safe_filename}"
        temp_path = self.temp_dir / temp_filename
        
        # Save file
        async with aiofiles.open(temp_path, 'wb') as f:
            await f.write(file_content)
        
        return str(temp_path)
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename to prevent path traversal attacks
        """
        # Remove directory separators and other dangerous characters
        safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_"
        sanitized = ''.join(c if c in safe_chars else '_' for c in filename)
        
        # Limit length and ensure it's not empty
        sanitized = sanitized[:100]  # Max 100 characters
        if not sanitized:
            sanitized = "unknown_file"
        
        return sanitized
    
    def cleanup_temp_file(self, file_path: str) -> bool:
        """
        Clean up temporary file
        """
        try:
            if os.path.exists(file_path) and str(file_path).startswith(str(self.temp_dir)):
                os.unlink(file_path)
                return True
        except Exception:
            pass
        return False
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """
        Get basic information about a file
        """
        try:
            stat = os.stat(file_path)
            return {
                "size_bytes": stat.st_size,
                "modified_time": stat.st_mtime,
                "is_file": os.path.isfile(file_path),
                "extension": Path(file_path).suffix.lower()
            }
        except Exception as e:
            return {
                "error": str(e),
                "size_bytes": 0,
                "modified_time": 0,
                "is_file": False,
                "extension": ""
            }