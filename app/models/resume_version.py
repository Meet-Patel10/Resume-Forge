import json
from datetime import datetime, timezone
from app import db


class ResumeVersion(db.Model):
    """Tracks every version of a tailored resume for a specific job application.

    Each time a resume is tailored, a new version is created — enabling
    version history and comparison.
    """
    __tablename__ = 'resume_versions'

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('applications.id'), nullable=False)
    version_number = db.Column(db.Integer, nullable=False, default=1)

    # Resume content
    _resume_json = db.Column('resume_json', db.Text)  # Full structured resume JSON
    resume_latex = db.Column(db.Text)                  # Rendered LaTeX output
    resume_plain_text = db.Column(db.Text)             # Plain text for scoring

    # Scoring
    ats_score = db.Column(db.Integer)  # 0-100
    _score_breakdown = db.Column('score_breakdown', db.Text)  # Detailed score JSON

    # AI metadata
    tokens_used = db.Column(db.Integer, default=0)
    cost_usd = db.Column(db.Float, default=0.0)
    _pipeline_steps = db.Column('pipeline_steps', db.Text, default='[]')

    # Timestamps
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    @property
    def resume_json(self):
        return json.loads(self._resume_json) if self._resume_json else None

    @resume_json.setter
    def resume_json(self, value):
        self._resume_json = json.dumps(value) if value else None

    @property
    def score_breakdown(self):
        return json.loads(self._score_breakdown) if self._score_breakdown else None

    @score_breakdown.setter
    def score_breakdown(self, value):
        self._score_breakdown = json.dumps(value) if value else None

    @property
    def pipeline_steps(self):
        return json.loads(self._pipeline_steps) if self._pipeline_steps else []

    @pipeline_steps.setter
    def pipeline_steps(self, value):
        self._pipeline_steps = json.dumps(value) if value else '[]'

    def to_dict(self):
        return {
            'id': self.id,
            'application_id': self.application_id,
            'version_number': self.version_number,
            'ats_score': self.ats_score,
            'score_breakdown': self.score_breakdown,
            'tokens_used': self.tokens_used,
            'cost_usd': round(self.cost_usd, 4) if self.cost_usd else 0,
            'pipeline_steps': self.pipeline_steps,
            'has_latex': self.resume_latex is not None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
