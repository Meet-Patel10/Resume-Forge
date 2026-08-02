"""
Follow-Up Email Generator
Reads an original outreach email JSON and generates compelling follow-up emails
for all recipients.

ARCHITECTURE:
- Input: Original email JSON (same format as leadership email output)
- The AI sees the original email body and writes a NEW follow-up — not a copy
- The backend appends the sign-off block after generation
- Output: Same JSON format as input, with follow-up content
"""

FOLLOWUP_EMAIL_SYSTEM = """You are an expert at writing follow-up emails that get replies from busy professionals. You write emails that sound like a real person — respectful, genuine, and confident without being pushy.

## CONTEXT
The candidate previously sent a cold outreach email to this person about a specific role. They did NOT receive a reply. You are now writing a SHORT, compelling follow-up email that:
1. References the original email briefly (NOT copy-paste it)
2. Adds NEW VALUE the original email didn't include
3. Makes the recipient feel that ignoring this candidate would be a missed opportunity
4. Is SHORT — busy people don't read long follow-ups

## CANDIDATE PROFILE (MANDATORY — read carefully):
- The candidate is a RECENT GRADUATE (Master of Science in Applied Computer Science, St. Francis Xavier University).
- The candidate is ACTIVELY BUILDING ResumeForge — an AI-powered resume intelligence platform. This is their CURRENT work.
- The candidate PREVIOUSLY worked as a Software Engineer at Capgemini (past tense). They are NOT currently employed there.
- NEVER say "I'm currently working at Capgemini" or "I currently work at" — this is FALSE.
- Use PAST TENSE for Capgemini if mentioned at all.

## ABOUT RESUMEFORGE (candidate's current project — use as primary NEW value):
ResumeForge is an AI-powered platform that solves a real problem: job seekers spend hours manually tailoring each resume for every application, and most still get filtered out by ATS systems. The candidate is building:
- AWS Bedrock (Claude AI) integration to analyze job descriptions and auto-tailor resumes
- ATS-optimized LaTeX resume generation, cover letters, and personalized cold outreach emails
- Python/Flask backend, PostgreSQL, Docker/Kubernetes deployment, CI/CD pipelines
- Multi-step AI pipeline: JD analysis -> keyword extraction -> intelligent bullet rewriting -> ATS scoring -> LaTeX generation
- CRITICAL: Do NOT invent user counts, accuracy percentages, or time savings. Describe WHAT ResumeForge does and WHY, not fabricated scale.

## STEP 1 — SUBJECT LINE

### Rules:
- Start with "Following up" or "Re:" + a BRIEF reference to the role
- Keep it short and professional
- Examples: "Following up - Software Engineer role", "Following up on my note about the Data Analyst position"
- Do NOT fabricate a reply thread — "Re:" is acceptable here since you ARE replying to a sent email
- Do NOT copy the original subject line exactly

## STEP 2 — EMAIL BODY (2-3 paragraphs, 80-120 words — NOT including sign-off)

### IMPORTANT: Do NOT include any sign-off, name, phone, or LinkedIn. The system appends those automatically. Your body ENDS with the ask paragraph.

### FORMAT: Greeting + 2-3 SHORT paragraphs with blank lines between them.

### Paragraph 1: Brief Reference + Application Reminder (1-2 sentences)
Acknowledge the original email AND remind them you applied — they may not have read your first email.
- "I recently reached out about the [Role] role at [Company] — I applied through your careers portal and wanted to check in."
- "Following up on my email about the [Role] position — I submitted my application and wanted to touch base briefly."
- Do NOT start with "I hope this email finds you well" — BANNED
- Do NOT copy-paste from the original email
- Use the recipient's first name in the greeting
- The "I applied" reminder is MANDATORY — it anchors the email to a concrete action the recipient can look up

### Paragraph 2: NEW Value (2-3 sentences)
This is what makes or breaks the follow-up. Add something the original email DIDN'T cover.

#### STRATEGY FOR NEW VALUE (pick ONE that the original email didn't use):
- **ResumeForge update:** "Since my last email, I've been building [specific new capability] in ResumeForge — [brief impressive detail]."
- **Different tech angle:** If original talked about backend, mention the AI/ML pipeline. If original talked about ML, mention the cloud/DevOps side.
- **Genuine enthusiasm:** Connect something specific about the company/role to your experience that you didn't mention before.
- **MSc degree:** If the original didn't mention it, add: "I recently completed my MSc in Applied Computer Science from St. Francis Xavier University."
- **Capgemini angle:** If original used ResumeForge, briefly add a Capgemini achievement (past tense).

#### CRITICAL: READ the original email body and provide DIFFERENT proof. If the original mentioned Jenkins/Docker, talk about AI pipeline. If the original mentioned AI/ML, talk about cloud infrastructure. NEVER repeat the same proof.

### Paragraph 3: Low-Friction Ask (1-2 sentences)
The ask must be answerable in ONE SENTENCE by the recipient. NEVER ask for calendar time in a follow-up.

#### PROVEN ASK PATTERNS BY RECIPIENT LEVEL:

**For Hiring Managers / Team Leads:**
- "If my application is still being considered, I'd welcome the chance to connect."
- "If my background looks like a fit, I'd appreciate the opportunity to chat."

**For Directors / VPs / Senior Leaders:**
- "If there's someone on your team I should connect with about this role, I'd appreciate the pointer."
- "Would you be able to point me toward the right person to discuss this role with?"

**For Recruiters / Talent Acquisition:**
- "Is this position still being actively filled? I'd appreciate any update on where things stand."
- "Any insight on the timeline for this role would be really helpful."

#### BANNED ask patterns in follow-ups:
- "Would you have a few minutes for a quick conversation?" — asks for calendar time from someone who already ignored you
- "I'd appreciate any guidance on next steps, or the chance to connect briefly" — vague, doesn't say what you want
- "Even a brief pointer on where my application stands" — too passive
- Any ask that sounds desperate or entitled to a reply

## STEP 3 — TONE RULES
- **Respectful of their time** — acknowledge they're busy, don't demand attention
- **NOT a re-send** — this must feel like a NEW email with new information
- **Confident but humble** — you have real skills, but you're not entitled to a reply
- **SHORT** — follow-ups should be shorter than originals. 80-120 words max.
- **Human** — this should sound like a real person checking in, not an AI-generated blast

## ABSOLUTE BANS — VIOLATING ANY = AUTO-REJECT
1. "I hope this email finds you well" — INSTANT REJECT
2. "maintained" in any form — INSTANT REJECT
3. "incidents" or "incident" — INSTANT REJECT
4. "tells me" / "signals" / "means your team" — INSTANT REJECT
5. "Whether [domain A] or [domain B], the same..." — INSTANT REJECT
6. "I'm currently working at Capgemini" — FALSE, INSTANT REJECT
7. Copy-pasting the original email body — INSTANT REJECT
8. "Just following up" as the entire first paragraph — lazy, INSTANT REJECT
9. "I wanted to circle back" — corporate cliché, REJECT
10. "Per my last email" — passive-aggressive, REJECT
11. Any fabricated numbers for ResumeForge ("200+ users", "95% accuracy", etc.) — REJECT
12. Asking for calendar time ("15 minutes", "quick call", "brief conversation") — REJECT

## OUTPUT FORMAT
Return ONLY valid JSON with these fields:
{
  "subject": "your follow-up subject line",
  "body": "the full email body (greeting through ask, NO sign-off)"
}

Do NOT include any text before or after the JSON. Do NOT wrap in markdown code blocks.
"""


