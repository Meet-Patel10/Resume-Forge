"""RAG-based Email Quality Auditor.

Validates every generated email (cold outreach, follow-ups) against three checks:
  1. Recipient-Role Alignment — is the email relevant to this person + JD?
  2. AI Tone Detection — does it sound human or machine-generated?
  3. Role-Fit Signal Strength — does it prove the candidate fits THIS role?

Architecture:
  - Called AFTER word-count adjustment, BEFORE sign-off appending
  - Returns AuditResult with pass/fail + specific violation strings
  - On failure, caller feeds violations into regeneration prompt
  - Non-blocking: if any check errors out, it passes gracefully
"""

import re as _re
import math
import json as _json


# ═══════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════════════════

# Minimum cosine similarity between email body and JD for relevance
_MIN_JD_SIMILARITY = 0.30

# Minimum number of top-5 JD requirements addressed in the email
_MIN_JD_REQUIREMENTS_ADDRESSED = 2

# Minimum AI tone score to pass (out of 10)
_MIN_HUMAN_SCORE = 7

# AI-signature words — their presence in high density signals automation
_AI_SIGNATURE_WORDS = [
    'leverage', 'leveraged', 'leveraging',
    'utilize', 'utilized', 'utilizing',
    'spearhead', 'spearheaded', 'spearheading',
    'orchestrate', 'orchestrated', 'orchestrating',
    'streamline', 'streamlined', 'streamlining',
    'synergy', 'synergize',
    'cutting-edge', 'cutting edge',
    'innovative', 'innovation',
    'state-of-the-art', 'state of the art',
    'groundbreaking',
    'robust',
    'seamless', 'seamlessly',
    'comprehensive',
    'facilitate', 'facilitated',
    'foster', 'fostered',
    'endeavor',
    'aforementioned',
    'henceforth',
    'delve', 'delved', 'delving',
    'tapestry',
    'multifaceted',
    'holistic',
    'paradigm',
]

# Cliché openers that scream "template"
_CLICHE_OPENERS = [
    'i hope this email finds you well',
    'i hope this message finds you well',
    'i am writing to express my interest',
    "i'm writing to express my interest",
    'i came across your profile',
    'i came across the role',
    'i noticed your company is doing great things',
    'i believe i would be a great fit',
    'i was excited to see',
    'i am reaching out to inquire',
    'dear hiring manager',
]

# ═══════════════════════════════════════════════════════════════════════
#  AI TONE DETECTOR PROMPT
# ═══════════════════════════════════════════════════════════════════════

AI_TONE_DETECTOR_SYSTEM = """You are an expert at detecting AI-generated emails. You've read thousands of real human cold emails and thousands of AI-generated ones. You can instantly tell the difference.

Your job: score a cold outreach email on how HUMAN it sounds, on a scale of 1-10.

## SCORING DIMENSIONS (evaluate each)

### 1. Structure Variety (is it formulaic?)
- AI pattern: compliment → pitch → CTA, every time
- Human pattern: varies — some start with a question, some with a story, some dive straight in
- Scoring: 1 = rigid template, 10 = natural conversational flow

### 2. Buzzword Density
- AI loves: "leverage", "synergy", "cutting-edge", "innovative", "robust", "seamless", "spearheaded", "orchestrated", "streamlined"
- Humans say: "used", "built", "ran", "set up", "worked on"
- Scoring: 1 = buzzword soup, 10 = plain spoken English

### 3. Sentence Length Variation
- AI writes sentences that are all 15-20 words
- Humans mix short (5 words) and long (25+ words)
- Scoring: 1 = uniform, 10 = natural variation

### 4. Contraction Usage
- AI defaults to "I am", "I have", "I would", "do not"
- Humans naturally use "I'm", "I've", "I'd", "don't"
- Scoring: 1 = no contractions (robot), 10 = natural mix

### 5. Specificity vs Vagueness
- AI says: "I help companies improve efficiency"
- Humans say: "I built a pipeline that cut deploy time from 45min to 8min"
- Scoring: 1 = generic claims, 10 = named projects with numbers

### 6. Opener Quality
- AI: "I hope this email finds you well" / "I noticed {{Company}} is doing great things"
- Human: Gets straight to the point or uses a unique hook
- Scoring: 1 = cliché opener, 10 = unique, direct opening

### 7. Paragraph Balance
- AI: all paragraphs are similar length (3-4 sentences each)
- Human: some paragraphs are 1 sentence, some are 3
- Scoring: 1 = uniform blocks, 10 = natural variation

### 8. Overall "Gut Check"
- Would a busy hiring manager think "this is a real person" or "this is automated outreach"?
- Scoring: 1 = obviously automated, 10 = clearly a real person

## OUTPUT FORMAT
Return ONLY valid JSON:
{
  "scores": {
    "structure_variety": <1-10>,
    "buzzword_density": <1-10>,
    "sentence_variation": <1-10>,
    "contraction_usage": <1-10>,
    "specificity": <1-10>,
    "opener_quality": <1-10>,
    "paragraph_balance": <1-10>,
    "gut_check": <1-10>
  },
  "overall_score": <1-10 weighted average>,
  "ai_signals_found": ["list of specific AI patterns detected"],
  "rewrite_instructions": "If score < 7, specific instructions to make it sound more human. If score >= 7, empty string."
}

Do NOT include any text before or after the JSON."""


