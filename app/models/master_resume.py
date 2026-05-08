import json
from datetime import datetime, timezone
from app import db


class MasterResume(db.Model):
    """The user's master resume -- one big record with everything."""
    __tablename__ = 'master_resume'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
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
        """Plain text version for scoring and AI analysis."""
        lines = [self.full_name]

        # Contact info — all fields so format compliance scoring works
        contact_parts = []
        if self.location:
            contact_parts.append(self.location)
        if self.phone:
            contact_parts.append(self.phone)
        if self.email:
            contact_parts.append(self.email)
        if self.linkedin_url:
            contact_parts.append(self.linkedin_url)
        if self.github_url:
            contact_parts.append(self.github_url)
        if self.portfolio_url:
            contact_parts.append(self.portfolio_url)
        if contact_parts:
            lines.append(' | '.join(contact_parts))

        if self.tagline:
            lines.append(self.tagline)

        if self.summary:
            lines.append(f"\nPROFESSIONAL SUMMARY\n{self.summary}")

        if self.skills:
            lines.append("\nTECHNICAL SKILLS")
            for group in self.skills:
                lines.append(f"{group.get('category', '')}: {', '.join(group.get('items', []))}")

        # Separate bullets into experience vs projects
        if self.bullets:
            exp_bullets = [b for b in self.bullets if (b.section_type or 'experience') == 'experience']
            proj_bullets = [b for b in self.bullets if (b.section_type or '') == 'project']

            # Projects section (if any)
            if proj_bullets:
                lines.append("\nPROJECTS")
                current_key = None
                for b in sorted(proj_bullets, key=lambda x: x.sort_order or 0):
                    key = f"{b.company}"  # project name
                    if key != current_key:
                        current_key = key
                        tech = f" | {b.tech_stack}" if b.tech_stack else ""
                        lines.append(f"\n{b.company}{tech}")
                    lines.append(f"  • {b.original_text}")

            # Experience section
            if exp_bullets:
                lines.append("\nPROFESSIONAL EXPERIENCE")
                current_key = None
                for b in sorted(exp_bullets, key=lambda x: x.sort_order or 0):
                    key = f"{b.role} | {b.company}"
                    if key != current_key:
                        current_key = key
                        lines.append(f"\n{b.role} — {b.company} ({b.dates or ''})")
                    lines.append(f"  • {b.original_text}")

        if self.education:
            lines.append("\nEDUCATION")
            for edu in self.education:
                loc = f", {edu['location']}" if edu.get('location') else ""
                lines.append(f"{edu.get('degree', '')} — {edu.get('school', '')}{loc} ({edu.get('dates', '')})")
                if edu.get('details'):
                    lines.append(f"  {edu['details']}")

        if self.languages:
            lines.append("\nLANGUAGES")
            lines.append(', '.join(self.languages) if isinstance(self.languages, list) else str(self.languages))

        return "\n".join(lines)
