"""
Second Follow-Up Email Generator — Route
Upload BOTH the original outreach JSON AND the first follow-up JSON.
AI generates second follow-up emails for all recipients.
"""

import json
import re as _re
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, session
from app.routes.auth import login_required
from app.services.claude_client import BedrockClient
from app.services.prompts.second_followup_email import (
    SECOND_FOLLOWUP_EMAIL_SYSTEM,
    build_second_followup_email_message,
    SECOND_FOLLOWUP_ADJUST_SYSTEM,
    build_second_followup_adjust_message,
)

from app.services.email_core import build_sign_off, resolve_sign_off_location, _DEFAULT_LOCATION

second_followup_bp = Blueprint('second_followup', __name__)
bedrock = BedrockClient()

# ========== Constants ==========
TARGET_MIN = 50
TARGET_MAX = 90


# ========== Shared Utilities (same as first follow-up) ==========

def _check_banned_words(text):
    """Check if body contains banned patterns. Returns list of violations."""
    violations = []
    text_lower = text.lower()
    if 'maintained' in text_lower or 'maintaining' in text_lower or 'maintenance' in text_lower:
        violations.append('"maintained" (passive verb)')
    if 'incident' in text_lower:
        violations.append('"incidents"')
    if 'resolving' in text_lower and any(c.isdigit() for c in text_lower.split('resolving')[-1][:20]):
        violations.append('"resolving [number]"')
    if 'sop' in text_lower.split() or 'sops' in text_lower.split():
        violations.append('"SOPs"')
    if 'troubleshooting guide' in text_lower or 'troubleshooting doc' in text_lower:
        violations.append('"troubleshooting guides"')
    if 'runbook' in text_lower:
        violations.append('"runbook"')
    if 'whether' in text_lower and 'the same' in text_lower:
        violations.append('"Whether X or Y, the same..."')
    if 'root cause analysis' in text_lower:
        violations.append('"root cause analysis"')
    if 'tells me' in text_lower:
        violations.append('"tells me"')
    if 'signals' in text_lower and ('your team' in text_lower or 'you are' in text_lower or "you're" in text_lower):
        violations.append('"signals"')
    if 'means your team' in text_lower:
        violations.append('"means your team"')
    if 'i hope this email finds you well' in text_lower:
        violations.append('"I hope this email finds you well"')
    if 'i am writing to express' in text_lower:
        violations.append('"I am writing to express"')
    if 'i believe i would be a great fit' in text_lower:
        violations.append('"I believe I would be a great fit"')
    if 'currently working at capgemini' in text_lower or 'currently work at capgemini' in text_lower:
        violations.append('"currently working at Capgemini" (FALSE)')
    if "i'm currently a" in text_lower and 'capgemini' in text_lower:
        violations.append('"I\'m currently a ... at Capgemini" (FALSE)')
    if 'i currently' in text_lower and 'capgemini' in text_lower:
        violations.append('"I currently ... Capgemini" (FALSE)')
    # Second follow-up specific bans
    if 'just following up' in text_lower and text_lower.index('just following up') < 50:
        violations.append('"Just following up" as opener (lazy)')
    if 'circle back' in text_lower:
        violations.append('"circle back" (corporate cliché)')
    if 'per my last email' in text_lower:
        violations.append('"per my last email" (passive-aggressive)')
    if "i'm sorry to bother" in text_lower or 'sorry to bother' in text_lower:
        violations.append('"sorry to bother" (too apologetic)')
    if 'not sure if you saw' in text_lower:
        violations.append('"not sure if you saw" (condescending)')
    return violations


def _clean_body(body):
    """Clean and normalize email body text."""
    body = body.replace('\u2019', "'").replace('\u2018', "'")
    body = body.replace('\u201c', '"').replace('\u201d', '"')
    body = body.replace('\u2013', '-').replace('\u2014', '-')
    body = body.replace('\u2026', '...')
    body = body.replace('\u00a0', ' ')
    body = body.encode('ascii', 'ignore').decode('ascii')
    lines = body.split('\n')
    cleaned_lines = []
    for line in lines:
        cleaned_lines.append(' '.join(line.split()))
    body = '\n'.join(cleaned_lines)
    body = _re.sub(r'\n{3,}', '\n\n', body)
    return body.strip()


