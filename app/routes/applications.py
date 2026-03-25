from flask import Blueprint, render_template, request, jsonify
from app import db
from app.models.application import Application

applications_bp = Blueprint('applications', __name__)


@applications_bp.route('/')
def applications_page():
    """Render the applications tracker page."""
    applications = Application.query.order_by(Application.applied_at.desc()).all()
    return render_template('applications.html', applications=applications)


@applications_bp.route('/api/update-status', methods=['POST'])
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
    if not app_record:
        return jsonify({'error': 'Application not found'}), 404

    app_record.status = new_status
    db.session.commit()

    return jsonify({'success': True, 'status': new_status})


@applications_bp.route('/api/delete', methods=['POST'])
def delete_application():
    """Delete an application."""
    data = request.get_json()
    app_id = data.get('id')

    app_record = Application.query.get(app_id)
    if not app_record:
        return jsonify({'error': 'Application not found'}), 404

    db.session.delete(app_record)
    db.session.commit()

    return jsonify({'success': True})
