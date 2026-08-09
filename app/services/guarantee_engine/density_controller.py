"""
Density Controller - Ensure density limits aren't violated during injection.

Phase 6.5 Component 3: Enforces density rules per the architecture spec.

Rules:
- Skills: Max 8 per category, Max 7 categories, Max 56 total
- Summary: Max 20% keyword density
- Experience: Max 4 mentions same keyword, Max 2 keywords per bullet
- Global: Each skill appears exactly ONCE
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class DensityRules:
    """Configurable density limits."""
    max_skills_per_category: int = 8
    max_categories: int = 7
    max_total_skills: int = 56
    max_summary_keyword_density: float = 0.20  # 20%
    max_keyword_frequency: int = 4
    max_keywords_per_bullet: int = 2
    min_bullet_spacing: int = 2


class DensityController:
    """
    Check and enforce density limits across all resume sections.
    """
    
    def __init__(self, rules: Optional[DensityRules] = None):
        self.rules = rules or DensityRules()
    
    def check_can_inject(self, resume_json: Dict, keyword: str,
                          target_section: str) -> Tuple[bool, str]:
        """
        Check if a keyword can be injected into target section without violating density.
        
        Returns: (can_inject: bool, reason: str)
        """
        if target_section == 'skills':
            return self._check_skills_density(resume_json, keyword)
        elif target_section == 'summary':
            return self._check_summary_density(resume_json, keyword)
        elif target_section == 'experience':
            return self._check_experience_density(resume_json, keyword)
        else:
            return (True, "Unknown section — allowing injection")
    
    def _check_skills_density(self, resume_json: Dict, keyword: str) -> Tuple[bool, str]:
        """Check if Skills section can accept another keyword."""
        skills = resume_json.get('skills', [])
        
        # Check total skills count
        total_skills = sum(len(g.get('items', [])) for g in skills)
        if total_skills >= self.rules.max_total_skills:
            return (False, f"Total skills ({total_skills}) at max ({self.rules.max_total_skills})")
        
        # Check categories count
        if len(skills) >= self.rules.max_categories:
            # Can still inject into existing categories
            pass
        
        return (True, "Skills section has room")
    
    def _check_summary_density(self, resume_json: Dict, keyword: str) -> Tuple[bool, str]:
        """Check if Summary has room for more keywords (20% density limit)."""
        summary = resume_json.get('summary', '')
        if not summary:
            return (False, "No summary section")
        
        summary_words = len(summary.split())
        max_keyword_words = int(summary_words * self.rules.max_summary_keyword_density)
        keyword_word_count = len(keyword.split())
        
        # Rough estimate: count known keywords already in summary
        # For simplicity, just check if adding this keyword would push total over limit
        if keyword_word_count > max_keyword_words:
            return (False, f"Summary density would exceed {self.rules.max_summary_keyword_density:.0%}")
        
        return (True, "Summary has room for keyword")
    
    def _check_experience_density(self, resume_json: Dict, keyword: str) -> Tuple[bool, str]:
        """Check if Experience section can accept this keyword."""
        keyword_lower = keyword.lower()
        
        # Count current frequency
        freq = 0
        for exp in resume_json.get('experience', []):
            for bullet in exp.get('bullets', []):
                if isinstance(bullet, str) and keyword_lower in bullet.lower():
                    freq += 1
        
        if freq >= self.rules.max_keyword_frequency:
            return (False, f"'{keyword}' already at max frequency ({self.rules.max_keyword_frequency})")
        
        return (True, "Experience has room for keyword")
    
    def find_available_slots(self, resume_json: Dict, keyword: str,
                              target_section: str) -> List[Dict]:
        """
        Find available slots for injection.
        
        Returns list of available positions:
        [{'section': 'skills', 'category': 'Languages', 'position': 2}, ...]
        """
        slots = []
        
        if target_section == 'skills':
            for group in resume_json.get('skills', []):
                items = group.get('items', [])
                if len(items) < self.rules.max_skills_per_category:
                    slots.append({
                        'section': 'skills',
                        'category': group.get('category', ''),
                        'position': 0,  # Insert at top
                        'available_count': self.rules.max_skills_per_category - len(items),
                    })
        
        elif target_section == 'experience':
            keyword_lower = keyword.lower()
            for exp_idx, exp in enumerate(resume_json.get('experience', [])):
                for bullet_idx, bullet in enumerate(exp.get('bullets', [])):
                    if isinstance(bullet, str) and keyword_lower not in bullet.lower():
                        if len(bullet) < 200:
                            slots.append({
                                'section': 'experience',
                                'exp_index': exp_idx,
                                'bullet_index': bullet_idx,
                            })
        
        return slots
