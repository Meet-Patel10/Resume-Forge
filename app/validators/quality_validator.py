"""
Quality Validation Framework — Task 10
Implements quality gates to prevent bad resumes from reaching output.

Chunks:
- 10.1: Summary completeness validator
- 10.2: Skills validity validator
- 10.3: Evidence requirement validator
- 10.4: Categorization validator
- 10.5: Role level consistency validator
"""

import re
from app.validators.skill_validator import validate_skill


# ═══════════════════════════════════════════════════════════════════
# CHUNK 10.1: Summary Completeness Validator
# Ensures summary has no truncated or incomplete sentences
# ═══════════════════════════════════════════════════════════════════

def validate_summary_quality(summary_text):
    """
    Comprehensive summary quality validation.
    
    Returns: {
        'is_valid': bool,
        'score': float (0-100),
        'issues': list of issues found,
        'suggestions': list of improvement suggestions
    }
    """
    issues = []
    suggestions = []
    score = 100
    
    if not summary_text:
        return {'is_valid': False, 'score': 0, 'issues': ['Empty summary'], 'suggestions': ['Add summary']}
    
    # Check for incomplete patterns
    incomplete_patterns = [
        (r'focusing on\.\.\.', "Incomplete phrase: 'focusing on...'", -20),
        (r'based on\.\.\.', "Incomplete phrase: 'based on...'", -20),
        (r'involved in\.\.\.', "Incomplete phrase: 'involved in...'", -20),
        (r',\s*$', "Ends with comma (incomplete)", -15),
        (r'\s+and\s*$', "Ends with 'and' (incomplete)", -15),
    ]
    
    for pattern, message, penalty in incomplete_patterns:
        if re.search(pattern, summary_text, re.IGNORECASE):
            issues.append(message)
            score += penalty
    
    # Check word count
    word_count = len(summary_text.split())
    if word_count > 150:
        issues.append(f"Summary too long: {word_count} words (max 150)")
        score -= 10
    elif word_count < 20:
        issues.append(f"Summary too short: {word_count} words (min 20)")
        score -= 15
    
    # Check for duplicate phrases
    sentences = [s.strip() for s in summary_text.split('.') if s.strip()]
    if len(sentences) != len(set(sentences)):
        issues.append("Duplicate sentences detected")
        score -= 15
    
    # Check sentence count (3-4 recommended)
    if len(sentences) > 5:
        suggestions.append(f"Consider reducing to 3-4 sentences (currently {len(sentences)})")
        score -= 5
    
    return {
        'is_valid': len(issues) == 0,
        'score': max(0, score),
        'issues': issues,
        'suggestions': suggestions
    }


# ═══════════════════════════════════════════════════════════════════
# CHUNK 10.2: Skills Validity Validator
# Ensures all skills in resume are valid and not nonsense
# ═══════════════════════════════════════════════════════════════════

def validate_all_skills(resume_json):
    """
    Validate all skills in the resume.
    
    Returns: {
        'is_valid': bool,
        'total_skills': int,
        'valid_skills': int,
        'invalid_skills': list of (skill, reason),
        'score': float (0-100)
    }
    """
    invalid_skills = []
    valid_count = 0
    total_count = 0
    
    for skill_group in resume_json.get('skills', []):
        for skill in skill_group.get('items', []):
            total_count += 1
            is_valid, reason = validate_skill(skill)
            if is_valid:
                valid_count += 1
            else:
                invalid_skills.append((skill, reason))
    
    score = (valid_count / total_count * 100) if total_count > 0 else 100
    
    return {
        'is_valid': len(invalid_skills) == 0,
        'total_skills': total_count,
        'valid_skills': valid_count,
        'invalid_skills': invalid_skills,
        'score': score
    }


# ═══════════════════════════════════════════════════════════════════
# CHUNK 10.3: Evidence Requirement Validator
# Ensures skills have evidence in experience bullets
# ═══════════════════════════════════════════════════════════════════

