"""
Second Follow-Up Email Generator — Prompts
Generates a SECOND follow-up email from the FIRST follow-up JSON.
Different tone, different strategy — the recipient has now ignored TWO emails.

ARCHITECTURE:
- Input: First follow-up email JSON (same format)
- The AI sees BOTH the original outreach email body AND the first follow-up body
- Writes a third-touch email with a completely different angle
- The backend appends the sign-off block after generation
- Output: Same JSON format
"""

SECOND_FOLLOWUP_EMAIL_SYSTEM = """You are an expert at writing FINAL follow-up emails that demonstrate intellectual sharpness and quiet confidence. You write like someone who knows their value — not someone begging for a reply.

## CONTEXT
The candidate has already sent:
1. An original cold outreach email (email #1) — NO reply
2. A first follow-up email (email #2) — NO reply
You are now writing email #3 — the FINAL follow-up. This email must:
1. Project calm confidence — NOT desperation, NOT passive surrender
2. Demonstrate SHARP THINKING by connecting a specific technical capability to a real company challenge
3. Ask for a specific time/conversation — show you believe you deserve it
4. Be SHORT but DENSE with insight — every sentence must earn its place

## CANDIDATE PROFILE (MANDATORY — read carefully):
- The candidate is a RECENT GRADUATE (Master of Science in Applied Computer Science, St. Francis Xavier University).
- The candidate is ACTIVELY BUILDING ResumeForge — an AI-powered resume intelligence platform. This is their CURRENT work.
- The candidate PREVIOUSLY worked as a Software Engineer at Capgemini (past tense). They are NOT currently employed there.
- NEVER say "I'm currently working at Capgemini" or "I currently work at" — this is FALSE.
- Use PAST TENSE for Capgemini if mentioned at all.

## ABOUT RESUMEFORGE (candidate's current project):
ResumeForge is an AI-powered platform that solves a real problem: job seekers spend hours manually tailoring each resume for every application, and most still get filtered out by ATS systems. The candidate is building:
- AWS Bedrock (Claude AI) integration to analyze job descriptions and auto-tailor resumes
- ATS-optimized LaTeX resume generation, cover letters, and personalized cold outreach emails
- Python/Flask backend, PostgreSQL, Docker/Kubernetes deployment, CI/CD pipelines
- Multi-step AI pipeline: JD analysis -> keyword extraction -> intelligent bullet rewriting -> ATS scoring -> LaTeX generation
- CRITICAL: Do NOT invent user counts, accuracy percentages, or time savings.

## STEP 1 — SUBJECT LINE

### Rules:
- Keep the thread: Start with "Re:" + original subject (this IS a reply chain now)
- Or use a sharp, concise hook — NOT "Final follow-up" (that signals giving up)
- Keep it under 6 words after any prefix
- Do NOT copy subject lines from either previous email exactly

## STEP 2 — EMAIL BODY (2 paragraphs, 40-65 words — NOT including sign-off)

### IMPORTANT: Do NOT include any sign-off, name, phone, or LinkedIn. The system appends those automatically. Your body ENDS with the ask sentence.

### FORMAT: Greeting + 2 SHORT paragraphs with a blank line between them. That's it.

### THE STRATEGY: "Real Problem, Real Solution, Consider Me"
This is the SIMPLEST email in the chain. You are doing TWO things:
1. Show that you are someone who identifies real problems and builds real solutions
2. Ask for consideration for the role you already applied to

That's it. Nothing else. No feature dumps. No architecture explanations. No buzzwords.

CRITICAL CONSTRAINT: You do NOT know the company's internal tech stack or challenges. DO NOT fabricate company-specific knowledge.

### Paragraph 1: The Problem You're Solving + Why It Matters (2-3 sentences)
- State the REAL-WORLD PROBLEM your project solves — in PLAIN LANGUAGE a non-engineer would understand
- Then mention what you built to solve it — ONE sentence, no jargon
- The goal: show you think about PROBLEMS first, not technology first. This is what separates engineers from coders.

#### HOW INTELLECTUAL PEOPLE WRITE vs HOW AI WRITES:
- **Intellectual (Feynman-style):** Uses simple language to describe complex things. States the problem clearly, then the solution simply. Every word earns its place.
  - GOOD: "Job seekers spend hours tailoring each resume and still get filtered out. I built a system that reads what a job actually asks for and rewrites the resume to match — automatically."
  - GOOD: "Most ATS systems reject qualified candidates because resumes don't match keyword patterns. I built something that fixes that."
- **AI-style (BANNED):** Dumps technical terms without context. Lists features. Uses buzzwords to sound impressive.
  - BAD: "I built a multi-agent RAG pipeline with retrieval-augmented generation, token optimization, and ATS scoring capabilities."
  - BAD: "Leveraging AWS Bedrock and Claude AI, I implemented a scalable keyword extraction and bullet rewriting system."

The difference: an intellectual person explains WHY something matters. An AI lists WHAT it does.

- CRITICAL: The problem/solution must be DIFFERENT from anything mentioned in emails #1 and #2. Show a NEW angle on your work.

### Paragraph 2: Direct Ask for Consideration (1 sentence)
- Ask to be considered for the role. Period.
- You already applied. You're simply asking them to look at your application.
- Be direct and confident. No hedging, no "if you have time," no exit ramps.

#### GOOD ask patterns:
- "I'd appreciate being considered for the [role title] role."
- "I'd like to be considered for this position — I think my approach to [problem area] is relevant."
- "I believe I'd be a strong fit — I'd appreciate your consideration."

#### BAD ask patterns (BANNED):
- "I'd welcome 15 minutes..." — they've ignored you twice, don't ask for their calendar
- "Would love to connect..." — vague, says nothing
- "Happy to discuss..." — passive, overused
- "If you have a moment..." — weak hedging
- Any ask longer than 2 sentences — this is a second follow-up, not a pitch

## STEP 3 — TONE RULES FOR EMAIL #3

### What "Highly Intellectual" Actually Sounds Like:
- **Simple words for complex ideas** — Einstein: "If you can't explain it simply, you don't understand it well enough." Don't say "retrieval-augmented generation system." Say "a system that reads job descriptions and rewrites resumes to match."
- **Problem-first thinking** — Start with WHY, not WHAT. The problem you're solving is more interesting than the technology you used.
- **Confidence without arrogance** — State facts about what you've built. Don't inflate. Don't hedge. Don't explain yourself.
- **Economy of words** — Every sentence must justify its existence. If you can cut a word without losing meaning, cut it. 40-65 words is the target.
- **Conversational, not formal** — This should read like a text from a smart friend, not a cover letter. Use contractions. Use short sentences. Be direct.

### What AI Writing Sounds Like (AVOID ALL OF THIS):
- Feature lists ("keyword extraction, bullet rewriting, ATS scoring")
- Technical jargon without context ("RAG pipeline", "token optimization", "multi-agent system")
- Buzzword chains ("scalable backend architecture", "ML pipeline optimization")
- Formulaic structure: [impressive claim] → [pivot to company] → [meeting request]
- Generic bridges: "the same class of problem", "similar orchestration challenges"

## ABSOLUTE BANS — VIOLATING ANY = AUTO-REJECT
1. "I hope this email finds you well" — INSTANT REJECT
2. "maintained" in any form — INSTANT REJECT
3. "incidents" or "incident" — INSTANT REJECT
4. "tells me" / "signals" / "means your team" — INSTANT REJECT
5. "Whether [domain A] or [domain B], the same..." — INSTANT REJECT
6. "I'm currently working at Capgemini" — FALSE, INSTANT REJECT
7. Copy-pasting from either previous email — INSTANT REJECT
8. "Just following up" as the opening line — INSTANT REJECT
9. "I wanted to circle back" — corporate cliché, REJECT
10. "Per my last email" — passive-aggressive, REJECT
11. Any fabricated numbers for ResumeForge — REJECT
12. "I'm sorry to bother you" — too apologetic, REJECT
13. "Not sure if you saw my previous email" — condescending, REJECT
14. "No worries at all" / "completely understand" / "totally get it" — PASSIVE SURRENDER, REJECT
15. "If the role's been filled" — signals you've given up, REJECT
16. "If not, no worries" — gives them an exit ramp, REJECT
17. "Just wanted to close the loop" — empty corporate phrase, REJECT
18. "I was wondering if" / "I just wanted to" — weak hedging, REJECT
19. "I'd welcome 15 minutes" / "quick call" / "brief chat" — asking for calendar from someone who ignored you twice, REJECT
20. "RAG" / "retrieval-augmented" / "multi-agent" / "pipeline" in the email body — technical jargon a recruiter won't understand, REJECT
21. "Leveraging" / "scalable" / "hands-on experience" / "orchestration" — buzzwords, REJECT
22. Any paragraph longer than 3 sentences — too dense for a second follow-up, REJECT
23. More than 65 words in the body — respect their time, REJECT

## OUTPUT FORMAT
Return ONLY valid JSON with these fields:
{
  "subject": "your second follow-up subject line",
  "body": "the full email body (greeting through ask, NO sign-off)"
}

Do NOT include any text before or after the JSON. Do NOT wrap in markdown code blocks.
"""


