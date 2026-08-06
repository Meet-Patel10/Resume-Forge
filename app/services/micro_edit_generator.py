# FILE: app/services/micro_edit_generator.py

from dataclasses import dataclass

from app.services.claude_client import claude
from app.scoring.gap_analyzer import GapAnalysis


@dataclass
class MicroEdit:
    gap_skill: str = ''                # "Kubernetes"
    gap_type: str = 'missing'          # "missing" or "weak_evidence"
    gap_weight: float = 0.0            # How much score improves if closed

    # Where to inject
    target_section: str = ''           # "summary", "skills", "bullet_3", etc.
    position_weight: float = 0.0       # Front-loading matters: summary > bullets

    # What to inject
    edit_type: str = ''                # "inject", "rewrite", "add_bullet"
    suggested_edit: str = ''           # Actual text change
    context: str = ''                  # Why this edit matters

    # Confidence
    feasibility: float = 0.0           # Can we authentically add this? (0-1)
    ats_gain: float = 0.0              # Estimated ATS score gain


def can_inject_into_summary(resume: dict, skill: str) -> bool:
    """Can this skill be authentically woven into the summary?"""
    summary = resume.get('summary', '') if isinstance(resume, dict) else ''
    return bool(summary) and skill.lower() not in summary.lower()


def can_add_to_skills_section(resume: dict, skill: str) -> bool:
    """Does the resume have a skills section this skill can be appended to?"""
    skills = resume.get('skills', []) if isinstance(resume, dict) else []
    if not skills:
        return False
    existing = {item.lower() for group in skills for item in group.get('items', []) or []}
    return skill.lower() not in existing


def can_rewrite_bullet(resume: dict, skill: str) -> bool:
    """Is there an experience bullet available to rewrite with this skill?"""
    experience = resume.get('experience', []) if isinstance(resume, dict) else []
    return bool(experience) and bool(experience[0].get('bullets'))


def find_best_bullet_for_skill(resume: dict, skill: str) -> int:
    """Pick the bullet index in the first experience entry to rewrite for this skill."""
    return 0


def apply_edit(resume: dict, edit: MicroEdit) -> dict:
    """Apply a MicroEdit to the resume dict, mutating and returning it."""
    if not isinstance(resume, dict):
        return resume

    if edit.target_section == 'summary' and edit.edit_type == 'inject':
        resume['summary'] = f"{resume.get('summary', '')} {edit.suggested_edit}".strip()

    elif edit.target_section == 'skills':
        skills = resume.get('skills', [])
        if skills:
            skills[0].setdefault('items', []).append(edit.suggested_edit)
        else:
            resume['skills'] = [{'category': 'Additional Skills', 'items': [edit.suggested_edit]}]

    elif edit.target_section.startswith('bullet_') and edit.edit_type == 'rewrite':
        bullet_idx = int(edit.target_section.split('_')[1])
        experience = resume.get('experience', [])
        if experience and 0 <= bullet_idx < len(experience[0].get('bullets', [])):
            experience[0]['bullets'][bullet_idx] = edit.suggested_edit

    return resume


class MicroEditGenerator:
    def generate_edits(self, resume: dict, gap: GapAnalysis) -> list:
        """
        For each top-5 missing skills, generate targeted edits.
        """

        edits = []

        for skill in gap.required_missing[:5]:  # Top 5 gaps by weight
            # Choose best strategy
            if can_inject_into_summary(resume, skill):
                edit = MicroEdit(
                    gap_skill=skill,
                    target_section="summary",
                    edit_type="inject",
                    suggested_edit=f"Experienced with {skill}, focusing on...",
                    feasibility=0.9,
                    ats_gain=8.5,
                )
            elif can_add_to_skills_section(resume, skill):
                # If resume has skills section, just add it
                edit = MicroEdit(
                    gap_skill=skill,
                    target_section="skills",
                    edit_type="inject",
                    suggested_edit=skill,
                    feasibility=0.95,
                    ats_gain=5.2,
                )
            elif can_rewrite_bullet(resume, skill):
                # Rewrite existing bullet to mention skill
                bullet_idx = find_best_bullet_for_skill(resume, skill)
                original = resume['experience'][0]['bullets'][bullet_idx]

                # Use Claude to rewrite briefly
                rewrite_result = claude.analyze(
                    "Rewrite this bullet to include mention of " + skill,
                    original,
                    max_tokens=100
                )
                rewritten = rewrite_result.get('response') or original

                edit = MicroEdit(
                    gap_skill=skill,
                    target_section=f"bullet_{bullet_idx}",
                    edit_type="rewrite",
                    suggested_edit=rewritten,
                    feasibility=0.7,
                    ats_gain=6.1,
                )
            else:
                continue

            edits.append(edit)

        return edits
