"""
Audit Engine - Analyze resume and determine what must-have/important keywords are missing.

Phase 6.5 Component 1: Finds gaps between extracted keywords and tailored resume.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class AuditReport:
    """Result of auditing a resume against expected keywords."""
    total_must_haves: int = 0
    total_important: int = 0
    found_must_haves: List[str] = field(default_factory=list)
    missing_must_haves: List[str] = field(default_factory=list)
    found_important: List[str] = field(default_factory=list)
    missing_important: List[str] = field(default_factory=list)
    found_count: int = 0
    missing_count: int = 0
    coverage_percentage: float = 0.0
    audit_status: str = "NOT_RUN"  # COMPLETE, CRITICAL_GAPS, MINOR_GAPS
    recommendation: str = ""


class AuditEngine:
    """
    Analyze current resume and determine what's missing.
    
    For each must_have_keyword:
      - Convert to lowercase for comparison
      - Search in resume.summary, resume.skills, resume.experience, resume.projects
      - Mark as: PRESENT or MISSING
      - If MISSING, calculate injection_priority
    """
    
    def audit(self, resume_json: Dict, must_haves: List[str],
              important_keywords: List[str]) -> AuditReport:
        """
        Audit resume against expected must-have and important keywords.
        
        Returns AuditReport with found/missing counts and coverage.
        """
        report = AuditReport()
        report.total_must_haves = len(must_haves)
        report.total_important = len(important_keywords)
        
        # Build searchable text from all resume sections
        resume_text_lower = self._build_searchable_text(resume_json)
        
        # Check must-haves
        for keyword in must_haves:
            if self._keyword_present(keyword, resume_text_lower, resume_json):
                report.found_must_haves.append(keyword)
            else:
                report.missing_must_haves.append(keyword)
        
        # Check important keywords
        for keyword in important_keywords:
            if self._keyword_present(keyword, resume_text_lower, resume_json):
                report.found_important.append(keyword)
            else:
                report.missing_important.append(keyword)
        
        # Calculate totals
        report.found_count = len(report.found_must_haves) + len(report.found_important)
        report.missing_count = len(report.missing_must_haves) + len(report.missing_important)
        total = report.total_must_haves + report.total_important
        report.coverage_percentage = (report.found_count / max(total, 1)) * 100
        
        # Determine status
        if report.missing_count == 0:
            report.audit_status = "COMPLETE"
            report.recommendation = "All must-haves and important keywords present"
        elif len(report.missing_must_haves) > 0:
            report.audit_status = "CRITICAL_GAPS"
            report.recommendation = f"Inject {len(report.missing_must_haves)} missing must-haves immediately"
        else:
            report.audit_status = "MINOR_GAPS"
            report.recommendation = f"Inject {len(report.missing_important)} missing important keywords"
        
        return report
    
    def _build_searchable_text(self, resume_json: Dict) -> str:
        """Build a lowercase searchable string from all resume sections."""
        parts = []
        
        # Summary
        summary = resume_json.get('summary', '')
        if summary:
            parts.append(summary.lower())
        
        # Skills
        for skill_group in resume_json.get('skills', []):
            for item in skill_group.get('items', []):
                parts.append(item.lower())
        
        # Experience
        for exp in resume_json.get('experience', []):
            for bullet in exp.get('bullets', []):
                if isinstance(bullet, str):
                    parts.append(bullet.lower())
            ts = exp.get('tech_stack', '')
            if ts:
                parts.append(ts.lower())
        
        # Projects
        for proj in resume_json.get('projects', []):
            for bullet in proj.get('bullets', []):
                if isinstance(bullet, str):
                    parts.append(bullet.lower())
            ts = proj.get('tech_stack', '')
            if ts:
                parts.append(ts.lower())
        
        return ' '.join(parts)
    
    def _keyword_present(self, keyword: str, resume_text_lower: str,
                         resume_json: Dict) -> bool:
        """Check if a keyword is present in the resume (exact or fuzzy)."""
        keyword_lower = keyword.lower()
        
        # Check 1: Exact match in full text
        if keyword_lower in resume_text_lower:
            return True
        
        # Check 2: Check skills items directly (handles abbreviations)
        for skill_group in resume_json.get('skills', []):
            for item in skill_group.get('items', []):
                item_lower = item.lower()
                if keyword_lower == item_lower:
                    return True
                # Substring containment both ways
                if keyword_lower in item_lower or item_lower in keyword_lower:
                    return True
        
        # Check 3: All significant words present
        words = [w for w in keyword_lower.split() if len(w) > 2]
        if words and all(w in resume_text_lower for w in words):
            return True
        
        return False
