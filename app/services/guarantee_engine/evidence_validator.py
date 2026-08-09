"""
Evidence Validator - Only inject skills that have resume evidence.

Phase 6.5 Component 5: Honesty filter that prevents fabrication.

Evidence levels:
- STRONG_MATCH (0.95): Exact keyword in resume
- PARTIAL_MATCH (0.70): Related/transferable experience
- VARIATION_MATCH (0.75): Known variation exists in resume
- NO_MATCH (0.0): No evidence at all
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
import re


@dataclass
class EvidenceResult:
    """Result of evidence check for a single keyword."""
    keyword: str
    confidence: float
    evidence_type: str  # exact_match, partial_match, variation_match, no_match
    should_inject: bool
    evidence_source: Optional[str] = None  # Where evidence was found


# Known variation mapping for evidence checking
EVIDENCE_VARIATIONS = {
    'python': ['python', 'python3', 'python 3'],
    'javascript': ['javascript', 'js', 'ecmascript'],
    'typescript': ['typescript', 'ts'],
    'react': ['react', 'react.js', 'reactjs'],
    'vue': ['vue', 'vue.js', 'vuejs'],
    'angular': ['angular', 'angular.js', 'angularjs'],
    'node.js': ['node', 'node.js', 'nodejs'],
    'postgresql': ['postgresql', 'postgres', 'psql'],
    'mongodb': ['mongodb', 'mongo'],
    'kubernetes': ['kubernetes', 'k8s'],
    'aws': ['aws', 'amazon web services'],
    'gcp': ['gcp', 'google cloud', 'google cloud platform'],
    'azure': ['azure', 'microsoft azure'],
    'docker': ['docker', 'containerization', 'containers'],
    'ci/cd': ['ci/cd', 'cicd', 'continuous integration', 'continuous deployment'],
    'restful apis': ['restful apis', 'rest apis', 'rest api', 'restful'],
    'oop': ['oop', 'object-oriented programming', 'object oriented'],
    'tdd': ['tdd', 'test-driven development', 'test driven development'],
    'sdlc': ['sdlc', 'software development lifecycle'],
    'sql': ['sql', 'database', 'queries'],
    'multithreading': ['multithreading', 'multi-threading', 'concurrent', 'concurrency'],
}


class EvidenceValidator:
    """
    Validate that keywords have resume evidence before injection.
    
    Only inject skills with confidence >= 0.70 (partial match or better).
    """
    
    CONFIDENCE_THRESHOLD = 0.70
    
    def check_evidence(self, keyword: str, resume_json: Dict) -> EvidenceResult:
        """
        Check if a keyword has evidence in the resume.
        
        Returns EvidenceResult with confidence and injection decision.
        """
        resume_text_lower = self._build_full_text(resume_json)
        keyword_lower = keyword.lower().strip()
        
        # Check 1: Exact phrase match
        if keyword_lower in resume_text_lower:
            return EvidenceResult(
                keyword=keyword,
                confidence=0.95,
                evidence_type="exact_match",
                should_inject=True,
                evidence_source="exact phrase found in resume",
            )
        
        # Check 2: All words present (partial match)
        words = [w for w in keyword_lower.split() if len(w) > 2]
        if words and all(w in resume_text_lower for w in words):
            return EvidenceResult(
                keyword=keyword,
                confidence=0.70,
                evidence_type="partial_match",
                should_inject=True,
                evidence_source="all key words present in resume",
            )
        
        # Check 3: Check variation map
        for canonical, variations in EVIDENCE_VARIATIONS.items():
            if keyword_lower in variations or canonical == keyword_lower:
                for variant in variations:
                    if variant in resume_text_lower:
                        return EvidenceResult(
                            keyword=keyword,
                            confidence=0.75,
                            evidence_type="variation_match",
                            should_inject=True,
                            evidence_source=f"variation '{variant}' found in resume",
                        )
        
        # Check 4: Check skills section directly
        for group in resume_json.get('skills', []):
            for item in group.get('items', []):
                item_lower = item.lower()
                if keyword_lower in item_lower or item_lower in keyword_lower:
                    return EvidenceResult(
                        keyword=keyword,
                        confidence=0.80,
                        evidence_type="skill_section_match",
                        should_inject=True,
                        evidence_source=f"found '{item}' in skills section",
                    )
        
        # No match
        return EvidenceResult(
            keyword=keyword,
            confidence=0.0,
            evidence_type="no_match",
            should_inject=False,
            evidence_source="no evidence found in resume",
        )
    
    def _build_full_text(self, resume_json: Dict) -> str:
        """Build searchable lowercase text from all resume sections."""
        parts = []
        
        # Summary
        summary = resume_json.get('summary', '')
        if summary:
            parts.append(summary.lower())
        
        # Skills
        for group in resume_json.get('skills', []):
            for item in group.get('items', []):
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
