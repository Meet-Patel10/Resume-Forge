import json
from datetime import datetime, timezone
from app import db


class Application(db.Model):
    """Tracks every job application with its JD, tailored resume, and status."""
    __tablename__ = 'applications'

    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(300), nullable=False)
    role_title = db.Column(db.String(300), nullable=False)
    jd_text = db.Column(db.Text, nullable=False)
    jd_url = db.Column(db.String(500))

    status = db.Column(db.String(50), default='applied')
    # applied | screening | interview | offer | rejected | ghosted

    ats_score = db.Column(db.Integer)  # 0-100
    _keyword_matches = db.Column('keyword_matches', db.Text, default='[]')
    _tailored_resume = db.Column('tailored_resume', db.Text)
    tailored_latex = db.Column(db.Text)
    cover_letter = db.Column(db.Text)
    notes = db.Column(db.Text)

    applied_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    analyses = db.relationship('AnalysisHistory', backref='application', lazy=True,
                               cascade='all, delete-orphan')

    @property
    def keyword_matches(self):
        return json.loads(self._keyword_matches) if self._keyword_matches else []

    @keyword_matches.setter
    def keyword_matches(self, value):
        self._keyword_matches = json.dumps(value)

    @property
    def tailored_resume(self):
        return json.loads(self._tailored_resume) if self._tailored_resume else None

    @tailored_resume.setter
    def tailored_resume(self, value):
        self._tailored_resume = json.dumps(value)

    def to_dict(self):
        return {
            'id': self.id,
            'company_name': self.company_name,
            'role_title': self.role_title,
            'jd_text': self.jd_text[:200] + '...' if self.jd_text and len(self.jd_text) > 200 else self.jd_text,
            'jd_url': self.jd_url,
            'status': self.status,
            'ats_score': self.ats_score,
            'keyword_matches': self.keyword_matches,
            'has_tailored_resume': self._tailored_resume is not None,
            'has_cover_letter': self.cover_letter is not None,
            'notes': self.notes,
            'applied_at': self.applied_at.isoformat() if self.applied_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