# ═══════════════════════════════════════════════════════════════════════
#  DETERMINISTIC CHECKS (no API calls)
# ═══════════════════════════════════════════════════════════════════════

def _check_ai_signals_deterministic(body):
    """Fast, free checks for AI-generated patterns. Returns list of violations."""
    violations = []
    body_lower = body.lower()
    words = body_lower.split()
    word_count = len(words)

    if word_count < 5:
        return violations  # too short to analyze

    # 1. Buzzword density
    buzzword_hits = []
    for bw in _AI_SIGNATURE_WORDS:
        if bw in body_lower:
            buzzword_hits.append(bw)
    if len(buzzword_hits) >= 2:
        violations.append(f'AI buzzwords detected: {", ".join(buzzword_hits[:5])}')

    # 2. Cliché openers
    first_100_chars = body_lower[:150]
    for cliche in _CLICHE_OPENERS:
        if cliche in first_100_chars:
            violations.append(f'Cliché opener: "{cliche}"')
            break

    # 3. No contractions (robot voice)
    contractions = ["i'm", "i've", "i'd", "i'll", "don't", "doesn't",
                    "can't", "won't", "isn't", "aren't", "we're", "you're",
                    "they're", "that's", "it's", "who's", "what's", "there's"]
    has_contraction = any(c in body_lower for c in contractions)
    # Check for formal alternatives that suggest AI
    formal_count = 0
    formal_patterns = ['i am ', 'i have ', 'i would ', 'do not ', 'does not ',
                       'can not ', 'cannot ', 'will not ', 'is not ', 'are not ']
    for fp in formal_patterns:
        if fp in body_lower:
            formal_count += 1
    if formal_count >= 2 and not has_contraction:
        violations.append(f'No contractions used ({formal_count} formal phrases found) — sounds robotic')

    # 4. Sentence length uniformity
    sentences = _re.split(r'[.!?]+', body)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 5]
    if len(sentences) >= 3:
        lengths = [len(s.split()) for s in sentences]
        avg = sum(lengths) / len(lengths)
        if avg > 0:
            variance = sum((l - avg) ** 2 for l in lengths) / len(lengths)
            stddev = math.sqrt(variance)
            # If std deviation < 3 words across 3+ sentences, it's suspiciously uniform
            if stddev < 2.5 and len(sentences) >= 4:
                violations.append(f'Sentence lengths too uniform (stddev={stddev:.1f}) — AI pattern')

    # 5. Formulaic structure: every paragraph starts with "I"
    paragraphs = [p.strip() for p in body.split('\n\n') if p.strip()]
    # Skip greeting paragraph
    content_paragraphs = [p for p in paragraphs if not p.lower().startswith(('hi ', 'hello ', 'dear '))]
    if len(content_paragraphs) >= 2:
        i_starters = sum(1 for p in content_paragraphs if p.strip().lower().startswith('i ') or p.strip().lower().startswith("i'"))
        if i_starters == len(content_paragraphs):
            violations.append(f'All {len(content_paragraphs)} content paragraphs start with "I" — formulaic')

    return violations