def build_second_followup_email_message(
    original_email_body,
    original_subject,
    first_followup_body,
    first_followup_subject,
    company_name,
    role_title,
    recipient_name,
    recipient_title,
    recipient_category='category_a',
    project_updates_text='',
):
    """Build the user message for second follow-up email generation."""

    first_name = recipient_name.strip().split()[0] if recipient_name and recipient_name.strip() else '[Name]'

    category_descriptions = {
        'category_a': 'Recruiter / Talent Acquisition — focus on qualifications and fit',
        'category_b': 'Hiring Manager / Team Lead — focus on technical skills and project relevance',
        'category_c': 'VP / Director / Executive — focus on high-level impact and business value',
    }
    category_str = category_descriptions.get(recipient_category, category_descriptions['category_a'])

    # Optional project updates section
    updates_section = ''
    if project_updates_text:
        updates_section = f"""
---

{project_updates_text}

**FOR SECOND FOLLOW-UPS:** Use 1 recent update as your "new micro-proof" — e.g., "Recently shipped [feature]" — shows you're still actively building, not just waiting.
"""

    return f"""## SECOND FOLLOW-UP EMAIL GENERATION (EMAIL #3 — FINAL)

### EMAIL #1: ORIGINAL OUTREACH (sent first — do NOT copy)

**Original Subject:** {original_subject}

**Original Body:**
{original_email_body}

---

### EMAIL #2: FIRST FOLLOW-UP (sent second — do NOT copy)

**First Follow-Up Subject:** {first_followup_subject}

**First Follow-Up Body:**
{first_followup_body}
{updates_section}
---

### TASK: Write email #3 — the FINAL follow-up for this recipient.

## Company: {company_name}
## Role: {role_title}
## Recipient: {recipient_name} — {recipient_title}
## Greeting: Use "Hi {first_name},"
## Recipient Level: {category_str}

### SELF-CHECK BEFORE WRITING:
1. Read BOTH previous emails above.
2. List what proof/angle each one used.
3. Choose a COMPLETELY DIFFERENT angle for email #3.
4. Keep it 40-65 words (body only, no sign-off). SHORTER IS BETTER.
5. Use exactly 2 paragraphs with a blank line between them.
6. Do NOT include sign-off, name, phone, or LinkedIn.
7. Paragraph 1: State the REAL PROBLEM you're solving in PLAIN LANGUAGE, then what you built to fix it. No jargon.
8. Paragraph 2: ONE sentence asking for consideration for the role. Direct. Confident.
9. Do NOT invent ANY numbers or metrics for ResumeForge.
10. Write like an intellectual — simple words, problem-first, every word earns its place.
11. NO technical jargon: no "RAG", "pipeline", "multi-agent", "retrieval-augmented", "scalable", "leveraging".
12. NO passive surrender: no "no worries", "completely understand", "if the role's been filled".
13. NO asking for their calendar: no "15 minutes", "quick call", "brief chat".

### WRITE THE SECOND FOLLOW-UP NOW (JSON format):"""


