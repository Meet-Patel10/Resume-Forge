# FILE: app/scoring/gap_analyzer.py

from dataclasses import dataclass, field
from typing import List, Optional

from app.services.jd_tier_extractor import JDTierAnalysis
from app.validators.cover_letter_validator import flatten_resume_to_text


@dataclass
class GapAnalysis:
    # Required tier (70% weight)
    required_matched: List[str] = field(default_factory=list)      # Candidate has this
    required_missing: List[str] = field(default_factory=list)      # Candidate lacks this
    required_match_score: float = 0.0                              # 0-100%, weight: 70%

    # Preferred tier (20% weight)
    preferred_matched: List[str] = field(default_factory=list)
    preferred_missing: List[str] = field(default_factory=list)
    preferred_match_score: float = 0.0                             # 0-100%, weight: 20%

    # Nice-to-have tier (10% weight)
    nice_matched: List[str] = field(default_factory=list)
    nice_missing: List[str] = field(default_factory=list)
    nice_match_score: float = 0.0                                  # 0-100%, weight: 10%

    # Weighted composite score
    weighted_ats_estimate: float = 0.0                             # 0.7*required + 0.2*preferred + 0.1*nice

    # Impact prioritization
    top_impact_gaps: List[str] = field(default_factory=list)       # Gaps that move score most if closed
    closure_strategy: str = ''                                     # Which gap to close first for max return

    # NEW: Convergence control fields
    skip_convergence: bool = False
    skip_reason: Optional[str] = None


def extract_resume_skills(resume: dict) -> set:
    """Pull the flat set of skills the resume already lists in its skills section."""
    skills = set()
    if not isinstance(resume, dict):
        return skills
    for group in resume.get('skills', []) or []:
        for item in group.get('items', []) or []:
            skills.add(item)
    return skills


def match_percentage(resume_text: str, jd_skills: List[str]) -> float:
    """Percentage of jd_skills that appear anywhere in resume_text."""
    if not jd_skills:
        return 100.0
    resume_lower = resume_text.lower()
    matched = sum(1 for skill in jd_skills if skill.lower() in resume_lower)
    return round((matched / len(jd_skills)) * 100, 1)


class WeightedGapAnalyzer:
    def analyze_gap(self, resume: dict, jd_tiers: JDTierAnalysis) -> GapAnalysis:
        """
        Compare resume against tiered requirements.
        CRITICAL: Validate that JD extraction succeeded before proceeding.
        """

        # Validation: Check if JD extraction was high-quality
        if jd_tiers.quality_score < 0.5:
            print(f"[gap-analyzer] ⚠ WARNING: JD extraction quality is low ({jd_tiers.quality_score*100:.0f}%)")
            print(f"  Required skills found: {len(jd_tiers.required_hard_skills)}")
            print(f"  Preferred skills found: {len(jd_tiers.preferred_hard_skills)}")
            print(f"  → Convergence loop will skip (cannot trust this JD analysis)")

            # Return early with flag
            return GapAnalysis(
                required_match_score=0.0,
                preferred_match_score=0.0,
                nice_match_score=0.0,
                weighted_ats_estimate=0.0,
                skip_convergence=True,  # NEW FIELD
                skip_reason="JD extraction quality too low",
            )

        # Normal flow (unchanged)
        # Extract resume skills
        resume_skills = extract_resume_skills(resume)
        resume_text = flatten_resume_to_text(resume) if isinstance(resume, dict) else ''

        # Tier-by-tier matching — don't return 100% for empty list
        required_match_pct = match_percentage(
            resume_text,
            jd_tiers.required_hard_skills
        ) if jd_tiers.required_hard_skills else 0.0
        preferred_match_pct = match_percentage(
            resume_text,
            jd_tiers.preferred_hard_skills
        ) if jd_tiers.preferred_hard_skills else 0.0
        nice_match_pct = match_percentage(
            resume_text,
            jd_tiers.nice_to_have_skills
        ) if jd_tiers.nice_to_have_skills else 0.0

        required_matched = [s for s in jd_tiers.required_hard_skills if s.lower() in resume_text.lower()]
        required_missing = [s for s in jd_tiers.required_hard_skills if s.lower() not in resume_text.lower()]
        preferred_matched = [s for s in jd_tiers.preferred_hard_skills if s.lower() in resume_text.lower()]
        preferred_missing = [s for s in jd_tiers.preferred_hard_skills if s.lower() not in resume_text.lower()]
        nice_matched = [s for s in jd_tiers.nice_to_have_skills if s.lower() in resume_text.lower()]
        nice_missing = [s for s in jd_tiers.nice_to_have_skills if s.lower() not in resume_text.lower()]

        # Weighted composite
        weighted_score = (
            required_match_pct * 0.70 +
            preferred_match_pct * 0.20 +
            nice_match_pct * 0.10
        )

        # Required tier gaps carry the most weight (70%), so they're closed first.
        top_impact_gaps = (required_missing + preferred_missing + nice_missing)[:10]
        closure_strategy = (
            "Close required-tier gaps first (70% weight), "
            "then preferred (20%), then nice-to-have (10%)."
        )

        print(f"[gap-analyzer] Gap scores: required={required_match_pct:.0f}%, "
              f"preferred={preferred_match_pct:.0f}%, nice={nice_match_pct:.0f}%")

        return GapAnalysis(
            required_matched=required_matched,
            required_missing=required_missing,
            required_match_score=required_match_pct,
            preferred_matched=preferred_matched,
            preferred_missing=preferred_missing,
            preferred_match_score=preferred_match_pct,
            nice_matched=nice_matched,
            nice_missing=nice_missing,
            nice_match_score=nice_match_pct,
            weighted_ats_estimate=weighted_score,
            top_impact_gaps=top_impact_gaps,
            closure_strategy=closure_strategy,
            skip_convergence=False,
            skip_reason=None,
        )