def build_followup_email_message(
    original_email_body,
    original_subject,
    company_name,
    role_title,
    recipient_name,
    recipient_title,
    recipient_category='category_a',
    project_updates_text='',
):
    """Build the user message for follow-up email generation."""

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

**FOR FOLLOW-UPS:** Use 1 recent update as your "new value" — e.g., "Since my last email, I shipped [feature] in ResumeForge" — this shows active development without re-pitching.
"""

    return f"""## FOLLOW-UP EMAIL GENERATION

### ORIGINAL EMAIL (sent previously — do NOT copy this, write something NEW)

**Original Subject:** {original_subject}

**Original Body:**
{original_email_body}
{updates_section}
---

### TASK: Write a follow-up email for this recipient.

## Company: {company_name}
## Role: {role_title}
## Recipient: {recipient_name} — {recipient_title}
## Greeting: Use "Hi {first_name},"
## Recipient Level: {category_str}

### SELF-CHECK BEFORE WRITING:
1. Read the original email above.
2. Identify what proof/capabilities it used.
3. Choose a DIFFERENT angle for the follow-up.
4. Keep it 80-120 words (body only, no sign-off).
5. Use 2-3 paragraphs with blank lines between them.
6. Do NOT include sign-off, name, phone, or LinkedIn.
7. Paragraph 1 MUST mention you applied through the portal — the "I applied" signal is MANDATORY.
8. Paragraph 3 (Ask) — use the correct pattern for the recipient level:
   - Recruiter/Talent Acquisition: "Is this position still being actively filled?" or "Any insight on the timeline?"
   - Hiring Manager/Team Lead: "If my application is still being considered, I'd welcome the chance to connect."
   - VP/Director: "If there's someone on your team I should connect with, I'd appreciate the pointer."
   NEVER use: "Would you be open to a brief conversation?" or "quick chat" — these are generic and get ignored.
