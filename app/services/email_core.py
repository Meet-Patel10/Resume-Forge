"""Shared email generation core — used by both tailor and outreach routes."""
import json as json_mod
import re as _re
import unicodedata as _ud
from flask import current_app


# ─── Shared: city → province short code (for email sign-off) ───

_CITY_TO_PROVINCE = {
    'toronto': 'ON', 'ottawa': 'ON', 'mississauga': 'ON', 'brampton': 'ON',
    'hamilton': 'ON', 'london': 'ON', 'markham': 'ON', 'vaughan': 'ON',
    'kitchener': 'ON', 'windsor': 'ON', 'richmond hill': 'ON', 'oakville': 'ON',
    'burlington': 'ON', 'waterloo': 'ON', 'guelph': 'ON', 'barrie': 'ON',
    'oshawa': 'ON', 'cambridge': 'ON', 'kanata': 'ON', 'pickering': 'ON',
    'montreal': 'QC', 'quebec city': 'QC', 'laval': 'QC', 'gatineau': 'QC',
    'sherbrooke': 'QC',
    'vancouver': 'BC', 'surrey': 'BC', 'burnaby': 'BC', 'richmond': 'BC',
    'victoria': 'BC', 'kelowna': 'BC', 'nanaimo': 'BC',
    'calgary': 'AB', 'edmonton': 'AB', 'red deer': 'AB', 'lethbridge': 'AB',
    'winnipeg': 'MB', 'brandon': 'MB',
    'saskatoon': 'SK', 'regina': 'SK',
    'halifax': 'NS', 'dartmouth': 'NS',
    'saint john': 'NB', 'moncton': 'NB', 'fredericton': 'NB',
    "st. john's": 'NL', 'charlottetown': 'PE',
    'yellowknife': 'NT', 'whitehorse': 'YT', 'iqaluit': 'NU',
}

_DEFAULT_LOCATION = 'Halifax, NS'


def resolve_sign_off_location(city_input):
    """Resolve a city name to 'City, Province' for the email sign-off line."""
    if not city_input:
        return _DEFAULT_LOCATION
    city_lower = city_input.lower().strip()
    province = _CITY_TO_PROVINCE.get(city_lower)
    city_display = city_input.strip().title()
    city_display = _re.sub(r"'S\b", "'s", city_display)
    if province:
        return f"{city_display}, {province}"
    return f"{city_display}"


def build_sign_off(location=None):
    """Build the sign-off block with the given location (defaults to Halifax, NS)."""
    loc = location if location else _DEFAULT_LOCATION
    return (
        "\n\nBest regards,\n"
        "Meet Patel\n"
        f"{loc}\n"
        "https://www.linkedin.com/in/meettpatel28/"
    )


