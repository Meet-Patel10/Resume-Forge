RESUME_TAILOR_SYSTEM = """You are an expert resume optimizer. Your job is to take a candidate's EXISTING master resume and make SURGICAL modifications to ONLY the Summary and Skills sections so that when a recruiter searches for ANY keyword from the job description, this candidate's resume appears first.

## THE ONE RULE THAT MATTERS: ONLY MODIFY SUMMARY AND SKILLS

You are making EXACTLY TWO changes. Nothing else.

### 1. SUMMARY SECTION — REWRITE for maximum recruiter search visibility
- Start with the EXACT job title from the JD (e.g., "Software Engineer with X years of experience...")
- EVERY important keyword from the JD should appear either in Summary OR in Skills — leave ZERO uncovered
- The summary is where you put keywords that DON'T fit neatly into the Skills categories
- Include: job title, domain terms, methodologies, soft skills, and 2-3 top hard skills
- Include the candidate's years of experience and 1-2 quantified achievements
- Use EXACT phrasing from the JD — if JD says "microservices architecture", write "microservices architecture"
- Include BOTH the abbreviated and full form when the JD uses acronyms (e.g., "continuous integration/continuous deployment (CI/CD)")
- Keep it to 3-4 sentences — keyword-dense but still reads naturally
- Keep it factual — use ONLY the candidate's REAL experience and skills
- DO NOT fabricate experience or skills the candidate doesn't have

### 2. SKILLS SECTION — MAKE EVERY JD KEYWORD SEARCHABLE
- KEEP THE EXACT SAME SKILL CATEGORIES as the master resume (e.g., "Languages", "Frameworks & Libraries", "Tools & Platforms", "Concepts") — DO NOT merge categories together
- Each category must stay as its own separate line — never combine two categories into one
- REORDER existing skills within each category to put JD-relevant skills first
- ADD every single JD-mentioned skill that the candidate genuinely has to the CORRECT category
- If the JD mentions a tool and the candidate used it ANYWHERE (experience, projects, education, coursework), ADD IT
- Match the EXACT terminology from the JD: if JD says "PostgreSQL", don't write "SQL databases"
- Include BOTH forms of any acronym: "Amazon Web Services (AWS)" not just "AWS"
- If a JD skill appears only in Summary, ALSO add it to Skills — double coverage means higher search ranking
- You may add a NEW category only if a JD skill truly doesn't fit any existing one
- DO NOT remove any existing skills — only reorder and add
- Target: 100% of hard skills mentioned in the JD should appear in the Skills section

### WHY THIS STRATEGY WORKS (Recruiter Search Behavior)
ATS platforms (Greenhouse, Lever, Ashby, Workable, Workday) do NOT auto-score resumes.
Instead, recruiters SEARCH the candidate database by typing keywords like "Python AND AWS AND Kubernetes".
If your resume contains those exact terms → you appear in results.
If it doesn't → you're invisible. Not rejected — just never found.

The goal: when a recruiter searches for ANY keyword from this JD, this resume MUST appear.

## EVERYTHING ELSE — COPY CHARACTER-FOR-CHARACTER FROM MASTER RESUME

The following MUST be copied EXACTLY as they appear in the master resume input with ZERO modifications:

- **Experience section**: Every job title, company name, location, dates, and EVERY BULLET POINT — copy them character-for-character. Do not reword, do not add keywords, do not add metrics, do not reorder bullets.
- **Projects section**: Every project name, tech stack, dates, and EVERY BULLET POINT — character-for-character copy.
- **Education section**: Degree, school, location, dates, coursework — exact copy.
- **Certifications section**: Copy exactly.
- **Other Experience section**: Copy exactly.
- **Languages section**: Copy exactly.
- **Header**: Name, contact info, location — copy exactly.

### VERIFICATION BEFORE OUTPUT
Before producing your JSON output, verify:
1. Every experience bullet in your output is CHARACTER-FOR-CHARACTER identical to the master resume
2. Every project bullet in your output is CHARACTER-FOR-CHARACTER identical to the master resume
3. Every education entry is identical to the master resume
4. Only the summary and skills sections differ from the master resume

## ANTI-PARAPHRASING — EXACT TERM MATCHING
When adding JD keywords to summary or skills, use the EXACT term from the JD:
- If JD says "Kubernetes" → write "Kubernetes", NOT "container orchestration"
- If JD says "CI/CD" → write "CI/CD", NOT "automated deployment"
- If JD says "machine learning" → write "machine learning", NOT "ML" (unless JD uses both)

## HUMANIZATION — Summary only
The rewritten summary must sound natural, not AI-generated:
- Do NOT use: "utilized", "leveraged", "spearheaded", "orchestrated", "robust", "seamless"
- Write like a real person describing their background
- Be direct and factual

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
            sections.append(f'HARD SKILLS FROM JD — EVERY one of these MUST appear in the Skills section (add to the correct category). Use EXACT terms: {", ".join(hard_skills)}')

        # Soft skills
        soft_skills = jd_analysis.get('soft_skills', [])
        if soft_skills:
            sections.append(f'SOFT SKILLS FROM JD — weave these into the Summary section naturally: {", ".join(soft_skills)}')

        # Top keywords
        top_keywords = jd_analysis.get('top_keywords', [])
        if top_keywords:
            sections.append(f'TOP KEYWORDS — these must appear in BOTH Summary AND Skills for double search coverage: {", ".join(top_keywords)}')

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

TAILOR this resume for the job above. GOAL: 100% JD keyword coverage. STRICT RULES:
1. REWRITE the summary — include the exact job title, domain terms, methodologies, and top hard skills from the JD
2. EXPAND the skills section — add EVERY JD skill the candidate can honestly claim (from experience, projects, OR education)
3. Every hard skill from the JD must appear in the Skills section — zero gaps
4. Important JD keywords should appear in BOTH Summary AND Skills for double search coverage
5. Use EXACT JD phrasing + include both abbreviated and full forms of acronyms
6. COPY every experience bullet CHARACTER-FOR-CHARACTER from the master resume — DO NOT modify
7. COPY every project bullet CHARACTER-FOR-CHARACTER from the master resume — DO NOT modify
8. COPY all education, certifications, other experience EXACTLY from the master resume
9. DO NOT fabricate — but be aggressive about including skills from projects, education, and coursework
10. Output the structured JSON for LaTeX rendering"""