def _strip_sign_off(body):
    """Remove any sign-off the AI might have included."""
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
    return '\n'.join(clean_lines).rstrip()


def _count_words(text):
    """Count words in text, excluding the greeting line."""
    lines = text.strip().split('\n')
    body_lines = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if i == 0 and (stripped.lower().startswith('hi ') or stripped.lower().startswith('hello ') or stripped.lower().startswith('dear ')):
            continue
        body_lines.append(stripped)
    body_text = ' '.join(body_lines)
    return len(body_text.split())


def _generate_single_second_followup(original_email, followup_email, company_name, role_title):
    """Generate a second follow-up email for a single recipient. Returns dict."""

    recipient_name = followup_email.get('recipient_name', '')
    recipient_email = followup_email.get('recipient_email', '')
    recipient_title = followup_email.get('recipient_title', '')
    recipient_category = followup_email.get('recipient_category', 'category_a')

    # First follow-up data
    followup_subject = followup_email.get('subject', '')
    followup_body = followup_email.get('body', '')

    # Original outreach data
    original_subject = original_email.get('subject', '') if original_email else ''
    original_body = original_email.get('body', '') if original_email else ''

    if not recipient_name or not recipient_name.strip():
        return {
            'error': f'Missing recipient name for email to {recipient_email}',
            'recipient_email': recipient_email,
        }

    first_name = recipient_name.strip().split()[0]
    total_tokens = 0
    total_cost = 0.0

    # Extract location from follow-up email's sign-off
    original_location = _DEFAULT_LOCATION
    source_body = followup_body or original_body
    if source_body:
        lines = source_body.strip().split('\n')
        for idx, line in enumerate(lines):
            if 'linkedin.com/in/meettpatel28' in line.lower() and idx > 0:
                candidate = lines[idx - 1].strip()
                if _re.match(r'^[A-Za-z .\'-]+,\s*[A-Z]{2}$', candidate):
                    original_location = candidate
                    break
    print(f"[second-followup] Location from previous: {original_location}")

    print(f"\n[second-followup] === Generating second follow-up for {recipient_name} ({recipient_title}) ===")

    # Build the user message
    user_message = build_second_followup_email_message(
        original_email_body=original_body,
        original_subject=original_subject,
        first_followup_body=followup_body,
        first_followup_subject=followup_subject,
        company_name=company_name,
        role_title=role_title,
        recipient_name=recipient_name,
        recipient_title=recipient_title,
        recipient_category=recipient_category,
    )

    # Generate with retry loop
    MAX_RETRIES = 3
    subject = ''
    body = ''

    for attempt in range(1, MAX_RETRIES + 1):
        print(f"[second-followup] Attempt {attempt}/{MAX_RETRIES}")

        result = bedrock.analyze(
            system_prompt=SECOND_FOLLOWUP_EMAIL_SYSTEM,
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
                print(f"[second-followup] ⚠️ Failed to parse JSON response, retrying...")
                continue

        subject = response.get('subject', '')
        body = response.get('body', '')

        if not subject or not body:
            print(f"[second-followup] ⚠️ Missing subject or body, retrying...")
            continue

        # Clean the body
        body = _clean_body(body)

        # Check banned words
        violations = _check_banned_words(body)
        if violations:
            print(f"[second-followup] ⚠️ Banned words found: {violations} — retrying...")
            continue

        # Check body isn't a copy of EITHER previous email
        for label, prev_body in [('original', original_body), ('first follow-up', followup_body)]:
            if prev_body:
                prev_lower = prev_body.lower()
                body_lower = body.lower()
                prev_words = set(prev_lower.split())
                body_words = set(body_lower.split())
                overlap = prev_words & body_words
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
                if len(meaningful_overlap) > 20:
                    print(f"[second-followup] ⚠️ Too similar to {label} ({len(meaningful_overlap)} overlapping words), retrying...")
                    violations.append(f'Too similar to {label}')

        if violations:
            continue

        # Passed all checks
        print(f"[second-followup] ✅ Passed all checks on attempt {attempt}")
        break
    else:
        print(f"[second-followup] ❌ All {MAX_RETRIES} attempts failed for {recipient_name}")
        return {
            'error': f'Failed to generate second follow-up for {recipient_name} after {MAX_RETRIES} attempts',
            'recipient_email': recipient_email,
        }

    # Word count adjustment
    word_count = _count_words(body)
    print(f"[second-followup] Initial word count: {word_count}")

    if word_count < TARGET_MIN or word_count > TARGET_MAX:
        print(f"[second-followup] Adjusting word count ({word_count} -> {TARGET_MIN}-{TARGET_MAX})")

        adjust_message = build_second_followup_adjust_message(body, word_count, TARGET_MIN, TARGET_MAX)
        adjust_result = bedrock.analyze(
            system_prompt=SECOND_FOLLOWUP_ADJUST_SYSTEM,
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
            print(f"[second-followup] Adjusted word count: {word_count}")

    # RAG Quality Audit
    from app.services.email_auditor import audit_email as _audit_email, build_audit_rejection_feedback

    MAX_AUDIT_RETRIES = 2
    for audit_attempt in range(MAX_AUDIT_RETRIES):
        audit_result = _audit_email(
            email_body=body,
            jd_text='',
            resume_text='',
            recipient_name=recipient_name,
            recipient_title=recipient_title,
            recipient_category=recipient_category,
            email_type='second_followup',
        )
        total_tokens += audit_result.tokens_used
        total_cost += audit_result.cost_usd

        if audit_result.passed:
            print(f"[second-followup] ✅ RAG audit passed on attempt {audit_attempt + 1}")
            break
        else:
            print(f"[second-followup] ❌ RAG audit FAILED on attempt {audit_attempt + 1}")
            if audit_attempt < MAX_AUDIT_RETRIES - 1:
                audit_feedback = build_audit_rejection_feedback(audit_result)
                print(f"[second-followup] 🔄 Regenerating with audit feedback...")

                regen_message = audit_feedback + build_second_followup_email_message(
                    original_email_body=original_body,
                    original_subject=original_subject,
                    first_followup_body=followup_body,
                    first_followup_subject=followup_subject,
                    company_name=company_name,
                    role_title=role_title,
                    recipient_name=recipient_name,
                    recipient_title=recipient_title,
                    recipient_category=recipient_category,
                )

                regen_result = bedrock.analyze(
                    system_prompt=SECOND_FOLLOWUP_EMAIL_SYSTEM,
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
                    print(f"[second-followup] Regenerated body ({word_count} words)")
            else:
                print(f"[second-followup] ⚠️ Max audit retries reached — using last output")

    # Final cleanup
    body = _strip_sign_off(body)
    body = _re.sub(r'\s*\(ref\s*REFENUM\)', '', body, flags=_re.IGNORECASE)
    body = _re.sub(r'\s*ref\s+REFENUM', '', body, flags=_re.IGNORECASE)

    # Append sign-off with location from previous email
    body = body.rstrip() + build_sign_off(original_location)
    print(f"[second-followup] Sign-off appended with location: {original_location}")

    # Final word count
    final_body_for_count = _strip_sign_off(body)
    final_word_count = _count_words(final_body_for_count)
    print(f"[second-followup] Final word count: {final_word_count}")
    print(f"[second-followup] Subject: {subject[:80]}")


    return {
        'subject': subject,
        'body': body,
        'company_name': company_name,
        'role_title': role_title,
        'recipient_name': recipient_name,
        'recipient_email': recipient_email,
        'recipient_title': recipient_title,
        'recipient_category': recipient_category,
        'signal_used': f'Second follow-up to: {followup_subject}',
        'word_count': final_word_count,
        'generated_at': datetime.now().isoformat(),
        'tokens_used': total_tokens,
        'cost_usd': total_cost,
    }


# ========== Routes ==========

@second_followup_bp.route('/')
@login_required
def second_followup_page():
    """Render the second follow-up email generator page."""
    return render_template('second_followup.html')


@second_followup_bp.route('/generate', methods=['POST'])
@login_required
def generate_second_followups():
    """Accept uploaded JSONs (original + first follow-up), generate second follow-ups."""

    # Check if first follow-up file was uploaded
    if 'followup_json' not in request.files:
        return jsonify({'error': 'No first follow-up JSON file uploaded.'}), 400

    followup_file = request.files['followup_json']
    if not followup_file.filename or not followup_file.filename.endswith('.json'):
        return jsonify({'error': 'Invalid file type. Please upload a .json file for the first follow-up.'}), 400

    # Parse the first follow-up JSON
    try:
        followup_content = followup_file.read().decode('utf-8')
        followup_data = json.loads(followup_content)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return jsonify({'error': f'Invalid first follow-up JSON: {str(e)}'}), 400

    # Optionally parse the original outreach JSON
    original_data = None
    if 'original_json' in request.files and request.files['original_json'].filename:
        original_file = request.files['original_json']
        if original_file.filename.endswith('.json'):
            try:
                original_content = original_file.read().decode('utf-8')
                original_data = json.loads(original_content)
                print(f"[second-followup] Original outreach JSON loaded: {len(original_data.get('emails', []))} recipients")
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                print(f"[second-followup] Warning: Could not parse original JSON: {e}")

    # Validate structure
    company_name = followup_data.get('company', '')
    role_title = followup_data.get('role', '')
    followup_emails = followup_data.get('emails', [])

    if not company_name:
        return jsonify({'error': 'JSON missing "company" field.'}), 400
    if not role_title:
        return jsonify({'error': 'JSON missing "role" field.'}), 400
    if not followup_emails or not isinstance(followup_emails, list):
        return jsonify({'error': 'JSON missing "emails" array or it is empty.'}), 400

    # Build a lookup from recipient name/email to original outreach email
    original_emails_map = {}
    if original_data and original_data.get('emails'):
        for oe in original_data['emails']:
            key = (oe.get('recipient_name', '').strip().lower(), oe.get('recipient_email', '').strip().lower())
            original_emails_map[key] = oe

    print(f"\n[second-followup] ========================================")
    print(f"[second-followup] Generating second follow-ups for {company_name} - {role_title}")
    print(f"[second-followup] {len(followup_emails)} recipients")
    if original_data:
        print(f"[second-followup] Original outreach JSON provided ({len(original_emails_map)} mapped)")
    else:
        print(f"[second-followup] No original outreach JSON — will use first follow-up only")
    print(f"[second-followup] ========================================")

    # Generate second follow-up for each recipient
    result_emails = []
    errors = []
    total_tokens = 0
    total_cost = 0.0

    for i, followup_email in enumerate(followup_emails):
        recipient_name = followup_email.get('recipient_name', f'Recipient {i+1}')
        print(f"\n[second-followup] --- [{i+1}/{len(followup_emails)}] {recipient_name} ---")

        # Try to find the original outreach email for this recipient
        key = (recipient_name.strip().lower(), followup_email.get('recipient_email', '').strip().lower())
        original_email = original_emails_map.get(key, None)
        if not original_email:
            # Try matching by name only
            for k, v in original_emails_map.items():
                if k[0] == key[0]:
                    original_email = v
                    break

        if original_email:
            print(f"[second-followup] ✅ Matched original outreach email for {recipient_name}")
        else:
            print(f"[second-followup] ⚠️ No original outreach found for {recipient_name} — using follow-up only")

        result = _generate_single_second_followup(original_email, followup_email, company_name, role_title)

        if 'error' in result:
            errors.append(result)
            print(f"[second-followup] ❌ Error: {result['error']}")
        else:
            total_tokens += result.pop('tokens_used', 0)
            total_cost += result.pop('cost_usd', 0.0)
            result_emails.append(result)
            print(f"[second-followup] ✅ Done: {recipient_name}")

    # Build output JSON
    output = {
        'company': company_name,
        'role': role_title,
        'generated_at': datetime.now().isoformat(),
        'total_recipients': len(result_emails),
        'emails': result_emails,
    }

    print(f"\n[second-followup] ========================================")
    print(f"[second-followup] COMPLETE: {len(result_emails)}/{len(followup_emails)} second follow-ups generated")
    print(f"[second-followup] Total tokens: {total_tokens}")
    print(f"[second-followup] Total cost: ${total_cost:.4f}")
    if errors:
        print(f"[second-followup] Errors: {len(errors)}")
    print(f"[second-followup] ========================================")

    return jsonify({
        'output': output,
        'stats': {
            'total_generated': len(result_emails),
            'total_recipients': len(followup_emails),
            'errors': errors,
            'tokens_used': total_tokens,
            'cost_usd': total_cost,
        }
    })
