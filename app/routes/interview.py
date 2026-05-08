from flask import Blueprint, render_template, request, jsonify, session
from app.routes.auth import login_required
from app.models.master_resume import MasterResume
from app.services.claude_client import claude
from app.services.prompts.interview_planner import INTERVIEW_PLANNER_SYSTEM, build_interview_message

interview_bp = Blueprint('interview', __name__)


@interview_bp.route('/')
@login_required
def interview_page():
    """Render the interview preparation page."""
    resume = MasterResume.query.filter_by(user_id=session.get('user_id')).first()
    return render_template('interview_prep.html', resume=resume)


@interview_bp.route('/api/plan', methods=['POST'])
@login_required
def api_interview_plan():
    """Generate a 2-week interview preparation action plan."""
    data = request.get_json()
    jd_text = data.get('jd_text', '')
    resume_text = data.get('resume_text', '')
    skill_list = data.get('skill_list', '')

    if not jd_text or not resume_text:
        return jsonify({'error': 'Both job description and resume text are required'}), 400

    user_message = build_interview_message(resume_text, jd_text, skill_list)
    result = claude.analyze(INTERVIEW_PLANNER_SYSTEM, user_message, max_tokens=6000)

    if result.get('error'):
        return jsonify({'error': result['error']}), 500

    return jsonify({
        'plan': result['response'],
        'tokens_used': result['tokens_used'],
        'cost_usd': result['cost_usd'],
    })
