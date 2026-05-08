import json
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from app import db


class User(db.Model):
    """User accounts for the resume builder application."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(200), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(200))

    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    master_resumes = db.relationship('MasterResume', backref='user', lazy=True,
                                     cascade='all, delete-orphan')
    applications = db.relationship('Application', backref='user', lazy=True,
                                    cascade='all, delete-orphan')

    def set_password(self, password):
        """Hash and store the password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify a password against the stored hash."""
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'resume_count': len(self.master_resumes) if self.master_resumes else 0,
            'application_count': len(self.applications) if self.applications else 0,
        }
