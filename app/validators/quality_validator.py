"""
Quality Validation Framework — Task 10
Implements quality gates to prevent bad resumes from reaching output.

Chunks:
- 10.1: Summary completeness validator
- 10.2: Skills validity validator
- 10.3: Evidence requirement validator
- 10.4: Categorization validator
- 10.5: Role level consistency validator
- 10.6: Keyword/language naturalness validator (AI-cliché phrasing)

TASK 10 fix: this framework (run_quality_gates + its five chunks) already
existed and was already unit-tested (tests/test_tailoring_fixes.py::
TestQualityGates) — but nothing in app/routes/tailor.py ever called it.
Resumes were generated and sent with a fully-built quality gate sitting
unused, exactly matching TASK_10_COMPLETE_SOLUTION.md's Problem 1 ("no
comprehensive quality checks after tailoring") and Problem 6 ("no way to
know if resume is suitable for submission"). The doc's proposed fix was a
brand-new parallel framework (ResumeIntegrityValidator/KeywordQuality
Scorer/NaturalLanguageValidator in a from-scratch quality_validator.py) —
not implemented as-is since it would have discarded this real, working,
tested module and assumed a resume schema this app doesn't use (flat
`skills: List[str]` and `experience[].description`, vs. this app's real
`skills: [{category, items}]` and `experience[].bullets`). The actual fix:
add the one genuinely missing check (10.6, Problem 4 — keyword/language
naturalness, which nothing here covered) and wire run_quality_gates into
the real tailor pipeline (see app/routes/tailor.py, "TASK 10" block).
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

def validate_skill_evidence(resume_json, master_skills=None):
    """
    Validate that every skill claimed in the Skills section is backed by
    something — either the master resume, or prose elsewhere in the document.

    Two things this deliberately does NOT do:

    1. It does not require a bullet per skill. Real resumes list tools
       (Jira, Postman, GitHub) that never earn their own bullet. Demanding
       one would fail every honest resume ever written.
    2. It does not read only bullets. Project tech stacks and education
       coursework are evidence too — PyTorch and Hugging Face live in a
       project's tech_stack, Embedded Systems in coursework. Reading only
       bullets reported all of them as fabricated.

    What it DOES catch is the thing that matters: a skill that appears in
    neither the master resume nor anywhere in the document's prose — i.e. one
    the pipeline injected because a JD asked for it.

    Args:
        resume_json: the resume dict
        master_skills: skill names from the master resume. Anything here is
            evidenced by definition — the candidate genuinely has it.

    Returns: {
        'is_valid': bool,
        'skills_with_evidence': int,
        'skills_without_evidence': list,
        'coverage_percentage': float
    }
    """
    def _norm(text):
        """Loose key for master-set comparison: 'Object-Oriented Programming
        (OOP)' and 'object oriented programming oop' should match. Keeps
        +#. so C++, C# and Node.js stay distinct."""
        return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9+#.]+', ' ', str(text).lower())).strip()

    master = set()
    for s in (master_skills or set()):
        master.add(str(s).lower().strip())
        master.add(_norm(s))

    # Collect every piece of prose that can evidence a skill.
    evidence_parts = [resume_json.get('summary', '') or '']
    for exp in resume_json.get('experience', []):
        evidence_parts.extend(exp.get('bullets', []) or [])
        evidence_parts.append(exp.get('title', '') or '')
    for proj in resume_json.get('projects', []):
        evidence_parts.extend(proj.get('bullets', []) or [])
        evidence_parts.append(proj.get('tech_stack', '') or '')
        evidence_parts.append(proj.get('name', '') or '')
    for edu in resume_json.get('education', []):
        details = edu.get('details', '') or ''
        if isinstance(details, list):
            evidence_parts.extend(details)
        else:
            evidence_parts.append(details)
        evidence_parts.append(edu.get('degree', '') or '')

    evidence_text = ' ' + ' '.join(str(p).lower() for p in evidence_parts) + ' '

    # Check each skill
    skills_with_evidence = 0
    skills_without_evidence = []
    total_skills = 0
    
    for skill_group in resume_json.get('skills', []):
        for skill in skill_group.get('items', []):
            total_skills += 1
            skill_lower = skill.lower()

            # Present in the master resume → evidenced, no further questions.
            # Same standard aggressive_cleanup uses; the master resume is the
            # only thing in this system that knows what the candidate has.
            if skill_lower.strip() in master or _norm(skill) in master:
                skills_with_evidence += 1
                continue

            # EVERY token of the skill must appear on a word boundary.
            # `any(word in evidence_text ...)` passed 'cloud platforms' on the
            # bare word 'cloud', which made this check pass almost anything —
            # unacceptable now that it participates in overall_pass.
            #
            # Skills whose tokens are all <=2 chars ('Go', 'R', 'C', 'AI') have
            # no long tokens to match on, so they match the whole name instead.
            # Dropping them outright would report a skill named in the bullets
            # as unevidenced.
            skill_tokens = {w for w in skill_lower.split() if len(w) > 2}
            if not skill_tokens:
                skill_tokens = {skill_lower.strip()}
            has_evidence = all(
                re.search(rf'\b{re.escape(w)}\b', evidence_text) for w in skill_tokens
            )
            
            if has_evidence:
                skills_with_evidence += 1
            else:
                skills_without_evidence.append(skill)
    
    coverage = (skills_with_evidence / total_skills * 100) if total_skills > 0 else 100
    
    return {
        # 90, not 70. The old tolerance assumed evidence meant "has a bullet",
        # where many legitimate skills genuinely have none. Now that the master
        # resume counts as evidence, an unevidenced skill is a skill the
        # candidate does not demonstrably have — i.e. injected. At 70% a resume
        # could carry four fabricated tools and still pass. The remaining slack
        # absorbs naming variation (master "RESTful APIs" vs output "REST API"),
        # not fabrication.
        'is_valid': coverage >= 90,
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
# CHUNK 10.6: Keyword/Language Naturalness Validator (TASK 10 fix)
#
# TASK_10_COMPLETE_SOLUTION.md's Problem 4 ("Missing Validation for
# Keyword Naturalness") is real: nothing in this file checked resume
# prose for AI-cliché phrasing before this fix. But the doc's proposed
# KeywordQualityScorer/NaturalLanguageValidator classes weren't wired in
# as-is — this codebase already has a production-confirmed AI-phrasing
# pattern list (validate_soft_skill_grammaticality in app/routes/
# tailor.py, added for TASK 7), scoped to soft-skill-injected bullets
# only. This reuses that same pattern list, generalized to scan the
# WHOLE resume (summary + every experience/project bullet), so a bullet
# that becomes AI-sounding from some OTHER pipeline step (hard-skill
# injection) is also caught — not just soft
# skill injections.
# ═══════════════════════════════════════════════════════════════════

AI_WRITTEN_PATTERNS = [
    (r'\bInnovatively\s+\w+', "AI-sounding adverb: 'Innovatively'"),
    (r'\bCommunicated\s+automation', "Unnatural phrase: 'Communicated automation'"),
    (r'\bCollaboratively\s+developed', "AI-sounding: 'Collaboratively developed'"),
    (r'\bProactively\s+\w+ed', "AI-sounding adverb: 'Proactively'"),
    (r'^(Innovatively|Communicatively|Collaboratively|Adaptably|Accountably)\s',
     "Opens with an awkward -ly adverb"),
    (r'\bDynamically\s+(optimized|implemented)', "AI-sounding adverb: 'Dynamically'"),
    (r'\bSeamlessly\s+(integrated|implemented)', "AI-sounding adverb: 'Seamlessly'"),
    (r'\bLeveraging\s+(cutting-edge|advanced)\b', "Cliché phrase: 'leveraging cutting-edge/advanced'"),
    (r'\b(cutting-edge|state-of-the-art)\s+(solutions|technologies)\b', "Cliché phrase"),
]


def validate_keyword_naturalness(resume_json):
    """
    Chunk 10.6: scan the resume's prose (summary + experience/project
    bullets) for AI-cliché phrasing.

    Returns: {
        'is_valid': bool,       # True if no flagged phrases found
        'score': float (0-100),
        'flagged_phrases': list of (location, message, matched_text),
    }
    """
    flagged = []

    def _scan(text, location):
        if not isinstance(text, str) or not text:
            return
        for pattern, message in AI_WRITTEN_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                flagged.append((location, message, match.group()))

    _scan(resume_json.get('summary', ''), 'summary')
    for i, exp in enumerate(resume_json.get('experience', [])):
        for j, bullet in enumerate(exp.get('bullets', [])):
            _scan(bullet, f'experience[{i}].bullets[{j}]')
    for i, proj in enumerate(resume_json.get('projects', [])):
        for j, bullet in enumerate(proj.get('bullets', [])):
            _scan(bullet, f'projects[{i}].bullets[{j}]')

    score = max(0.0, 100.0 - len(flagged) * 15)

    return {
        'is_valid': len(flagged) == 0,
        'score': score,
        'flagged_phrases': flagged,
    }


# ═══════════════════════════════════════════════════════════════════
# Master Quality Gate — Runs all validators
# ═══════════════════════════════════════════════════════════════════

def run_quality_gates(resume_json, detected_role_level='mid_level', master_skills=None):
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
    evidence_result = validate_skill_evidence(resume_json, master_skills=master_skills)
    categorization_result = validate_skill_categorization(resume_json)
    role_result = validate_role_consistency(resume_json, detected_role_level)
    naturalness_result = validate_keyword_naturalness(resume_json)  # TASK 10 fix

    # `evidence` was 20% of the score but excluded from overall_pass — the one
    # check that can catch fabrication could not fail the gate. Now it can.
    overall_pass = all([
        summary_result['is_valid'],
        skills_result['is_valid'],
        evidence_result['is_valid'],
        categorization_result['is_valid'],
        role_result['is_valid'],
        naturalness_result['is_valid'],
    ])

    # Conversely, role_consistency counted toward overall_pass but not toward
    # overall_score, which is how a run could report "score 90.3, pass=False".
    # Every component that can fail the gate now also moves the number.
    overall_score = (
        summary_result['score'] * 0.20 +
        skills_result['score'] * 0.15 +
        evidence_result['coverage_percentage'] * 0.20 +
        (100 if categorization_result['is_valid'] else 50) * 0.15 +
        (100 if role_result['is_valid'] else 50) * 0.15 +
        naturalness_result['score'] * 0.15
    )

    return {
        'overall_pass': overall_pass,
        'summary': summary_result,
        'skills': skills_result,
        'evidence': evidence_result,
        'categorization': categorization_result,
        'role_consistency': role_result,
        'naturalness': naturalness_result,
        'overall_score': overall_score,
    }