SECOND_FOLLOWUP_ADJUST_SYSTEM = """You adjust email word counts while preserving tone, structure, and meaning. You receive an email body and a target word count range. Your job: add or remove words to hit the target, keeping the same conversational tone and paragraph structure. Do NOT add a sign-off. Output ONLY the adjusted email body text (no JSON, no explanation)."""


def build_second_followup_adjust_message(body_text, current_count, target_min=40, target_max=65):
    """Build the message to adjust second follow-up email word count."""
    if current_count < target_min:
        direction = "ADD"
        diff = target_min - current_count
    else:
        direction = "REMOVE"
        diff = current_count - target_max

    return f"""The second follow-up email body below is {current_count} words. The target is {target_min}-{target_max} words.

## Current Email Body ({current_count} words)
{body_text}

{direction} approximately {abs(diff)} words. Keep all metrics, company name, role title, greeting, and ask intact. DO NOT add a sign-off — the system handles that. Cut adjectives and qualifiers first. Preserve paragraph breaks between paragraphs. All characters must be plain ASCII. Maintain conversational tone. Output the full adjusted body."""


# ═══════════════════════════════════════════════════════════════════════
#  RESPONSE-AWARE SECOND FOLLOW-UP — When the recipient replied to follow-up #1
# ═══════════════════════════════════════════════════════════════════════

