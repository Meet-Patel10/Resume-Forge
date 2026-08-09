# ============================================================================
# TASK 10: TEST SUITE - QUALITY VALIDATION GATE
#
# TASK_10_COMPLETE_SOLUTION.md proposes a brand-new app/validators/
# quality_validator.py: a from-scratch ResumeIntegrityValidator/
# KeywordQualityScorer/NaturalLanguageValidator/QualityValidationFramework
# hierarchy assuming a resume schema this app doesn't use (flat
# `skills: List[str]` and `experience[].description`, vs. this app's real
# `skills: [{category, items}]` and `experience[].bullets`).
#
# That file already existed in this codebase — with a real, working,
# already-unit-tested implementation (run_quality_gates + five validator
# functions: summary completeness, skill validity, evidence coverage,
# categorization, role consistency — see
# tests/test_tailoring_fixes.py::TestQualityGates). Comparing it against
# the guide's six problems turned up the real gaps:
#
#   - Problem 1 / 6 (no quality checks after tailoring, no submission
#     gate): run_quality_gates() was never called from app/routes/
#     tailor.py. A fully-built quality gate sat unused — resumes were
#     generated and sent without it ever running. Fixed by wiring it into
#     the real pipeline (tailor.py, "TASK 10" block, right before LaTeX
#     rendering) as a non-fatal check that logs + stores the report,
#     matching this file's existing safety-net pattern (TASK 4/5 blocks
#     just above it) rather than the guide's hard reject/rewrite gate,
#     which would change the API's behavior beyond what was asked.
#   - Problem 4 (missing keyword/language naturalness validation): this
#     was a genuine, real gap — nothing in quality_validator.py checked
#     resume prose for AI-cliché phrasing. Rather than the guide's new
#     KeywordQualityScorer/NaturalLanguageValidator classes, this reuses
#     the production-confirmed AI-phrasing pattern list from TASK 7's
#     validate_soft_skill_grammaticality (app/routes/tailor.py) —
#     generalized here to scan the WHOLE resume, not just soft-skill
#     bullets — as a new validate_keyword_naturalness() chunk (10.6),
#     wired into run_quality_gates()'s overall_score/overall_pass.
#   - Problems 2, 3, 5 were already covered by the pre-existing
#     validators (skill validity, evidence coverage, categorization,
#     role consistency) — confirmed by the passing tests below and the
#     pre-existing tests in test_tailoring_fixes.py::TestQualityGates.
# ============================================================================

import pytest
from app.validators.quality_validator import (
    validate_summary_quality,
    validate_all_skills,
    validate_skill_categorization,
    validate_keyword_naturalness,
    run_quality_gates,
)


class TestKeywordNaturalness:
    """Chunk 10.6: the genuinely new check."""

    def test_clean_resume_has_no_flagged_phrases(self):
        resume = {
            'summary': 'Backend engineer with 4 years building distributed systems.',
            'experience': [{'bullets': ['Built REST APIs with Python.', 'Reduced latency by 30%.']}],
            'projects': [{'bullets': ['Implemented a caching layer using Redis.']}],
        }
        result = validate_keyword_naturalness(resume)
        assert result['is_valid'] is True
        assert result['score'] == 100.0
        assert result['flagged_phrases'] == []

    def test_ai_sounding_summary_flagged(self):
        resume = {
            'summary': 'Innovatively developed cutting-edge microservices leveraging cutting-edge platforms.',
            'experience': [],
            'projects': [],
        }
        result = validate_keyword_naturalness(resume)
        assert result['is_valid'] is False
        assert result['score'] < 100.0
        assert any(loc == 'summary' for loc, _, _ in result['flagged_phrases'])

    def test_ai_sounding_bullet_flagged_with_location(self):
        resume = {
            'summary': 'Engineer.',
            'experience': [{'bullets': ['Seamlessly integrated payment systems.']}],
            'projects': [],
        }
        result = validate_keyword_naturalness(resume)
        assert result['is_valid'] is False
        assert any(loc == 'experience[0].bullets[0]' for loc, _, _ in result['flagged_phrases'])

    def test_score_never_goes_below_zero(self):
        resume = {
            'summary': (
                'Innovatively developed. Communicated automation. '
                'Collaboratively developed. Proactively managed. '
                'Dynamically optimized. Seamlessly integrated. '
                'Leveraging cutting-edge tools. Cutting-edge solutions.'
            ),
            'experience': [],
            'projects': [],
        }
        result = validate_keyword_naturalness(resume)
        assert 0.0 <= result['score'] <= 100.0


class TestQualityGateWiredIn:
    """run_quality_gates now includes naturalness in its score/pass gate."""

    def test_good_resume_passes_and_scores_high(self):
        resume = {
            'summary': (
                'Experienced backend engineer with four years of experience building '
                'scalable distributed systems in Python and Go for high traffic '
                'production environments.'
            ),
            'skills': [{'category': 'Languages', 'items': ['Python', 'Go', 'SQL']}],
            'experience': [{'bullets': [
                'Built REST APIs with Python and Go.',
                'Wrote complex SQL queries to reduce latency by 30%.',
            ]}],
            'projects': [],
        }
        report = run_quality_gates(resume, 'mid_level')

        assert report['overall_pass'] is True
        assert report['overall_score'] > 70
        assert 'naturalness' in report
        assert report['naturalness']['is_valid'] is True

    def test_ai_sounding_resume_fails_gate(self):
        resume = {
            'summary': (
                'Innovatively developed cutting-edge microservices leveraging '
                'cutting-edge platforms with 4 years of backend experience.'
            ),
            'skills': [{'category': 'Languages', 'items': ['Python', 'Go', 'SQL']}],
            'experience': [{'bullets': ['Seamlessly integrated payment systems using Python.']}],
            'projects': [],
        }
        report = run_quality_gates(resume, 'mid_level')

        assert report['naturalness']['is_valid'] is False
        assert report['overall_pass'] is False

    def test_report_shape_unchanged_for_existing_consumers(self):
        """Pre-existing keys (tests/test_tailoring_fixes.py::TestQualityGates)
        must still be present — this fix only adds 'naturalness', it must
        not remove or rename anything."""
        resume = {'summary': '', 'skills': [], 'experience': [], 'projects': []}
        report = run_quality_gates(resume)

        for key in ('overall_pass', 'summary', 'skills', 'evidence',
                    'categorization', 'role_consistency', 'overall_score'):
            assert key in report


class TestPreExistingValidatorsStillWork:
    """Sanity check the pre-existing chunks (10.1-10.5) weren't disturbed."""

    def test_summary_quality(self):
        result = validate_summary_quality(
            'Backend engineer with five years of experience building distributed '
            'systems, leading small teams, and shipping high-traffic production '
            'services at scale for enterprise customers.'
        )
        assert result['is_valid'] is True

    def test_skill_validity(self):
        result = validate_all_skills({'skills': [{'category': 'Languages', 'items': ['Python', 'end interfaces']}]})
        assert result['is_valid'] is False

    def test_categorization(self):
        result = validate_skill_categorization({'skills': [{'category': 'Languages', 'items': ['communication']}]})
        assert result['is_valid'] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
