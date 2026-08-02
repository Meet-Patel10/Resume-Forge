"""
Follow-Up Email Generator — Route
Upload an original outreach email JSON file, AI generates follow-up emails
for all recipients, outputs same JSON format.
"""

import json
import re as _re
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, session
from app.routes.auth import login_required
from app.services.claude_client import BedrockClient, NvidiaClient
from app.services.github_fetcher import get_project_updates_for_prompt
from app.services.prompts.followup_email import (
    FOLLOWUP_EMAIL_SYSTEM,
    build_followup_email_message,
    FOLLOWUP_EMAIL_ADJUST_SYSTEM,
    build_followup_adjust_message,
    RESPONSE_AWARE_FOLLOWUP_SYSTEM,
    build_response_aware_followup_message,
)

from app.services.email_core import build_sign_off as _build_sign_off, resolve_sign_off_location as _resolve_sign_off_location, _DEFAULT_LOCATION

followup_bp = Blueprint('followup', __name__)


def _get_ai_client():
    """Get the right AI client based on APP_ENV."""
    from flask import current_app
    app_env = current_app.config.get('APP_ENV', 'testing').strip()
    if app_env == 'nvidia':
        print("[followup-email] Using NVIDIA Llama-3.3-Nemotron")
        return NvidiaClient()
    else:
        print(f"[followup-email] Using AWS Bedrock/Claude (APP_ENV={app_env})")
        return BedrockClient()

# ========== Constants ==========
TARGET_MIN = 80
TARGET_MAX = 120


# ========== Shared Utilities ==========

def _check_banned_words(text):
    """Check if body contains banned patterns. Returns list of violations."""
    violations = []
    text_lower = text.lower()
    # Banned verbs/words
    if 'maintained' in text_lower or 'maintaining' in text_lower or 'maintenance' in text_lower:
        violations.append('"maintained" (passive verb)')
    if 'incident' in text_lower:
        violations.append('"incidents"')
    if 'resolving' in text_lower and any(c.isdigit() for c in text_lower.split('resolving')[-1][:20]):
        violations.append('"resolving [number]"')
    # Banned proof types
    if 'sop' in text_lower.split() or 'sops' in text_lower.split():
        violations.append('"SOPs"')
    if 'troubleshooting guide' in text_lower or 'troubleshooting doc' in text_lower:
        violations.append('"troubleshooting guides"')
    if 'runbook' in text_lower:
        violations.append('"runbook"')
    # Banned bridge patterns
    if 'whether' in text_lower and 'the same' in text_lower:
        violations.append('"Whether X or Y, the same..."')
    if 'root cause analysis' in text_lower:
        violations.append('"root cause analysis"')
    # Banned AI inference language
    if 'tells me' in text_lower:
        violations.append('"tells me"')
    if 'signals' in text_lower and ('your team' in text_lower or 'you are' in text_lower or "you're" in text_lower):
        violations.append('"signals"')
    if 'means your team' in text_lower:
        violations.append('"means your team"')
    # Banned cliché openers
    if 'i hope this email finds you well' in text_lower:
        violations.append('"I hope this email finds you well"')
    if 'i am writing to express' in text_lower:
        violations.append('"I am writing to express"')
    if 'i believe i would be a great fit' in text_lower:
        violations.append('"I believe I would be a great fit"')
    # Banned false employment claims
    if 'currently working at capgemini' in text_lower or 'currently work at capgemini' in text_lower:
        violations.append('"currently working at Capgemini" (FALSE)')
    if "i'm currently a" in text_lower and 'capgemini' in text_lower:
        violations.append('"I\'m currently a ... at Capgemini" (FALSE)')
    if 'i currently' in text_lower and 'capgemini' in text_lower:
        violations.append('"I currently ... Capgemini" (FALSE)')
    # Follow-up specific bans
    if 'just following up' in text_lower and text_lower.index('just following up') < 50:
        violations.append('"Just following up" as opener (lazy)')
    if 'circle back' in text_lower:
        violations.append('"circle back" (corporate cliché)')
    if 'per my last email' in text_lower:
        violations.append('"per my last email" (passive-aggressive)')
    return violations


