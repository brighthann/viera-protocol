import subprocess
import os
import json
import ast
import re
from typing import Dict, List, Any
import tempfile
from pathlib import Path

class CodeValidator:
    def __init__(self):
        self.supported_languages = {
            'python': {
                'extensions': ['.py'],
                'validators': ['pylint', 'flake8', 'bandit'],
                'syntax_checker': self._check_python_syntax
            },
            'javascript': {
                'extensions': ['.js', '.jsx'],
                'validators': ['eslint'],
                'syntax_checker': self._check_javascript_syntax
            }
        }
    
    async def validate_code_file(self, file_path: str, file_info: Dict) -> Dict[str, Any]:
        """
        Comprehensive code validation for a single file
        """
        issues = []
        technical_score = 100  # Start with perfect score
        
        try:
            # Determine language from file extension
            file_extension = os.path.splitext(file_info["name"])[1].lower()
            language = self._detect_language(file_extension)
            
            if not language:
                return {
                    "score": 50,  # Neutral score for unknown file types
                    "issues": [{
                        "severity": "info",
                        "message": f"Unsupported file type for code validation: {file_extension}",
                        "file": file_info["name"],
                        "rule": "language_detection"
                    }]
                }
            
            # 1. Syntax validation
            syntax_result = await self._validate_syntax(file_path, language, file_info)
            issues.extend(syntax_result["issues"])
            technical_score -= syntax_result["score_deduction"]
            
            # 2. Code quality analysis
            quality_result = await self._analyze_code_quality(file_path, language, file_info)
            issues.extend(quality_result["issues"])
            technical_score -= quality_result["score_deduction"]
            
            # 3. Security analysis for code
            security_result = await self._analyze_code_security(file_path, language, file_info)
            issues.extend(security_result["issues"])
            technical_score -= security_result["score_deduction"]
            
            # 4. Complexity and best practices
            complexity_result = await self._analyze_complexity(file_path, language, file_info)
            issues.extend(complexity_result["issues"])
            technical_score -= complexity_result["score_deduction"]
            
            # Ensure score doesn't go below 0
            technical_score = max(0, technical_score)
            
            return {
                "score": technical_score,
                "issues": issues,
                "language": language
            }
            
        except Exception as e:
            return {
                "score": 0,
                "issues": [{
                    "severity": "error",
                    "message": f"Code validation failed: {str(e)}",
                    "file": file_info["name"],
                    "rule": "validation_error"
                }]
            }
    
    def _detect_language(self, file_extension: str) -> str:
        """Detect programming language from file extension"""
        for language, config in self.supported_languages.items():
            if file_extension in config['extensions']:
                return language
        return None
    
    async def _validate_syntax(self, file_path: str, language: str, file_info: Dict) -> Dict[str, Any]:
        """Validate code syntax"""
        issues = []
        score_deduction = 0
        
        try:
            config = self.supported_languages[language]
            syntax_checker = config['syntax_checker']
            
            syntax_result = syntax_checker(file_path)
            
            if not syntax_result['valid']:
                issues.append({
                    "severity": "error",
                    "message": f"Syntax error: {syntax_result['error']}",
                    "file": file_info["name"],
                    "line": syntax_result.get('line'),
                    "rule": "syntax_validation"
                })
                score_deduction = 50  # Major deduction for syntax errors
            
            return {
                "issues": issues,
                "score_deduction": score_deduction
            }
            
        except Exception as e:
            return {
                "issues": [{
                    "severity": "warning",
                    "message": f"Syntax validation failed: {str(e)}",
                    "file": file_info["name"],
                    "rule": "syntax_validation_error"
                }],
                "score_deduction": 10
            }
    
    def _check_python_syntax(self, file_path: str) -> Dict[str, Any]:
        """Check Python syntax using AST"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            # Parse with AST
            ast.parse(code)
            return {"valid": True}
            
        except SyntaxError as e:
            return {
                "valid": False,
                "error": str(e),
                "line": e.lineno
            }
        except Exception as e:
            return {
                "valid": False,
                "error": f"Parsing error: {str(e)}"
            }
    
    def _check_javascript_syntax(self, file_path: str) -> Dict[str, Any]:
        """Check JavaScript syntax using Node.js"""
        try:
            # Use Node.js to check syntax
            result = subprocess.run(
                ['node', '--check', file_path],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return {"valid": True}
            else:
                return {
                    "valid": False,
                    "error": result.stderr.strip()
                }
                
        except subprocess.TimeoutExpired:
            return {
                "valid": False,
                "error": "Syntax check timed out"
            }
        except FileNotFoundError:
            return {
                "valid": False,
                "error": "Node.js not available for syntax checking"
            }
        except Exception as e:
            return {
                "valid": False,
                "error": f"Syntax check error: {str(e)}"
            }
    
    async def _analyze_code_quality(self, file_path: str, language: str, file_info: Dict) -> Dict[str, Any]:
        """Analyze code quality using language-specific tools"""
        issues = []
        score_deduction = 0
        
        try:
            if language == 'python':
                # Use Flake8 for Python code quality
                result = subprocess.run(
                    ['flake8', '--format=%(path)s:%(row)d:%(col)d:%(code)s:%(text)s', file_path],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode != 0 and result.stdout:
                    # Parse flake8 output
                    for line in result.stdout.strip().split('\n'):
                        if line:
                            parts = line.split(':')
                            if len(parts) >= 5:
                                file_name = parts[0]
                                line_num = parts[1]
                                column = parts[2]
                                code = parts[3]
                                message = ':'.join(parts[4:]).strip()
                                
                                severity = "warning"
                                if any(error_code in code for error_code in ['E9', 'F']):
                                    severity = "error"
                                    score_deduction += 5
                                else:
                                    score_deduction += 2
                                
                                issues.append({
                                    "severity": severity,
                                    "message": f"{code}: {message}",
                                    "file": file_info["name"],
                                    "line": int(line_num) if line_num.isdigit() else None,
                                    "rule": "flake8"
                                })
            
            elif language == 'javascript':
                # Use ESLint for JavaScript code quality
                result = subprocess.run(
                    ['eslint', '--format=json', file_path],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.stdout:
                    try:
                        eslint_results = json.loads(result.stdout)
                        for file_result in eslint_results:
                            for message in file_result.get('messages', []):
                                severity_map = {1: "warning", 2: "error"}
                                severity = severity_map.get(message.get('severity', 1), "info")
                                
                                if severity == "error":
                                    score_deduction += 5
                                else:
                                    score_deduction += 2
                                
                                issues.append({
                                    "severity": severity,
                                    "message": message.get('message', ''),
                                    "file": file_info["name"],
                                    "line": message.get('line'),
                                    "rule": message.get('ruleId', 'eslint')
                                })
                    except json.JSONDecodeError:
                        pass  # ESLint might not return valid JSON if no issues
            
            return {
                "issues": issues,
                "score_deduction": min(score_deduction, 30)  # Cap at 30 points
            }
            
        except subprocess.TimeoutExpired:
            return {
                "issues": [{
                    "severity": "warning",
                    "message": "Code quality analysis timed out",
                    "file": file_info["name"],
                    "rule": "quality_timeout"
                }],
                "score_deduction": 5
            }
        except Exception as e:
            return {
                "issues": [{
                    "severity": "info",
                    "message": f"Code quality analysis failed: {str(e)}",
                    "file": file_info["name"],
                    "rule": "quality_analysis_error"
                }],
                "score_deduction": 0
            }
    
    async def _analyze_code_security(self, file_path: str, language: str, file_info: Dict) -> Dict[str, Any]:
        """Analyze code for security issues"""
        issues = []
        score_deduction = 0
        
        try:
            if language == 'python':
                # Use Bandit for Python security analysis
                result = subprocess.run(
                    ['bandit', '-f', 'json', file_path],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.stdout:
                    try:
                        bandit_results = json.loads(result.stdout)
                        for issue in bandit_results.get('results', []):
                            severity_map = {"LOW": "info", "MEDIUM": "warning", "HIGH": "error"}
                            severity = severity_map.get(issue.get('issue_severity', 'LOW'), "info")
                            
                            if severity == "error":
                                score_deduction += 15
                            elif severity == "warning":
                                score_deduction += 8
                            else:
                                score_deduction += 3
                            
                            issues.append({
                                "severity": severity,
                                "message": f"{issue.get('issue_text', '')}: {issue.get('test_name', '')}",
                                "file": file_info["name"],
                                "line": issue.get('line_number'),
                                "rule": f"bandit-{issue.get('test_id', '')}"
                            })
                    except json.JSONDecodeError:
                        pass  # Bandit might not return valid JSON if no issues
            
            elif language == 'javascript':
                # Basic security pattern matching for JavaScript (since ESLint security plugin might not be available)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Common JavaScript security issues
                security_patterns = [
                    (r'eval\s*\(', "Use of eval() detected", "error"),
                    (r'innerHTML\s*=', "Potential XSS with innerHTML", "warning"),
                    (r'document\.write\s*\(', "Use of document.write detected", "warning"),
                    (r'setTimeout\s*\(\s*["\']', "setTimeout with string argument", "warning"),
                    (r'setInterval\s*\(\s*["\']', "setInterval with string argument", "warning")
                ]
                
                for pattern, message, sev in security_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        if sev == "error":
                            score_deduction += 15
                        elif sev == "warning":
                            score_deduction += 8
                        
                        issues.append({
                            "severity": sev,
                            "message": f"{message} ({len(matches)} occurrences)",
                            "file": file_info["name"],
                            "rule": "js_security_pattern"
                        })
            
            return {
                "issues": issues,
                "score_deduction": min(score_deduction, 40)  # Cap at 40 points
            }
            
        except subprocess.TimeoutExpired:
            return {
                "issues": [{
                    "severity": "warning",
                    "message": "Security analysis timed out",
                    "file": file_info["name"],
                    "rule": "security_timeout"
                }],
                "score_deduction": 5
            }
        except Exception as e:
            return {
                "issues": [{
                    "severity": "info",
                    "message": f"Security analysis failed: {str(e)}",
                    "file": file_info["name"],
                    "rule": "security_analysis_error"
                }],
                "score_deduction": 0
            }
    
    async def _analyze_complexity(self, file_path: str, language: str, file_info: Dict) -> Dict[str, Any]:
        """Analyze code complexity and best practices"""
        issues = []
        score_deduction = 0
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.split('\n')
            line_count = len(lines)
            non_empty_lines = len([line for line in lines if line.strip()])
            
            # Basic complexity metrics
            if language == 'python':
                # Count functions and classes
                function_count = len(re.findall(r'^def\s+\w+', content, re.MULTILINE))
                class_count = len(re.findall(r'^class\s+\w+', content, re.MULTILINE))
                
            elif language == 'javascript':
                # Count functions
                function_count = len(re.findall(r'function\s+\w+|const\s+\w+\s*=.*?=>|\w+\s*:\s*function', content))
                class_count = len(re.findall(r'class\s+\w+', content))
            
            # File size analysis
            if line_count > 500:
                issues.append({
                    "severity": "info",
                    "message": f"Large file: {line_count} lines (consider splitting)",
                    "file": file_info["name"],
                    "rule": "file_size_complexity"
                })
                score_deduction += 3
            
            # Documentation analysis
            if language == 'python':
                docstring_count = len(re.findall(r'""".*?"""', content, re.DOTALL))
                comment_count = len(re.findall(r'#.*$', content, re.MULTILINE))
            elif language == 'javascript':
                docstring_count = len(re.findall(r'/\*\*.*?\*/', content, re.DOTALL))
                comment_count = len(re.findall(r'//.*$', content, re.MULTILINE))
            
            # Documentation ratio (rough measure of code quality)
            if non_empty_lines > 20:  # Only check for longer files
                doc_ratio = (docstring_count + comment_count) / non_empty_lines
                if doc_ratio < 0.1:  # Less than 10% documentation
                    issues.append({
                        "severity": "info",
                        "message": "Consider adding more comments and documentation",
                        "file": file_info["name"],
                        "rule": "documentation_ratio"
                    })
                    score_deduction += 2
            
            return {
                "issues": issues,
                "score_deduction": score_deduction
            }
            
        except Exception as e:
            return {
                "issues": [{
                    "severity": "info",
                    "message": f"Complexity analysis failed: {str(e)}",
                    "file": file_info["name"],
                    "rule": "complexity_analysis_error"
                }],
                "score_deduction": 0
            }