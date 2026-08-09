"""
JD Structure Parser - Parse job description into sections.

Returns structured sections with clear boundaries for Approach 2 (semantic) extraction.
"""

import re
from typing import Dict, List, Optional
from .keyword_models import JDSection

class JDStructureParser:
    """
    Parse JD into sections: Title, Summary, Requirements, Responsibilities, Preferred.
    
    Why: Approach 2 needs to distinguish "required" (weight=3) from "preferred" (weight=1).
    This is CRITICAL for must-have detection.
    """
    
    # Section headers to look for
    SECTION_HEADERS = {
        'requirements': [
            r'requirements', r'qualifications', r'what you[\'"]?ll bring',
            r'must have', r'required skills', r'essential skills'
        ],
        'responsibilities': [
            r'responsibilities', r'what you[\'"]?ll do', r'your role',
            r'day-to-day', r'core activities'
        ],
        'preferred': [
            r'preferred', r'nice to have', r'bonus', r'would be great',
            r'additional', r'desired'
        ],
        'summary': [
            r'about the role', r'overview', r'introduction', r'^(about|we[\'"]?re hiring)'
        ],
    }
    
    def __init__(self):
        pass
    
    def parse(self, jd_text: str) -> Dict[str, JDSection]:
        """
        Parse JD into sections.
        
        Returns:
        {
            'title': JDSection(name='title', weight=3, text='...', keywords=[]),
            'summary': JDSection(name='summary', weight=1, text='...'),
            'requirements': JDSection(name='requirements', weight=3, text='...'),
            'responsibilities': JDSection(name='responsibilities', weight=2, text='...'),
            'preferred': JDSection(name='preferred', weight=0, text='...'),
        }
        
        Weight system (CRITICAL for Approach 2):
        - Title (3): Job title defines the role
        - Requirements (3): Explicitly required qualifications
        - Responsibilities (2): What you'll do (implied requirement)
        - Summary (1): Nice context but lower priority
        - Preferred (0): Explicitly optional
        """
        
        sections = {}
        
        # Extract title (usually first line or after "Position:" / "Job Title:")
        title_match = re.search(
            r'^(?:Position|Job Title|Title)[\s:]*(.+?)(?:\n|$)',
            jd_text,
            re.IGNORECASE | re.MULTILINE
        )
        title_text = title_match.group(1).strip() if title_match else ""
        sections['title'] = JDSection(
            name='title',
            weight=3,
            text=title_text,
            keywords=[]
        )
        
        # Find section boundaries
        section_positions = {}
        for section_name, patterns in self.SECTION_HEADERS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, jd_text, re.IGNORECASE | re.MULTILINE):
                    # Find the line that contains this match
                    line_start = jd_text.rfind('\n', 0, match.start()) + 1
                    pos = line_start
                    if pos not in section_positions:
                        section_positions[pos] = (section_name, match.start())
                    break  # Use first pattern match for this section
        
        # Extract text for each section
        sorted_positions = sorted(section_positions.keys())
        
        for idx, start_pos in enumerate(sorted_positions):
            section_name, header_pos = section_positions[start_pos]
            
            # Find end of this section (start of next section or end of text)
            if idx < len(sorted_positions) - 1:
                end_pos = sorted_positions[idx + 1]
            else:
                end_pos = len(jd_text)
            
            # Extract section text (skip header line)
            section_text_start = jd_text.find('\n', header_pos) + 1
            section_text = jd_text[section_text_start:end_pos].strip()
            
            # Weight by section type
            weights = {
                'requirements': 3,
                'responsibilities': 2,
                'summary': 1,
                'preferred': 0,
            }
            weight = weights.get(section_name, 1)
            
            if section_name not in sections:
                sections[section_name] = JDSection(
                    name=section_name,
                    weight=weight,
                    text=section_text,
                    keywords=[]
                )
        
        return sections
    
    def get_section_text(self, jd_text: str, section_name: str) -> Optional[str]:
        """Get text for a specific section."""
        sections = self.parse(jd_text)
        return sections.get(section_name, {}).text if section_name in sections else None
