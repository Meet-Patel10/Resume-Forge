"""
Skill Validator — Validates individual skills before adding to resume.
Prevents nonsense skills like "end interfaces", "product teams", etc.

Implements (merged from the original AI_IMPLEMENTATION_GUIDE.md chunks,
already wired into app/routes/tailor.py:4187, and TASK_4_COMPLETE_SOLUTION.md's
more comprehensive patterns + confidence scoring):
- CHUNK 4.1: Skill Validation Rules (comprehensive rejection/valid patterns)
- CHUNK 4.2: validate_skill() — kept as the real, load-bearing 2-tuple API
  (is_valid, reason) since app/routes/tailor.py already unpacks it that way;
  validate_skill_with_confidence() added alongside for the 3-tuple version
- CHUNK 4.4: aggressive_cleanup() — final post-processing safety net over
  the real resume_json['skills'] shape (list of {category, items} dicts),
  wired into the tailor pipeline right before LaTeX rendering
"""

import re


# ═══════════════════════════════════════════════════════════════════
# CHUNK 4.1: Skill Validation Rules
# Defines what makes a valid skill
# ═══════════════════════════════════════════════════════════════════

SKILL_VALIDATION_RULES = {
    'min_length': 2,               # At least 2 characters
    'max_length': 50,              # Max 50 chars (prevents long phrases)
    'max_words': 4,                # Max 4 words (prevents fragments like "and implement cloud")
    'required_content': 'letters', # Must contain letters
}

# ═══════════════════════════════════════════════════════════════════
# CHUNK 8.1 / TASK 4: Comprehensive Rejection Patterns
# Prevents fragments, connectors, and non-skills from being accepted.
# Merged from both the original chunk set and TASK_4_COMPLETE_SOLUTION.md.
# ═══════════════════════════════════════════════════════════════════

REJECT_PATTERNS = [
    # Fragment patterns (starts with a connector/article — mid-sentence cut)
    r'^end\s',                    # "end interfaces", "end system"
    r'stack\s+or\s',               # "stack or backend"
    r'^\s*and\s',                  # "and implement", "and configure"
    r'^\s*with\s',                 # "with cloud platforms"
    r'^\s*or\s',                   # "or backend"
    r'^\s*the\s',                  # "the system"
    r'^\s*a\s',                    # "a framework"
    r'^\s*an\s',                   # "an approach"
    r'^\s*to\s',                   # "to implement"
    r'^\s*of\s',                   # "of the"
    r'^\s*in\s',                   # "in production"
    r'^\s*for\s',                  # "for deployment"
    r'^team\s+',                   # "team at", "team and"
    r'team\s+and',                 # "team and what we"
    r'will\s+',                    # "will contribute"
    r"'?ll\s+",                    # "'ll contribute"

    # Team/role patterns (not skills)
    r'product\s+teams',            # "product teams"
    r'functional\s+teams',         # "functional teams"
    r'engineering\s+teams',        # "engineering teams"
    r'cross.functional',           # "cross-functional" (as standalone)

    # Incomplete/truncated phrase patterns
    r'focusing\s+on',              # "focusing on"
    r'based\s+on',                 # "based on"
    r'involved\s+in',              # "involved in"
    r'responsible\s+for',          # "responsible for"
    r'working\s+with',             # "working with"
    r'experience\s+with',          # "experience with"
    r'knowledge\s+of',             # "knowledge of"
    r'\.\.\.',                     # ellipsis (truncation indicator)

    # Ability/generic patterns
    r'able\s+to',                  # "able to X"
    r'\d+\s+hour',                 # "10 hours weekly"
    r'solving\s+for',              # "solving for X"
    r'\d+\s+year',                 # "5 years experience"

    # Outcome patterns (not skills)
    r'system\s+reliability',       # "system reliability"
    r'code\s+quality',             # "code quality"
    r'best\s+practices',           # "best practices"
    r'communication\s+skills',     # "communication skills"
    r'solving\s+skills',           # "problem solving skills"

    # Structural/formatting rejects
    r'^(the|a|an|is|are|was|were|be|been|being)\s',
    r'(,|;|\.|:)\s*$',             # Ends with punctuation
    r'^\d+',                       # Starts with a number
    r'^\W+$',                      # Only special characters
    r'^\s*$',                      # Only whitespace
]

