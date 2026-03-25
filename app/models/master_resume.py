import json
from datetime import datetime, timezone
from app import db


class MasterResume(db.Model):
    """Stores the user's master resume — one comprehensive record
    containing every experience, project, and skill they have."""
    __tablename__ = 'master_resume'

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200))
    phone = db.Column(db.String(50))
    location = db.Column(db.String(200))
    linkedin_url = db.Column(db.String(500))
    github_url = db.Column(db.String(500))
    portfolio_url = db.Column(db.String(500))
    tagline = db.Column(db.String(300))  # e.g. "PGWP-eligible | Available full-time"
    summary = db.Column(db.Text)

    # JSON fields stored as text
    _skills = db.Column('skills', db.Text, default='[]')
    _education = db.Column('education', db.Text, default='[]')
    _languages = db.Column('languages', db.Text, default='[]')

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    bullets = db.relationship('Bullet', backref='master_resume', lazy=True,
                              cascade='all, delete-orphan')

    @property
    def skills(self):
        return json.loads(self._skills) if self._skills else []

    @skills.setter
    def skills(self, value):
        self._skills = json.dumps(value)

    @property
    def education(self):
        return json.loads(self._education) if self._education else []

    @education.setter
    def education(self, value):
        self._education = json.dumps(value)

    @property
    def languages(self):
        return json.loads(self._languages) if self._languages else []

    @languages.setter
    def languages(self, value):
        self._languages = json.dumps(value)

    def to_dict(self):
        return {
            'id': self.id,
            'full_name': self.full_name,
            'email': self.email,
            'phone': self.phone,
            'location': self.location,
            'linkedin_url': self.linkedin_url,
            'github_url': self.github_url,
            'portfolio_url': self.portfolio_url,
            'tagline': self.tagline,
            'summary': self.summary,
            'skills': self.skills,
            'education': self.education,
            'languages': self.languages,
            'bullets': [b.to_dict() for b in self.bullets],
        }

    def to_resume_text(self):
        """Convert to plain text for Claude analysis."""
        lines = [self.full_name]
        if self.location:
            lines.append(self.location)
        if self.email:
            lines.append(self.email)
        if self.summary:
            lines.append(f"\nSUMMARY\n{self.summary}")

        if self.skills:
            lines.append("\nSKILLS")
            for group in self.skills:
                lines.append(f"{group.get('category', '')}: {', '.join(group.get('items', []))}")

        # Group bullets by company/role
        if self.bullets:
            lines.append("\nEXPERIENCE")
            current_key = None
            for b in sorted(self.bullets, key=lambda x: x.sort_order or 0):
                key = f"{b.role} | {b.company}"
                if key != current_key:
                    current_key = key
                    lines.append(f"\n{b.role} — {b.company} ({b.dates or ''})")
                lines.append(f"  • {b.original_text}")

        if self.education:
            lines.append("\nEDUCATION")
            for edu in self.education:
                lines.append(f"{edu.get('degree', '')} — {edu.get('school', '')} ({edu.get('dates', '')})")
                if edu.get('details'):
                    lines.append(f"  {edu['details']}")

        return "\n".join(lines)
