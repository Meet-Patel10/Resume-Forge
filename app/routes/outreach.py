"""Standalone outreach email generation — independent of the tailor pipeline."""
import json as json_mod
import io
from flask import Blueprint, render_template, request, jsonify, session, send_file, current_app
from app.routes.auth import login_required
from app.services.email_core import generate_email_core, build_email_download
from app.services.resume_parser import parse_resume_file
from app.services.github_fetcher import get_project_updates_for_prompt

outreach_bp = Blueprint('outreach', __name__)


@outreach_bp.route('/')
@login_required
def outreach_page():
    """Render the standalone outreach email page."""
    return render_template('outreach.html')


@outreach_bp.route('/api/generate', methods=['POST'])
@login_required
def api_generate_outreach_email():
    """Generate an outreach email from uploaded resume + cover letter + JD.

    Accepts multipart form data:
      - resume_file: PDF/DOCX/TXT file upload OR resume_text: pasted text
      - cover_letter_file: PDF/DOCX/TXT upload OR cover_letter_text: pasted text
      - jd_text: job description (plain text in form field)
      - company_name, role_title, recipient_name, recipient_title,
        recipient_category, target_city
      - previously_used_signals/subjects/bodies/proofs (JSON strings for dedup)
    """
    try:
        # ── Parse resume: file upload OR pasted text ──
        resume_text = ''
        if 'resume_file' in request.files and request.files['resume_file'].filename:
            resume_file = request.files['resume_file']
            try:
                parsed = parse_resume_file(resume_file)
                resume_text = parsed.get('text', '')
                print(f"[outreach] Parsed resume from {parsed['filename']} ({parsed['format']}) — {len(resume_text)} chars")
            except ValueError as e:
                return jsonify({'error': str(e)}), 400
        else:
            resume_text = request.form.get('resume_text', '').strip()

        if not resume_text:
            return jsonify({'error': 'Please upload a resume file or paste resume text.'}), 400

        # ── Parse cover letter: file upload OR pasted text ──
        cover_letter_text = ''
        if 'cover_letter_file' in request.files and request.files['cover_letter_file'].filename:
            cl_file = request.files['cover_letter_file']
            try:
                parsed_cl = parse_resume_file(cl_file)  # same parser works for any text doc
                cover_letter_text = parsed_cl.get('text', '')
                print(f"[outreach] Parsed cover letter from {parsed_cl['filename']} ({parsed_cl['format']}) — {len(cover_letter_text)} chars")
            except ValueError as e:
                return jsonify({'error': f'Cover letter error: {str(e)}'}), 400
        else:
            cover_letter_text = request.form.get('cover_letter_text', '').strip()

        # ── Get form fields ──
        jd_text = request.form.get('jd_text', '').strip()
        company_name = request.form.get('company_name', '').strip()
        role_title = request.form.get('role_title', '').strip()
        recipient_name = request.form.get('recipient_name', '').strip()
        recipient_title = request.form.get('recipient_title', '').strip()
        recipient_category = request.form.get('recipient_category', '').strip()
        target_city = request.form.get('target_city', '').strip()

        # ── Parse dedup arrays (sent as JSON strings in form data) ──
        def _parse_json_field(field_name):
            raw = request.form.get(field_name, '[]')
            try:
                return json_mod.loads(raw) if raw else []
            except (json_mod.JSONDecodeError, TypeError):
                return []

        previously_used_signals = _parse_json_field('previously_used_signals')
        previously_used_subjects = _parse_json_field('previously_used_subjects')
        previously_used_bodies = _parse_json_field('previously_used_bodies')
        previously_used_proofs = _parse_json_field('previously_used_proofs')

        # ── Fetch GitHub project updates (once per request) ──
        project_updates_text = get_project_updates_for_prompt()

        # ── Generate email using shared core ──
        result = generate_email_core(
            resume_text=resume_text,
            jd_text=jd_text,
            company_name=company_name,
            role_title=role_title,
            recipient_name=recipient_name,
            cover_letter_text=cover_letter_text,
            recipient_title=recipient_title,
            recipient_category=recipient_category,
            target_city=target_city,
            previously_used_signals=previously_used_signals,
            previously_used_subjects=previously_used_subjects,
            previously_used_bodies=previously_used_bodies,
            previously_used_proofs=previously_used_proofs,
            project_updates_text=project_updates_text,
        )

        if 'error' in result:
            return jsonify({'error': result['error']}), result.get('status_code', 500)

        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Outreach email generation failed: {str(e)}'}), 500


@outreach_bp.route('/api/download', methods=['POST'])
@login_required
def api_download_outreach_email():
    """Download outreach email(s) as a structured JSON file."""
    data = request.get_json()
    company_name = data.get('company_name', '')
    role_title = data.get('role_title', '')

    emails = data.get('emails', None)
    if emails is None:
        body = data.get('body', '')
        if not body:
            return jsonify({'error': 'No email body provided'}), 400
        emails = [{
            'subject': data.get('subject', ''),
            'body': body,
            'ref_number': data.get('ref_number', 'REFENUM'),
            'company_name': company_name,
            'role_title': role_title,
            'recipient_name': data.get('recipient_name', ''),
            'recipient_email': data.get('recipient_email', ''),
            'recipient_title': data.get('recipient_title', ''),
            'recipient_category': data.get('recipient_category', 'category_a'),
            'signal_used': data.get('signal_used', ''),
            'word_count': data.get('word_count', 0),
        }]

    if not emails or len(emails) == 0:
        return jsonify({'error': 'No emails provided'}), 400

    output, filename = build_email_download(emails, company_name, role_title)
    if not output:
        return jsonify({'error': 'No emails provided'}), 400

    json_bytes = json_mod.dumps(output, indent=2, ensure_ascii=False).encode('utf-8')

    return send_file(
        io.BytesIO(json_bytes),
        mimetype='application/json',
        as_attachment=True,
        download_name=filename,
    )