# ═══════════════════════════════════════════════════════════════════
# Known non-skills (too generic or not technical)
# ═══════════════════════════════════════════════════════════════════

NON_SKILLS = {
    'team', 'ability', 'capability', 'experience',
    'potential', 'knowledge', 'skill', 'expertise',
    'proficiency', 'strong', 'good', 'excellent',
    'understanding', 'awareness', 'familiarity',
    'background', 'exposure', 'competency',
    'quality', 'efficiency', 'reliability',
    'performance', 'scalability', 'productivity',
    'people', 'person', 'group', 'company', 'organization',
    'solution', 'system', 'application', 'software', 'process',
    'development', 'production', 'environment', 'platform',
}

# ═══════════════════════════════════════════════════════════════════
# CHUNK 8.3 / TASK 4: Known-Pattern Matching
# Extended known valid patterns for better coverage
# ═══════════════════════════════════════════════════════════════════

VALID_SKILL_PATTERNS = [
    r'python|java|javascript|go|rust|kotlin|scala',      # Languages
    r'typescript|swift|objective.c|ruby|php|perl',        # More languages
    r'c\+\+|c#',                                           # C-family
    r'react|angular|vue|svelte|ember',                     # Frontend
    r'docker|kubernetes|jenkins|aws|gcp|azure',            # DevOps
    r'flask|django|spring|express|fastapi|rails',          # Frameworks
    r'terraform|ansible|puppet|chef|vagrant',              # IaC
    r'kafka|rabbitmq|celery|airflow',                      # Message queues
    r'git|github|gitlab|bitbucket|svn',                    # Version control
    r'linux|unix|bash|shell|powershell',                   # OS/Shell
    r'mongodb|postgresql|mysql|redis|cassandra|oracle',    # Databases
    r'sql|nosql|elasticsearch|solr|neo4j',                 # Data
    r'microservice|rest\s*api|grpc|graphql',                # Architecture
    r'oop|design\s+pattern|algorithm|data\s+structure',    # Concepts
    r'ci.cd|devops|sre|agile|scrum|kanban',                # Methodologies
    r'machine\s+learning|deep\s+learning|nlp|\bcv\b',      # ML/AI
    r'authentication|encryption|security',                 # Security
    r'torch|tensorflow|keras|scikit-learn|pandas|numpy',   # ML frameworks
]


def calculate_skill_confidence(skill_text):
    """
    CHUNK 8.2 / TASK 4: Calculate confidence score for an extracted skill.

    Returns: float (0.0 to 1.0) where 1.0 = definitely a skill.
    """
    score = 0.5  # Base score

    # Known pattern match = high confidence
    for pattern in VALID_SKILL_PATTERNS:
        if re.search(pattern, skill_text, re.IGNORECASE):
            score += 0.4
            break

    # Tech indicator words = medium confidence bump (matches heuristics
    # from TASK_4_COMPLETE_SOLUTION.md, for skills that don't match a
    # known pattern but still look technical)
    tech_indicators = ['api', 'microservice', 'cloud', 'framework',
                        'library', 'database', 'protocol', 'architecture']
    if not any(re.search(p, skill_text, re.IGNORECASE) for p in VALID_SKILL_PATTERNS):
        for indicator in tech_indicators:
            if indicator in skill_text.lower():
                score = max(score, 0.75)
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

    # Suspicious connector words = lower confidence
    if any(f' {w} ' in f' {skill_text.lower()} ' for w in ('the', 'and', 'or')):
        score = min(score, 0.4)

    return min(1.0, max(0.0, score))


# ═══════════════════════════════════════════════════════════════════
# CHUNK 4.2: validate_skill() Function
# Validates individual skill, returns true/false + reason.
#
# NOTE: kept as a 2-tuple (is_valid, reason) — this is the real function
# already called at app/routes/tailor.py:4187 as
# `is_valid_skill, reject_reason = validate_skill(skill)`. Changing the
# return arity would break that call site. validate_skill_with_confidence()
# below provides the 3-tuple (is_valid, reason, confidence) version.
# ═══════════════════════════════════════════════════════════════════

