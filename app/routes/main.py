from flask import Blueprint, render_template
from app.models.application import Application
from app.models.master_resume import MasterResume
from app.models.analysis import AnalysisHistory
from app import db
from sqlalchemy import func

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Landing page."""
    return render_template('index.html')


@main_bp.route('/dashboard')
def dashboard():
    """Dashboard with application tracker and stats."""
    resume = MasterResume.query.first()
    applications = Application.query.order_by(Application.applied_at.desc()).all()

    # Calculate token & request usage
    total_tokens = db.session.query(func.sum(AnalysisHistory.tokens_used)).scalar() or 0
    total_requests = db.session.query(func.count(AnalysisHistory.id)).scalar() or 0

    # Calculate stats
    total = len(applications)
    by_status = {}
    total_ats = 0
    ats_count = 0
    for app in applications:
        by_status[app.status] = by_status.get(app.status, 0) + 1
        if app.ats_score:
            total_ats += app.ats_score
            ats_count += 1

    stats = {
        'total_applications': total,
        'by_status': by_status,
        'avg_ats_score': round(total_ats / ats_count) if ats_count else 0,
        'response_rate': round(
            (by_status.get('screening', 0) + by_status.get('interview', 0) +
             by_status.get('offer', 0)) / max(total, 1) * 100
        ),
        'total_tokens': f"{total_tokens:,}",  # Format with commas
        'total_requests': f"{total_requests:,}",
    }

    return render_template('dashboard.html',
                           resume=resume,
                           applications=applications,
                           stats=stats)
