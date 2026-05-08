from flask import Blueprint, render_template, request, jsonify, session
from app.routes.auth import login_required
from app import db
from app.models.master_resume import MasterResume
from app.models.application import Application
from app.models.analysis import AnalysisHistory
from app.services.claude_client import claude
from app.services.prompts.brutal_critic import BRUTAL_CRITIC_SYSTEM, build_critique_message
from app.services.prompts.keyword_extractor import KEYWORD_EXTRACTOR_SYSTEM, build_keyword_message
from app.services.prompts.gap_filler import GAP_FILLER_SYSTEM, build_gap_message

analyze_bp = Blueprint('analyze', __name__)


@analyze_bp.route('/')
@login_required
def analyze_page():
    """Render the analysis page."""
    resume = MasterResume.query.filter_by(user_id=session.get('user_id')).first()
    return render_template('analyze.html', resume=resume)


@analyze_bp.route('/api/critique', methods=['POST'])
@login_required
def api_critique():
    """Run brutal critique analysis on resume vs JD."""
    data = request.get_json()
    jd_text = data.get('jd_text', '')
    resume_text = data.get('resume_text', '')

    if not jd_text or not resume_text:
        return jsonify({'error': 'Both job description and resume text are required'}), 400

    # Get critique from Claude
    user_message = build_critique_message(resume_text, jd_text)
    result = claude.analyze(BRUTAL_CRITIC_SYSTEM, user_message, max_tokens=4096)

    if result.get('error'):
        return jsonify({'error': result['error']}), 500

    # Save to history if an application_id is provided
    app_id = data.get('application_id')
    if app_id:
        history = AnalysisHistory(
            application_id=app_id,
            analysis_type='critique',
        )
        history.input_data = {'jd_length': len(jd_text), 'resume_length': len(resume_text)}
        history.output_data = result['response'] if isinstance(result['response'], dict) else {'raw': result['raw_text']}
        history.tokens_used = result['tokens_used']
        history.cost_usd = result['cost_usd']
        db.session.add(history)
        db.session.commit()

    return jsonify({
        'critique': result['response'],
        'tokens_used': result['tokens_used'],
        'cost_usd': result['cost_usd'],
    })


@analyze_bp.route('/api/keywords', methods=['POST'])
@login_required
def api_keywords():
    """Extract top keywords and map against resume."""
    data = request.get_json()
    jd_text = data.get('jd_text', '')
    resume_text = data.get('resume_text', '')

    if not jd_text or not resume_text:
        return jsonify({'error': 'Both job description and resume text are required'}), 400

    user_message = build_keyword_message(resume_text, jd_text)
    result = claude.analyze(KEYWORD_EXTRACTOR_SYSTEM, user_message, max_tokens=4096)

    if result.get('error'):
        return jsonify({'error': result['error']}), 500

    # Save to history
    app_id = data.get('application_id')
    if app_id:
        history = AnalysisHistory(
            application_id=app_id,
            analysis_type='keywords',
        )
        history.input_data = {'jd_length': len(jd_text)}
        history.output_data = result['response'] if isinstance(result['response'], dict) else {'raw': result['raw_text']}
        history.tokens_used = result['tokens_used']
        history.cost_usd = result['cost_usd']
        db.session.add(history)
        db.session.commit()

    return jsonify({
        'keywords': result['response'],
        'tokens_used': result['tokens_used'],
        'cost_usd': result['cost_usd'],
    })


@analyze_bp.route('/api/gap-fill', methods=['POST'])
@login_required
def api_gap_fill():
    """Generate gap-filling micro-projects and certifications."""
    data = request.get_json()
    jd_text = data.get('jd_text', '')
    resume_text = data.get('resume_text', '')
    keyword_gaps = data.get('keyword_gaps', [])

    if not jd_text or not resume_text:
        return jsonify({'error': 'Both job description and resume text are required'}), 400

    user_message = build_gap_message(resume_text, jd_text, keyword_gaps)
    result = claude.analyze(GAP_FILLER_SYSTEM, user_message, max_tokens=4096)

    if result.get('error'):
        return jsonify({'error': result['error']}), 500

    return jsonify({
        'gap_analysis': result['response'],
        'tokens_used': result['tokens_used'],
        'cost_usd': result['cost_usd'],
    })