def _clean_body(body):
    """Clean and normalize email body text."""
    # Fix encoding artifacts
    body = body.replace('\u2019', "'").replace('\u2018', "'")
    body = body.replace('\u201c', '"').replace('\u201d', '"')
    body = body.replace('\u2013', '-').replace('\u2014', '-')
    body = body.replace('\u2026', '...')
    body = body.replace('\u00a0', ' ')
    # Remove non-ASCII
    body = body.encode('ascii', 'ignore').decode('ascii')
    # Normalize whitespace within lines (but preserve paragraph breaks)
    lines = body.split('\n')
    cleaned_lines = []
    for line in lines:
        cleaned_lines.append(' '.join(line.split()))
    body = '\n'.join(cleaned_lines)
    # Collapse 3+ newlines into 2
    body = _re.sub(r'\n{3,}', '\n\n', body)
    return body.strip()


def _strip_sign_off(body):
    """Remove any sign-off the AI might have included despite instructions."""
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
        # Strip any city/province line the AI may have auto-appended
        if _re.match(r'^[a-z .\'-]+,\s*[a-z]{2}$', stripped):
            continue
        clean_lines.append(line)
    return '\n'.join(clean_lines).rstrip()


def _count_words(text):
    """Count words in text, excluding the greeting line."""
    lines = text.strip().split('\n')
    body_lines = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Skip greeting line
        if i == 0 and (stripped.lower().startswith('hi ') or stripped.lower().startswith('hello ') or stripped.lower().startswith('dear ')):
            continue
        body_lines.append(stripped)
    body_text = ' '.join(body_lines)
    return len(body_text.split())


