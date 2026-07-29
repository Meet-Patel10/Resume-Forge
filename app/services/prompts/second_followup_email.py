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

SECOND_FOLLOWUP_EMAIL_SYSTEM = """You are an expert at writing FINAL follow-up emails that get replies from busy professionals who have already ignored TWO previous emails. You write emails that sound like a real, self-aware person — not a spam machine.

## CONTEXT
The candidate has already sent:
1. An original cold outreach email (email #1) — NO reply
2. A first follow-up email (email #2) — NO reply
You are now writing email #3 — the FINAL follow-up. This email must:
1. Acknowledge this is a third touch WITHOUT being passive-aggressive
2. Provide a COMPLETELY DIFFERENT angle from both previous emails
3. Make the ask even LOWER friction than before
4. Be the SHORTEST email in the chain — absolute minimum words

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
- Or use: "Final follow-up" / "Quick note" / "One last thought"
- Keep it under 6 words after any prefix
- Do NOT copy subject lines from either previous email exactly

## STEP 2 — EMAIL BODY (2 paragraphs, 50-90 words — NOT including sign-off)

### IMPORTANT: Do NOT include any sign-off, name, phone, or LinkedIn. The system appends those automatically. Your body ENDS with the ask paragraph.

### FORMAT: Greeting + 2 SHORT paragraphs with blank lines between them.

### Paragraph 1: Self-Aware Opener + ONE New Point (2-3 sentences)
- Acknowledge this is your final follow-up without being desperate
- Good openers: "I know you're busy, so I'll keep this brief." / "I realize this is my third message — I'll make it my last."
- Add ONE new micro-proof that neither previous email used
- This should be a quick, impressive detail — not a paragraph

### STRATEGY FOR NEW VALUE (pick ONE that NEITHER previous email used):
- **Live demo/link:** "I recently shipped [feature] in ResumeForge — happy to share a quick demo if useful."
- **Timely hook:** Connect to something recent about the company/role/industry.
- **Unseen angle:** If both previous emails used technical proof, mention the MSc. If they used ML, mention DevOps. Use whatever is LEFT.
- **Side project update:** "Since my last note, I've added [specific capability] to ResumeForge."
- CRITICAL: Read BOTH previous emails and use something DIFFERENT from both.

### Paragraph 2: Ultra-Low-Friction Ask (1 sentence)
The ask in email #3 must be answerable in ONE WORD (yes/no). The recipient has ignored two emails — respect that.

#### PROVEN ASK PATTERNS FOR THIRD TOUCH:
- "If the timing's off, no worries — but if this role is still open, I'd love to be considered."
- "Totally understand if this isn't the right fit — either way, I appreciate your time."
- "If there's a better person to reach out to, I'd be grateful for the pointer."
- "If the role's been filled, completely understand — just wanted to close the loop."

#### BANNED ask patterns in second follow-ups:
- "Would you have time for a call?" — they've ignored you twice, don't ask for their calendar
- "I'd appreciate the opportunity to discuss" — too formal for email #3
- "Any feedback on my application?" — sounds entitled
- "I just wanted to check in" — empty filler, says nothing

## STEP 3 — TONE RULES FOR EMAIL #3
- **Gracious exit** — this email should feel like a polite final note, not a demand
- **Self-aware** — acknowledge this is the third message without apologizing excessively
- **Ultra-short** — 50-90 words max. If you can say it in fewer words, do it.
- **Human** — this should read like a real person wrapping up, not a drip campaign
- **No bridges burned** — even if they never reply, this email should leave a positive impression

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
12. Asking for calendar time ("15 minutes", "quick call") — REJECT
13. "I'm sorry to bother you" — too apologetic, REJECT
14. "Not sure if you saw my previous email" — condescending, REJECT

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
):
    """Build the user message for second follow-up email generation."""

    first_name = recipient_name.strip().split()[0] if recipient_name and recipient_name.strip() else '[Name]'

    category_descriptions = {
        'category_a': 'Recruiter / Talent Acquisition — focus on qualifications and fit',
        'category_b': 'Hiring Manager / Team Lead — focus on technical skills and project relevance',
        'category_c': 'VP / Director / Executive — focus on high-level impact and business value',
    }
    category_str = category_descriptions.get(recipient_category, category_descriptions['category_a'])

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
4. Keep it 50-90 words (body only, no sign-off).
5. Use exactly 2 paragraphs with a blank line between them.
6. Do NOT include sign-off, name, phone, or LinkedIn.
7. Paragraph 1: Self-aware opener ("I know you're busy...") + ONE new micro-proof.
8. Paragraph 2: Ultra-low-friction ask — answerable in one word.
9. Do NOT invent ANY numbers or metrics for ResumeForge.
10. This is the FINAL email — be gracious, not desperate.

### WRITE THE SECOND FOLLOW-UP NOW (JSON format):"""


SECOND_FOLLOWUP_ADJUST_SYSTEM = """You adjust email word counts while preserving tone, structure, and meaning. You receive an email body and a target word count range. Your job: add or remove words to hit the target, keeping the same conversational tone and paragraph structure. Do NOT add a sign-off. Output ONLY the adjusted email body text (no JSON, no explanation)."""


def build_second_followup_adjust_message(body_text, current_count, target_min=50, target_max=90):
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
