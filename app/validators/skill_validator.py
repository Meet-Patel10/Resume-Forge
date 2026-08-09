"""
Skill Validator — Validates individual skills before adding to resume.
Prevents nonsense skills like "end interfaces", "product teams", etc.

Implements:
- CHUNK 4.1: Skill Validation Rules
- CHUNK 4.2: validate_skill() Function
- CHUNK 4.4: Post-Processing Cleanup
"""

import re


# ═══════════════════════════════════════════════════════════════════
# CHUNK 4.1: Create Skill Validation Rules
# Defines what makes a valid skill
# ═══════════════════════════════════════════════════════════════════

# Define valid skill characteristics
SKILL_VALIDATION_RULES = {
    'min_length': 2,              # At least 2 characters
    'max_length': 100,            # Max 100 characters (prevents long phrases)
    'max_words': 5,               # Max 5 words (prevents fragments like "and implement cloud")
    'required_content': 'letters', # Must contain letters
}

# Rejection patterns (things that are NOT skills)
# ═══════════════════════════════════════════════════════════════════
# CHUNK 8.1: Comprehensive Rejection Patterns
# Prevents fragments, connectors, and non-skills from being accepted
# ═══════════════════════════════════════════════════════════════════

REJECT_PATTERNS = [
    # Fragment patterns
    r'^end\s',                    # "end interfaces", "end system"
    r'stack\s+or\s',              # "stack or backend"
    r'^and\s',                    # "and implement", "and configure"
    r'^\s*with\s',                # "with cloud platforms"
    r'^or\s',                     # "or backend"
    r'^the\s',                    # "the system"
    r'^a\s',                      # "a framework"
    r'^an\s',                     # "an approach"
    r'^to\s',                     # "to implement"
    r'^of\s',                     # "of the"
    r'^in\s',                     # "in production"
    r'^for\s',                    # "for deployment"
    
    # Team/role patterns (not skills)
    r'product\s+teams',           # "product teams"
    r'functional\s+teams',        # "functional teams"
    r'engineering\s+teams',       # "engineering teams"
    r'cross.functional',          # "cross-functional" (as standalone)
    
    # Incomplete phrase patterns
    r'focusing\s+on',             # "focusing on"
    r'based\s+on',                # "based on"
    r'involved\s+in',             # "involved in"
    r'responsible\s+for',         # "responsible for"
    r'working\s+with',            # "working with"
    r'experience\s+with',         # "experience with"
    r'knowledge\s+of',            # "knowledge of"
    
    # Ability/generic patterns
    r'able\s+to',                 # "able to X"
    r'\d+\s+hour',                # "10 hours weekly"
    r'solving\s+for',             # "solving for X"
    r'\d+\s+year',                # "5 years experience"
    
    # Outcome patterns (not skills)
    r'system\s+reliability',      # "system reliability"
    r'code\s+quality',            # "code quality"
    r'best\s+practices',          # "best practices"
]

# Known non-skills (too generic or not technical)
NON_SKILLS = {
    'team', 'ability', 'capability', 'experience',
    'potential', 'knowledge', 'skill', 'expertise',
    'proficiency', 'strong', 'good', 'excellent',
    'understanding', 'awareness', 'familiarity',
    'background', 'exposure', 'competency',
    'quality', 'efficiency', 'reliability',
    'performance', 'scalability', 'productivity',
}

# ═══════════════════════════════════════════════════════════════════
# CHUNK 8.2: Confidence Scoring for Extracted Keywords
# Higher confidence = more likely a real skill
# ═══════════════════════════════════════════════════════════════════

def calculate_skill_confidence(skill_text):
    """
    Calculate confidence score for an extracted skill.
    
    Returns: float (0.0 to 1.0) where 1.0 = definitely a skill
    """
    score = 0.5  # Base score
    
    # Known pattern match = high confidence
    for pattern in VALID_SKILL_PATTERNS:
        if re.search(pattern, skill_text, re.IGNORECASE):
            score += 0.4
            break
    
    # Short, specific terms = higher confidence
    words = skill_text.split()
    if len(words) == 1:
        score += 0.1  # Single words are often real skills
    elif len(words) > 3:
        score -= 0.2  # Long phrases less likely to be skills
    
    # Contains numbers/versions = higher confidence (e.g., "Python 3", "ES6")
    if re.search(r'\d', skill_text):
        score += 0.1
    
    return min(1.0, max(0.0, score))