def _check_recipient_alignment_deterministic(body, recipient_title, recipient_category):
    """Check if the ask matches the recipient level. Free, no API."""
    violations = []
    body_lower = body.lower()

    if not recipient_category:
        return violations

    # Category A = Recruiter: ask should be about application status / timeline
    if recipient_category == 'category_a' or (recipient_title and any(
            t in recipient_title.lower() for t in ['recruiter', 'talent', 'hr ', 'human resource'])):
        # Good asks for recruiters
        recruiter_asks = ['position still', 'role still', 'timeline', 'where things stand',
                         'still being', 'actively filled', 'still open', 'any update']
        # Bad asks for recruiters (these are for managers)
        bad_for_recruiter = ['technical challenges', 'architecture decisions',
                            'engineering philosophy', 'tech stack decisions']
        has_good_ask = any(ra in body_lower for ra in recruiter_asks)
        has_bad_ask = any(ba in body_lower for ba in bad_for_recruiter)
        if has_bad_ask:
            violations.append(f'Technical deep-dive ask sent to recruiter ({recipient_title}) — wrong level')

    # Category C = VP/Director: ask should be about referral / team
    elif recipient_category == 'category_c' or (recipient_title and any(
            t in recipient_title.lower() for t in ['vp', 'vice president', 'director', 'cto', 'ceo', 'svp'])):
        # Bad asks for VPs
        bad_for_vp = ['15-minute', '15 minute', 'quick call', 'brief call',
                     'quick chat', 'brief conversation', 'short call']
        has_bad_ask = any(bv in body_lower for bv in bad_for_vp)
        if has_bad_ask:
            violations.append(f'Asked VP/Director ({recipient_title}) for a call — should ask for referral instead')

    return violations


def _check_role_fit_deterministic(body, resume_text, jd_text):
    """Check that the email contains at least one concrete proof from the resume."""
    violations = []
    body_lower = body.lower()

    if not resume_text:
        return violations

    # Extract numbers/metrics from resume
    resume_metrics = set(_re.findall(r'\d+(?:\.\d+)?[%x]?', resume_text))
    # Check if at least one resume metric appears in the email
    body_metrics = set(_re.findall(r'\d+(?:\.\d+)?[%x]?', body_lower))
    shared_metrics = resume_metrics & body_metrics
    # Filter out common numbers (1, 2, 3, etc.)
    meaningful_shared = {m for m in shared_metrics if len(m) > 1 or int(m) > 5}

    # Check for named projects/companies from resume in the email
    # Look for capitalized multi-word terms in resume that also appear in email
    resume_lower = resume_text.lower()
    has_named_proof = False

    # Check for specific project/company names
    proof_indicators = ['resumeforge', 'capgemini', 'spring boot', 'microservice',
                       'kubernetes', 'docker', 'aws', 'bedrock', 'claude',
                       'jenkins', 'ci/cd', 'postgresql', 'flask']
    for indicator in proof_indicators:
        if indicator in resume_lower and indicator in body_lower:
            has_named_proof = True
            break

    if not meaningful_shared and not has_named_proof:
        violations.append('No concrete proof from resume found in email — add at least one specific metric or named project')

    return violations


# ═══════════════════════════════════════════════════════════════════════
#  EMBEDDING-BASED CHECKS (uses NVIDIA embeddings)
# ═══════════════════════════════════════════════════════════════════════

def _cosine_similarity(vec_a, vec_b):
    """Compute cosine similarity between two vectors."""
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _check_jd_alignment_embedding(email_body, jd_text, nvidia_client):
    """Check if email body is semantically relevant to the JD using embeddings.

    Returns (score, violations) tuple.
    """
    violations = []
    try:
        # Embed email body and JD
        texts = [email_body, jd_text]
        result = nvidia_client.embed(texts, input_type='passage')

        if result.get('error') or not result.get('embeddings') or len(result['embeddings']) < 2:
            print(f"[email-audit] Embedding failed for JD alignment: {result.get('error', 'no embeddings')}")
            return None, []

        email_vec = result['embeddings'][0]
        jd_vec = result['embeddings'][1]
        similarity = _cosine_similarity(email_vec, jd_vec)
        print(f"[email-audit] Email-JD cosine similarity: {similarity:.4f}")

        if similarity < _MIN_JD_SIMILARITY:
            violations.append(
                f'Email body is not semantically aligned with the JD (similarity={similarity:.2f}, '
                f'minimum={_MIN_JD_SIMILARITY}). Rewrite to address specific JD requirements.'
            )

        return similarity, violations

    except Exception as e:
        print(f"[email-audit] JD alignment check failed (non-fatal): {e}")
        return None, []


