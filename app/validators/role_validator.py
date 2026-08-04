# Role-level validation matrix
ROLE_SKILL_MATRIX = {
    'entry_level': {
        'max_total_skills': 12,
        'ok_frameworks': ['Flask', 'React', 'Express', 'Django'],
        'forbidden': ['Kubernetes', 'Machine Learning', 'Data Pipelines', 'Data Engineering',
                     'Distributed Systems', 'Architecture', 'Leadership'],
        'years_experience': (0, 2)
    },
    'mid_level': {
        'max_total_skills': 16,
        'ok_frameworks': ['Flask', 'React', 'Express', 'Django', 'Spring Boot', 'FastAPI'],
        'forbidden': ['Chief Architect', 'Principal Engineer'],
        'years_experience': (2, 7)
    },
    'senior': {
        'max_total_skills': 20,
        'ok_frameworks': ['All modern stacks'],
        'forbidden': [],
        'years_experience': (7, 100)
    }
}


def detect_role_level(resume_json, jd_text):
    """
    Detect if this is entry, mid, or senior level role.
    Based on: years experience in resume, JD keywords
    """
    # Look at experience section
    experiences = resume_json.get('experience', [])
    if not experiences:
        return 'entry_level'

    # Calculate total years
    total_years = 0
    for exp in experiences:
        dates = exp.get('dates', '')
        # Simple parsing: "Jan 2022 – Dec 2023" = 1 year
        # More sophisticated parsing would be better
        if ' – ' in dates:
            try:
                start_str, end_str = dates.split(' – ')
                # Extract years from "Jan 2022" format
                # This is simplified; real implementation would parse properly
                total_years += 1  # Placeholder
            except Exception:
                pass

    # Check JD keywords for seniority indicators
    jd_lower = jd_text.lower()
    if any(word in jd_lower for word in ['architect', 'principal', 'director', 'head of']):
        return 'senior'
    elif any(word in jd_lower for word in ['lead', 'senior', 'staff']):
        if total_years >= 5:
            return 'senior'
        return 'mid_level'
    else:
        if total_years >= 2:
            return 'mid_level'
        return 'entry_level'


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