def validate_skill_evidence(resume_json):
    """
    Validate that skills have evidence in experience/projects.
    
    Returns: {
        'is_valid': bool,
        'skills_with_evidence': int,
        'skills_without_evidence': list,
        'coverage_percentage': float
    }
    """
    # Collect all experience/project text
    evidence_text = ''
    for exp in resume_json.get('experience', []):
        for bullet in exp.get('bullets', []):
            evidence_text += ' ' + bullet.lower()
    for proj in resume_json.get('projects', []):
        for bullet in proj.get('bullets', []):
            evidence_text += ' ' + bullet.lower()
    
    # Check each skill
    skills_with_evidence = 0
    skills_without_evidence = []
    total_skills = 0
    
    for skill_group in resume_json.get('skills', []):
        for skill in skill_group.get('items', []):
            total_skills += 1
            skill_lower = skill.lower()
            
            # Check if any word from the skill appears in evidence
            skill_words = [w for w in skill_lower.split() if len(w) > 2]
            has_evidence = any(word in evidence_text for word in skill_words)
            
            if has_evidence:
                skills_with_evidence += 1
            else:
                skills_without_evidence.append(skill)
    
    coverage = (skills_with_evidence / total_skills * 100) if total_skills > 0 else 100
    
    return {
        'is_valid': coverage >= 70,  # Allow some skills without direct evidence
        'skills_with_evidence': skills_with_evidence,
        'skills_without_evidence': skills_without_evidence,
        'coverage_percentage': coverage
    }


# ═══════════════════════════════════════════════════════════════════
# CHUNK 10.4: Categorization Validator
# Ensures skills are in correct categories
# ═══════════════════════════════════════════════════════════════════

def validate_skill_categorization(resume_json):
    """
    Validate skills are properly categorized.
    
    Returns: {
        'is_valid': bool,
        'issues': list of categorization issues
    }
    """
    issues = []
    
    # Soft skills that should NOT be in Skills section
    soft_skills = {
        'communication', 'collaboration', 'teamwork', 'leadership',
        'problem-solving', 'adaptability', 'mentoring', 'innovation',
        'accountability', 'curiosity', 'critical thinking',
    }
    
    for skill_group in resume_json.get('skills', []):
        category = skill_group.get('category', '').lower()
        items = skill_group.get('items', [])
        
        for skill in items:
            skill_lower = skill.lower().strip()
            
            # Check soft skills in Skills section
            if skill_lower in soft_skills:
                issues.append(f"Soft skill '{skill}' in Skills section (should be in Experience/Summary)")
    
    return {
        'is_valid': len(issues) == 0,
        'issues': issues
    }


# ═══════════════════════════════════════════════════════════════════
# CHUNK 10.5: Role Level Consistency Validator
# Validates role level matches skills and experience
# ═══════════════════════════════════════════════════════════════════

def validate_role_consistency(resume_json, detected_role_level):
    """
    Validate role level is consistent with resume content.
    
    Returns: {
        'is_valid': bool,
        'issues': list of consistency issues
    }
    """
    from app.validators.role_validator import ROLE_SKILL_MATRIX
    
    issues = []
    
    config = ROLE_SKILL_MATRIX.get(detected_role_level, {})
    max_skills = config.get('max_total_skills', 30)
    
    # Count total skills
    total_skills = sum(
        len(group.get('items', []))
        for group in resume_json.get('skills', [])
    )
    
    if total_skills > max_skills:
        issues.append(
            f"Too many skills ({total_skills}) for {detected_role_level} level "
            f"(max {max_skills})"
        )
    
    return {
        'is_valid': len(issues) == 0,
        'issues': issues
    }


# ═══════════════════════════════════════════════════════════════════
# Master Quality Gate — Runs all validators
# ═══════════════════════════════════════════════════════════════════

def run_quality_gates(resume_json, detected_role_level='mid_level'):
    """
    Run all quality validation gates.
    
    Returns: {
        'overall_pass': bool,
        'summary': dict,
        'skills': dict,
        'evidence': dict,
        'categorization': dict,
        'role_consistency': dict,
        'overall_score': float
    }
    """
    summary_result = validate_summary_quality(resume_json.get('summary', ''))
    skills_result = validate_all_skills(resume_json)
    evidence_result = validate_skill_evidence(resume_json)
    categorization_result = validate_skill_categorization(resume_json)
    role_result = validate_role_consistency(resume_json, detected_role_level)
    
    overall_pass = all([
        summary_result['is_valid'],
        skills_result['is_valid'],
        categorization_result['is_valid'],
        role_result['is_valid'],
    ])
    
    overall_score = (
        summary_result['score'] * 0.25 +
        skills_result['score'] * 0.25 +
        evidence_result['coverage_percentage'] * 0.25 +
        (100 if categorization_result['is_valid'] else 50) * 0.25
    )
    
    return {
        'overall_pass': overall_pass,
        'summary': summary_result,
        'skills': skills_result,
        'evidence': evidence_result,
        'categorization': categorization_result,
        'role_consistency': role_result,
        'overall_score': overall_score,
    }
