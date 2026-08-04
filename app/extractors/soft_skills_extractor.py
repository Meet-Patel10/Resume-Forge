# FILE: app/extractors/soft_skills_extractor.py

import re
from typing import Dict, List, Set

class SoftSkillsExtractor:
    """
    Extracts soft skills from job descriptions.
    Maps keywords to soft skill categories.
    """
    
    # Soft skills dictionary: skill name → list of keywords
    SOFT_SKILLS_DICT = {
        'curiosity': {
            'keywords': [
                'curiosity', 'curious', 'inquisitive', 'eager to learn',
                'thirst for knowledge', 'love learning', 'learning mindset'
            ],
            'importance': 'critical'
        },
        'innovation': {
            'keywords': [
                'innovative', 'innovation', 'creative', 'creativity',
                'think outside the box', 'novel solutions', 'pioneering',
                'disruptive', 'forward thinking'
            ],
            'importance': 'critical'
        },
        'collaboration': {
            'keywords': [
                'collaborative', 'collaboration', 'teamwork', 'team player',
                'cross-functional', 'work with teams', 'communicate with',
                'partner with', 'work across', 'together'
            ],
            'importance': 'critical'
        },
        'mentoring': {
            'keywords': [
                'mentor', 'mentorship', 'coach', 'coaching', 'guide others',
                'share knowledge', 'knowledge sharing', 'lead by example',
                'develop others', 'grow the team'
            ],
            'importance': 'important'
        },
        'communication': {
            'keywords': [
                'communication', 'communicate', 'articulate', 'clear writing',
                'presentation', 'present', 'explain', 'convey', 'speak clearly'
            ],
            'importance': 'important'
        },
        'problem_solving': {
            'keywords': [
                'problem solving', 'solve problems', 'problem-solver',
                'troubleshoot', 'analytical', 'analytical thinking',
                'logical thinking', 'critical thinking', 'solve challenges'
            ],
            'importance': 'important'
        },
        'adaptability': {
            'keywords': [
                'adapt', 'adaptable', 'flexibility', 'flexible', 'pivot',
                'agile', 'quickly learn', 'adjust', 'dynamic environment'
            ],
            'importance': 'important'
        },
        'accountability': {
            'keywords': [
                'accountability', 'responsible', 'responsibility',
                'take ownership', 'own your work', 'deliver results',
                'follow through', 'reliable', 'dependable'
            ],
            'importance': 'important'
        }
    }
    
    def __init__(self):
        """Initialize the extractor with all soft skills."""
        self.all_skills = list(self.SOFT_SKILLS_DICT.keys())
    
    def extract_from_text(self, text: str) -> Dict[str, Dict]:
        """
        Extract soft skills from job description text.
        
        Returns:
        {
            'curiosity': {'found': True, 'importance': 'critical'},
            'collaboration': {'found': True, 'importance': 'critical'},
            ...
        }
        """
        found_skills = {}
        text_lower = text.lower()
        
        for skill_name, skill_info in self.SOFT_SKILLS_DICT.items():
            keywords = skill_info['keywords']
            importance = skill_info['importance']
            
            # Check if ANY keyword appears in text
            found = any(
                re.search(r'\b' + re.escape(keyword) + r'\b', text_lower)
                for keyword in keywords
            )
            
            found_skills[skill_name] = {
                'found': found,
                'importance': importance,
                'keywords_matched': [
                    kw for kw in keywords 
                    if re.search(r'\b' + re.escape(kw) + r'\b', text_lower)
                ] if found else []
            }
        
        return found_skills
    
    def get_missing_soft_skills(self, text: str) -> List[str]:
        """Return list of soft skills NOT mentioned in JD."""
        found = self.extract_from_text(text)
        return [skill for skill, data in found.items() if not data['found']]
    
    def get_emphasized_soft_skills(self, text: str) -> List[str]:
        """Return list of soft skills MENTIONED in JD."""
        found = self.extract_from_text(text)
        return [skill for skill, data in found.items() if data['found']]


# USAGE EXAMPLE:
if __name__ == "__main__":
    extractor = SoftSkillsExtractor()
    
    jd_text = """
    We're looking for a curious developer with a passion to challenge the status quo.
    You'll collaborate with cross-functional teams and mentor junior developers.
    Strong communication skills are essential.
    """
    
    skills = extractor.extract_from_text(jd_text)
    print("Found soft skills:")
    for skill, data in skills.items():
        if data['found']:
            print(f"  ✓ {skill} (importance: {data['importance']})")
    
    print("\nMissing soft skills:")
    for skill in extractor.get_missing_soft_skills(jd_text):
        print(f"  ✗ {skill}")