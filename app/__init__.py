import os
from datetime import timedelta
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from app.config import config

db = SQLAlchemy()


def create_app(config_name=None):
    """Application factory pattern."""
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'default')

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Initialize extensions
    db.init_app(app)

    # Register blueprints
    from app.routes.main import main_bp
    from app.routes.analyze import analyze_bp
    from app.routes.tailor import tailor_bp
    from app.routes.master_resume import master_resume_bp
    from app.routes.applications import applications_bp
    from app.routes.interview import interview_bp

    from app.routes.auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(main_bp)
    app.register_blueprint(analyze_bp, url_prefix='/analyze')
    app.register_blueprint(tailor_bp, url_prefix='/tailor')
    app.register_blueprint(master_resume_bp, url_prefix='/master-resume')
    app.register_blueprint(applications_bp, url_prefix='/applications')
    app.register_blueprint(interview_bp, url_prefix='/interview-prep')

    # 30-day session for 'remember me'
    app.permanent_session_lifetime = timedelta(days=30)

    # Create database tables
    with app.app_context():
        from app.models import master_resume, bullet, application, analysis, user, resume_version
        db.create_all()

    return app
