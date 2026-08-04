import re as _re_align


def flatten_resume_to_text(resume_json):
    """Flatten resume JSON into plain text for matching."""
    parts = []
    # Summary
    summary = resume_json.get('summary', '')
    if summary:
        parts.append(summary)
    # Skills
    for skill_group in resume_json.get('skills', []):
        items = skill_group.get('items', [])
        if items:
            parts.append(', '.join(items))
    # Experience
    for exp in resume_json.get('experience', []):
        title = exp.get('title', '')
        company = exp.get('company', '')
        if title:
            parts.append(title)
        if company:
            parts.append(company)
        for bullet in exp.get('bullets', []):
            parts.append(bullet)
    # Projects
    for proj in resume_json.get('projects', []):
        name = proj.get('name', '')
        if name:
            parts.append(name)
        for bullet in proj.get('bullets', []):
            parts.append(bullet)
    # Education
    for edu in resume_json.get('education', []):
        degree = edu.get('degree', '')
        school = edu.get('school', '')
        if degree:
            parts.append(degree)
        if school:
            parts.append(school)
    return ' '.join(parts)


def validate_cover_letter_resume_alignment(cover_letter_text, resume_json):
    """
    Extract claims from cover letter.
    Verify each claim is backed by resume evidence.
    """
    # Extract achievement claims (sentences with action verbs)
    claim_verbs = ['led', 'built', 'developed', 'architected', 'designed', 'managed',
                   'increased', 'improved', 'reduced', 'optimized', 'launched', 'delivered']

    claims = []
    sentences = _re_align.split(r'(?<=[.!?])\s+', cover_letter_text)

    for sentence in sentences:
        for verb in claim_verbs:
            if f' {verb} ' in sentence.lower() or sentence.lower().startswith(verb):
                claims.append(sentence.strip())
                break

    # Build proof text from resume
    resume_proof_text = flatten_resume_to_text(resume_json)
    resume_proof_lower = resume_proof_text.lower()

    # Check each claim
    mismatches = []
    proven = []

    for claim in claims:
        # Extract key terms from claim (skip common words)
        claim_terms = [w for w in claim.lower().split()
                      if len(w) > 3 and w not in ['that', 'with', 'have', 'from', 'were']]

        # Check if resume contains these terms
        match_count = sum(1 for term in claim_terms if term in resume_proof_lower)
        match_ratio = match_count / len(claim_terms) if claim_terms else 0

        if match_ratio >= 0.7:  # At least 70% of terms in resume
            proven.append({'claim': claim[:80], 'confidence': match_ratio})
        else:
            mismatches.append({
                'claim': claim[:80],
                'severity': 'CRITICAL' if any(v in claim.lower() for v in ['led', 'managed', 'architected']) else 'MEDIUM',
                'missing_terms': [t for t in claim_terms if t not in resume_proof_lower]
            })

    alignment_score = (len(proven) / len(claims) * 100) if claims else 100

    return {
        'alignment_score': alignment_score,
        'proven': len(proven),
        'mismatches': mismatches,
        'status': 'PASS' if len(mismatches) == 0 else 'FAIL',
        'recommendation': 'Either remove unsubstantiated claims or enhance resume' if mismatches else 'All claims backed by resume'
    }
