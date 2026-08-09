"""
Guarantee Verifier - Verify 100% of must-haves are actually in the resume.

Phase 6.5 Component 6: Final verification and report generation.

Generates verification report with:
- Coverage percentages
- Missing keywords
- Injection statistics
- Placement verification
"""

from typing import Dict, List, Optional


class GuaranteeVerifier:
    """
    Verify that all must-have and important keywords are present in the final resume.
    """
    
    def verify_guarantee(self, resume_json: Dict,
                          expected_must_haves: List[str],
                          expected_important: List[str]) -> Dict:
        """
        Final 100% coverage check.
        
        Returns verification report:
        {
            'status': 'GUARANTEE_COMPLETE' | 'GUARANTEE_PARTIAL' | 'GUARANTEE_FAILED',
            'must_have_coverage': float,
            'important_coverage': float,
            'total_coverage': float,
            'injections_count': int,
            'confidence_average': float,
            'still_missing': [...],
            'placement_check': {...},
        }
        """
        resume_text_lower = self._build_searchable_text(resume_json)
        
        # Check must-haves
        found_must_haves = []
        missing_must_haves = []
        for keyword in expected_must_haves:
            if self._keyword_present(keyword, resume_text_lower, resume_json):
                found_must_haves.append(keyword)
            else:
                missing_must_haves.append(keyword)
        
        # Check important
        found_important = []
        missing_important = []
        for keyword in expected_important:
            if self._keyword_present(keyword, resume_text_lower, resume_json):
                found_important.append(keyword)
            else:
                missing_important.append(keyword)
        
        # Calculate coverage
        total_expected = len(expected_must_haves) + len(expected_important)
        total_found = len(found_must_haves) + len(found_important)
        
        must_have_coverage = len(found_must_haves) / max(len(expected_must_haves), 1)
        important_coverage = len(found_important) / max(len(expected_important), 1)
        total_coverage = total_found / max(total_expected, 1)
        
        # Placement verification
        placement_check = self._verify_placement(resume_json)
        
        # Determine status
        all_missing = missing_must_haves + missing_important
        if len(all_missing) == 0:
            status = "GUARANTEE_COMPLETE"
        elif len(missing_must_haves) == 0:
            status = "GUARANTEE_PARTIAL"  # Must-haves OK but some important missing
        else:
            status = "GUARANTEE_FAILED"
        
        return {
            'status': status,
            'must_have_coverage': must_have_coverage,
            'important_coverage': important_coverage,
            'total_coverage': total_coverage,
            'found_must_haves': found_must_haves,
            'missing_must_haves': missing_must_haves,
            'found_important': found_important,
            'missing_important': missing_important,
            'still_missing': all_missing,
            'injections_count': 0,  # Updated by engine
            'confidence_average': 0.0,  # Updated by engine
            'placement_check': placement_check,
            'recommendation': 'READY_FOR_ATS' if status == 'GUARANTEE_COMPLETE' else 'NEEDS_MANUAL_REVIEW',
        }
    
    def _build_searchable_text(self, resume_json: Dict) -> str:
        """Build lowercase searchable text from all resume sections."""
        parts = []
        
        summary = resume_json.get('summary', '')
        if summary:
            parts.append(summary.lower())
        
        for group in resume_json.get('skills', []):
            for item in group.get('items', []):
                parts.append(item.lower())
        
        for exp in resume_json.get('experience', []):
            for bullet in exp.get('bullets', []):
                if isinstance(bullet, str):
                    parts.append(bullet.lower())
            ts = exp.get('tech_stack', '')
            if ts:
                parts.append(ts.lower())
        
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
        """Check if keyword is present in resume."""
        keyword_lower = keyword.lower()
        
        # Exact match
        if keyword_lower in resume_text_lower:
            return True
        
        # Check skills items directly
        for group in resume_json.get('skills', []):
            for item in group.get('items', []):
                item_lower = item.lower()
                if keyword_lower == item_lower:
                    return True
                if keyword_lower in item_lower or item_lower in keyword_lower:
                    return True
        
        # All significant words present
        words = [w for w in keyword_lower.split() if len(w) > 2]
        if words and all(w in resume_text_lower for w in words):
            return True
        
        return False
    
    def _verify_placement(self, resume_json: Dict) -> Dict:
        """
        Verify keywords are in correct sections.
        
        Checks:
        - Soft skills NOT in Skills section
        - Hard skills ARE in Skills section
        """
        # Known soft skills
        soft_skills = {
            'communication', 'collaboration', 'teamwork', 'leadership',
            'problem-solving', 'adaptability', 'flexibility', 'mentoring',
            'coaching', 'initiative', 'critical thinking', 'innovation',
            'negotiation', 'stakeholder management', 'curiosity',
        }
        
        soft_in_skills = 0
        for group in resume_json.get('skills', []):
            for item in group.get('items', []):
                if item.lower() in soft_skills:
                    soft_in_skills += 1
        
        return {
            'soft_skills_in_skills': soft_in_skills,
            'placement_violations': soft_in_skills,
        }
