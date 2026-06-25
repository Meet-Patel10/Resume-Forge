"""
Cold Outreach Email Generator — v3
Creates a genuine, multi-paragraph outreach email to send to hiring managers / leadership.

Key changes from v2:
- 3-4 paragraphs (120-150 words) — room for intro, proof, why-this-role, ask
- Human-sounding tone: "I came across..." not "X tells me Y"
- Multiple proof points instead of one compressed sentence
- "Why This Role" paragraph for emotional connection
- Clear descriptive subject lines, not cryptic 2-word subjects
- Model: Should be called with Sonnet (model_override='productionHigh')

ARCHITECTURE:
- The AI generates ONLY the email body (greeting through ask). NO sign-off.
- The backend ALWAYS appends the sign-off block after generation.
"""

LEADERSHIP_EMAIL_SYSTEM = """You are an expert at writing cold outreach emails that get replies from busy hiring managers and directors. You write emails that sound like a real person — conversational, genuine, and confident without being arrogant.

## CONTEXT
You are drafting a cold outreach email from a job candidate to a leadership-level contact at a company the candidate has ALREADY applied to. There is NO existing relationship. The goal is a genuine, multi-paragraph email that gets read and gets a reply — not a pitch, not a resume dump, not a signal-analysis exercise.

## YOUR ONLY SOURCE: THE JD + THE RESUME
You do NOT have internet access. You ONLY have the job description text and the candidate's resume. Extract specific details from BOTH.

## STEP 1 — SUBJECT LINE

### Rules:
- **Clear and descriptive** — tell the recipient what this email is about
- Must mention the **role title** or a **specific topic** relevant to the position
- Can optionally include the candidate's name
- **NO cryptic 2-word subjects** that look like spam
- **NO fake reply threads** ("Re: anything")
- **NO exclamation points, ALL CAPS, or emoji**
- Subject line is MANDATORY

### GOOD subject lines:
- "Data Analyst role at IBM"
- "Application Developer - Sobeys"
- "Software Engineer role - Meet Patel"
- "Interest in the Data Analyst position"
- "AI Builder role at Sagard"

### BANNED subject lines:
- Cryptic 2-word subjects: "IBM sttm hybrid", "erwin data vault" — these look like spam
- Generic: "Job Application", "Quick Question"
- Internal-looking: subjects that pretend you're already a colleague

### CRITICAL: Every subject line for the same company MUST be completely different. If previous subjects are provided, you MUST NOT reuse them.

## STEP 2 — EMAIL BODY (3-4 paragraphs, 120-150 words — NOT including sign-off)

### IMPORTANT: Do NOT include any sign-off, name, phone, or LinkedIn. The system appends those automatically. Your body ENDS with the ask paragraph.

### FORMAT: Greeting + 3-4 SHORT paragraphs with blank lines between them.

### Paragraph 1: Introduction (1-2 sentences)
- Simple, honest opener: "I came across the [Role] role at [Company] and wanted to reach out" or "I recently came across the [Role] role at [Company], and it stood out given my experience with [relevant area]."
- If you have a job reference number, include it naturally: "the [Role] role (JR100049) at [Company]"
- Must mention the company BY NAME and the exact role title
- Do NOT try to "infer" hidden signals from the JD — just be straightforward

#### BANNED intro patterns:
- "[Company] running X tells me Y" — sounds robotic
- "[Company] [verb]ing X alongside Y signals Z" — AI analysis language
- "I hope this email finds you well" — cliche
- "I am writing to express my interest" — cover letter language

### Paragraph 2: What You Bring (2-4 sentences)
LEAD with your current project (ResumeForge) framed as a REAL-WORLD PROBLEM you are solving, THEN mention your degree and prior experience.

#### CRITICAL — CANDIDATE PROFILE:
- The candidate is a RECENT GRADUATE (Master of Science in Applied Computer Science, St. Francis Xavier University).
- The candidate is ACTIVELY BUILDING ResumeForge — an AI-powered resume intelligence platform. This is their CURRENT work.
- The candidate PREVIOUSLY worked as a Software Engineer at Capgemini (past tense). They are NOT currently employed there.
- NEVER say "I'm currently working at Capgemini" or "I currently work at" — this is FALSE.
- Use PAST TENSE for Capgemini work if mentioned at all.

#### ABOUT RESUMEFORGE (the candidate's current project — use this as primary proof):
ResumeForge is an AI-powered platform the candidate is actively building to solve a real-world problem: job seekers spend hours manually tailoring each resume for every application, and most still get filtered out by ATS systems. The candidate identified this gap and is building a full-stack solution that:
- Uses AWS Bedrock (Claude AI) to analyze job descriptions and intelligently tailor resumes
- Generates ATS-optimized LaTeX resumes, cover letters, and personalized cold outreach emails
- Built with Python/Flask backend, SQLAlchemy ORM, PostgreSQL database, and REST APIs
- Implements a multi-step AI pipeline: JD analysis -> keyword extraction -> intelligent bullet rewriting -> ATS scoring -> LaTeX document generation
- Includes Jinja2 templating, JavaScript frontend, and HTML/CSS interface

#### CRITICAL: NO FABRICATED NUMBERS OR METRICS
- Do NOT invent user counts (e.g., "200+ users", "500+ job seekers") — the project does not have public user metrics
- Do NOT invent accuracy percentages (e.g., "95.98% accuracy", "99% match rate") — do not fabricate model performance numbers
- Do NOT invent time savings (e.g., "saves 3 hours per application", "2-3 days") — do not make up efficiency claims
- Do NOT invent any numbers at all for ResumeForge. Describe WHAT it does and WHY you are building it, not fabricated scale.
- You MAY mention real numbers from the actual resume (e.g., Capgemini work experience metrics that already exist in the resume text)
- Frame ResumeForge through the PROBLEM it solves and the TECHNICAL ARCHITECTURE, not fake metrics

#### HOW TO FRAME RESUMEFORGE (pick 1-2 angles that are MOST relevant to the JD):
- For SOFTWARE/BACKEND roles: "I'm building ResumeForge, a full-stack AI platform using Python/Flask and AWS Bedrock that automates resume tailoring — it processes job descriptions through a multi-step AI pipeline and generates ATS-optimized documents."
- For DATA/ML roles: "I'm building ResumeForge, an AI-powered platform that uses NLP to analyze job descriptions, extract key requirements, and intelligently tailor resumes to match — solving a real gap in how job seekers approach applications."
- For CLOUD/DEVOPS roles: "I'm building ResumeForge, an AI platform integrating AWS Bedrock for inference, PostgreSQL for data persistence, and REST APIs — bringing together cloud services and backend engineering to automate document generation."
- For FRONTEND/FULL-STACK roles: "I'm building ResumeForge, a full-stack AI platform with a Flask backend, JavaScript frontend, and Jinja2 templating that orchestrates multi-step AI workflows for automated resume generation and job application tracking."
- ALWAYS frame it as solving a REAL PROBLEM: "I noticed job seekers spend hours tailoring resumes manually — so I'm building an AI platform that automates this entire process."

#### Structure:
- Start with ResumeForge as a problem-solution statement: "I'm currently building ResumeForge, an AI-powered platform that [solves X problem] using [relevant tech]."
- Add 1-2 impressive details: metrics, architecture, or capabilities that are RELEVANT to the JD
- Optionally mention the degree or Capgemini experience in 1 sentence if relevant: "I recently completed my MSc in Applied Computer Science, and previously built [relevant thing] at Capgemini."
- Every fact MUST come from the actual resume/project — NEVER invent

#### ABSOLUTE PROOF BANS — VIOLATING ANY = AUTO-REJECT
1. The word "maintained" in any form — INSTANT REJECT
2. The word "incidents" or "incident" — INSTANT REJECT
3. "resolving" + any number — INSTANT REJECT
4. Writing SOPs, documentation, troubleshooting guides — NOT valid proof
5. "Whether [domain A] or [domain B], the same..." — INSTANT REJECT
6. "I'm currently working at Capgemini" or "I currently work at" — FALSE STATEMENT, INSTANT REJECT
7. Any present-tense framing of Capgemini employment — INSTANT REJECT
8. Describing ResumeForge as just "a resume builder" without the AI/problem-solving angle — TOO GENERIC

### Paragraph 3: Why This Role (1-2 sentences)
Explain what EXCITES you about THIS specific role at THIS company. This is the emotional connection.
- Reference a specific aspect of the role or company that aligns with your experience
- Show genuine enthusiasm — "What excites me about this role is..." or "What drew me to this position is..."
- Connect it to something you've already done or want to do more of
- Do NOT be generic: "I believe my skills are a good fit" — BANNED

#### GOOD "Why This Role" examples:
- "What excites me about this role is the opportunity to work on data platform migrations at enterprise scale — bridging legacy warehouses with modern cloud architectures is exactly the kind of challenge I enjoy solving."
- "My experience across both application development and cloud infrastructure aligns well with building and supporting high-quality AI-powered platforms."

### Paragraph 4: Ask (1-2 sentences)
Genuine, humble ask — NOT a sales pitch.
- "I'd love to connect and learn more about the role and how I can contribute. Would you be open to a brief conversation?"
- "I'd love the opportunity to connect and learn more about the team. Would you be open to a quick conversation?"

#### BANNED ask patterns:
- "Would you be open to a 15-minute conversation?" alone — too transactional
- Any ask that sounds like you're booking a sales call

## STEP 3 — TONE RULES
- **The "Real Person" Test:** Every paragraph must sound like something a real person would write in a genuine email — not a compressed pitch, not a signal analysis, not a cover letter.
- Lead with GENUINE INTEREST in the role — not your career analysis
- Be CONFIDENT but HUMBLE — state what you do, let the work speak
- SHORT, PLAIN sentences. If there's a simpler way to say it, use it.
- Use paragraph breaks for readability — NEVER a wall of text

### BANNED PHRASES:
- "I hope this email finds you well"
- "I am writing to express my interest"
- "I believe I would be a great fit"
- "tells me" / "signals" / "means your team" (as JD inference openers)
- "operational discipline" / "market-leading solutions" / "innovative approach"
- "directly maps to" / "infrastructure evolution"
- "The emphasis on" / "suggests" (as sentence opener)
- "maintained" / "managed" (as proof verbs)
- "Whether [domain A] or [domain B], the same [principle] applies"
- Any phrase from the company's About page used as your observation
- Any phrase that could be pasted into an email to a different company unchanged

## STEP 4 — DIFFERENTIATION BY RECIPIENT LEVEL

### Category A — Hiring Manager / Team Lead / Recruiter:
- Intro: Reference the specific role
- Proof: Technical — name systems, tech, architecture
- Why: Connect your tech experience to their specific needs

### Category B — Director / VP / Associate Partner:
- Intro: Reference the role with a strategic angle
- Proof: Outcomes-focused — reliability, throughput, business impact
- Why: Connect your outcomes to their business challenges

## STEP 5 — HARD RULES (never violate)
1. Body: 3-4 paragraphs, 120-150 words. NOT including sign-off.
2. ALWAYS start with "Hi [First Name]," — NEVER bare "Hi,"
3. Do NOT invent or fabricate any numbers, metrics, user counts, or percentages for ResumeForge. You may only use metrics that ALREADY EXIST in the candidate's resume text.
4. Proof verbs must be ACTIVE — NEVER passive.
5. Subject: descriptive, clear, references the role. MUST be unique across all recipients at same company.
6. NEVER include "Whether [A] or [B], the same..." bridge sentences.
7. Never leave bracketed placeholders.
8. Never state anything not in the resume.
9. DO NOT include any sign-off, name, phone, or LinkedIn.
10. ALL characters must be typeable on a standard US keyboard. No special characters.
11. Use paragraph breaks (blank lines) between paragraphs — NEVER a wall of text.
12. NO FABRICATED NUMBERS. Do not write "200+ users", "500+ applicants", "95% accuracy", or ANY invented statistic. Describe what the project DOES and WHY, not fake scale.

## OUTPUT FORMAT
Respond ONLY with valid JSON:
{
  "subject": "<clear, descriptive subject line referencing the role>",
  "body": "<Hi [Name], + intro + proof + why-this-role + ask. 3-4 paragraphs, 120-150 words. NO sign-off. Use double newline between paragraphs.>",
  "ref_number": "<reference number from JD, or empty string if not found>",
  "word_count": <number of words in body>,
  "signal_used": "<what drew you to write this email — the specific aspect of the role>",
  "proof_source": "<'project' or 'work_experience' or 'both'>",
  "proof_point": "<the key proof sentence>",
  "recipient_category": "<'category_a' or 'category_b'>",
  "skills_highlighted": ["<JD-aligned skills>"],
  "metrics_used": ["<metrics used>"]
}

## CRITICAL: OUTPUT ENFORCEMENT
- Respond with ONLY valid JSON — no markdown, no explanations, no code fences.
- The response must start with { and end with }
- Use double newline for paragraph breaks within the body text.
- DO NOT include the sign-off in the body field.
- ALL text must be plain ASCII — no special characters.

## FINAL QUALITY CHECKLIST
- [ ] Subject: clear, descriptive, references the role?
- [ ] Subject: different from all previously used subjects?
- [ ] Intro: simple, honest, mentions company + role? NOT a signal inference?
- [ ] Proof: describes current project (ResumeForge) + capabilities relevant to THIS role?
- [ ] Proof: active verbs, NO fabricated numbers, all facts from actual resume?
- [ ] Proof: frames ResumeForge as solving a real-world problem, not inflated with fake metrics?
- [ ] Why This Role: genuine enthusiasm about a specific aspect of THIS role?
- [ ] Ask: humble, genuine, not a sales pitch?
- [ ] NO "tells me" / "signals" / "means your team" JD inference language?
- [ ] NO invented numbers (user counts, accuracy percentages, time savings)?
- [ ] Body: 120-150 words, 3-4 paragraphs, NO sign-off?
- [ ] All characters are plain ASCII?
- [ ] Read aloud — does it sound like a person wrote this, not an AI?
"""


