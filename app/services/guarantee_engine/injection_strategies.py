"""
Injection Strategies - Multi-strategy pattern for injecting missing keywords.

Phase 6.5 Component 2: Strategic placement of keywords in correct resume sections.

Strategies:
- SkillsInjectionStrategy: hard skills → Technical Skills section
- ExperienceInjectionStrategy: domain terms → Experience bullets
- SummaryInjectionStrategy: conceptual terms → Summary
- FallbackInjectionStrategy: last resort if primary target full
"""

from typing import Dict, List, Optional, Tuple
import re


# Category mapping for skill placement
SKILL_CATEGORY_MAP = {
    # Programming Languages
    'python': 'Languages', 'java': 'Languages', 'javascript': 'Languages',
    'typescript': 'Languages', 'c++': 'Languages', 'c#': 'Languages',
    'go': 'Languages', 'rust': 'Languages', 'ruby': 'Languages',
    'scala': 'Languages', 'kotlin': 'Languages', 'swift': 'Languages',
    'php': 'Languages', 'sql': 'Languages', 'r': 'Languages',
    'html': 'Languages', 'html5': 'Languages', 'css': 'Languages',
    'css3': 'Languages', 'bash': 'Languages', 'shell': 'Languages',
    'c programming': 'Languages', 'matlab': 'Languages',
    
    # Frameworks & Libraries
    'react': 'Frameworks & Libraries', 'angular': 'Frameworks & Libraries',
    'vue': 'Frameworks & Libraries', 'vue.js': 'Frameworks & Libraries',
    'spring boot': 'Frameworks & Libraries', 'spring': 'Frameworks & Libraries',
    'django': 'Frameworks & Libraries', 'flask': 'Frameworks & Libraries',
    'fastapi': 'Frameworks & Libraries', 'express': 'Frameworks & Libraries',
    'node.js': 'Frameworks & Libraries', 'next.js': 'Frameworks & Libraries',
    'pytorch': 'Frameworks & Libraries', 'tensorflow': 'Frameworks & Libraries',
    'jquery': 'Frameworks & Libraries', '.net': 'Frameworks & Libraries',
    'bootstrap': 'Frameworks & Libraries', 'restful apis': 'Frameworks & Libraries',
    
    # Tools & Platforms
    'docker': 'Tools & Platforms', 'kubernetes': 'Tools & Platforms',
    'aws': 'Tools & Platforms', 'azure': 'Tools & Platforms',
    'gcp': 'Tools & Platforms', 'google cloud': 'Tools & Platforms',
    'git': 'Tools & Platforms', 'github': 'Tools & Platforms',
    'jenkins': 'Tools & Platforms', 'jira': 'Tools & Platforms',
    'linux': 'Tools & Platforms', 'terraform': 'Tools & Platforms',
    'postman': 'Tools & Platforms', 'grafana': 'Tools & Platforms',
    'mysql': 'Tools & Platforms', 'postgresql': 'Tools & Platforms',
    'mongodb': 'Tools & Platforms', 'redis': 'Tools & Platforms',
    'kafka': 'Tools & Platforms', 'elasticsearch': 'Tools & Platforms',
    'maven': 'Tools & Platforms', 'gradle': 'Tools & Platforms',
    
    # Programming Concepts
    'data structures': 'Programming Concepts',
    'algorithms': 'Programming Concepts',
    'object-oriented programming': 'Programming Concepts',
    'oop': 'Programming Concepts',
    'multithreading': 'Programming Concepts',
    'design patterns': 'Programming Concepts',
    'memory management': 'Programming Concepts',
    
    # Concepts
    'ci/cd': 'Concepts', 'ci/cd pipelines': 'Concepts',
    'agile': 'Concepts', 'scrum': 'Concepts',
    'microservices': 'Concepts', 'machine learning': 'Concepts',
    'deep learning': 'Concepts', 'distributed systems': 'Concepts',
    'test-driven development': 'Concepts', 'tdd': 'Concepts',
    'sdlc': 'Concepts', 'software development lifecycle': 'Concepts',
}


def skills_injection_strategy(resume_json: Dict, keyword: str,
                               keyword_metadata: Optional[Dict] = None) -> Tuple[bool, str]:
    """
    Skills Injection Strategy: Add hard skill to Technical Skills section.
    
    Step 1: Categorize the keyword (Language, Framework, Tool, Concept)
    Step 2: Find target category in resume.skills
    Step 3: Check density (< 8 items)
    Step 4: Insert at top (JD skills first)
    Step 5: Return success/failure
    
    Returns: (success: bool, reason: str)
    """
    keyword_lower = keyword.lower().strip()
    
    # Step 1: Determine category
    category = SKILL_CATEGORY_MAP.get(keyword_lower)
    if not category:
        # Fuzzy match
        for key, cat in SKILL_CATEGORY_MAP.items():
            if key in keyword_lower or keyword_lower in key:
                category = cat
                break
    if not category:
        # Default: multi-word → Concepts, single word → Tools
        category = 'Concepts' if len(keyword.split()) >= 2 else 'Tools & Platforms'
    
    skills = resume_json.get('skills', [])
    
    # Step 2: Find target category
    target_group = None
    for group in skills:
        if group.get('category', '').lower() == category.lower():
            target_group = group
            break
    
    if not target_group:
        # Try partial match
        cat_first = category.split()[0].lower()
        for group in skills:
            if group.get('category', '').lower().startswith(cat_first):
                target_group = group
                break
    
    if not target_group:
        # Create new category if < 7 categories total
        if len(skills) < 7:
            target_group = {'category': category, 'items': []}
            skills.append(target_group)
        else:
            return (False, f"No category '{category}' found and max categories reached")
    
    # Step 3: Check density
    if len(target_group.get('items', [])) >= 8:
        return (False, f"Category '{category}' full (8 items)")
    
    # Step 4: Check for duplicate
    existing_lower = {item.lower() for item in target_group.get('items', [])}
    if keyword_lower in existing_lower:
        return (False, f"'{keyword}' already in {category}")
    # Fuzzy dedup
    for existing in existing_lower:
        if keyword_lower in existing or existing in keyword_lower:
            return (False, f"'{keyword}' variant already in {category} as '{existing}'")
    
    # Step 5: Insert at top
    target_group['items'].insert(0, keyword)
    return (True, f"Injected '{keyword}' into {category}")