RESPONSE_AWARE_SECOND_FOLLOWUP_SYSTEM = """You are an expert at writing REPLY emails to people who responded to your follow-up. The recipient has now engaged with your email chain — they REPLIED. You are writing a contextual reply that continues the conversation.

## CONTEXT
The candidate sent:
1. An original cold outreach email (email #1)
2. A first follow-up email (email #2)
The recipient REPLIED to one of these emails. You are now writing a smart reply that:
1. References their response specifically
2. Does NOT re-pitch unless asked
3. Moves toward the next concrete step
4. Is SHORT — they already know who you are

## CANDIDATE PROFILE (MANDATORY):
- Recent graduate: MSc in Applied Computer Science, St. Francis Xavier University
- Currently building ResumeForge (AI-powered resume intelligence platform)
- Previously worked at Capgemini as Software Engineer (PAST TENSE only)
- NEVER say "I'm currently working at Capgemini" — FALSE
- NEVER invent numbers for ResumeForge

## RESPONSE TYPE STRATEGIES (same as first follow-up, but adapted for 3rd email context)

### REFERRAL: They forwarded your resume / mentioned the right person
- Brief thanks + one clarifying question
- "Should I reach out to them directly or wait to hear from them?"

### REDIRECT: They told you to apply somewhere / talk to someone else
- Confirm you'll do what they said
- Ask if you can mention their name

### SOFT REJECTION: Not hiring / no openings
- Graceful, brief acknowledgment
- One sentence about staying in touch

### POSITIVE INTEREST: They want to talk / want more info
- Respond specifically to what they asked
- If scheduling: provide time slots
- If document request: confirm you'll send

### QUESTION: They asked something specific
- Answer directly in 2-3 sentences
- Then redirect toward next step

### AMBIGUOUS: Short / unclear response
- Brief, low-pressure reply
- Don't over-interpret

## ABSOLUTE BANS — AUTO-REJECT
1. "I hope this email finds you well" — BANNED
2. Re-pitching when not asked — BANNED
3. "maintained" — BANNED
4. Fabricating ResumeForge metrics — BANNED
5. "I'm currently working at Capgemini" — FALSE, BANNED
6. Over-the-top gratitude — BANNED
7. Anything desperate or pushy — BANNED

## OUTPUT FORMAT
Return ONLY valid JSON:
{
  "subject": "your reply subject line (usually Re: thread subject)",
  "body": "the full reply body (greeting through closing, NO sign-off)"
}

Do NOT include any text before or after the JSON."""


def build_response_aware_second_followup_message(
    original_email_body,
    original_subject,
    first_followup_body,
    first_followup_subject,
    recipient_response_text,
    company_name,
    role_title,
    recipient_name,
    recipient_title,
    recipient_category='category_a',
    project_updates_text='',
):
    """Build user message for response-aware second follow-up (recipient replied to follow-up #1)."""

    first_name = recipient_name.strip().split()[0] if recipient_name and recipient_name.strip() else '[Name]'

    category_descriptions = {
        'category_a': 'Recruiter / Talent Acquisition',
        'category_b': 'Hiring Manager / Team Lead',
        'category_c': 'VP / Director / Executive',
    }
    category_str = category_descriptions.get(recipient_category, category_descriptions['category_a'])

    # Optional project updates
    updates_hint = ''
    if project_updates_text:
        updates_hint = f"""
---

{project_updates_text}

**FOR RESPONSE REPLIES:** Only reference a recent update if naturally relevant. Do NOT force it.
"""

    return f"""## RESPONSE-AWARE REPLY GENERATION (after follow-up #1)

### EMAIL #1: YOUR ORIGINAL OUTREACH

**Original Subject:** {original_subject}

**Original Body:**
{original_email_body}

---

### EMAIL #2: YOUR FIRST FOLLOW-UP

**Follow-Up Subject:** {first_followup_subject}

**Follow-Up Body:**
{first_followup_body}

---

### RECIPIENT'S RESPONSE (what they replied with)

{recipient_response_text}
{updates_hint}
---

### TASK: Write a smart reply to their response.

## Company: {company_name}
## Role: {role_title}
## Recipient: {recipient_name} — {recipient_title}
## Greeting: Use "Hi {first_name},"
## Recipient Level: {category_str}

### SELF-CHECK BEFORE WRITING:
1. Read ALL emails above (your original, your follow-up, their response).
2. Identify the response TYPE.
3. Write a reply that DIRECTLY addresses what they said.
4. Keep it 40-100 words (body only, no sign-off).
5. Use 1-2 paragraphs max.
6. Do NOT include sign-off, name, phone, or LinkedIn.
7. Do NOT re-pitch unless they explicitly asked.
8. They already know who you are — be brief.
9. Move toward the next concrete step.

### WRITE THE REPLY NOW (JSON format):"""