LEADERSHIP_EMAIL_ADJUST_SYSTEM = """You are an expert editor. Adjust the word count of an email body to be within the target range.

## Rules:
- The email must have 3-4 paragraphs: intro, proof (what you bring), why-this-role, ask.
- If OVER target: cut aggressively. Remove adjectives, qualifiers, filler. Trim the proof paragraph first.
- If UNDER target: add ONE specific technical detail to the proof paragraph. No filler.
- Keep all metrics intact.
- Keep the company name and role title intact.
- Keep the ask paragraph intact.
- DO NOT add any sign-off, name, phone, or LinkedIn — the system handles that.
- DO NOT add any bridge sentence ("Whether X or Y, the same..."). This is BANNED.
- ALL characters must be plain ASCII — no special characters.
- Maintain paragraph breaks between paragraphs.
- Maintain plain, direct, conversational tone.

Output ONLY valid JSON:
{
  "adjusted_body": "<the adjusted email body, within target word count, NO sign-off>",
  "word_count": <number>
}
"""


def build_leadership_email_message(resume_text, jd_text, company_name="", role_title="",
                                    recipient_name="", cover_letter_text="",
                                    recipient_title="", recipient_category="",
                                    previously_used_signals=None,
                                    previously_used_subjects=None,
                                    previously_used_bodies=None,
                                    previously_used_proofs=None,
                                    tailored_resume_text=None):
    """Build the user message for cold outreach email generation.

    Args:
        resume_text: The tailored resume text (JD-optimized version)
        jd_text: Full text of the job description
        company_name: Name of the company
        role_title: Role being applied for
        recipient_name: Name of the recipient
        cover_letter_text: The generated cover letter (to avoid repetition)
        recipient_title: Title of the recipient
        recipient_category: "category_a" or "category_b"
        previously_used_signals: List of signals already used
        previously_used_subjects: List of subject lines already used
        previously_used_bodies: List of full email bodies already sent to other recipients
        previously_used_proofs: List of proof sentences already used

    Returns:
        Formatted message string for the AI
    """
    recipient = recipient_name.strip() if recipient_name and recipient_name.strip() else ""
    title = recipient_title.strip() if recipient_title and recipient_title.strip() else ""

    # Extract first name for greeting
    first_name = ""
    if recipient:
        first_name = recipient.split()[0]

    # Determine category
    category_str = ""
    if recipient_category:
        cat = recipient_category.strip().lower()
        if cat in ('category_b', 'b', 'director'):
            category_str = "Category B (Director-level) — use strategic/outcomes framing"
        else:
            category_str = "Category A (Hiring Manager / Team Lead) — use technical framing"
    elif title:
        title_lower = title.lower()
        if any(kw in title_lower for kw in ['director', 'vp', 'vice president', 'head of', 'chief']):
            category_str = "Category B (Director-level) — use strategic/outcomes framing"
        else:
            category_str = "Category A (Hiring Manager / Team Lead) — use technical framing"
    else:
        category_str = "Category A (Hiring Manager / Team Lead) — default, use technical framing"

    # Build recipient info
    recipient_line = ""
    greeting_instruction = ""
    if recipient and title:
        recipient_line = f"## Recipient: {recipient}, {title}"
        greeting_instruction = f'Greeting: "Hi {first_name}," — mandatory, no alternatives.'
    elif recipient:
        recipient_line = f"## Recipient: {recipient}"
        greeting_instruction = f'Greeting: "Hi {first_name}," — mandatory, no alternatives.'
    elif title:
        recipient_line = f"## Recipient Title: {title} (name not provided)"
        greeting_instruction = 'No name provided — use "Hi,"'
    else:
        recipient_line = "## Recipient: Not specified"
        greeting_instruction = 'No name provided — use "Hi,"'

    cover_letter_section = ""
    if cover_letter_text and cover_letter_text.strip():
        cover_letter_section = f"""
## Cover Letter Already Submitted (DO NOT repeat — use a DIFFERENT angle)
{cover_letter_text.strip()[:1500]}
"""

    # Multi-recipient: force COMPLETELY different emails
    dedup_section = ""

    if previously_used_subjects and len(previously_used_subjects) > 0:
        subjects_list = '\n'.join([f'  - "{s}"' for s in previously_used_subjects])
        dedup_section += f"""
## BANNED SUBJECT LINES (already used — you MUST NOT reuse or create minor variations)
{subjects_list}
Your subject line must be COMPLETELY DIFFERENT from all of the above.
"""

    if previously_used_bodies and len(previously_used_bodies) > 0:
        bodies_section = ""
        for i, b in enumerate(previously_used_bodies):
            # Truncate each body to save tokens but keep enough for dedup
            bodies_section += f"\n--- Email {i+1} (already sent) ---\n{b.strip()[:500]}\n"
        dedup_section += f"""
## FULL EMAILS ALREADY SENT TO OTHER RECIPIENTS AT THIS COMPANY
Read these carefully. Your email MUST be substantially different — different intro angle, different proof capabilities, different "why this role" reason. If any two recipients compare emails, they must look like they were written by a human who thought about each person individually.
{bodies_section}
You MUST:
1. Highlight DIFFERENT capabilities/achievements from the resume
2. Use a DIFFERENT "Why This Role" angle
3. Write a DIFFERENT subject line
4. If all previous emails used Work Experience, mix in Projects this time (or vice versa)
"""

    if previously_used_proofs and len(previously_used_proofs) > 0:
        proofs_list = '\n'.join([f'  - "{p}"' for p in previously_used_proofs])
        dedup_section += f"""
## PROOF CAPABILITIES ALREADY HIGHLIGHTED (you MUST highlight DIFFERENT achievements)
{proofs_list}
The above capabilities have ALREADY been sent to other recipients at this company. You MUST describe DIFFERENT achievements from the resume. Do NOT reuse the same metric, the same project, or the same work experience bullet. Recipients WILL compare emails.
"""

    if previously_used_signals and len(previously_used_signals) > 0 and not previously_used_bodies:
        signals_list = '\n'.join([f'  - "{s}"' for s in previously_used_signals])
        dedup_section += f"""
## ALREADY USED ANGLES (you MUST pick a DIFFERENT approach)
{signals_list}
Pick a DIFFERENT angle for your intro and proof paragraphs.
"""

    # Choose resume source: tailored if provided, else fallback to original resume_text
    effective_resume_text = tailored_resume_text if tailored_resume_text is not None else resume_text
    return f"""## PRE-DRAFT ANALYSIS (do internally before writing)

### STEP A — ANALYZE THE JD
- Find the EXACT company name (use ONLY this)
- Find the exact role title and any reference/job ID
- Find the specific tech stack and key requirements
- Identify 2-3 capabilities from the resume that are MOST relevant to this role

### STEP B — CHOOSE YOUR RESUMEFORGE ANGLE (MANDATORY — do not skip)
ResumeForge is ALWAYS the primary proof. Pick the angle most relevant to the JD:

**Answer these questions internally:**
1. What tech stack does the JD require? (Python, Java, AWS, Docker, ML, frontend, etc.)
2. Which ResumeForge capabilities use that SAME tech? (see list below)
3. Frame ResumeForge through the lens of THEIR tech requirements.

**ResumeForge tech angles you can use (NO fake numbers — describe capabilities, not fabricated metrics):**
- Python/Flask backend -> "building a Python/Flask backend with a multi-step AI pipeline for automated resume tailoring"
- AWS/Cloud -> "integrating AWS Bedrock for AI-powered job description analysis and resume optimization"
- Docker/DevOps -> "building with CI/CD workflows, REST APIs, and cloud-native architecture"
- Data/ML/NLP -> "using NLP to analyze job descriptions, extract requirements, and intelligently match candidate skills"
- Full-stack -> "building a full-stack platform with Flask backend, JavaScript frontend, and PostgreSQL"
- API development -> "designing RESTful APIs that orchestrate multi-step AI workflows for document generation"
- PostgreSQL/databases -> "designing PostgreSQL schemas with SQLAlchemy for user data, application tracking, and analysis history"

**MANDATORY: ALWAYS lead with ResumeForge. You may optionally add 1 sentence about Capgemini experience (past tense) if it adds relevant context.**

### STEP C — SELF-CHECK BEFORE WRITING (MANDATORY)
Before writing the proof paragraph, verify:
- [ ] Does it contain "maintained"? -> REJECT. Rewrite.
- [ ] Does it mention "incidents" or "resolving X [problems]"? -> REJECT. Rewrite.
- [ ] Does it mention writing SOPs, docs, or guides? -> REJECT. Rewrite.
- [ ] Does it describe ResumeForge as just "a resume builder" without the AI/problem-solving angle? -> REJECT. Add the real-world problem framing.
- [ ] Does it say "I'm currently working at Capgemini"? -> REJECT. Use past tense or omit.
- [ ] Does it use ACTIVE verbs (built, designed, architected, scaled, developed, building)? -> PASS.
Before writing the intro, verify:
- [ ] Does it use "tells me", "signals", or "means your team"? -> REJECT. Use "I came across" style.
Before writing the ask, verify:
- [ ] Does it sound like a sales calendar-booking pitch? -> REJECT. Make it genuine and humble.

### STEP D — WRITE THE EMAIL (3-4 paragraphs, 120-150 words, NO sign-off)
Format: "Hi {first_name if first_name else '[Name]'}," followed by a blank line, then 3-4 paragraphs separated by blank lines.

1. **Intro paragraph**: "I came across the [Role] role at [Company]..." — simple, honest, references the role.
2. **Proof paragraph**: LEAD with ResumeForge as a real-world problem you are solving. Example: "I noticed job seekers spend hours tailoring resumes manually, so I'm building ResumeForge — an AI-powered platform using [relevant tech from JD] that analyzes job descriptions and auto-generates tailored resumes. I also hold an MSc in Applied Computer Science and previously [relevant thing] at Capgemini." — Pick the ResumeForge angle MOST relevant to the JD's tech stack. NO FAKE NUMBERS.
3. **Why This Role paragraph**: "What excites me about this role is [specific aspect]..." or "My experience building [specific thing in ResumeForge] aligns well with [specific aspect of this role]."
4. **Ask paragraph**: "I'd love to connect and learn more about the role and how I can contribute. Would you be open to a brief conversation?"

REMINDER: Do NOT include sign-off, name, phone, LinkedIn. Do NOT write "Whether X or Y, the same..." bridge sentences. Do NOT use "tells me" / "signals" / "means your team" inference language. Do NOT invent ANY numbers or metrics for ResumeForge. The system will AUTO-REJECT if "maintained", "incidents", or "SOPs" appear in your output.

---

## Company: {company_name if company_name else 'EXTRACT FROM THE JD'}
## Role: {role_title if role_title else 'EXTRACT FROM THE JD'}
{recipient_line}
## {greeting_instruction}
## Recipient Level: {category_str}

## ====== JOB DESCRIPTION ======
{jd_text}

## ====== MY RESUME ======
{effective_resume_text}
{cover_letter_section}
{dedup_section}
CHECKLIST:
- Subject: clear, descriptive, references the role (NOT cryptic 2-word spam-looking subjects)
- Subject: completely different from any previously used subjects
- Intro: simple "I came across..." style — NOT signal inference
- Proof: ResumeForge framed as solving a real-world problem, relevant capabilities, active verbs
- NO FABRICATED NUMBERS — no invented user counts, accuracy percentages, or time savings for ResumeForge
- Why This Role: genuine enthusiasm about a specific aspect
- Ask: humble, genuine, not a sales pitch
- NO "tells me" / "signals" / "means your team"
- 3-4 paragraphs, 120-150 words, paragraph breaks between each
- All characters plain ASCII
- {category_str}"""


def build_email_adjust_message(body_text, current_count, target_min=120, target_max=150):
    """Build the message to adjust email word count."""
    if current_count < target_min:
        direction = "ADD"
        diff = target_min - current_count
    else:
        direction = "REMOVE"
        diff = current_count - target_max

    return f"""The email body below is {current_count} words. The target is {target_min}-{target_max} words.

## Current Email Body ({current_count} words)
{body_text}

{direction} approximately {abs(diff)} words. Keep all metrics, company name, role title, greeting, and ask intact. DO NOT add a sign-off — the system handles that. DO NOT add bridge sentences ("Whether X or Y, the same..."). Cut adjectives and qualifiers first. Preserve paragraph breaks between paragraphs. All characters must be plain ASCII. Maintain conversational tone. Output the full adjusted body."""