def _generate_single_followup(original_email, company_name, role_title, response_text='', project_updates_text=''):
    """Generate a follow-up email for a single recipient. Returns dict with result.

    If response_text is provided, generates a response-aware reply instead
    of a generic follow-up.
    """

    recipient_name = original_email.get('recipient_name', '')
    recipient_email = original_email.get('recipient_email', '')
    recipient_title = original_email.get('recipient_title', '')
    recipient_category = original_email.get('recipient_category', 'category_a')
    original_subject = original_email.get('subject', '')
    original_body = original_email.get('body', '')

    is_response_aware = bool(response_text and response_text.strip())

    if not recipient_name or not recipient_name.strip():
        return {
            'error': f'Missing recipient name for email to {recipient_email}',
            'recipient_email': recipient_email,
        }

    first_name = recipient_name.strip().split()[0]
    total_tokens = 0
    total_cost = 0.0

    # Get AI client based on APP_ENV
    ai_client = _get_ai_client()

    # Extract location from original email's sign-off (line before LinkedIn URL)
    original_location = _DEFAULT_LOCATION
    if original_body:
        orig_lines = original_body.strip().split('\n')
        for idx, line in enumerate(orig_lines):
            if 'linkedin.com/in/meettpatel28' in line.lower() and idx > 0:
                candidate = orig_lines[idx - 1].strip()
                # Should look like "City, Province" (e.g. "Ottawa, ON")
                if _re.match(r'^[A-Za-z .\'\-]+,\s*[A-Z]{2}$', candidate):
                    original_location = candidate
                    break
    print(f"[followup-email] Location from original: {original_location}")

    mode_label = '📨 RESPONSE-AWARE REPLY' if is_response_aware else '📩 FOLLOW-UP'
    print(f"\n[followup-email] === {mode_label} for {recipient_name} ({recipient_title}) ===")
    if is_response_aware:
        print(f"[followup-email] Response text ({len(response_text)} chars): {response_text[:120]}...")

    # Build the user message — branch based on whether we have a response
    if is_response_aware:
        system_prompt = RESPONSE_AWARE_FOLLOWUP_SYSTEM
        user_message = build_response_aware_followup_message(
            original_email_body=original_body,
            original_subject=original_subject,
            recipient_response_text=response_text.strip(),
            company_name=company_name,
            role_title=role_title,
            recipient_name=recipient_name,
            recipient_title=recipient_title,
            recipient_category=recipient_category,
            project_updates_text=project_updates_text,
        )
    else:
        system_prompt = FOLLOWUP_EMAIL_SYSTEM
        user_message = build_followup_email_message(
            original_email_body=original_body,
            original_subject=original_subject,
            company_name=company_name,
            role_title=role_title,
            recipient_name=recipient_name,
            recipient_title=recipient_title,
            recipient_category=recipient_category,
            project_updates_text=project_updates_text,
        )

    # Step 1: Generate the follow-up email
    MAX_RETRIES = 3
    subject = ''
    body = ''

    for attempt in range(1, MAX_RETRIES + 1):
        print(f"[followup-email] Attempt {attempt}/{MAX_RETRIES}")

        result = ai_client.analyze(
            system_prompt=system_prompt,
            user_message=user_message,
            max_tokens=1024,
            temperature=0.5,
            force_json=True,
            model_override='productionHigh',
        )

        total_tokens += result.get('tokens_used', 0)
        total_cost += result.get('cost_usd', 0.0)

        response = result.get('response', {})
        if isinstance(response, str):
            try:
                response = json.loads(response)
            except json.JSONDecodeError:
                print(f"[followup-email] ⚠️ Failed to parse JSON response, retrying...")
                continue

        subject = response.get('subject', '')
        body = response.get('body', '')

        if not subject or not body:
            print(f"[followup-email] ⚠️ Missing subject or body, retrying...")
            continue

        # Clean the body
        body = _clean_body(body)

        # Check banned words
        violations = _check_banned_words(body)
        if violations:
            print(f"[followup-email] ⚠️ Banned words found: {violations} — retrying...")
            continue

        # Check that follow-up is NOT a copy of original
        original_lower = original_body.lower()
        body_lower = body.lower()
        # Check for significant overlap (more than 40 words in common substring)
        original_words = set(original_lower.split())
        body_words = set(body_lower.split())
        overlap = original_words & body_words
        # Remove common English words from overlap check
        common_words = {'the', 'a', 'an', 'and', 'or', 'is', 'are', 'was', 'were', 'be', 'been',
                       'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
                       'may', 'might', 'can', 'shall', 'to', 'of', 'in', 'for', 'on', 'with', 'at',
                       'by', 'from', 'as', 'into', 'through', 'during', 'before', 'after', 'above',
                       'below', 'between', 'under', 'about', 'up', 'down', 'out', 'off', 'over',
                       'this', 'that', 'these', 'those', 'i', 'my', 'me', 'we', 'our', 'you', 'your',
                       'it', 'its', 'he', 'she', 'they', 'them', 'their', 'not', 'no', 'but', 'if',
                       'so', 'than', 'too', 'very', 'just', 'also', 'more', 'most', 'other', 'some',
                       'such', 'only', 'same', 'both', 'each', 'few', 'all', 'any', 'hi', 'hello',
                       'regards', 'best', 'meet', 'patel', '-', '--', 'role', 'team', 'work', 'working'}
        meaningful_overlap = overlap - common_words
        if len(meaningful_overlap) > 25:
            print(f"[followup-email] ⚠️ Too similar to original ({len(meaningful_overlap)} overlapping words), retrying...")
            continue

        # Passed all checks
        print(f"[followup-email] ✅ Passed all checks on attempt {attempt}")
        break
    else:
        print(f"[followup-email] ❌ All {MAX_RETRIES} attempts failed for {recipient_name}")
        return {
            'error': f'Failed to generate follow-up for {recipient_name} after {MAX_RETRIES} attempts',
            'recipient_email': recipient_email,
        }

    # Step 2: Word count adjustment
    word_count = _count_words(body)
    print(f"[followup-email] Initial word count: {word_count}")

    if word_count < TARGET_MIN or word_count > TARGET_MAX:
        print(f"[followup-email] Adjusting word count ({word_count} -> {TARGET_MIN}-{TARGET_MAX})")

        adjust_message = build_followup_adjust_message(body, word_count, TARGET_MIN, TARGET_MAX)
        adjust_result = ai_client.analyze(
            system_prompt=FOLLOWUP_EMAIL_ADJUST_SYSTEM,
            user_message=adjust_message,
            max_tokens=1024,
            temperature=0.2,
            model_override='productionLow',
        )

        total_tokens += adjust_result.get('tokens_used', 0)
        total_cost += adjust_result.get('cost_usd', 0.0)

        adjusted = adjust_result.get('response', '')
        if isinstance(adjusted, dict):
            adjusted = adjusted.get('body', adjusted.get('text', str(adjusted)))

        if adjusted and len(adjusted.strip()) > 20:
            body = _clean_body(adjusted)
            word_count = _count_words(body)
            print(f"[followup-email] Adjusted word count: {word_count}")

    # Step 2.5: RAG Quality Audit
    from app.services.email_auditor import audit_email as _audit_email, build_audit_rejection_feedback

    MAX_AUDIT_RETRIES = 2
    for audit_attempt in range(MAX_AUDIT_RETRIES):
        audit_result = _audit_email(
            email_body=body,
            jd_text='',  # Follow-ups don't have separate JD text
            resume_text='',  # Follow-ups don't have separate resume text
            recipient_name=recipient_name,
            recipient_title=recipient_title,
            recipient_category=recipient_category,
            email_type='followup',
        )
        total_tokens += audit_result.tokens_used
        total_cost += audit_result.cost_usd

        if audit_result.passed:
            print(f"[followup-email] ✅ RAG audit passed on attempt {audit_attempt + 1}")
            break
        else:
            print(f"[followup-email] ❌ RAG audit FAILED on attempt {audit_attempt + 1}")
            if audit_attempt < MAX_AUDIT_RETRIES - 1:
                audit_feedback = build_audit_rejection_feedback(audit_result)
                print(f"[followup-email] 🔄 Regenerating with audit feedback...")

                regen_message = audit_feedback + build_followup_email_message(
                    original_email_body=original_body,
                    original_subject=original_subject,
                    company_name=company_name,
                    role_title=role_title,
                    recipient_name=recipient_name,
                    recipient_title=recipient_title,
                    recipient_category=recipient_category,
                    project_updates_text=project_updates_text,
                )

                regen_result = ai_client.analyze(
                    system_prompt=FOLLOWUP_EMAIL_SYSTEM,
                    user_message=regen_message,
                    max_tokens=1024,
                    temperature=0.5,
                    force_json=True,
                    model_override='productionHigh',
                )
                total_tokens += regen_result.get('tokens_used', 0)
                total_cost += regen_result.get('cost_usd', 0.0)

                regen_response = regen_result.get('response', {})
                if isinstance(regen_response, str):
                    try:
                        regen_response = json.loads(regen_response)
                    except json.JSONDecodeError:
                        pass

                if isinstance(regen_response, dict) and regen_response.get('body'):
                    body = _clean_body(regen_response['body'])
                    subject = regen_response.get('subject', subject)
                    word_count = _count_words(body)
                    print(f"[followup-email] Regenerated body ({word_count} words)")
            else:
                print(f"[followup-email] ⚠️ Max audit retries reached — using last output")

    # Step 3: Final cleanup
    # Strip any sign-off the AI included
    body = _strip_sign_off(body)

    # Strip "ref REFENUM" artifacts
    body = _re.sub(r'\s*\(ref\s*REFENUM\)', '', body, flags=_re.IGNORECASE)
    body = _re.sub(r'\s*ref\s+REFENUM', '', body, flags=_re.IGNORECASE)

    # Append sign-off with location from original email
    body = body.rstrip() + _build_sign_off(original_location)
    print(f"[followup-email] Sign-off appended with location: {original_location}")

    # Final word count (for JSON output — count body excluding sign-off)
    final_body_for_count = _strip_sign_off(body)
    final_word_count = _count_words(final_body_for_count)
    print(f"[followup-email] Final word count: {final_word_count}")
    print(f"[followup-email] Subject: {subject[:80]}")


    return {
        'subject': subject,
        'body': body,
        'company_name': company_name,
        'role_title': role_title,
        'recipient_name': recipient_name,
        'recipient_email': recipient_email,
        'recipient_title': recipient_title,
        'recipient_category': recipient_category,
        'signal_used': f'Follow-up to: {original_subject}',
        'word_count': final_word_count,
        'is_response_reply': is_response_aware,
        'generated_at': datetime.now().isoformat(),
        'tokens_used': total_tokens,
        'cost_usd': total_cost,
    }