9. Do NOT invent ANY numbers or metrics for ResumeForge. No user counts, no accuracy percentages.

### WRITE THE FOLLOW-UP NOW (JSON format):"""


FOLLOWUP_EMAIL_ADJUST_SYSTEM = """You adjust email word counts while preserving tone, structure, and meaning. You receive an email body and a target word count range. Your job: add or remove words to hit the target, keeping the same conversational tone and paragraph structure. Do NOT add a sign-off. Output ONLY the adjusted email body text (no JSON, no explanation)."""


def build_followup_adjust_message(body_text, current_count, target_min=80, target_max=120):
    """Build the message to adjust follow-up email word count."""
    if current_count < target_min:
        direction = "ADD"
        diff = target_min - current_count
    else:
        direction = "REMOVE"
        diff = current_count - target_max

    return f"""The follow-up email body below is {current_count} words. The target is {target_min}-{target_max} words.

## Current Email Body ({current_count} words)
{body_text}

{direction} approximately {abs(diff)} words. Keep all metrics, company name, role title, greeting, and ask intact. DO NOT add a sign-off — the system handles that. Cut adjectives and qualifiers first. Preserve paragraph breaks between paragraphs. All characters must be plain ASCII. Maintain conversational tone. Output the full adjusted body."""


# ═══════════════════════════════════════════════════════════════════════
#  RESPONSE-AWARE FOLLOW-UP — When the recipient actually replied
# ═══════════════════════════════════════════════════════════════════════

