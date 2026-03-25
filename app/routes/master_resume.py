import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from app import db
from app.models.master_resume import MasterResume
from app.models.bullet import Bullet
from app.services.ats_scorer import calculate_ats_score

master_resume_bp = Blueprint('master_resume', __name__)


@master_resume_bp.route('/', methods=['GET'])
def master_resume_page():
    """Render the master resume management page."""
    resume = MasterResume.query.first()
    bullets_list = [b.to_dict() for b in resume.bullets] if resume and resume.bullets else []
    return render_template('master_resume.html', resume=resume, bullets_list=bullets_list)


@master_resume_bp.route('/save', methods=['POST'])
def save_master_resume():
    """Save or update the master resume from form data."""
    resume = MasterResume.query.first()
    is_new = resume is None

    if is_new:
        resume = MasterResume()

    # Basic info
    resume.full_name = request.form.get('full_name', '')
    resume.email = request.form.get('email', '')
    resume.phone = request.form.get('phone', '')
    resume.location = request.form.get('location', '')
    resume.linkedin_url = request.form.get('linkedin_url', '')
    resume.github_url = request.form.get('github_url', '')
    resume.portfolio_url = request.form.get('portfolio_url', '')
    resume.tagline = request.form.get('tagline', '')
    resume.summary = request.form.get('summary', '')

    # Skills (JSON from hidden input)
    skills_json = request.form.get('skills_json', '[]')
    try:
        resume.skills = json.loads(skills_json)
    except json.JSONDecodeError:
        resume.skills = []

    # Education (JSON from hidden input)
    education_json = request.form.get('education_json', '[]')
    try:
        resume.education = json.loads(education_json)
    except json.JSONDecodeError:
        resume.education = []

    # Languages (JSON from hidden input)
    languages_json = request.form.get('languages_json', '[]')
    try:
        resume.languages = json.loads(languages_json)
    except json.JSONDecodeError:
        resume.languages = []

    if is_new:
        db.session.add(resume)

    db.session.commit()

    # Handle bullets
    bullets_json = request.form.get('bullets_json', '[]')
    try:
        bullets_data = json.loads(bullets_json)
    except json.JSONDecodeError:
        bullets_data = []

    if bullets_data:
        # Clear existing bullets and re-add
        Bullet.query.filter_by(master_resume_id=resume.id).delete()
        for i, b in enumerate(bullets_data):
            bullet = Bullet(
                master_resume_id=resume.id,
                company=b.get('company', ''),
                role=b.get('role', ''),
                dates=b.get('dates', ''),
                section_type=b.get('section_type', 'experience'),
                sort_order=i,
                original_text=b.get('original_text', ''),
                xyz_version=b.get('xyz_version', ''),
                skill_tags=', '.join(b.get('skill_tags', [])),
                impact_score=b.get('impact_score'),
                is_active=b.get('is_active', True),
                tech_stack=b.get('tech_stack', ''),
                repo_url=b.get('repo_url', ''),
            )
            db.session.add(bullet)
        db.session.commit()

    flash('Master resume saved successfully!', 'success')
    return redirect(url_for('master_resume.master_resume_page'))


@master_resume_bp.route('/upload', methods=['POST'])
def upload_resume():
    """Upload a resume file (PDF, DOCX, TXT) and extract its text."""
    from app.services.resume_parser import parse_resume_file

    if 'resume_file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['resume_file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    try:
        from app.services.claude_client import claude
        from app.services.prompts.master_parser import MASTER_PARSER_SYSTEM

        # 1. Extract raw text from file
        result = parse_resume_file(file)
        raw_text = result['text']

        # 2. Parse text into structured JSON using AI
        user_message = f"Here is the raw resume text:\n\n{raw_text}"
        ai_result = claude.analyze(MASTER_PARSER_SYSTEM, user_message)

        if ai_result.get('error'):
            return jsonify({'error': f"AI parsing failed: {ai_result['error']}"}), 500

        parsed_data = ai_result['response']

        # In case the AI returned a string instead of JSON object
        if isinstance(parsed_data, str):
            try:
                parsed_data = json.loads(parsed_data)
            except json.JSONDecodeError:
                return jsonify({'error': 'AI failed to return valid JSON', 'raw_text': raw_text}), 500

        return jsonify({
            'success': True,
            'text': raw_text,
            'parsed_data': parsed_data,
            'filename': result['filename'],
            'format': result['format'],
            'cost_usd': ai_result['cost_usd']
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Failed to parse file: {str(e)}'}), 500


@master_resume_bp.route('/api/data', methods=['GET'])
def api_get_resume():
    """Get master resume as JSON."""
    resume = MasterResume.query.first()
    if not resume:
        return jsonify({'error': 'No master resume found. Please set one up first.'}), 404
    return jsonify(resume.to_dict())


@master_resume_bp.route('/api/text', methods=['GET'])
def api_get_resume_text():
    """Get master resume as plain text (for Claude analysis)."""
    resume = MasterResume.query.first()
    if not resume:
        return jsonify({'error': 'No master resume found'}), 404
    return jsonify({'text': resume.to_resume_text()})


@master_resume_bp.route('/ats-check', methods=['POST'])
def ats_check():
    """Check ATS score of master resume against a job description."""
    resume = MasterResume.query.first()
    if not resume:
        return jsonify({'error': 'No master resume found. Please save your resume first.'}), 404

    data = request.get_json()
    jd_text = data.get('jd_text', '').strip()
    if not jd_text:
        return jsonify({'error': 'Please paste a job description to check against.'}), 400

    resume_text = resume.to_resume_text()
    score = calculate_ats_score(resume_text, jd_text)
    return jsonify(score)


@master_resume_bp.route('/health-check', methods=['POST'])
def health_check():
    """Get a general resume health score — no JD required."""
    resume = MasterResume.query.first()
    if not resume:
        return jsonify({'error': 'No master resume found. Please save your resume first.'}), 404

    resume_text = resume.to_resume_text()

    from app.services.ats_scorer import calculate_general_health_score
    score = calculate_general_health_score(resume_text)
    return jsonify(score)