# ========== Routes ==========

@followup_bp.route('/')
@login_required
def followup_page():
    """Render the follow-up email generator page."""
    return render_template('followup.html')


@followup_bp.route('/generate', methods=['POST'])
@login_required
def generate_followups():
    """Accept uploaded JSON, generate follow-up emails for all recipients."""

    # Check if file was uploaded
    if 'email_json' not in request.files:
        return jsonify({'error': 'No file uploaded. Please select a JSON file.'}), 400

    file = request.files['email_json']
    if not file.filename or not file.filename.endswith('.json'):
        return jsonify({'error': 'Invalid file type. Please upload a .json file.'}), 400

    # Parse the JSON
    try:
        file_content = file.read().decode('utf-8')
        original_data = json.loads(file_content)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return jsonify({'error': f'Invalid JSON file: {str(e)}'}), 400

    # Validate structure
    company_name = original_data.get('company', '')
    role_title = original_data.get('role', '')
    original_emails = original_data.get('emails', [])

    if not company_name:
        return jsonify({'error': 'JSON missing "company" field.'}), 400
    if not role_title:
        return jsonify({'error': 'JSON missing "role" field.'}), 400
    if not original_emails or not isinstance(original_emails, list):
        return jsonify({'error': 'JSON missing "emails" array or it is empty.'}), 400

    print(f"\n[followup-email] ========================================")
    print(f"[followup-email] Generating follow-ups for {company_name} - {role_title}")
    print(f"[followup-email] {len(original_emails)} recipients")
    print(f"[followup-email] ========================================")

    # Generate follow-up for each recipient
    followup_emails = []
    errors = []
    total_tokens = 0
    total_cost = 0.0

    # Extract per-recipient responses from the request (sent as JSON field)
    responses_map = {}
    try:
        responses_json = request.form.get('responses', '{}')
        responses_map = json.loads(responses_json) if responses_json else {}
    except (json.JSONDecodeError, TypeError):
        pass

    # Fetch GitHub project updates (once per batch)
    project_updates_text = get_project_updates_for_prompt()

    for i, original_email in enumerate(original_emails):
        recipient_name = original_email.get('recipient_name', f'Recipient {i+1}')
        recipient_email_addr = original_email.get('recipient_email', '')
        print(f"\n[followup-email] --- [{i+1}/{len(original_emails)}] {recipient_name} ---")

        # Check if user provided a response for this recipient
        response_text = responses_map.get(recipient_email_addr, '')
        if response_text:
            print(f"[followup-email] 📨 Response provided for {recipient_name}")

        result = _generate_single_followup(original_email, company_name, role_title, response_text=response_text, project_updates_text=project_updates_text)

        if 'error' in result:
            errors.append(result)
            print(f"[followup-email] ❌ Error: {result['error']}")
        else:
            total_tokens += result.pop('tokens_used', 0)
            total_cost += result.pop('cost_usd', 0.0)
            followup_emails.append(result)
            print(f"[followup-email] ✅ Done: {recipient_name}")

    # Build output JSON (same format as input)
    output = {
        'company': company_name,
        'role': role_title,
        'generated_at': datetime.now().isoformat(),
        'total_recipients': len(followup_emails),
        'emails': followup_emails,
    }

    print(f"\n[followup-email] ========================================")
    print(f"[followup-email] COMPLETE: {len(followup_emails)}/{len(original_emails)} follow-ups generated")
    print(f"[followup-email] Total tokens: {total_tokens}")
    print(f"[followup-email] Total cost: ${total_cost:.4f}")
    if errors:
        print(f"[followup-email] Errors: {len(errors)}")
    print(f"[followup-email] ========================================")

    return jsonify({
        'output': output,
        'stats': {
            'total_generated': len(followup_emails),
            'total_recipients': len(original_emails),
            'errors': errors,
            'tokens_used': total_tokens,
            'cost_usd': total_cost,
        }
    })