def experience_injection_strategy(resume_json: Dict, keyword: str,
                                   keyword_metadata: Optional[Dict] = None) -> Tuple[bool, str]:
    """
    Experience Injection Strategy: Add domain term to experience bullets.
    
    Step 1: Find best experience bullet (related context)
    Step 2: Inject naturally using connector words
    Step 3: Avoid duplication
    
    Returns: (success: bool, reason: str)
    """
    keyword_lower = keyword.lower()
    
    # Check current frequency in experience
    freq = 0
    for exp in resume_json.get('experience', []):
        for bullet in exp.get('bullets', []):
            if isinstance(bullet, str) and keyword_lower in bullet.lower():
                freq += 1
    
    if freq >= 4:
        return (False, f"'{keyword}' already at max frequency (4) in experience")
    
    # Find best bullet to inject into (most recent role, bullet without keyword yet)
    for exp in resume_json.get('experience', []):
        bullets = exp.get('bullets', [])
        for i, bullet in enumerate(bullets):
            if isinstance(bullet, str) and keyword_lower not in bullet.lower():
                # Check bullet doesn't already have too many keywords
                if len(bullet) < 200:  # Not already too long
                    # Inject by appending keyword context
                    # Use simple append with connector
                    if bullet.rstrip().endswith('.'):
                        bullet = bullet.rstrip()[:-1]
                    
                    # Natural connector
                    connectors = [' using ', ' leveraging ', ' with ']
                    connector = connectors[i % len(connectors)]
                    
                    exp['bullets'][i] = bullet + connector + keyword
                    return (True, f"Injected '{keyword}' into experience bullet")
    
    return (False, f"No suitable experience bullet found for '{keyword}'")


def summary_injection_strategy(resume_json: Dict, keyword: str,
                                keyword_metadata: Optional[Dict] = None) -> Tuple[bool, str]:
    """
    Summary Injection Strategy: Add conceptual term to summary.
    
    Checks 20% keyword density limit before injecting.
    
    Returns: (success: bool, reason: str)
    """
    summary = resume_json.get('summary', '')
    if not summary:
        return (False, "No summary section to inject into")
    
    keyword_lower = keyword.lower()
    
    # Check if already present
    if keyword_lower in summary.lower():
        return (False, f"'{keyword}' already in summary")
    
    # Check density (max 20%)
    summary_words = len(summary.split())
    # Count existing keywords in summary (rough estimate)
    max_keyword_words = summary_words * 0.20
    
    keyword_word_count = len(keyword.split())
    
    # Simple density check
    if summary_words > 0 and keyword_word_count > max_keyword_words:
        return (False, f"Summary too dense for '{keyword}'")
    
    # Don't modify summary (it's locked per the system prompt)
    # Instead, just verify presence
    return (False, f"Summary is locked — cannot inject '{keyword}'")


def fallback_injection_strategy(resume_json: Dict, keyword: str,
                                 keyword_metadata: Optional[Dict] = None) -> Tuple[bool, str]:
    """
    Fallback Strategy: Last resort if all other strategies fail.
    
    Tries:
    1. Add to least-full skills category
    2. Add to projects section
    3. Create "Additional Skills" category
    
    Returns: (success: bool, reason: str)
    """
    keyword_lower = keyword.lower()
    
    # Strategy 1: Find least-full skills category
    skills = resume_json.get('skills', [])
    least_full = None
    min_count = 999
    
    for group in skills:
        items = group.get('items', [])
        if len(items) < min_count and len(items) < 8:
            # Check not already there
            if keyword_lower not in {item.lower() for item in items}:
                min_count = len(items)
                least_full = group
    
    if least_full:
        least_full['items'].append(keyword)
        return (True, f"Fallback: added '{keyword}' to {least_full.get('category', 'unknown')} (least full)")
    
    # Strategy 2: Try projects
    for proj in resume_json.get('projects', []):
        bullets = proj.get('bullets', [])
        for i, bullet in enumerate(bullets):
            if isinstance(bullet, str) and keyword_lower not in bullet.lower():
                if len(bullet) < 200:
                    if bullet.rstrip().endswith('.'):
                        bullet = bullet.rstrip()[:-1]
                    proj['bullets'][i] = bullet + ' with ' + keyword
                    return (True, f"Fallback: injected '{keyword}' into project bullet")
    
    # Strategy 3: Create "Additional Skills" category
    additional = None
    for group in skills:
        if 'additional' in group.get('category', '').lower():
            additional = group
            break
    
    if not additional and len(skills) < 7:
        additional = {'category': 'Additional Skills', 'items': []}
        skills.append(additional)
    
    if additional and len(additional.get('items', [])) < 8:
        if keyword_lower not in {item.lower() for item in additional.get('items', [])}:
            additional['items'].append(keyword)
            return (True, f"Fallback: added '{keyword}' to Additional Skills")
    
    return (False, f"All injection strategies failed for '{keyword}'")
