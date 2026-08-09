# ═══════════════════════════════════════════════════════════════════
# CHUNK 3.1: Experience-to-Level Mapping
# Defines proper mapping of years to role levels
# ═══════════════════════════════════════════════════════════════════

ROLE_LEVEL_MAPPING = {
    'junior': {
        'years_range': (0, 2),
        'max_skills': 12,
        'description': 'Entry level, fresh grad'
    },
    'mid_level': {
        'years_range': (2, 5),
        'max_skills': 25,  # Can show more varied skills
        'description': 'L2/L3, proven track record'
    },
    'senior': {
        'years_range': (5, 10),
        'max_skills': 30,
        'description': 'L4+, deep expertise'
    },
    'principal': {
        'years_range': (10, 100),
        'max_skills': 40,
        'description': 'Principal+, thought leader'
    }
}


# ═══════════════════════════════════════════════════════════════════
# CHUNK 3.3: Updated ROLE_SKILL_MATRIX with New Caps
# Skill caps match new role levels
# ═══════════════════════════════════════════════════════════════════

# Role-level validation matrix
ROLE_SKILL_MATRIX = {
    'entry_level': {
        'max_total_skills': 12,
        'max_per_category': 4,
        'ok_frameworks': ['Flask', 'React', 'Express', 'Django'],
        'forbidden': ['Kubernetes', 'Machine Learning', 'Data Pipelines', 'Data Engineering',
                     'Distributed Systems', 'Architecture', 'Leadership'],
        'years_experience': (0, 2),
        'rationale': 'Limited breadth, focus on depth'
    },
    'junior': {
        'max_total_skills': 12,
        'max_per_category': 4,
        'ok_frameworks': ['Flask', 'React', 'Express', 'Django'],
        'forbidden': ['Kubernetes', 'Machine Learning', 'Data Pipelines', 'Data Engineering',
                     'Distributed Systems', 'Architecture', 'Leadership'],
        'years_experience': (0, 2),
        'rationale': 'Limited breadth, focus on depth'
    },
    'mid_level': {
        'max_total_skills': 25,  # WAS 16 when detected as "senior"
        'max_per_category': 8,   # Allow more skills
        'ok_frameworks': ['Flask', 'React', 'Express', 'Django', 'Spring Boot', 'FastAPI'],
        'forbidden': ['Chief Architect', 'Principal Engineer'],
        'years_experience': (2, 5),
        'rationale': 'L2/L3 shows broader skill set'
    },
    'senior': {
        'max_total_skills': 30,
        'max_per_category': 10,
        'ok_frameworks': ['All modern stacks'],
        'forbidden': [],
        'years_experience': (5, 10),
        'rationale': 'L4+ has deep expertise'
    },
    'principal': {
        'max_total_skills': 40,
        'max_per_category': 12,
        'ok_frameworks': ['All modern stacks'],
        'forbidden': [],
        'years_experience': (10, 100),
        'rationale': 'Principal has very broad skillset'
    }
}


# ═══════════════════════════════════════════════════════════════════
# CHUNK 3.2: Fix detect_role_level() Function
# Uses correct mapping so 2.5 years = mid_level, not senior
# ═══════════════════════════════════════════════════════════════════

def detect_role_level_by_years(years_experience):
    """
    Detect role level based on years of experience
    
    Returns: role_level from ROLE_LEVEL_MAPPING
    """
    for level, config in ROLE_LEVEL_MAPPING.items():
        min_years, max_years = config['years_range']
        if min_years <= years_experience < max_years:
            return level
    
    # Fallback for edge cases
    return "principal" if years_experience >= 10 else "senior"


def calculate_years_experience(resume_json):
    """
    TASK 3 bugfix: Calculate total years of professional experience from real
    date math, summing the duration of every experience entry with a
    parseable 'Mon YYYY – Mon YYYY' (or '– Present'/'– Current') date range.

    Replaces the old placeholder that counted "1 year" per job entry
    regardless of how long that job actually lasted.
    """
    from datetime import date as _date
    from app.validators.timeline_validator import parse_date_string

    experiences = resume_json.get('experience', [])
    total_months = 0

    for exp in experiences:
        dates = exp.get('dates', '')
        if ' – ' not in dates:
            continue
        try:
            start_str, end_str = dates.split(' – ')
            start_str = start_str.strip()
            end_str = end_str.strip()

            start_month, start_year = parse_date_string(start_str)

            if end_str.lower() in ('present', 'current'):
                today = _date.today()
                end_month, end_year = today.month, today.year
            else:
                end_month, end_year = parse_date_string(end_str)

            months = (end_year - start_year) * 12 + (end_month - start_month)
            if months > 0:
                total_months += months
        except Exception:
            continue

    return round(total_months / 12, 1)


