RESUME_TAILOR_SYSTEM = """You are an expert resume modifier. Your job is to take a candidate's EXISTING master resume and make SURGICAL modifications to ONLY the Summary and Skills sections to optimize it for a specific job description.

## THE ONE RULE THAT MATTERS: ONLY MODIFY SUMMARY AND SKILLS

You are making EXACTLY TWO changes. Nothing else.

### 1. SUMMARY SECTION — REWRITE for the target JD
- Rewrite the summary to align with the target job description
- Start with the EXACT job title from the JD (e.g., "Software Engineer with X years of experience...")
- Embed the top 3-5 JD keywords naturally into the summary
- Keep it factual — use ONLY the candidate's REAL experience and skills
- 2-3 sentences maximum
- DO NOT sugarcoat, DO NOT use buzzwords, DO NOT fabricate

### 2. SKILLS SECTION — REORDER and ADD for the target JD
- REORDER existing skills to put JD-relevant skills first in each category
- ADD missing JD skills that the candidate genuinely has (based on their experience)
- DO NOT remove any existing skills — only reorder and add
- Use the EXACT skill name from the JD (e.g., if JD says "Kubernetes", write "Kubernetes", NOT "container orchestration")

## EVERYTHING ELSE — COPY CHARACTER-FOR-CHARACTER FROM MASTER RESUME

The following MUST be copied EXACTLY as they appear in the master resume input with ZERO modifications:

- **Experience section**: Every job title, company name, location, dates, and EVERY BULLET POINT — copy them character-for-character. Do not reword, do not add keywords, do not add metrics, do not reorder bullets.
- **Projects section**: Every project name, tech stack, dates, and EVERY BULLET POINT — character-for-character copy.
- **Education section**: Degree, school, location, dates, coursework — exact copy.
- **Certifications section**: Copy exactly.
- **Other Experience section**: Copy exactly.
- **Languages section**: Copy exactly.
- **Header**: Name, contact info, location — copy exactly.

### WHY THIS MATTERS
When the tailored resume is re-uploaded as a master resume and checked against the same JD, it MUST pass the brutal critique and keyword matching. If you change experience bullets, the ATS check will flag inconsistencies. The ONLY safe changes are to the summary and skills sections.

### VERIFICATION BEFORE OUTPUT
Before producing your JSON output, verify:
1. Every experience bullet in your output is CHARACTER-FOR-CHARACTER identical to the master resume
2. Every project bullet in your output is CHARACTER-FOR-CHARACTER identical to the master resume
3. Every education entry is identical to the master resume
4. Only the summary and skills sections differ from the master resume
5. If ANY experience or project bullet has been changed, your response is INVALID

## FORMAT PRESERVATION
- Same section order as master resume
- Same number of sections, entries, and bullets
- Same job titles, company names, dates — all IMMUTABLE

## ZERO TOLERANCE FOR FABRICATION
- If a JD keyword doesn't match the candidate's real experience → skip it
- Only add skills the candidate genuinely has
- DO NOT invent, embellish, or sugarcoat

## ANTI-PARAPHRASING — EXACT TERM MATCHING
When adding JD keywords to summary or skills, use the EXACT term from the JD:
- If JD says "Kubernetes" → write "Kubernetes", NOT "container orchestration"
- If JD says "CI/CD" → write "CI/CD", NOT "automated deployment"
- Include both abbreviated AND full forms where helpful

## HUMANIZATION — MANDATORY (Summary only)
The rewritten summary must sound human, not AI-generated:
- Do NOT use: "utilized", "leveraged", "spearheaded", "orchestrated", "robust", "seamless", "cutting-edge", "innovative"
- Write like a real person describing themselves
- Be direct and factual — no press-release language

## Output Format
Respond ONLY with valid JSON in this exact structure:
{
  "header": {
    "name": "<EXACT copy from master resume>",
    "location": "<EXACT copy>",
    "phone": "<EXACT copy>",
    "email": "<EXACT copy>",
    "linkedin": "<EXACT copy or null>",
    "github": "<EXACT copy or null>",
    "tagline": "<EXACT copy or null>"
  },
  "summary": "<REWRITTEN summary — this is the ONLY text you write from scratch>",
  "skills": [
    {
      "category": "<e.g. Languages, Frameworks & Libraries, Tools & Platforms, Concepts>",
      "items": ["<reordered and augmented skill list>"]
    }
  ],
  "projects": [
    {
      "name": "<EXACT copy from master resume>",
      "tech_stack": "<EXACT copy>",
      "dates": "<EXACT copy>",
      "bullets": ["<EXACT copy of bullet 1>", "<EXACT copy of bullet 2>"]
    }
  ],
  "experience": [
    {
      "title": "<EXACT copy — IMMUTABLE>",
      "company": "<EXACT copy — IMMUTABLE>",
      "location": "<EXACT copy>",
      "dates": "<EXACT copy — IMMUTABLE>",
      "bullets": ["<EXACT copy of bullet 1 — DO NOT MODIFY>", "<EXACT copy of bullet 2 — DO NOT MODIFY>"]
    }
  ],
  "education": [
    {
      "degree": "<EXACT copy — IMMUTABLE>",
      "school": "<EXACT copy — IMMUTABLE>",
      "location": "<EXACT copy>",
      "dates": "<EXACT copy — IMMUTABLE>",
      "details": "<EXACT copy of coursework/GPA>"
    }
  ],
  "certifications": [
    {
      "name": "<EXACT copy>",
      "dates": "<EXACT copy>"
    }
  ],
  "other_experience": [
    {
      "title": "<EXACT copy — IMMUTABLE>",
      "company": "<EXACT copy — IMMUTABLE>",
      "location": "<EXACT copy>",
      "dates": "<EXACT copy — IMMUTABLE>",
      "bullets": ["<EXACT copy — DO NOT MODIFY>"]
    }
  ],
  "other": {
    "additional": "<EXACT copy or null>",
    "languages": "<EXACT copy>"
  },
  "tailoring_notes": {
    "changes_made": ["<list each specific modification — should ONLY be summary rewrite and skills reorder/additions>"],
    "keywords_incorporated": ["<JD keywords added to summary and skills>"],
    "keywords_skipped": ["<JD keywords that could NOT be added honestly and why>"]
  },
  "keywords_used": ["<exact list of all JD keywords you embedded>"]
}

## Rules
- EVERY experience, project, education, and certification entry MUST appear in the output — UNCHANGED
- Bullet count per role MUST be IDENTICAL to the original — no additions, no removals
- The ONLY new text you write is the summary section
- Skills section: reorder + add. Do NOT remove existing skills.
- Experience entries in STRICT reverse-chronological order (same as master resume)
- DO NOT sugarcoat. Direct, professional, factual tone only.

## CRITICAL: OUTPUT FORMAT ENFORCEMENT
- You MUST respond with ONLY valid JSON — no markdown, no explanations, no code fences
- Do NOT wrap your response in ```json ... ``` blocks
- Do NOT include any text before or after the JSON object
- The response must start with { and end with }
- If you cannot produce valid JSON, still try your best — the system will parse it
"""