def generate_email_core(
    resume_text, jd_text, company_name, role_title,
    recipient_name, cover_letter_text='',
    recipient_title='', recipient_category='',
    target_city='',
    previously_used_signals=None,
    previously_used_subjects=None,
    previously_used_bodies=None,
    previously_used_proofs=None,
    project_updates_text='',
):
    """Core email generation logic. Returns a dict with email data or error.

    Returns:
        dict with keys: subject, body, ref_number, word_count, signal_used,
        proof_point, proof_source, recipient_category, skills_highlighted,
        metrics_used, company_name, role_title, recipient_name, recipient_title,
        tokens_used, cost_usd.
        On error, returns dict with 'error' key and 'status_code'.
    """
    from app.services.prompts.leadership_email import (
        LEADERSHIP_EMAIL_SYSTEM, LEADERSHIP_EMAIL_ADJUST_SYSTEM,
        build_leadership_email_message, build_email_adjust_message
    )

    TARGET_MIN = 140
    TARGET_MAX = 180

    if not jd_text or not resume_text:
        return {'error': 'Both job description and resume text are required', 'status_code': 400}

    # Recipient name is REQUIRED
    if not recipient_name or not recipient_name.strip():
        return {
            'error': 'Recipient name is required. Find the actual person\'s name on LinkedIn or the company site before generating an outreach email — there is no greeting that fixes "I don\'t know who you are."',
            'status_code': 400,
        }

    first_name = recipient_name.strip().split()[0]

    # Deduplication data
    previously_used_signals = previously_used_signals or []
    previously_used_subjects = previously_used_subjects or []
    previously_used_bodies = previously_used_bodies or []
    previously_used_proofs = previously_used_proofs or []

    total_tokens = 0
    total_cost = 0.0

    # ===== BANNED WORD CHECKER =====
    def _check_banned_words(text):
        violations = []
        text_lower = text.lower()
        _BANNED = [
            ('maintained', 'maintained'),
            ('incident', 'incident/SOP/post-mortem language'),
            ('troubleshoot', 'troubleshoot'),
            ('sop', 'SOP'),
            ('post-mortem', 'post-mortem'),
            ('postmortem', 'postmortem'),
            ('runbook', 'runbook'),
            ('documentation', 'documentation'),
            ('documented', 'documented'),
            ('i hope this email finds you well', '"I hope this email finds you well" (cliché opener)'),
            ('i came across', '"I came across" (overused opener)'),
            ('i noticed', '"I noticed" (overused opener)'),
            ('i was excited', '"I was excited" (overused)'),
            ('i am writing', '"I am writing" (overused)'),
            ('i\'m writing', '"I\'m writing" (overused)'),
            ('i believe', '"I believe" (hedge word)'),
            ('passionate about', '"passionate about" (cliché)'),
            ('proven track record', '"proven track record" (cliché)'),
            ('results-driven', '"results-driven" (cliché)'),
            ('synergy', '"synergy" (buzzword)'),
            ('leverage', '"leverage" (buzzword)'),
            ('utilize', '"utilize" (use "use")'),
        ]
        for pattern, label in _BANNED:
            if pattern in text_lower:
                violations.append(f'Contains "{label}"')
        # Check for "Whether X or Y, the same..." bridge pattern
        if 'whether' in text_lower and 'the same' in text_lower:
            violations.append('Contains banned bridge pattern ("Whether X or Y, the same...")')
        return violations

    def _check_proof_similarity(body, prev_proofs):
        """Check if proof is too similar to previously used proofs."""
        violations = []
        if not prev_proofs:
            return violations
        body_lower = body.lower()
        import re as _re_proof
        body_metrics = set(_re_proof.findall(r'\d+[\d,.]*%?', body_lower))
        for prev_body in prev_proofs:
            prev_lower = prev_body.lower() if isinstance(prev_body, str) else ''
            if not prev_lower:
                continue
            prev_metrics = set(_re_proof.findall(r'\d+[\d,.]*%?', prev_lower))
            shared_metrics = body_metrics & prev_metrics
            key_terms = ['api', 'pipeline', 'deploy', 'latency', 'throughput',
                         'uptime', 'reduce', 'automate', 'scale', 'optimize',
                         'build', 'design', 'architect', 'migrate', 'integrate']
            shared_terms = [t for t in key_terms if t in prev_lower and t in body_lower]
            if shared_metrics and len(shared_terms) >= 2:
                violations.append(f'Proof too similar to previous: shares metric(s) {shared_metrics} and terms {shared_terms}')
        return violations

    # Select AI provider
    app_env = current_app.config.get('APP_ENV', 'testing').strip()
    if app_env == 'nvidia':
        from app.services.claude_client import nvidia as ai_client
        print("[leadership-email] Using NVIDIA Llama-3.3-Nemotron for leadership email")
    else:
        from app.services.claude_client import claude as ai_client
        print(f"[leadership-email] Using AWS Bedrock/Claude for leadership email (APP_ENV={app_env})")

    # Step 1: Generate email with AUTO-REJECT retry loop
    MAX_GENERATION_ATTEMPTS = 3
    response = None
    generation_violations_log = []

    for gen_attempt in range(MAX_GENERATION_ATTEMPTS):
        user_message = build_leadership_email_message(
            resume_text, jd_text, company_name, role_title,
            recipient_name, cover_letter_text,
            recipient_title, recipient_category,
            previously_used_signals=previously_used_signals,
            previously_used_subjects=previously_used_subjects,
            previously_used_bodies=previously_used_bodies,
            previously_used_proofs=previously_used_proofs,
            tailored_resume_text=resume_text,
            project_updates_text=project_updates_text,
        )

        # On retry, prepend rejection feedback
        if gen_attempt > 0 and generation_violations_log:
            rejection_feedback = (
                f"\n\n## ⛔ YOUR PREVIOUS OUTPUT WAS AUTO-REJECTED (attempt {gen_attempt})\n"
                f"Violations found:\n"
            )
            for v in generation_violations_log[-1]:
                rejection_feedback += f"  - {v}\n"
            rejection_feedback += (
                "\nYou MUST write a COMPLETELY DIFFERENT proof sentence. "
                "Use an ACTIVE verb (built, designed, architected, scaled, deployed). "
                "Choose a DIFFERENT achievement from the resume. "
                "Do NOT use incidents, maintained, SOPs, or documentation. "
                "The system will reject again if violations are found.\n"
            )
            user_message = rejection_feedback + user_message

        result = ai_client.analyze(
            LEADERSHIP_EMAIL_SYSTEM, user_message,
            max_tokens=1000, force_json=True,
            model_override='productionHigh'
        )

        if result.get('error'):
            return {'error': result['error'], 'status_code': 500}

        total_tokens += result.get('tokens_used', 0)
        total_cost += result.get('cost_usd', 0.0)

        response = result['response']
        if not isinstance(response, dict):
            raw = response if isinstance(response, str) else str(response)

            # Attempt 1: Fix newlines inside JSON strings
            try:
                fixed = ai_client._fix_json_newlines(raw.strip())
                parsed = json_mod.loads(fixed)
                if isinstance(parsed, dict):
                    response = parsed
            except (json_mod.JSONDecodeError, ValueError):
                pass

            # Attempt 2: Extract JSON object with regex
            if not isinstance(response, dict):
                match = _re.search(r'\{[\s\S]*\}', raw)
                if match:
                    try:
                        fixed = ai_client._fix_json_newlines(match.group(0))
                        parsed = json_mod.loads(fixed)
                        if isinstance(parsed, dict):
                            response = parsed
                    except (json_mod.JSONDecodeError, ValueError):
                        pass

            # Last resort
            if not isinstance(response, dict):
                response = {
                    'subject': f'{company_name or "company"} role',
                    'body': raw,
                    'ref_number': '',
                }

        # Check for banned words
        body_text = response.get('body', '')
        violations = _check_banned_words(body_text)

        # Check for proof similarity
        proof_sim_violations = _check_proof_similarity(body_text, previously_used_proofs)
        violations.extend(proof_sim_violations)

        if not violations:
            print(f"[leadership-email] ✅ Generation attempt {gen_attempt + 1} passed QA checks")
            break
        else:
            generation_violations_log.append(violations)
            violation_str = ', '.join(violations)
            print(f"[leadership-email] ⛔ AUTO-REJECT attempt {gen_attempt + 1}: {violation_str}")
            if gen_attempt < MAX_GENERATION_ATTEMPTS - 1:
                print(f"[leadership-email] 🔄 Regenerating (attempt {gen_attempt + 2})...")
            else:
                print(f"[leadership-email] ⚠️ Max retries reached — using last output despite violations")

    subject = response.get('subject', '')
    body = response.get('body', '')

    # ===== ENCODING CLEANUP =====
    def _clean_encoding(text):
        replacements = {
            '\u00df': 'ss', '\u2018': "'", '\u2019': "'",
            '\u201c': '"', '\u201d': '"',
            '\u2013': '-', '\u2014': '-',
            '\u2026': '...', '\u00a0': ' ',
        }
        for char, repl in replacements.items():
            text = text.replace(char, repl)
        text = text.encode('ascii', 'ignore').decode('ascii')
        return text

    subject = _clean_encoding(subject)
    body = _clean_encoding(body)

    # FORCE subject line rules
    if subject:
        subject = _re.sub(r'^(re:\s*|fwd?:\s*)+', '', subject, flags=_re.IGNORECASE).strip()
        subject = _re.sub(r'[\U00010000-\U0010ffff]', '', subject, flags=_re.UNICODE).strip()
        subject = subject.replace('!', '')
        subject = _re.sub(r'\([^)]*\)', '', subject).strip()
        subject = _re.sub(r'\s{2,}', ' ', subject).strip()
        words = subject.split()
        if len(words) > 8:
            subject = ' '.join(words[:8])
            print(f"[leadership-email] Subject truncated to 8 words: {subject}")
        subject = subject.rstrip('.,;:--')

        if previously_used_subjects:
            used_lower = [s.lower().strip() for s in previously_used_subjects]
            if subject.lower().strip() in used_lower:
                print(f"[leadership-email] ⚠️ Subject '{subject}' already used — needs manual review")

        word_count_subj = len(subject.split())
        print(f"[leadership-email] Subject enforced ({word_count_subj} words): {subject}")

    if not body:
        return {'error': 'Email generation failed — no body text returned', 'status_code': 500}

    # FORCE greeting
    body = _re.sub(
        r'^\s*(Hi\s+\w+[,.]?|Hi\s+there[,.]?|Hi[,.]?|Hello\s+\w+[,.]?|Hello[,.]?|Hey\s+\w+[,.]?|Hey[,.]?|Dear\s+[^,\n]+[,.]?)\s*',
        f'Hi {first_name},\n\n',
        body,
        count=1,
        flags=_re.IGNORECASE
    )
    if not body.strip().lower().startswith(f'hi {first_name.lower()}'):
        body = f'Hi {first_name},\n\n' + body.strip()

    # Capitalize first letter after greeting
    greeting_end = f'Hi {first_name},\n\n'
    if body.startswith(greeting_end) and len(body) > len(greeting_end):
        rest = body[len(greeting_end):]
        body = greeting_end + rest[0].upper() + rest[1:]

    # Clean up excessive blank lines
    if greeting_end in body:
        greeting_part = body[:body.index(greeting_end) + len(greeting_end)]
        body_part = body[len(greeting_part):]
        body_part = _re.sub(r'\n{3,}', '\n\n', body_part)
        body = greeting_part + body_part.strip()

    print(f'[leadership-email] Greeting forced: Hi {first_name},')
    print(f'[leadership-email] Body formatted with paragraph breaks preserved')

    # Step 2: Count words (exclude sign-off)
    def count_words(text):
        lines = text.strip().split('\n')
        body_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.lower() in ['sincerely,', 'best regards,', 'regards,',
                                     'warm regards,', 'respectfully,', 'best,']:
                break
            body_lines.append(stripped)
        return len(' '.join(body_lines).split())

    ref_number = response.get('ref_number', '')
    if ref_number and ref_number.strip().upper() == 'REFENUM':
        ref_number = ''
        print("[leadership-email] Stripped REFENUM placeholder — no real ref found")

    current_count = count_words(body)

    # Step 3: Adjustment loop — enforce word count
    MAX_RETRIES = 3
    for attempt in range(MAX_RETRIES):
        if TARGET_MIN <= current_count <= TARGET_MAX:
            break

        print(f"[leadership-email] Body word count: {current_count}, target: {TARGET_MIN}-{TARGET_MAX}. Adjusting (attempt {attempt + 1})...")
        adjust_msg = build_email_adjust_message(body, current_count, TARGET_MIN, TARGET_MAX)
        adjust_result = ai_client.analyze(
            LEADERSHIP_EMAIL_ADJUST_SYSTEM, adjust_msg,
            max_tokens=1000, force_json=True,
            model_override='productionHigh'
        )

        total_tokens += adjust_result.get('tokens_used', 0)
        total_cost += adjust_result.get('cost_usd', 0.0)

        if adjust_result.get('error'):
            break

        adj_response = adjust_result['response']
        if isinstance(adj_response, dict) and adj_response.get('adjusted_body'):
            body = _clean_encoding(adj_response['adjusted_body'])
            current_count = count_words(body)
            response['body'] = body
        else:
            break

    print(f"[leadership-email] Final word count: {current_count}")
    print(f"[leadership-email] Subject: {subject[:80]}")

    # Step 3.5: RAG Quality Audit
    from app.services.email_auditor import audit_email, build_audit_rejection_feedback

    MAX_AUDIT_RETRIES = 2
    for audit_attempt in range(MAX_AUDIT_RETRIES):
        audit_result = audit_email(
            email_body=body,
            jd_text=jd_text,
            resume_text=resume_text,
            recipient_name=recipient_name,
            recipient_title=recipient_title,
            recipient_category=recipient_category or '',
            email_type='cold_outreach',
        )
        total_tokens += audit_result.tokens_used
        total_cost += audit_result.cost_usd

        if audit_result.passed:
            print(f"[leadership-email] ✅ RAG audit passed on attempt {audit_attempt + 1}")
            break
        else:
            print(f"[leadership-email] ❌ RAG audit FAILED on attempt {audit_attempt + 1}")
            if audit_attempt < MAX_AUDIT_RETRIES - 1:
                # Regenerate with audit feedback
                audit_feedback = build_audit_rejection_feedback(audit_result)
                print(f"[leadership-email] 🔄 Regenerating with audit feedback...")

                regen_message = audit_feedback + build_leadership_email_message(
                    resume_text, jd_text, company_name, role_title,
                    recipient_name, cover_letter_text,
                    recipient_title, recipient_category,
                    previously_used_signals=previously_used_signals,
                    previously_used_subjects=previously_used_subjects,
                    previously_used_bodies=previously_used_bodies,
                    previously_used_proofs=previously_used_proofs,
                    tailored_resume_text=resume_text,
                    project_updates_text=project_updates_text,
                )

                regen_result = ai_client.analyze(
                    LEADERSHIP_EMAIL_SYSTEM, regen_message,
                    max_tokens=1000, force_json=True,
                    model_override='productionHigh'
                )
                total_tokens += regen_result.get('tokens_used', 0)
                total_cost += regen_result.get('cost_usd', 0.0)

                if not regen_result.get('error'):
                    regen_response = regen_result.get('response', {})
                    if isinstance(regen_response, str):
                        try:
                            regen_response = _json.loads(regen_response)
                        except _json.JSONDecodeError:
                            match = _re.search(r'\{[\s\S]*\}', regen_response)
                            if match:
                                try:
                                    regen_response = _json.loads(match.group(0))
                                except _json.JSONDecodeError:
                                    pass

                    if isinstance(regen_response, dict) and regen_response.get('body'):
                        body = _clean_encoding(regen_response['body'])
                        subject = _clean_encoding(regen_response.get('subject', subject))
                        # Re-force greeting
                        body = _re.sub(
                            r'^\s*(Hi\s+\w+[,.]?|Hi\s+there[,.]?|Hi[,.]?|Hello\s+\w+[,.]?|Hello[,.]?|Hey\s+\w+[,.]?|Hey[,.]?|Dear\s+[^,\n]+[,.]?)\s*',
                            f'Hi {first_name},\n\n', body, count=1, flags=_re.IGNORECASE
                        )
                        if not body.strip().lower().startswith(f'hi {first_name.lower()}'):
                            body = f'Hi {first_name},\n\n' + body.strip()
                        current_count = count_words(body)
                        print(f"[leadership-email] Regenerated body ({current_count} words)")
            else:
                print(f"[leadership-email] ⚠️ Max audit retries reached — using last output")

    # Step 3.6: Legacy quality checks
    body_lower = body.lower()
    if 'whether' in body_lower and 'the same' in body_lower:
        print("[leadership-email] ⚠️ WARNING: Body contains banned bridge pattern ('Whether X or Y, the same...')")
    if 'maintained' in body_lower:
        print("[leadership-email] ⚠️ WARNING: Body contains 'maintained'")
    if 'ref refenum' in body_lower or '(ref refenum)' in body_lower:
        body = _re.sub(r'\s*\(ref\s*REFENUM\)', '', body, flags=_re.IGNORECASE)
        body = _re.sub(r'\s*ref\s+REFENUM', '', body, flags=_re.IGNORECASE)
        print("[leadership-email] ✂️ Stripped 'ref REFENUM' from body text")


    # Build sign-off
    sign_off_location = resolve_sign_off_location(target_city) if target_city else _DEFAULT_LOCATION
    SIGN_OFF_BLOCK = build_sign_off(sign_off_location)

    # Strip any sign-off fragments the AI included
    lines = body.rstrip().split('\n')
    clean_lines = []
    for line in lines:
        stripped = line.strip().lower()
        if stripped in ['best regards,', 'best regards', 'best,', 'regards,',
                        'sincerely,', 'warm regards,', 'meet patel',
                        '+1 (902) 322-3808', 'meet', 'patel', 'meet patel,',
                        'halifax, ns', 'halifax ns']:
            continue
        if 'linkedin.com/in/meettpatel28' in stripped:
            continue
        if stripped.startswith('+1 (902)'):
            continue
        if _re.match(r'^[a-z .\'-]+,\s*[a-z]{2}$', stripped):
            continue
        clean_lines.append(line)
    body = '\n'.join(clean_lines).rstrip() + SIGN_OFF_BLOCK
    print(f"[leadership-email] Sign-off appended with location: {sign_off_location}")

    return {
        'subject': subject,
        'body': body,
        'ref_number': ref_number if ref_number else None,
        'word_count': current_count,
        'signal_used': response.get('signal_used', ''),
        'proof_point': response.get('proof_point', ''),
        'proof_source': response.get('proof_source', ''),
        'recipient_category': response.get('recipient_category', recipient_category or 'category_a'),
        'skills_highlighted': response.get('skills_highlighted', []),
        'metrics_used': response.get('metrics_used', []),
        'company_name': company_name,
        'role_title': role_title,
        'recipient_name': recipient_name or '',
        'recipient_title': recipient_title or '',
        'tokens_used': total_tokens,
        'cost_usd': total_cost,
    }


