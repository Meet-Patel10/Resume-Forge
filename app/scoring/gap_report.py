# FILE: app/scoring/gap_report.py

"""
Read-only JD gap reporting.

Replaces the convergence engine, which closed gaps by appending a hardcoded
placeholder string to the summary and then scored the text it had just
written. A gap you cannot honestly close is information for the user, not a
defect to paper over — so this module reports and never edits.

The no-mutation guarantee is enforced by tests/test_invariants.py.
"""

from app.scoring.gap_analyzer import WeightedGapAnalyzer


def build_gap_report(resume: dict, jd_tiers) -> dict:
    """Report which JD requirements the resume does not evidence. Never edits.

    Args:
        resume: tailored resume dict
        jd_tiers: JDTierAnalysis from JDTierExtractor

    Returns:
        dict with the missing requirements per tier and current coverage.
    """
    gap = WeightedGapAnalyzer().analyze_gap(resume, jd_tiers)

    if gap.skip_convergence:
        return {
            'status': 'unreliable',
            'reason': gap.skip_reason,
            'required_missing': [],
            'preferred_missing': [],
            'coverage': {'required': 0.0, 'preferred': 0.0},
            'note': 'JD extraction quality too low to report gaps. Manual review recommended.',
        }

    return {
        'status': 'ok',
        'required_missing': gap.required_missing,
        'preferred_missing': gap.preferred_missing,
        'coverage': {
            'required': gap.required_match_score,
            'preferred': gap.preferred_match_score,
        },
        'note': 'Gaps are reported, not filled. Address in a cover letter or accept.',
    }