def _detect_section_order(resume_text):
    """Figure out what order the sections appear in the resume text."""
    import re as _re
    section_patterns = [
        ('Summary', r'(?i)\b(summary|professional summary|profile|objective|about)\b'),
        ('Skills', r'(?i)\b(skills|technical skills|competencies|technologies)\b'),
        ('Projects', r'(?i)\b(projects|academic projects|personal projects|portfolio)\b'),
        ('Experience', r'(?i)\b(experience|professional experience|work history|employment)\b'),
        ('Education', r'(?i)\b(education|academic|degree)\b'),
        ('Other Experience', r'(?i)\b(other experience|additional experience|volunteer)\b'),
        ('Languages', r'(?i)\b(languages|spoken languages)\b'),
        ('Certifications', r'(?i)\b(certifications|certificates|licenses)\b'),
    ]
    found = []
    for name, pattern in section_patterns:
        match = _re.search(pattern, resume_text)
        if match:
            found.append((match.start(), name))
    found.sort(key=lambda x: x[0])
    return [name for _, name in found]


def build_tailor_message(resume_text, jd_text, keyword_analysis=None,
                         critique_data=None, keyword_data=None, jd_analysis=None):
    """Assemble the user message for the tailor prompt with all context."""
    # figure out section order so we can tell the AI to preserve it
    section_order = _detect_section_order(resume_text)
    section_order_context = ""
    if section_order:
        section_order_context = f"\n\nDETECTED SECTION ORDER: [{', '.join(section_order)}]. You MUST preserve this EXACT section order in your output."

    # Process JD analysis
    jd_context = ""
    if jd_analysis and isinstance(jd_analysis, dict):
        sections = []

        # Job title
        job_title = jd_analysis.get('job_title', '')
        if job_title:
            sections.append(f'JOB TITLE FROM JD: "{job_title}" — Your summary MUST start with this EXACT title.')

        # Title variants
        variants = jd_analysis.get('job_title_variants', [])
        if variants:
            sections.append(f'TITLE VARIANTS: {", ".join(variants)}')

        # Job family (A5: role-specific bullet priority)
        job_family = jd_analysis.get('job_family', '')
        if job_family:
            sections.append(f'JOB FAMILY: {job_family} — Reorder bullets within each role to prioritize {job_family}-relevant experience first.')

        # Hard skills
        hard_skills = jd_analysis.get('hard_skills', [])
        if hard_skills:
            sections.append(f'HARD SKILLS FROM JD (embed these EXACTLY as written — no synonyms): {", ".join(hard_skills)}')

        # Soft skills
        soft_skills = jd_analysis.get('soft_skills', [])
        if soft_skills:
            sections.append(f'SOFT SKILLS FROM JD (weave into bullet action verbs): {", ".join(soft_skills)}')

        # Top keywords
        top_keywords = jd_analysis.get('top_keywords', [])
        if top_keywords:
            sections.append(f'TOP KEYWORDS — each MUST appear 3+ times across resume (use EXACT terms, no synonyms): {", ".join(top_keywords)}')

        # Qualification verdict
        verdict = jd_analysis.get('qualification_verdict', {})
        if verdict and isinstance(verdict, dict):
            rating = verdict.get('rating', 'unknown')
            reasoning = verdict.get('reasoning', '')
            sections.append(f'QUALIFICATION ASSESSMENT: {rating.upper()} — {reasoning}')

        # Honest gaps
        gaps = jd_analysis.get('honest_gaps', [])
        if gaps:
            gap_lines = []
            for g in gaps:
                if isinstance(g, dict):
                    status = g.get('candidate_status', 'unknown')
                    req = g.get('requirement', '')
                    severity = g.get('severity', '')
                    if status in ('missing', 'partial'):
                        gap_lines.append(f'  - [{severity.upper()}] {req}: {status} — {g.get("evidence", "No evidence")}')
            if gap_lines:
                sections.append('HONEST GAPS (do NOT fabricate these — skip or note in keywords_skipped):\n' + '\n'.join(gap_lines))

        # Section priority
        priority = jd_analysis.get('section_priority', {})
        if priority and isinstance(priority, dict):
            most_valued = priority.get('most_valued', '')
            if most_valued:
                sections.append(f'JD EMPHASIS: This JD values "{most_valued}" most — prioritize this section.')

        if sections:
            jd_context = '\n\n## Dynamic JD Analysis (use this to guide your tailoring — these are the EXACT requirements)\n' + '\n'.join(sections)

    # Build critique context
    critique_context = ""
    if critique_data and isinstance(critique_data, dict):
        sections = []

        verdict = critique_data.get('verdict', '')
        if verdict:
            sections.append(f"HIRING MANAGER VERDICT: {verdict}")

        weaknesses = critique_data.get('weaknesses', [])
        if weaknesses:
            items = []
            for w in weaknesses:
                if isinstance(w, dict):
                    items.append(f"  - [{w.get('severity','?')}] {w.get('issue','')}: {w.get('fix','')}")
                else:
                    items.append(f"  - {w}")
            sections.append("WEAKNESSES TO FIX:\n" + "\n".join(items))

        red_flags = critique_data.get('red_flags', [])
        if red_flags:
            sections.append("RED FLAGS: " + "; ".join(
                [r if isinstance(r, str) else str(r) for r in red_flags]))

        missing = critique_data.get('missing_for_role', [])
        if missing:
            sections.append("MISSING FOR THIS ROLE: " + ", ".join(
                [m if isinstance(m, str) else str(m) for m in missing]))

        if sections:
            critique_context = "\n\n## Brutal Critique Feedback (Address what you CAN — skip what requires fabrication)\n" + "\n".join(sections)

    # Build keyword context
    keyword_context = ""
    if keyword_data and isinstance(keyword_data, dict):
        top_kw = keyword_data.get('top_keywords', [])
        if top_kw:
            applicable_kw = [k for k in top_kw
                             if isinstance(k, dict) and k.get('resume_status') != 'not_applicable']
            missing_kw = [k for k in applicable_kw
                          if k.get('resume_status') == 'missing']
            weak_kw = [k for k in applicable_kw
                       if k.get('resume_status') == 'weak_match']

            sections = []
            if missing_kw:
                items = []
                for k in missing_kw:
                    phrase = k.get('phrase_to_add', '')
                    where = k.get('where_to_add', '')
                    items.append(f"  - KEYWORD: \"{k.get('keyword','')}\" → SUGGESTED: \"{phrase}\" in {where}")
                sections.append("MISSING KEYWORDS (incorporate ONLY if candidate has real experience):\n" + "\n".join(items))

            if weak_kw:
                items = []
                for k in weak_kw:
                    phrase = k.get('phrase_to_add', '')
                    items.append(f"  - KEYWORD: \"{k.get('keyword','')}\" → STRENGTHEN WITH: \"{phrase}\"")
                sections.append("WEAK KEYWORDS (strengthen with candidate's actual evidence):\n" + "\n".join(items))

            critical = keyword_data.get('ats_optimization', {}).get('critical_missing', [])
            if critical:
                sections.append("CRITICAL MISSING SKILLS: " + ", ".join(critical))

            if sections:
                keyword_context = "\n\n## Keyword Gap Analysis (incorporate truthfully — skip keywords outside candidate's experience)\n" + "\n".join(sections)

    elif keyword_analysis:
        keyword_context = f"\n\n## Previous Keyword Analysis\nTop keywords: {keyword_analysis}"

    return f"""## Target Job Description
{jd_text}

## Master Resume (COPY EVERYTHING EXCEPT Summary and Skills — those you may modify)
{resume_text}
{section_order_context}
{jd_context}
{critique_context}
{keyword_context}

TAILOR this resume for the job above. STRICT RULES:
1. REWRITE the summary section to target this specific role — embed top JD keywords
2. REORDER and ADD to the skills section — put JD-relevant skills first, add missing ones the candidate has
3. COPY every experience bullet CHARACTER-FOR-CHARACTER from the master resume — DO NOT modify any bullet
4. COPY every project bullet CHARACTER-FOR-CHARACTER from the master resume — DO NOT modify any bullet
5. COPY all education entries EXACTLY from the master resume
6. COPY all certifications, other experience, languages EXACTLY from the master resume
7. COPY all job titles, company names, dates, locations EXACTLY from the master resume
8. DO NOT fabricate or sugarcoat — if a keyword doesn't fit the candidate's real experience, skip it
9. Output the structured JSON for LaTeX rendering"""