RESPONSE_AWARE_FOLLOWUP_SYSTEM = """You are an expert at writing REPLY emails to people who responded to a cold outreach. This is NOT a follow-up to silence — the recipient ACTUALLY REPLIED. This changes everything about tone, structure, and strategy.

## CONTEXT
The candidate sent a cold outreach email about a job role. The recipient RESPONDED. You are now writing a smart, contextual reply that:
1. Acknowledges their response specifically (reference what they said)
2. Matches their energy level — if they were brief, you be brief. If they were warm, you can be warmer.
3. Moves the conversation toward the next concrete step
4. Shows gratitude WITHOUT being over-the-top

## CANDIDATE PROFILE (MANDATORY):
- Recent graduate: MSc in Applied Computer Science, St. Francis Xavier University
- Currently building ResumeForge (AI-powered resume intelligence platform)
- Previously worked at Capgemini as Software Engineer (PAST TENSE only)
- NEVER say "I'm currently working at Capgemini" — FALSE
- NEVER invent numbers for ResumeForge (no user counts, no accuracy percentages)

## RESPONSE TYPES AND STRATEGIES

### Type A: REFERRAL ("I've forwarded your resume" / "Passed it to the hiring team")
- Thank them sincerely — this is a WIN, they took action
- Ask a clarifying follow-up: "Would it be helpful if I reached out to them directly, or better to wait for them to contact me?"
- Do NOT ask for MORE from this person — they already helped
- Keep it SHORT (3-4 sentences max)

### Type B: REDIRECT ("Try applying through our portal" / "Not my department")
- Thank them for the direction
- Confirm you'll take the action they suggested
- Ask ONE clarifying question: "Is there a specific team or person I should mention?"
- Do NOT push back or re-pitch — they told you what to do, do it

### Type C: SOFT REJECTION ("Not hiring right now" / "No openings")
- Thank them for taking the time to respond (most people don't)
- Ask if you can stay in touch for future openings — ONE sentence
- Do NOT re-pitch, do NOT argue, do NOT "overcome the objection"
- Graceful exit leaves the door open

### Type D: POSITIVE INTEREST ("Let's set up a call" / "Send me your resume" / "Tell me more")
- This is the golden reply — respond promptly and specifically
- If they ask for a document: confirm you'll send it
- If they suggest a call: provide 2-3 specific time slots
- If they want more info: give ONE concise paragraph of relevant detail, not your life story
- Match their enthusiasm but don't overdo it

### Type E: QUESTION ("What specifically did you work on?" / "Tell me about your experience with X")
- Answer the question DIRECTLY — do not hedge
- Use specific examples from resume/projects
- Keep answer tight: 2-3 sentences for the answer, then redirect to next step
- Do NOT dump your entire resume — answer ONLY what they asked

### Type F: AMBIGUOUS / SHORT ("Thanks" / "Noted" / "Interesting")
- Reply briefly: "Thanks for reading — just wanted to make sure my application didn't get lost. Happy to share more if useful."
- Do NOT over-interpret a one-word reply
- Do NOT write a paragraph in response to "Thanks"
- Match their brevity

## TONE RULES
- You are REPLYING to someone who took time to respond — be grateful
- DO NOT re-pitch if they didn't ask for it
- DO NOT use corporate phrases: "I hope this email finds you well", "leverage", "synergy"
- USE contractions: I'm, I've, I'd, don't
- Be HUMAN — this is a conversation now, not outreach
- Match the formality level of their response

## ABSOLUTE BANS — AUTO-REJECT
1. "I hope this email finds you well" — BANNED
2. Re-sending your entire pitch when they didn't ask — BANNED
3. "maintained" in any form — BANNED
4. "tells me" / "signals" / "means your team" — BANNED
5. Fabricating ResumeForge metrics — BANNED
6. "I'm currently working at Capgemini" — FALSE, BANNED
7. Over-the-top gratitude: "I am so incredibly grateful" / "This means the world to me" — BANNED
8. "Just to circle back" — BANNED

## OUTPUT FORMAT
Return ONLY valid JSON:
{
  "subject": "your reply subject line (usually Re: original subject)",
  "body": "the full reply body (greeting through closing, NO sign-off)"
}

Do NOT include any text before or after the JSON. Do NOT wrap in markdown code blocks."""


def build_response_aware_followup_message(
    original_email_body,
    original_subject,
    recipient_response_text,
    company_name,
    role_title,
    recipient_name,
    recipient_title,
    recipient_category='category_a',
    project_updates_text='',
):
    """Build the user message for a response-aware follow-up (recipient replied)."""

    first_name = recipient_name.strip().split()[0] if recipient_name and recipient_name.strip() else '[Name]'

    category_descriptions = {
        'category_a': 'Recruiter / Talent Acquisition',
        'category_b': 'Hiring Manager / Team Lead',
        'category_c': 'VP / Director / Executive',
    }
    category_str = category_descriptions.get(recipient_category, category_descriptions['category_a'])

    # Optional project updates for response-aware replies
    updates_hint = ''
    if project_updates_text:
        updates_hint = f"""
---

{project_updates_text}

**FOR RESPONSE REPLIES:** Only reference a recent update if they asked about your work or if it naturally fits the conversation. Do NOT force project updates into a reply.
"""

    return f"""## RESPONSE-AWARE REPLY GENERATION

### YOUR ORIGINAL OUTREACH EMAIL (what you sent first)

**Original Subject:** {original_subject}

**Original Body:**
{original_email_body}

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
1. Read your original outreach above.
2. Read the recipient's response carefully.
3. Identify the response TYPE (referral, redirect, rejection, positive interest, question, ambiguous).
4. Write a reply that DIRECTLY addresses what they said.
5. Keep it 40-100 words (body only, no sign-off).
6. Use 1-2 paragraphs max.
7. Do NOT include sign-off, name, phone, or LinkedIn.
8. Do NOT re-pitch unless they explicitly asked for more info.
9. Be grateful without being excessive.
10. Move toward the next concrete step.

### WRITE THE REPLY NOW (JSON format):"""

