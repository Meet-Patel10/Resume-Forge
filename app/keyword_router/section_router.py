"""
Section Router - Routes keywords to resume sections based on type and tier.

Hard skills → Skills section
Domain terms → Summary/Experience
Soft skills → Experience/Summary (NEVER Skills)
"""

from typing import Dict, List, Tuple
from app.extractors.keyword_models import ExtractedKeyword, KeywordType, Tier

class SectionRouter:
    """Route keywords to resume sections."""
    
    def route(self, keywords: List[ExtractedKeyword]) -> Dict[str, List[ExtractedKeyword]]:
        """
        Route keywords to target sections.
        
        Returns: {
            'skills': [...],         # Hard skills (MUST_HAVE + IMPORTANT only)
            'summary': [...],        # Domain terms + soft skills
            'experience': [...],     # All tiers can go here
            'excluded': [...],       # Soft skills, NICE_TO_HAVE (depending on strategy)
        }
        """
        
        routed = {
            'skills': [],
            'summary': [],
            'experience': [],
            'excluded': [],
        }
        
        for keyword in keywords:
            targets = self._get_routing_decision(keyword)
            
            for target in targets:
                routed[target].append(keyword)
        
        return routed
    
    def _get_routing_decision(self, keyword: ExtractedKeyword) -> List[str]:
        """Determine routing for a single keyword."""
        
        # HARD RULE: Soft skills NEVER in Skills section
        if keyword.keyword_type == KeywordType.SOFT_SKILL:
            if keyword.tier in [Tier.MUST_HAVE, Tier.IMPORTANT]:
                return ['summary', 'experience']
            else:
                return ['experience']
        
        # Hard skills → Skills section (MUST_HAVE + IMPORTANT)
        if keyword.keyword_type in [KeywordType.HARD_SKILL, KeywordType.TOOL_PLATFORM]:
            if keyword.tier == Tier.MUST_HAVE:
                return ['skills', 'experience']
            elif keyword.tier == Tier.IMPORTANT:
                return ['skills', 'experience']
            else:  # NICE_TO_HAVE
                return ['experience']
        
        # Domain terms → Summary/Experience
        if keyword.keyword_type == KeywordType.DOMAIN_TERM:
            if keyword.tier in [Tier.MUST_HAVE, Tier.IMPORTANT]:
                return ['summary', 'experience']
            else:
                return ['experience']
        
        # Catch-all
        return ['experience']
