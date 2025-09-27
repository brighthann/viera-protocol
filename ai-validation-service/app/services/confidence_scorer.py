from typing import Dict, List

class ConfidenceScorer:
    def __init__(self):
        # Weights for different scoring categories
        self.weights = {
            "security": 0.35,        # 35% - Most important
            "technical_quality": 0.30,  # 30% - Code quality
            "originality": 0.20,     # 20% - Plagiarism/uniqueness
            "completeness": 0.15     # 15% - Meeting requirements
        }
    
    def calculate_overall_confidence(self, scores: Dict[str, float]) -> int:
        """
        Calculate overall confidence score (0-100) from category scores
        """
        try:
            weighted_score = 0
            total_weight = 0
            
            for category, score in scores.items():
                if category in self.weights:
                    weight = self.weights[category]
                    weighted_score += score * weight
                    total_weight += weight
            
            # Normalize if not all categories are present
            if total_weight > 0:
                final_score = weighted_score / total_weight
            else:
                final_score = 50  # Default neutral score
            
            # Apply confidence adjustments based on specific criteria
            adjusted_score = self._apply_confidence_adjustments(scores, final_score)
            
            # Ensure score is within bounds and return as integer
            return max(0, min(100, round(adjusted_score)))
            
        except Exception:
            return 50  # Default neutral score if calculation fails
    
    def _apply_confidence_adjustments(self, scores: Dict[str, float], base_score: float) -> float:
        """
        Apply additional adjustments to confidence score based on specific criteria
        """
        adjusted_score = base_score
        
        # Security is critical - major penalties for low security scores
        security_score = scores.get("security", 100)
        if security_score < 50:
            adjusted_score *= 0.3  # Severe penalty for security issues
        elif security_score < 70:
            adjusted_score *= 0.7  # Moderate penalty
        
        # Technical quality threshold
        technical_score = scores.get("technical_quality", 100)
        if technical_score < 30:
            adjusted_score *= 0.5  # Penalty for very poor code quality
        
        # Bonus for high performance across all categories
        if all(score >= 85 for score in scores.values()):
            adjusted_score = min(100, adjusted_score * 1.05)  # 5% bonus
        
        return adjusted_score
    
    def get_confidence_category(self, confidence_score: int) -> str:
        """
        Categorize confidence score into human-readable categories
        """
        if confidence_score >= 85:
            return "high"
        elif confidence_score >= 70:
            return "medium"
        elif confidence_score >= 50:
            return "low"
        else:
            return "very_low"
    
    def get_recommendation_reason(self, scores: Dict[str, float], issues: List[Dict]) -> str:
        """
        Generate human-readable explanation for the confidence score
        """
        try:
            reasons = []
            
            # Security analysis
            security_score = scores.get("security", 100)
            if security_score < 70:
                critical_security_issues = [issue for issue in issues 
                                           if issue.get("severity") == "error" and "security" in issue.get("rule", "").lower()]
                if critical_security_issues:
                    reasons.append("Critical security vulnerabilities detected")
                else:
                    reasons.append("Security concerns identified")
            
            # Technical quality
            technical_score = scores.get("technical_quality", 100)
            if technical_score < 50:
                reasons.append("Significant code quality issues")
            elif technical_score < 70:
                reasons.append("Minor code quality improvements needed")
            
            # Error analysis
            error_count = len([issue for issue in issues if issue.get("severity") == "error"])
            if error_count > 0:
                reasons.append(f"{error_count} critical issue(s) found")
            
            # Positive indicators
            if all(score >= 85 for score in scores.values()):
                reasons.append("High quality across all criteria")
            
            return "; ".join(reasons) if reasons else "Standard validation completed"
            
        except Exception:
            return "Validation completed with standard criteria"