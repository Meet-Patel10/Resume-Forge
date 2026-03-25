from datetime import datetime, timezone
from app import db


class Bullet(db.Model):
    """Individual bullet points from experience/projects,
    stored in the bullet bank for reuse across tailored resumes."""
    __tablename__ = 'bullet_bank'

    id = db.Column(db.Integer, primary_key=True)
    master_resume_id = db.Column(db.Integer, db.ForeignKey('master_resume.id'), nullable=False)

    # Context
    company = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(200), nullable=False)
    dates = db.Column(db.String(100))
    section_type = db.Column(db.String(50), default='experience')  # experience | project
    sort_order = db.Column(db.Integer, default=0)

    # Content
    original_text = db.Column(db.Text, nullable=False)
    xyz_version = db.Column(db.Text)  # X-Y-Z rewritten version

    # Metadata
    skill_tags = db.Column(db.Text, default='')  # comma-separated tags
    impact_score = db.Column(db.Integer)  # 1-10 rated by AI
    is_active = db.Column(db.Boolean, default=True)

    # Project-specific fields
    tech_stack = db.Column(db.String(500))
    repo_url = db.Column(db.String(500))

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def get_tags(self):
        return [t.strip() for t in self.skill_tags.split(',') if t.strip()] if self.skill_tags else []

    def set_tags(self, tags_list):
        self.skill_tags = ', '.join(tags_list)

    def to_dict(self):
        return {
            'id': self.id,
            'company': self.company,
            'role': self.role,
            'dates': self.dates,
            'section_type': self.section_type,
            'sort_order': self.sort_order,
            'original_text': self.original_text,
            'xyz_version': self.xyz_version,
            'skill_tags': self.get_tags(),
            'impact_score': self.impact_score,
            'is_active': self.is_active,
            'tech_stack': self.tech_stack,
            'repo_url': self.repo_url,
        }
