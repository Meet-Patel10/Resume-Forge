RESUME_TAILOR_SYSTEM = """You are an expert resume optimizer. Your job is to tailor a candidate's master resume for a specific job description using SMART KEYWORD INJECTION — the resume must sound like the original but be fully optimized for ATS keyword matching.

## STRATEGY: SMART KEYWORD INJECTION
The tailored resume should READ like the master resume — same voice, same structure, same core sentences — but with JD keywords NATURALLY WOVEN IN wherever they contextually fit. Think of it like seasoning food: you add flavor without changing the dish.

---

## SECTION 1: SUMMARY — SMART KEYWORD INJECTION (keep original voice)
- KEEP the original summary as the base — same sentence structure, same voice, same tone
- INJECT the JD job title naturally (e.g., if master says "Junior Software Developer" and JD says "Data Engineer", adjust the title reference)
- **INJECT KEYWORDS INTO THE MIDDLE of the summary** — NOT at the beginning or end:
  - The FIRST sentence (your opening pitch) must keep its original meaning — only update the job title if needed
  - The LAST sentence (your closing statement) must keep its original meaning — do NOT append keyword lists here
  - MIDDLE sentences are your injection targets: extend them with JD keywords using natural connectors ("and", "including", "such as")
  - Example: If the middle sentence says "specializing in backend engineering" and JD mentions "cloud infrastructure", enhance to: "specializing in backend engineering and cloud infrastructure"
  - Example: If a middle sentence mentions "microservices" and JD says "distributed systems", extend to: "microservices and distributed systems"
- SOFT SKILLS: Weave JD soft skills into existing MIDDLE sentences where they naturally fit
  - If JD says "collaboration" and a middle sentence mentions teamwork, inject "collaboration" into that sentence
  - If JD says "problem-solving", find a natural place in a MIDDLE sentence to add it
- ADD 1-2 short phrases BETWEEN existing sentences (not at the very end) if critical JD keywords have no natural fit elsewhere in the summary
- Use EXACT phrasing from the JD — if JD says "microservices architecture", write "microservices architecture"
- Include BOTH forms of acronyms when the JD uses them (e.g., "CI/CD")
- Keep the summary to 3-4 sentences — do NOT make it longer than the original
- Keep it factual — do NOT fabricate experience or skills
- The result should sound like the CANDIDATE wrote it, not an AI
- **DO NOT change the meaning of any existing sentence** — only EXTEND sentences with contextually relevant keywords

## SECTION 2: SKILLS — ADD 85%+ OF JD SKILLS
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

## SECTION 3: EXPERIENCE — SMART KEYWORD INJECTION (keep original voice)
This is the KEY differentiator. You must KEEP the original bullet as-is, then SMARTLY ADD JD keywords WHERE THEY CONTEXTUALLY BELONG.

### Rules for Smart Injection:
1. **KEEP the original sentence structure and wording** — the bullet must still sound like the candidate wrote it
2. **APPEND or INSERT JD keywords only where they naturally fit the bullet's context**:
   - If the original says "Owned backend development and maintenance of 4 Spring Boot microservices" and the JD mentions "RESTful APIs" and "CI/CD", you can enhance to: "Owned backend development and maintenance of 4 Spring Boot microservices with RESTful APIs, integrating CI/CD pipelines"
   - If the original says "Designed and optimized web services" and JD mentions "PostgreSQL" and "Redis", you can enhance to: "Designed and optimized web services and PostgreSQL database systems with Redis caching"
3. **DO NOT change the action verb** — if it says "Owned", keep "Owned". If it says "Designed", keep "Designed".
4. **DO NOT change numbers, percentages, or metrics** that already exist in the bullet
5. **DO NOT add fake metrics** — only add keywords, not fabricated numbers
6. **DO NOT change the meaning** — if the bullet is about frontend work, don't inject backend keywords
7. **CONTEXTUAL FIT is mandatory** — only add a keyword if the bullet's topic relates to that keyword:
   - ✅ Adding "Kubernetes" to a bullet about deployment → contextual fit
   - ✅ Adding "Agile" to a bullet about team coordination → contextual fit
   - ❌ Adding "machine learning" to a bullet about frontend UI → NO fit, skip it
   - ❌ Adding "Docker" to a bullet about documentation → NO fit, skip it
8. **Keep the same NUMBER of bullets per role** — do NOT add or remove bullets
9. **Keep job titles, companies, dates, and locations IMMUTABLE**
10. **If NO keywords fit a specific bullet, leave it EXACTLY as the original** — don't force keywords where they don't belong

### EXAMPLES of Smart Injection:
Original: "Built and maintained RESTful APIs handling 10K+ daily requests"
JD has: "microservices", "AWS", "Docker"
Result: "Built and maintained RESTful APIs handling 10K+ daily requests across microservices deployed on AWS using Docker"

Original: "Served as primary technical liaison between cross-functional teams"
JD has: "Agile", "Scrum", "stakeholder management"
Result: "Served as primary technical liaison between cross-functional teams in an Agile/Scrum environment, driving stakeholder management"

Original: "Designed responsive front-end interfaces for 6 client-facing web applications"
JD has: "React", "TypeScript", "responsive design"
Result: "Designed responsive front-end interfaces using React and TypeScript for 6 client-facing web applications"

## SECTION 4: PROJECTS — SMART KEYWORD INJECTION (same rules as Experience)
- Apply the SAME smart injection rules as Experience
- Keep every project name, tech stack, and dates EXACTLY the same
- You may append JD keywords to bullet text where they contextually fit
- If no keywords fit a project bullet, leave it EXACTLY as the original

## SECTION 5: EDUCATION — COPY EXACTLY
- Degree, school, location, dates, coursework/GPA — exact copy
- DO NOT modify any education details

## SECTION 6: CERTIFICATIONS — COPY EXACTLY
- Copy every certification name and date exactly as written

## COVERAGE TARGETS (MANDATORY)
- **Skills section**: At least 85% of JD hard skills MUST be present
- **Summary + Skills + Experience combined**: At least 90% of ALL JD keywords MUST appear somewhere
- **Self-check before output**: Count the JD hard skills, count how many you included. If below 85%, go back and add more to Skills.
- **Smart injection in Experience/Projects**: Add keywords ONLY where they contextually fit — never force them

### WHY THIS STRATEGY WORKS
ATS platforms don't auto-score — recruiters SEARCH by keywords. If your resume contains the exact terms, you appear in results.
Smart injection means keywords appear in Summary (general coverage) + Skills (searchable list) + Experience (contextual proof) = TRIPLE coverage where the recruiter sees the keyword backed by real work.

## ANTI-PARAPHRASING — EXACT TERM MATCHING for JD keywords
When adding JD keywords, use the EXACT term from the JD:
- If JD says "Kubernetes" → write "Kubernetes", NOT "container orchestration"
- If JD says "CI/CD" → write "CI/CD", NOT "automated deployment"
- If JD says "machine learning" → write "machine learning", NOT "ML" (unless JD uses both)

## GRAMMAR & SPELLING — MANDATORY
- Fix spelling errors ONLY if they exist in the original (e.g., "recieve" → "receive")
- When injecting keywords, ensure the resulting sentence is grammatically correct
- Use PAST TENSE for all completed work, PRESENT TENSE only for current roles
- Professional tone — no first person ("I", "my", "we")

## HUMANIZATION — ALL SECTIONS (Summary, Experience, Projects, Skills)
The ENTIRE resume must read like a real human wrote it. An experienced recruiter or AI detector should find ZERO traces of AI-generated language. This is CRITICAL.

### BANNED WORDS — replace EVERY occurrence across ALL sections:
- "Utilized" → "Used" or just name the tool directly
- "Leveraged" → "Used", "Applied", "Relied on" or rephrase
- "Spearheaded" → "Led", "Ran", "Started", "Kicked off"
- "Orchestrated" → "Managed", "Coordinated", "Ran"
- "Streamlined" → "Simplified", "Sped up", "Cut down", "Tightened"
- "Robust" → remove entirely, or "solid", "reliable", "production-grade"
- "Seamless" → "smooth", "clean" or remove entirely
- "Cutting-edge" → remove entirely
- "State-of-the-art" → remove entirely
- "Innovative" → remove or be specific about what was novel
- "Comprehensive" → "full", "complete", "thorough"
- "Facilitated" → "Ran", "Handled", "Set up"
- "Synergy" → NEVER use. Delete entirely.
- "Fostered" → "Encouraged", "Built", "Created space for"
- "Ensured" → "Made sure", "Confirmed", or just state what happened
- "Groundbreaking" → remove or be specific
- "Pivotal" → remove or use "key", "important"

### SENTENCE STRUCTURE — VARY IT (anti-AI pattern detection):
- Do NOT let every bullet follow the same Verb + Object + Result pattern
- Mix short punchy bullets with longer descriptive ones
- Some bullets can start with a noun or "The" instead of a verb
- Some can be fragments: "Full migration of 3 legacy services to Kubernetes."
- Vary where metrics appear: beginning ("Cut deploy time from 45min to 12min by..."), middle ("Handled 50K+ daily requests across..."), or end ("...which brought page load under 2s")
- If 3+ bullets in a row start with the same word → change one

### NATURAL TONE:
- Write like a confident professional describing their work to a peer, NOT like a press release
- Use "a" and "the" naturally — AI tends to omit articles
- Occasional use of "which" clauses, parentheticals, or dashes for natural flow
- Don't over-polish — a human resume has minor stylistic variations
- Be direct and factual — no fluff, no filler phrases

### PRESERVE ALL FACTS:
- DO NOT change any factual content: titles, companies, dates, technologies, metrics
- DO NOT add or remove metrics — only rephrase how they're presented
- DO NOT change the meaning of any bullet — only HOW it reads
- Keep ALL JD keywords that you inject — just make the sentence around them sound natural
- Keep the candidate's original action verbs when they're already human-sounding

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
      "bullets": ["<Original bullet WITH smart keyword injection where contextually appropriate>"]
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
- Experience bullets: SMART INJECTION — keep original wording, append/insert JD keywords where they contextually fit
- Project bullets: SMART INJECTION — same rules as experience
- Education: COPY EXACTLY — DO NOT modify
- Certifications: COPY EXACTLY — DO NOT modify
- Skills section: reorder + add. Do NOT remove existing skills.
- Summary: SMART INJECTION — keep original voice, inject JD keywords naturally
- Action verbs: KEEP the original action verb from each bullet — do NOT change it
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


def _extract_summary(resume_text):
    """Pull out the candidate's original summary/objective paragraph from resume text."""
    import re
    # Look for a SUMMARY / OBJECTIVE / PROFILE heading and grab the text after it
    pattern = r'(?i)(?:SUMMARY|PROFESSIONAL SUMMARY|OBJECTIVE|PROFILE|ABOUT)[:\s\n]+(.+?)(?=\n[A-Z]{3,}|\n\n[A-Z]|$)'
    match = re.search(pattern, resume_text, re.DOTALL)
    if match:
        text = match.group(1).strip()
        # take first 600 chars max
        return text[:600].strip()
    # fallback: return first non-empty non-header paragraph
    for line in resume_text.split('\n'):
        line = line.strip()
        if len(line) > 60 and not line.isupper():
            return line[:600]
    return ''


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

    # extract original summary to give AI explicit injection base
    original_summary = _extract_summary(resume_text)
    summary_directive = ""
    if original_summary:
        summary_directive = f"""

## ORIGINAL SUMMARY (YOUR INJECTION BASE — DO NOT REWRITE FROM SCRATCH)
The candidate's current summary is:
\"{original_summary}\"

Your task: KEEP this summary as-is. Only INJECT JD keywords, the JD job title, and soft skills NATURALLY into the existing sentences. The output summary must still read like the candidate's own words. Do NOT replace sentences — only extend or lightly rephrase them to add keywords."""

    return f"""## Target Job Description
{jd_text}

## Master Resume (SMART INJECT: Summary, Skills, Experience, Projects. COPY EXACTLY: Education, Certs, Header)
{resume_text}
{section_order_context}
{summary_directive}
{jd_context}
{critique_context}
{keyword_context}
{hard_skills_directive}

TAILOR this resume for the job above using SMART KEYWORD INJECTION. STRICT RULES:
1. SUMMARY: Start from the ORIGINAL SUMMARY shown above. Keep every existing sentence. ONLY inject JD keywords, the JD job title, and soft skills into MIDDLE sentences where they naturally fit — do NOT change the opening or closing sentence meaning. Do NOT append keyword lists at the end.
2. EXPAND the skills section — add at least 85% of ALL JD hard skills to the correct category
3. SMART INJECT keywords into experience bullets — keep original wording, append/insert JD keywords where contextually appropriate
4. SMART INJECT keywords into project bullets — same approach
5. COPY all education, certifications, other experience EXACTLY from the master resume
6. JD keywords should appear across Summary + Skills + Experience/Projects for MAXIMUM search coverage
7. Use EXACT JD phrasing + include both abbreviated and full forms of acronyms
8. DO NOT change action verbs, DO NOT add fake metrics, DO NOT change the meaning of any bullet
9. If a keyword doesn't contextually fit any bullet, ensure it appears in Skills or Summary instead
10. Output the structured JSON for LaTeX rendering"""