def build_email_download(emails, company_name, role_title):
    """Build the JSON download response for email(s).

    Args:
        emails: list of email dicts
        company_name: company name
        role_title: role title

    Returns:
        tuple of (output_dict, filename)
    """
    from datetime import datetime

    if not emails or len(emails) == 0:
        return None, None

    # Add timestamps and clean up
    for email in emails:
        email['generated_at'] = datetime.now().isoformat()
        ref = email.get('ref_number', '')
        if not ref or (isinstance(ref, str) and ref.strip().upper() == 'REFENUM'):
            email.pop('ref_number', None)

    output = {
        'company': company_name,
        'role': role_title,
        'generated_at': datetime.now().isoformat(),
        'total_recipients': len(emails),
        'emails': emails,
    }

    # Build filename
    def _slug(text, max_len=25):
        return ''.join(c if c.isalnum() or c in ('-', '_') else '_' for c in text.strip()).strip('_')[:max_len]

    first_email = emails[0] if emails else {}
    recipient_raw = first_email.get('recipient_name', '')
    name_parts = recipient_raw.strip().split()
    if len(name_parts) >= 2:
        first_name = _slug(name_parts[0])
        last_name = _slug(name_parts[-1])
    elif len(name_parts) == 1:
        first_name = _slug(name_parts[0])
        last_name = 'Unknown'
    else:
        first_name = 'Unknown'
        last_name = 'Unknown'

    recipient_title_raw = (first_email.get('recipient_title', '') or '').strip()
    designation_raw = recipient_title_raw if recipient_title_raw else role_title.strip()
    initials = ''.join(w[0].upper() for w in designation_raw.split() if w)
    designation = initials if initials else _slug(designation_raw, 20)

    safe_company = _slug(company_name, 25) if company_name else 'Company'
    filename = f"{last_name}_{first_name}_{designation}_{safe_company}.json"

    return output, filename
