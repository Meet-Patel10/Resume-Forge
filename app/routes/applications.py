from flask import Blueprint, render_template, request, jsonify, session
from app import db
from app.models.application import Application
from app.routes.auth import login_required

applications_bp = Blueprint('applications', __name__)


@applications_bp.route('/')
@login_required
def applications_page():
    """Render the applications tracker page."""
    applications = Application.query.filter_by(user_id=session.get('user_id')).order_by(Application.applied_at.desc()).all()
    return render_template('applications.html', applications=applications)


@applications_bp.route('/api/update-status', methods=['POST'])
@login_required
def update_status():
    """Update an application's status."""
    data = request.get_json()
    app_id = data.get('id')
    new_status = data.get('status')

    if not app_id or not new_status:
        return jsonify({'error': 'Application ID and status are required'}), 400

    valid = ['applied', 'screening', 'interview', 'offer', 'rejected', 'ghosted']
    if new_status not in valid:
        return jsonify({'error': f'Invalid status. Must be one of: {", ".join(valid)}'}), 400

    app_record = Application.query.get(app_id)
    if not app_record or app_record.user_id != session.get('user_id'):
        return jsonify({'error': 'Application not found'}), 404

    app_record.status = new_status
    db.session.commit()

    return jsonify({'success': True, 'status': new_status})


@applications_bp.route('/api/delete', methods=['POST'])
@login_required
def delete_application():
    """Delete an application."""
    data = request.get_json()
    app_id = data.get('id')

    app_record = Application.query.get(app_id)
    if not app_record or app_record.user_id != session.get('user_id'):
        return jsonify({'error': 'Application not found'}), 404

    db.session.delete(app_record)
    db.session.commit()

    return jsonify({'success': True})


@applications_bp.route('/api/versions/<int:app_id>')
@login_required
def get_versions(app_id):
    """Get version history for an application with score deltas."""
    from app.models.resume_version import ResumeVersion

    app_record = Application.query.get(app_id)
    if not app_record or app_record.user_id != session.get('user_id'):
        return jsonify({'error': 'Application not found'}), 404

    versions = ResumeVersion.query.filter_by(application_id=app_id)\
        .order_by(ResumeVersion.version_number.asc()).all()

    result = []
    prev_score = None
    for v in versions:
        entry = v.to_dict()
        entry['score_delta'] = (v.ats_score - prev_score) if (v.ats_score and prev_score) else None
        prev_score = v.ats_score
        result.append(entry)

    return jsonify({
        'application': {
            'company': app_record.company_name,
            'role': app_record.role_title,
            'current_score': app_record.ats_score,
        },
        'versions': result,
        'total_versions': len(result),
    })