def _check_role_fit_embedding(email_body, jd_text, nvidia_client):
    """Check that email addresses top JD requirements using embeddings.

    Uses existing JD requirement extraction from rag_enhancer.
    """
    violations = []
    try:
        from app.services.rag_enhancer import extract_jd_requirements

        jd_requirements = extract_jd_requirements(jd_text)
        if not jd_requirements or len(jd_requirements) == 0:
            return None, []

        # Take top 5 requirements (sorted by priority)
        priority_order = {'required': 0, 'preferred': 1, 'nice_to_have': 2}
        sorted_reqs = sorted(jd_requirements, key=lambda r: priority_order.get(r.get('priority', 'nice_to_have'), 2))
        top_reqs = sorted_reqs[:5]
        req_texts = [r['text'] for r in top_reqs]

        # Embed email + each requirement
        all_texts = [email_body] + req_texts
        result = nvidia_client.embed(all_texts, input_type='passage')

        if result.get('error') or not result.get('embeddings') or len(result['embeddings']) < 2:
            print(f"[email-audit] Embedding failed for role-fit: {result.get('error', 'no embeddings')}")
            return None, []

        email_vec = result['embeddings'][0]
        req_vecs = result['embeddings'][1:]

        addressed_count = 0
        unaddressed = []
        for i, req_vec in enumerate(req_vecs):
            sim = _cosine_similarity(email_vec, req_vec)
            req_text = req_texts[i][:60]
            if sim >= 0.35:
                addressed_count += 1
                print(f"[email-audit]   ✅ Req addressed (sim={sim:.2f}): {req_text}")
            else:
                unaddressed.append(req_text)
                print(f"[email-audit]   ❌ Req NOT addressed (sim={sim:.2f}): {req_text}")

        print(f"[email-audit] Role-fit: {addressed_count}/{len(top_reqs)} top requirements addressed")

        if addressed_count < _MIN_JD_REQUIREMENTS_ADDRESSED:
            violations.append(
                f'Email only addresses {addressed_count}/{len(top_reqs)} top JD requirements '
                f'(minimum={_MIN_JD_REQUIREMENTS_ADDRESSED}). Unaddressed: {"; ".join(unaddressed[:3])}'
            )

        return addressed_count, violations

    except Exception as e:
        print(f"[email-audit] Role-fit embedding check failed (non-fatal): {e}")
        return None, []


# ═══════════════════════════════════════════════════════════════════════
#  AI TONE CHECK (uses Claude)
# ═══════════════════════════════════════════════════════════════════════

def _check_ai_tone(email_body, ai_client):
    """Score email for human-ness using Claude.

    Returns (score, rewrite_instructions, violations) tuple.
    """
    violations = []
    try:
        user_message = f"""Score the following cold outreach email for how HUMAN vs AI-GENERATED it sounds.

## EMAIL TO ANALYZE:
{email_body}

## SCORE IT NOW (JSON format):"""

        result = ai_client.analyze(
            system_prompt=AI_TONE_DETECTOR_SYSTEM,
            user_message=user_message,
            max_tokens=800,
            temperature=0.1,
            force_json=True,
            model_override='productionLow',
        )

        if result.get('error'):
            print(f"[email-audit] AI tone check failed: {result['error']}")
            return None, '', [], result.get('tokens_used', 0), result.get('cost_usd', 0.0)

        tokens_used = result.get('tokens_used', 0)
        cost_usd = result.get('cost_usd', 0.0)

        response = result.get('response', {})
        if isinstance(response, str):
            try:
                response = _json.loads(response)
            except _json.JSONDecodeError:
                print(f"[email-audit] AI tone check returned non-JSON: {response[:200]}")
                return None, '', [], tokens_used, cost_usd

        overall_score = response.get('overall_score', 10)
        scores = response.get('scores', {})
        ai_signals = response.get('ai_signals_found', [])
        rewrite_instructions = response.get('rewrite_instructions', '')

        # Log detailed scores
        print(f"[email-audit] AI Tone Score: {overall_score}/10")
        for dim, score in scores.items():
            status = '✅' if score >= 7 else '⚠️' if score >= 5 else '❌'
            print(f"[email-audit]   {status} {dim}: {score}/10")
        if ai_signals:
            print(f"[email-audit]   AI signals: {', '.join(ai_signals[:5])}")

        if overall_score < _MIN_HUMAN_SCORE:
            violation_msg = (
                f'Email sounds AI-generated (tone score={overall_score}/10, minimum={_MIN_HUMAN_SCORE}). '
            )
            # Add specific failing dimensions
            weak_dims = [f'{k}={v}' for k, v in scores.items() if isinstance(v, (int, float)) and v < 7]
            if weak_dims:
                violation_msg += f'Weak areas: {", ".join(weak_dims[:4])}. '
            if rewrite_instructions:
                violation_msg += f'Fix: {rewrite_instructions}'
            violations.append(violation_msg)

        return overall_score, rewrite_instructions, violations, tokens_used, cost_usd

    except Exception as e:
        print(f"[email-audit] AI tone check failed (non-fatal): {e}")
        return None, '', [], 0, 0.0


