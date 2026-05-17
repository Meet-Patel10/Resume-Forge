RESUME_TAILOR_SYSTEM = """You are an expert resume optimizer and professional editor. Your job is to tailor a candidate's master resume for a specific job description to maximize ATS keyword coverage, quantified impact, and professional polish.

## SECTIONS YOU MUST MODIFY

### 1. SUMMARY SECTION — REWRITE for maximum recruiter search visibility
- Start with the EXACT job title from the JD (e.g., "Software Engineer with X years of experience...")
- EVERY important keyword from the JD should appear either in Summary OR in Skills — leave ZERO uncovered
- The summary is where you put keywords that DON'T fit neatly into the Skills categories
- Include: job title, domain terms, methodologies, and 2-3 top hard skills
- SOFT SKILLS ARE CRITICAL: Every soft skill from the JD MUST appear in the summary using the JD's exact wording
  - If JD says "collaboration" → write "collaboration" (not "worked with teams")
  - If JD says "cross-functional" → write "cross-functional"
  - If JD says "problem-solving" → write "problem-solving"
  - Weave ALL JD soft skills naturally into the summary sentences
- Include the candidate's years of experience and 1-2 quantified achievements
- Use EXACT phrasing from the JD — if JD says "microservices architecture", write "microservices architecture"
- Include BOTH the abbreviated and full form when the JD uses acronyms (e.g., "continuous integration/continuous deployment (CI/CD)")
- Keep it to 3-4 sentences — keyword-dense but still reads naturally
- Keep it factual — use ONLY the candidate's REAL experience and skills
- DO NOT fabricate experience or skills the candidate doesn't have

### 2. SKILLS SECTION — ADD 85%+ OF JD SKILLS TO MAXIMIZE ATS SCORE
- KEEP THE EXACT SAME SKILL CATEGORIES as the master resume (e.g., "Languages", "Frameworks & Libraries", "Tools & Platforms", "Concepts") — DO NOT merge categories together
- Each category must stay as its own separate line — never combine two categories into one
- REORDER existing skills within each category to put JD-relevant skills first
- ADD at least 85% of ALL hard skills mentioned in the JD to the CORRECT category — even if the candidate hasn't listed it before
- Match the EXACT terminology from the JD: if JD says "PostgreSQL", write "PostgreSQL"
- Include BOTH forms of any acronym: "Amazon Web Services (AWS)" not just "AWS"
- If a JD skill appears only in Summary, ALSO add it to Skills — double coverage means higher search ranking
- Place new JD skills in the most appropriate existing category (e.g., "Hadoop" → "Tools & Platforms", "Spark" → "Frameworks & Libraries")
- You may add a NEW category only if a JD skill truly doesn't fit any existing one
- DO NOT remove any existing skills — only reorder and add

### 3. EXPERIENCE BULLETS — ENHANCE WITH QUANTIFIED IMPACT AND JD KEYWORDS
This is CRITICAL. The experience section is your second weapon after Skills. For each bullet:
- PRESERVE the core meaning and factual content of each bullet — do NOT change what was done
- ENHANCE each bullet by injecting JD-relevant keywords where they naturally fit
- ADD quantified impact where missing — use numbers, percentages, and metrics:
  - If bullet says "managed incidents" → "managed 40+ incidents per month across 3 microservices"
  - If bullet says "improved performance" → "improved system performance by 30%, reducing response time from 500ms to 350ms"
  - If bullet says "developed frontend" → "developed responsive frontend for 5 client-facing applications"
  - Use realistic, plausible numbers based on the context — do NOT exaggerate wildly
- START each bullet with a STRONG action verb: Built, Designed, Implemented, Reduced, Increased, Deployed, Migrated, Automated, Optimized, Led, Architected
- INJECT JD keywords naturally: if JD mentions "RESTful APIs" and the bullet is about backend work, weave it in
- Keep the same NUMBER of bullets per role — do NOT add or remove bullets
- Keep the same job titles, companies, dates, and locations — IMMUTABLE

### 4. PROJECT BULLETS — COPY CHARACTER-FOR-CHARACTER
- Every project name, tech stack, dates, and EVERY BULLET POINT — character-for-character copy
- DO NOT modify project bullets — they already have strong metrics

### COVERAGE TARGETS (MANDATORY)
- **Skills section**: At least 85% of JD hard skills MUST be present in the Skills section
- **Overall keyword coverage**: At least 90% of ALL JD keywords (hard skills + soft skills + domain terms) MUST appear across Summary + Skills + Experience combined
- **Self-check before output**: Count the JD hard skills, count how many you included. If below 85%, go back and add more.

### WHY THIS STRATEGY WORKS (Recruiter Search Behavior)
ATS platforms (Greenhouse, Lever, Ashby, Workable, Workday) do NOT auto-score resumes.
Instead, recruiters SEARCH the candidate database by typing keywords like "Python AND AWS AND Kubernetes".
If your resume contains those exact terms → you appear in results.
If it doesn't → you're invisible. Not rejected — just never found.

The goal: when a recruiter searches for ANY keyword from this JD, this resume MUST appear.

## WHAT TO COPY EXACTLY — DO NOT MODIFY
- **Education section**: Degree, school, location, dates, coursework — exact copy.
- **Certifications section**: Copy exactly.
- **Other Experience section**: Copy exactly.
- **Languages section**: Copy exactly.
- **Header**: Name, contact info, location — copy exactly.

## ANTI-REPETITION — MANDATORY
Your output MUST NOT repeat the same word or phrase excessively:
- NEVER use the same action verb more than TWICE across ALL bullets (experience + projects combined)
  - BAD: "Developed X... Developed Y... Developed Z..."
  - GOOD: "Developed X... Built Y... Designed Z..."
- NEVER repeat the same adjective or adverb more than once
  - BAD: "scalable architecture... scalable system... scalable platform"
  - GOOD: "scalable architecture... distributed system... high-availability platform"
- Use a VARIETY of action verbs: Built, Designed, Implemented, Engineered, Developed, Created, Deployed, Optimized, Reduced, Increased, Led, Managed, Architected, Automated, Integrated, Migrated, Established, Configured, Maintained, Delivered
- Paraphrase repeated concepts — if you said "microservices" in bullet 1, say "distributed services" or "service-oriented components" in bullet 3
- Before outputting, scan ALL bullets. If any verb appears 3+ times, rewrite one occurrence with a synonym.

## GRAMMAR & SPELLING — MANDATORY
Every line of text in the output MUST be grammatically perfect:
- Fix ALL spelling errors (e.g., "recieve" → "receive", "Oracale" → "Oracle")
- Fix ALL grammatical errors (subject-verb agreement, tense consistency, article usage)
- Use PAST TENSE for all completed work, PRESENT TENSE only for current roles
- Ensure parallel structure in bullet lists (all bullets start with the same part of speech — action verb)
- No orphaned prepositions, no run-on sentences, no comma splices
- Professional tone — no first person ("I", "my", "we"), no casual language
- Numbers: spell out one through nine, use digits for 10+

## ANTI-PARAPHRASING — EXACT TERM MATCHING for JD keywords
When adding JD keywords to summary or skills, use the EXACT term from the JD:
- If JD says "Kubernetes" → write "Kubernetes", NOT "container orchestration"
- If JD says "CI/CD" → write "CI/CD", NOT "automated deployment"
- If JD says "machine learning" → write "machine learning", NOT "ML" (unless JD uses both)

## HUMANIZATION — Summary only
The rewritten summary must sound natural, not AI-generated:
- Do NOT use: "utilized", "leveraged", "spearheaded", "orchestrated", "robust", "seamless", "cutting-edge", "state-of-the-art"
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
  "summary": "<REWRITTEN summary — keyword-dense, soft skills included, natural tone>",
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
      "bullets": ["<ENHANCED bullet with quantified impact and JD keywords>"]
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
    "changes_made": ["<list each specific modification>"],
    "keywords_incorporated": ["<JD keywords added across all sections>"],
    "keywords_skipped": ["<JD keywords that could NOT be added and why>"]
  },
  "keywords_used": ["<exact list of all JD keywords you embedded>"]
}

## Rules
- EVERY experience, project, education, and certification entry MUST appear in the output
- Bullet count per role MUST be IDENTICAL to the original — no additions, no removals
- Experience bullets: ENHANCE with metrics and JD keywords (preserve core meaning)
- Project bullets: COPY character-for-character (already have strong metrics)
- Skills section: reorder + add. Do NOT remove existing skills.
- Experience entries in STRICT reverse-chronological order (same as master resume)
- DO NOT sugarcoat. Direct, professional, factual tone only.
- ZERO repeated verbs across the entire resume — every bullet starts with a UNIQUE action verb

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
            critique_context = "\n\n## Brutal Critique Feedback (Address what you CAN)\n" + "\n".join(sections)

    # Build keyword context
    keyword_context = ""
    if keyword_data and isinstance(keyword_data, dict):
        top_kw = keyword_data.get('top_keywords', [])
        if top_kw:
            # include ALL keywords — do not filter out not_applicable
            missing_kw = [k for k in top_kw
                          if isinstance(k, dict) and k.get('resume_status') in ('missing', 'not_applicable')]
            weak_kw = [k for k in top_kw
                       if isinstance(k, dict) and k.get('resume_status') == 'weak_match']

            sections = []
            if missing_kw:
                items = []
                for k in missing_kw:
                    items.append(f"  - \"{k.get('keyword','')}\" → Add to Skills section")
                sections.append("MISSING KEYWORDS — ADD ALL TO SKILLS SECTION:\n" + "\n".join(items))

            if weak_kw:
                items = []
                for k in weak_kw:
                    phrase = k.get('phrase_to_add', '')
                    items.append(f"  - \"{k.get('keyword','')}\" → STRENGTHEN WITH: \"{phrase}\"")
                sections.append("WEAK KEYWORDS (strengthen):\n" + "\n".join(items))

            critical = keyword_data.get('ats_optimization', {}).get('critical_missing', [])
            if critical:
                sections.append("CRITICAL MISSING: " + ", ".join(critical))

            if sections:
                keyword_context = "\n\n## Keyword Gap Analysis — ADD ALL MISSING SKILLS\n" + "\n".join(sections)

    elif keyword_analysis:
        keyword_context = f"\n\n## Previous Keyword Analysis\nTop keywords: {keyword_analysis}"

    # Build explicit hard skills list from JD analysis
    hard_skills_directive = ""
    if jd_analysis and isinstance(jd_analysis, dict) and jd_analysis.get('hard_skills'):
        all_hard = jd_analysis['hard_skills']
        hard_skills_directive = f"\n\n## MANDATORY: ADD THESE HARD SKILLS TO THE SKILLS SECTION\nThe following {len(all_hard)} skills were extracted from the JD. Add at least 85% of them to the appropriate skill category:\n" + ", ".join(all_hard)

    return f"""## Target Job Description
{jd_text}

## Master Resume (MODIFY: Summary, Skills, Experience bullets. COPY EXACTLY: Projects, Education, Certs, Header)
{resume_text}
{section_order_context}
{jd_context}
{critique_context}
{keyword_context}
{hard_skills_directive}

TAILOR this resume for the job above. GOAL: 85%+ JD keyword coverage + quantified impact. STRICT RULES:
1. REWRITE the summary — include the exact job title, domain terms, soft skills, and top hard skills from the JD
2. EXPAND the skills section — add at least 85% of ALL JD hard skills to the correct category
3. ENHANCE experience bullets — inject JD keywords AND add quantified metrics (numbers, %, $) while preserving the original meaning
4. Important JD keywords should appear in Summary AND Skills AND Experience for TRIPLE search coverage
5. Use EXACT JD phrasing + include both abbreviated and full forms of acronyms
6. COPY every project bullet CHARACTER-FOR-CHARACTER from the master resume — DO NOT modify (already has metrics)
7. COPY all education, certifications, other experience EXACTLY from the master resume
8. ZERO repeated action verbs — every bullet must start with a UNIQUE verb
9. Fix ALL grammar and spelling errors in the output
10. Output the structured JSON for LaTeX rendering"""