# ═══════════════════════════════════════════════════════════════════
# CHUNK 8.3: Known-Pattern Matching (expanded)
# Extended known valid patterns for better coverage
# ═══════════════════════════════════════════════════════════════════

# Known valid skill patterns
VALID_SKILL_PATTERNS = [
    r'python|java|javascript|go|rust|kotlin|scala',  # Languages
    r'react|angular|vue|svelte|ember',               # Frontend
    r'docker|kubernetes|jenkins|aws|gcp|azure',      # DevOps
    r'mongodb|postgresql|mysql|redis|cassandra',     # Databases
    r'microservice|api|rest|grpc|graphql',           # Architecture
    r'oop|design\s+pattern|algorithm|data\s+structure', # Concepts
    r'typescript|swift|objective.c|ruby|php|perl',   # More languages
    r'flask|django|spring|express|fastapi|rails',    # Frameworks
    r'terraform|ansible|puppet|chef|vagrant',        # IaC
    r'kafka|rabbitmq|celery|airflow',                # Message queues
    r'git|github|gitlab|bitbucket|svn',              # Version control
    r'linux|unix|bash|shell|powershell',             # OS/Shell
    r'ci.cd|devops|sre|agile|scrum|kanban',          # Methodologies
    r'machine\s+learning|deep\s+learning|nlp|cv',    # ML/AI
    r'sql|nosql|elasticsearch|solr|neo4j',           # Data
]


# ═══════════════════════════════════════════════════════════════════
# CHUNK 4.2: Implement validate_skill() Function
# Validates individual skill, returns true/false + reason
# ═══════════════════════════════════════════════════════════════════

def validate_skill(skill_text, skill_type=None):
    """
    Validate that a skill is real and not corrupted/nonsensical
    
    Args:
        skill_text: The skill name/phrase
        skill_type: Type (HARD_SKILL, SOFT_SKILL, etc.)
    
    Returns:
        (is_valid: bool, reason: str)
    """
    if not skill_text:
        return False, "Empty skill"
    
    skill_text = skill_text.strip()
    
    # Length check
    if len(skill_text) < SKILL_VALIDATION_RULES['min_length']:
        return False, f"Too short: '{skill_text}'"
    
    if len(skill_text) > SKILL_VALIDATION_RULES['max_length']:
        return False, f"Too long: '{skill_text}'"
    
    # Word count check
    words = skill_text.split()
    if len(words) > SKILL_VALIDATION_RULES['max_words']:
        return False, f"Too many words ({len(words)}): '{skill_text}'"
    
    # Rejection pattern check
    for pattern in REJECT_PATTERNS:
        if re.search(pattern, skill_text, re.IGNORECASE):
            return False, f"Matches rejection pattern: {pattern}"
    
    # Non-skill check
    if skill_text.lower() in NON_SKILLS:
        return False, f"Generic non-skill: '{skill_text}'"
    
    # Must contain letters
    if not re.search(r'[a-zA-Z]', skill_text):
        return False, f"No letters: '{skill_text}'"
    
    # Bonus: Matches known pattern
    is_known_pattern = any(
        re.search(pattern, skill_text, re.IGNORECASE)
        for pattern in VALID_SKILL_PATTERNS
    )
    
    # If matches known pattern, definitely valid
    if is_known_pattern:
        return True, "Valid (known pattern)"
    
    # If matches none, but passes checks, accept cautiously
    if len(words) <= 3:  # Short phrase
        return True, "Valid (passes basic checks)"
    
    # Long phrase without pattern match
    return False, f"Unknown skill pattern: '{skill_text}'"


# ═══════════════════════════════════════════════════════════════════
# CHUNK 4.4: Post-Processing Cleanup
# Catches any remaining bad patterns in final output
# ═══════════════════════════════════════════════════════════════════

def cleanup_skills_section(skills_dict):
    """
    Final cleanup of skills section before output
    
    Catches any remaining bad patterns
    """
    cleaned = {}
    
    for category, skills_list in skills_dict.items():
        cleaned_skills = []
        
        for skill in skills_list:
            # Double-check validation
            is_valid, _ = validate_skill(skill)
            if is_valid:
                # Remove any trailing garbage
                skill = skill.rstrip('.,;:')
                skill = re.sub(r'\s+', ' ', skill)  # Normalize whitespace
                if skill and len(skill) > 1:
                    cleaned_skills.append(skill)
        
        if cleaned_skills:
            cleaned[category] = cleaned_skills
    
    return cleaned