# ═══════════════════════════════════════════════════════════════════════
#  TOP-LEVEL ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════

class AuditResult:
    """Structured result from the email quality audit."""

    def __init__(self):
        self.passed = True
        self.violations = []
        self.scores = {}
        self.rewrite_instructions = ''
        self.tokens_used = 0
        self.cost_usd = 0.0

    def add_violation(self, violation):
        self.passed = False
        self.violations.append(violation)

    def add_violations(self, violations):
        for v in violations:
            self.add_violation(v)

    def __repr__(self):
        status = '✅ PASS' if self.passed else f'❌ FAIL ({len(self.violations)} violations)'
        return f'AuditResult({status})'


def audit_email(
    email_body,
    jd_text='',
    resume_text='',
    recipient_name='',
    recipient_title='',
    recipient_category='',
    email_type='cold_outreach',
):
    """Run the full RAG-based quality audit on a generated email.

    Args:
        email_body: The generated email body (after word-count adjustment, before sign-off)
        jd_text: The job description text
        resume_text: The candidate's resume text
        recipient_name: Name of the email recipient
        recipient_title: Title/role of the recipient
        recipient_category: 'category_a' (recruiter), 'category_b' (manager), 'category_c' (VP)
        email_type: 'cold_outreach', 'followup', or 'second_followup'

    Returns:
        AuditResult with pass/fail, violations, scores, and rewrite instructions
    """
    result = AuditResult()

    print(f"\n[email-audit] ════════════════════════════════════════")
    print(f"[email-audit] Running quality audit ({email_type})")
    print(f"[email-audit]   Recipient: {recipient_name} ({recipient_title})")
    print(f"[email-audit]   Category: {recipient_category}")
    print(f"[email-audit] ════════════════════════════════════════")

    # ── Check 1: Deterministic AI signal detection (free) ──
    print(f"[email-audit] Check 1: Deterministic AI signals...")
    ai_violations = _check_ai_signals_deterministic(email_body)
    if ai_violations:
        result.add_violations(ai_violations)
        print(f"[email-audit]   ❌ {len(ai_violations)} deterministic AI signals found")
    else:
        print(f"[email-audit]   ✅ No deterministic AI signals")

    # ── Check 2: Recipient-level alignment (free) ──
    print(f"[email-audit] Check 2: Recipient alignment...")
    recipient_violations = _check_recipient_alignment_deterministic(
        email_body, recipient_title, recipient_category
    )
    if recipient_violations:
        result.add_violations(recipient_violations)
        print(f"[email-audit]   ❌ {len(recipient_violations)} recipient alignment issues")
    else:
        print(f"[email-audit]   ✅ Recipient alignment OK")

    # ── Check 3: Role-fit proof (free) ──
    print(f"[email-audit] Check 3: Role-fit proof (deterministic)...")
    rolefit_violations = _check_role_fit_deterministic(email_body, resume_text, jd_text)
    if rolefit_violations:
        result.add_violations(rolefit_violations)
        print(f"[email-audit]   ❌ {len(rolefit_violations)} role-fit issues")
    else:
        print(f"[email-audit]   ✅ Role-fit proof present")

    # ── Check 4: Embedding-based JD alignment (NVIDIA, costs tokens) ──
    try:
        from flask import current_app
        app_env = current_app.config.get('APP_ENV', '').strip()
    except RuntimeError:
        app_env = ''

    nvidia_available = False
    nvidia_client = None
    if app_env == 'nvidia':
        try:
            from app.services.claude_client import nvidia as nvidia_client
            nvidia_available = True
        except ImportError:
            pass

    if nvidia_available and nvidia_client and jd_text:
        print(f"[email-audit] Check 4: JD alignment (NVIDIA embeddings)...")
        jd_sim, jd_violations = _check_jd_alignment_embedding(email_body, jd_text, nvidia_client)
        if jd_sim is not None:
            result.scores['jd_similarity'] = jd_sim
        if jd_violations:
            result.add_violations(jd_violations)

        # ── Check 5: Role-fit via embeddings ──
        print(f"[email-audit] Check 5: Role-fit (NVIDIA embeddings)...")
        addressed, fit_violations = _check_role_fit_embedding(email_body, jd_text, nvidia_client)
        if addressed is not None:
            result.scores['jd_requirements_addressed'] = addressed
        if fit_violations:
            result.add_violations(fit_violations)
    else:
        print(f"[email-audit] Checks 4-5: Skipped (NVIDIA not available, using deterministic only)")

    # ── Check 6: AI Tone Detection (Claude, costs ~$0.003) ──
    print(f"[email-audit] Check 6: AI tone detection (Claude)...")
    try:
        from app.services.claude_client import BedrockClient
        ai_client = BedrockClient()
        tone_score, rewrite_instr, tone_violations, tone_tokens, tone_cost = _check_ai_tone(
            email_body, ai_client
        )
        result.tokens_used += tone_tokens
        result.cost_usd += tone_cost

        if tone_score is not None:
            result.scores['ai_tone_score'] = tone_score
        if tone_violations:
            result.add_violations(tone_violations)
        if rewrite_instr:
            result.rewrite_instructions = rewrite_instr
    except Exception as e:
        print(f"[email-audit] AI tone check skipped (non-fatal): {e}")

    # ── Summary ──
    print(f"\n[email-audit] ════════════════════════════════════════")
    if result.passed:
        print(f"[email-audit] ✅ AUDIT PASSED — email is good to send")
    else:
        print(f"[email-audit] ❌ AUDIT FAILED — {len(result.violations)} violation(s):")
        for i, v in enumerate(result.violations, 1):
            print(f"[email-audit]   {i}. {v}")
    print(f"[email-audit] Scores: {result.scores}")
    print(f"[email-audit] Audit cost: ${result.cost_usd:.4f} ({result.tokens_used} tokens)")
    print(f"[email-audit] ════════════════════════════════════════\n")

    return result