def detect_role_level(resume_json, jd_text):
    """
    Detect if this is entry, mid, or senior level role.
    Based on: years experience in resume, JD keywords.

    FIXED: Now uses ROLE_LEVEL_MAPPING for correct year ranges.
    2.5 years → mid_level (was incorrectly returning senior)
    """
    # Look at experience section
    experiences = resume_json.get('experience', [])
    if not experiences:
        return 'entry_level'

    # TASK 3 bugfix: real date math instead of "1 year per job" placeholder
    total_years = calculate_years_experience(resume_json)

    # Check JD keywords for seniority indicators
    jd_lower = jd_text.lower()
    if any(word in jd_lower for word in ['architect', 'principal', 'director', 'head of']):
        return 'senior'
    elif any(word in jd_lower for word in ['lead', 'senior', 'staff']):
        if total_years >= 5:
            return 'senior'
        return 'mid_level'
    else:
        # FIXED: Use ROLE_LEVEL_MAPPING for proper year-based detection
        return detect_role_level_by_years(total_years)


# ═══════════════════════════════════════════════════════════════════
# CHUNK 3.4: Validate Role Level Consistency
# Catches inconsistencies between detected level and years
# ═══════════════════════════════════════════════════════════════════

def validate_role_level_consistency(years_experience, detected_level):
    """
    Validate that detected role level matches years
    
    Returns: (is_valid, error_message)
    """
    config = ROLE_LEVEL_MAPPING.get(detected_level)
    if not config:
        return False, f"Unknown role level: {detected_level}"
    
    min_years, max_years = config['years_range']
    
    if not (min_years <= years_experience < max_years):
        return False, (
            f"Role level '{detected_level}' requires {min_years}-{max_years} years, "
            f"but user has {years_experience} years"
        )
    
    return True, "Consistent"


def validate_role_skill_coherence(resume_json, role_level):
    """
    Ensure skills match role level.
    Reject skills that create incoherence.
    """
    issues = []
    suggestions = []

    config = ROLE_SKILL_MATRIX.get(role_level, {})

    # Count all skills
    all_skills = []
    for skill_group in resume_json.get('skills', []):
        all_skills.extend(skill_group.get('items', []))

    # Check 1: Too many skills for level
    if len(all_skills) > config.get('max_total_skills', 20):
        issues.append({
            'severity': 'HIGH',
            'message': f"Too many skills ({len(all_skills)}) for {role_level} level (max {config['max_total_skills']})",
            'recommendation': f'Remove {len(all_skills) - config["max_total_skills"]} least-relevant skills'
        })

    # Check 2: Forbidden skills for level
    forbidden = config.get('forbidden', [])
    for skill in all_skills:
        if any(forbidden_word.lower() in skill.lower() for forbidden_word in forbidden):
            issues.append({
                'severity': 'CRITICAL',
                'message': f"Skill '{skill}' inappropriate for {role_level} level",
                'recommendation': f'Remove "{skill}" or update role level'
            })

    # Check 3: Skill-to-experience mismatch
    if role_level == 'entry_level':
        ml_skills = [s for s in all_skills if 'machine learning' in s.lower() or 'ml' in s.lower()]
        if ml_skills:
            issues.append({
                'severity': 'CRITICAL',
                'message': f"Entry-level dev claiming ML expertise is suspicious",
                'recommendation': f'Either add ML project to experience or remove ML skills'
            })

    return {
        'coherence_score': 100 - (len(issues) * 25),
        'issues': issues,
        'suggestions': suggestions,
        'forbidden': forbidden,
        'status': 'PASS' if len(issues) == 0 else 'FAIL'
    }
