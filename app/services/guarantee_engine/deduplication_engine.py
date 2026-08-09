"""
Deduplication Engine - Handle skill variations and prevent duplicates.

Phase 6.5 Component 4: Normalizes skill names and removes duplicates.

Handles variations like:
- "Python" = "Python 3" = "Python 3.8+"
- "Kubernetes" = "K8s"
- "AWS" = "Amazon Web Services"
"""

import re
from typing import Dict, List, Set, Tuple


# Variation mapping for common skill name differences
SKILL_VARIATION_MAP = {
    # Programming Languages
    'python 3': 'python', 'python 3.8+': 'python', 'python3': 'python',
    'js': 'javascript', 'ecmascript': 'javascript',
    'c plus plus': 'c++', 'cpp': 'c++',
    'c sharp': 'c#', 'csharp': 'c#',
    'golang': 'go',
    'ts': 'typescript',
    
    # Frameworks
    'react.js': 'react', 'reactjs': 'react',
    'vue.js': 'vue', 'vuejs': 'vue',
    'angular.js': 'angular', 'angularjs': 'angular',
    'node': 'node.js', 'nodejs': 'node.js',
    'express.js': 'express', 'expressjs': 'express',
    'next': 'next.js', 'nextjs': 'next.js',
    
    # Databases
    'postgres': 'postgresql', 'postgresql (postgres)': 'postgresql',
    'mongo': 'mongodb', 'mongo db': 'mongodb',
    'mysql database': 'mysql',
    
    # Cloud
    'amazon web services': 'aws', 'amazon web services (aws)': 'aws',
    'google cloud': 'gcp', 'google cloud platform': 'gcp',
    'microsoft azure': 'azure',
    
    # Orchestration
    'k8s': 'kubernetes', 'k8': 'kubernetes',
    'docker orchestration': 'docker swarm',
    
    # CI/CD
    'ci/cd pipelines': 'ci/cd',
    'continuous integration/deployment': 'ci/cd',
    'continuous integration': 'ci/cd',
    
    # OOP
    'object-oriented programming (oop)': 'object-oriented programming',
    'oop': 'object-oriented programming',
    
    # SDLC
    'software development lifecycle (sdlc)': 'sdlc',
    'software development lifecycle': 'sdlc',
    
    # TDD
    'test-driven development (tdd)': 'test-driven development',
    'tdd': 'test-driven development',
    
    # REST
    'rest apis': 'restful apis', 'rest api': 'restful apis',
}


class DeduplicationEngine:
    """
    Handle skill variations and prevent duplicates.
    """
    
    def normalize_skill(self, skill_name: str) -> str:
        """
        Normalize a skill name to its canonical form.
        
        Steps:
        1. Lowercase
        2. Strip whitespace
        3. Expand abbreviations via VARIATION_MAP
        4. Remove parenthetical abbreviations
        """
        normalized = skill_name.lower().strip()
        
        # Check variation map
        if normalized in SKILL_VARIATION_MAP:
            return SKILL_VARIATION_MAP[normalized]
        
        # Remove parenthetical abbreviations: "Amazon Web Services (AWS)" → "amazon web services"
        without_parens = re.sub(r'\s*\([^)]*\)\s*', '', normalized).strip()
        if without_parens in SKILL_VARIATION_MAP:
            return SKILL_VARIATION_MAP[without_parens]
        
        # If the version without parens is different, check the map
        if without_parens != normalized:
            return without_parens
        
        return normalized
    
    def find_duplicates(self, resume_json: Dict) -> List[Tuple[str, str, str]]:
        """
        Find duplicate skills across all categories.
        
        Returns: List of (skill1, skill2, category) tuples that are duplicates.
        """
        duplicates = []
        seen = {}  # normalized → (original_name, category)
        
        for group in resume_json.get('skills', []):
            category = group.get('category', '')
            for item in group.get('items', []):
                normalized = self.normalize_skill(item)
                if normalized in seen:
                    original, orig_cat = seen[normalized]
                    duplicates.append((original, item, f"{orig_cat} / {category}"))
                else:
                    seen[normalized] = (item, category)
        
        return duplicates
    
    def is_duplicate(self, keyword: str, resume_json: Dict) -> bool:
        """
        Check if a keyword (or its variation) already exists in the resume.
        """
        keyword_normalized = self.normalize_skill(keyword)
        
        for group in resume_json.get('skills', []):
            for item in group.get('items', []):
                if self.normalize_skill(item) == keyword_normalized:
                    return True
        
        return False
    
    def deduplicate_skills(self, resume_json: Dict) -> Tuple[Dict, int]:
        """
        Remove duplicate skills from resume, keeping the more complete version.
        
        Returns: (cleaned_resume_json, duplicates_removed_count)
        """
        removed_count = 0
        seen_normalized = {}  # normalized → (original_name, group_ref)
        
        for group in resume_json.get('skills', []):
            deduped_items = []
            category = group.get('category', '')
            
            for item in group.get('items', []):
                normalized = self.normalize_skill(item)
                
                if normalized in seen_normalized:
                    # Duplicate found — keep the more complete version
                    existing, existing_cat = seen_normalized[normalized]
                    if len(item) > len(existing):
                        # New version is more complete — replace
                        # Remove from old location
                        for other_group in resume_json.get('skills', []):
                            if existing in other_group.get('items', []):
                                other_group['items'].remove(existing)
                                break
                        deduped_items.append(item)
                        seen_normalized[normalized] = (item, category)
                    # else: skip this duplicate (keep existing)
                    removed_count += 1
                else:
                    deduped_items.append(item)
                    seen_normalized[normalized] = (item, category)
            
            group['items'] = deduped_items
        
        # Remove empty groups
        resume_json['skills'] = [g for g in resume_json.get('skills', []) if g.get('items')]
        
        return resume_json, removed_count