def validate_skill(skill_text, skill_type=None):
    """
    Validate that a skill is real and not corrupted/nonsensical.

    Args:
        skill_text: The skill name/phrase
        skill_type: Type (HARD_SKILL, SOFT_SKILL, etc.) — currently unused,
            kept for signature compatibility with existing callers.

    Returns:
        (is_valid: bool, reason: str)
    """
    is_valid, reason, _confidence = validate_skill_with_confidence(skill_text)
    return is_valid, reason


def validate_skill_with_confidence(skill_text):
    """
    TASK 4: Validate a skill and return a confidence score alongside the
    decision, instead of the coarse "accept any short phrase" fallback the
    original chunk 4.2 used.

    Returns:
        (is_valid: bool, reason: str, confidence: float 0.0-1.0)
    """
    if not skill_text:
        return False, "Empty skill", 0.0

    skill = skill_text.strip()

    # Length checks
    if len(skill) < SKILL_VALIDATION_RULES['min_length']:
        return False, f"Too short: '{skill}'", 0.0

    if len(skill) > SKILL_VALIDATION_RULES['max_length']:
        return False, f"Too long: '{skill}'", 0.1

    # Only special characters / whitespace
    if not re.sub(r'[\W_\s]', '', skill):
        return False, "Only special characters", 0.0

    # Word count check
    words = skill.split()
    if len(words) > SKILL_VALIDATION_RULES['max_words']:
        return False, f"Too many words ({len(words)}): '{skill}'", 0.1

    # Rejection pattern check (highest priority)
    for pattern in REJECT_PATTERNS:
        if re.search(pattern, skill, re.IGNORECASE):
            return False, f"Matches rejection pattern: {pattern}", 0.05

    # Non-skill check (all words are generic non-skills)
    non_skill_words = sum(1 for w in words if w.lower() in NON_SKILLS)
    if non_skill_words == len(words):
        return False, f"Generic non-skill: '{skill}'", 0.05

    # Must contain letters
    if not re.search(r'[a-zA-Z]', skill):
        return False, f"No letters: '{skill}'", 0.0

    confidence = calculate_skill_confidence(skill)

    if confidence >= 0.7:
        return True, f"Valid (confidence={confidence:.2f})", confidence
    elif confidence >= 0.5:
        return True, f"Probably valid (confidence={confidence:.2f})", confidence
    else:
        return False, f"Low confidence (confidence={confidence:.2f})", confidence


# ═══════════════════════════════════════════════════════════════════
# CHUNK 4.4 / TASK 4: Post-Processing Cleanup
# Final safety net over the real resume_json['skills'] shape — catches
# nonsense skills regardless of which pipeline stage introduced them
# (AI tailoring output, master-skill preservation, guarantee engine
# injection, etc.), not just the ones added by the deterministic
# hard-skills-injection step that validate_skill() already gates.
# ═══════════════════════════════════════════════════════════════════

def aggressive_cleanup(resume_json, min_confidence=0.7):
    """
    Final cleanup pass: validate every skill in resume_json['skills'] and
    drop anything that doesn't pass, regardless of how it got there.

    Args:
        resume_json: Resume dict with a 'skills' key
            (list of {'category': str, 'items': [str, ...]})
        min_confidence: Minimum confidence threshold (default 0.7)

    Returns:
        The same resume_json dict, mutated in place, with 'skills' cleaned.
    """
    if not isinstance(resume_json, dict) or 'skills' not in resume_json:
        return resume_json

    cleaned_skills = []
    total_removed = 0

    for skill_category in resume_json.get('skills', []):
        category_name = skill_category.get('category', 'Unknown')
        items = skill_category.get('items', [])

        cleaned_items = []
        for item in items:
            is_valid, reason, confidence = validate_skill_with_confidence(item)
            if is_valid and confidence >= min_confidence:
                cleaned_items.append(item)
            else:
                total_removed += 1
                print(f"[tailor] ✗ Skill '{item}' REMOVED from {category_name} (final cleanup): {reason}")

        if cleaned_items:
            cleaned_skills.append({'category': category_name, 'items': cleaned_items})

    resume_json['skills'] = cleaned_skills

    if total_removed:
        print(f"[tailor] Aggressive skill cleanup: removed {total_removed} invalid skill(s)")

    return resume_json