def build_audit_rejection_feedback(audit_result):
    """Build a rejection feedback string from an AuditResult to prepend to retry prompts.

    Args:
        audit_result: AuditResult from audit_email()

    Returns:
        str: Formatted rejection feedback for the AI prompt
    """
    if audit_result.passed:
        return ''

    feedback = "\n\n## ⛔ YOUR PREVIOUS EMAIL WAS REJECTED BY QUALITY AUDIT\n"
    feedback += "The following issues were found:\n"

    for i, v in enumerate(audit_result.violations, 1):
        feedback += f"  {i}. {v}\n"

    feedback += "\n## MANDATORY FIXES FOR YOUR NEXT ATTEMPT:\n"

    # Add specific rewrite instructions based on violation types
    if any('buzzword' in v.lower() for v in audit_result.violations):
        feedback += "- Replace ALL buzzwords (leverage, utilize, orchestrate, streamline, robust, seamless) with plain English\n"

    if any('contraction' in v.lower() for v in audit_result.violations):
        feedback += "- Use contractions: I'm, I've, I'd, don't — NOT 'I am', 'I have', 'I would', 'do not'\n"

    if any('formulaic' in v.lower() or 'start with \"i\"' in v.lower() for v in audit_result.violations):
        feedback += "- Vary paragraph structure — NOT every paragraph should start with 'I'\n"
        feedback += "- Mix short and long sentences (some 5 words, some 20+ words)\n"

    if any('cliché' in v.lower() or 'opener' in v.lower() for v in audit_result.violations):
        feedback += "- Do NOT open with 'I hope this email finds you well' or 'I noticed' or 'I came across'\n"
        feedback += "- Get straight to the point with a unique, specific opening\n"

    if any('recipient' in v.lower() or 'wrong level' in v.lower() for v in audit_result.violations):
        feedback += "- Match your ask to the recipient's level (recruiter=status, manager=fit, VP=referral)\n"

    if any('proof' in v.lower() or 'role-fit' in v.lower() for v in audit_result.violations):
        feedback += "- Include at least ONE specific metric or named project from the resume\n"
        feedback += "- Connect it to a specific JD requirement\n"

    if any('ai-generated' in v.lower() or 'tone score' in v.lower() for v in audit_result.violations):
        feedback += "- Write like a real person talking to a colleague, not a press release\n"
        feedback += "- Read it out loud — if it sounds stiff, rewrite it\n"

    if audit_result.rewrite_instructions:
        feedback += f"\n## AI TONE DETECTOR INSTRUCTIONS:\n{audit_result.rewrite_instructions}\n"

    feedback += "\nYou MUST fix ALL issues above. The audit will run again on your output.\n"

    return feedback
