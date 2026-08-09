# ============================================================================
# TASK 3: TEST SUITE - ROLE LEVEL DETECTION
#
# Adapted from TASK_3_COMPLETE_SOLUTION.md's test suite to the REAL API in
# this codebase (dict/string-keyed ROLE_LEVEL_MAPPING/ROLE_SKILL_MATRIX and
# detect_role_level(resume_json, jd_text)), not the guide's fictional
# RoleLevel Enum / RoleDetector class, which don't exist here and would
# break the three real call sites in app/routes/tailor.py if introduced.
# ============================================================================

import pytest
from app.validators.role_validator import (
    ROLE_LEVEL_MAPPING,
    ROLE_SKILL_MATRIX,
    detect_role_level_by_years,
    detect_role_level,
    validate_role_level_consistency,
    validate_role_skill_coherence,
    calculate_years_experience,
)


class TestRoleLevelMapping:
    """Test Chunk 3.1: Experience-to-level mapping (via detect_role_level_by_years)."""

    def test_junior_range(self):
        assert detect_role_level_by_years(0) == 'junior'
        assert detect_role_level_by_years(1) == 'junior'
        assert detect_role_level_by_years(1.5) == 'junior'

    def test_mid_level_range(self):
        assert detect_role_level_by_years(2) == 'mid_level'
        assert detect_role_level_by_years(2.5) == 'mid_level'  # CRITICAL: the production bug
        assert detect_role_level_by_years(3) == 'mid_level'
        assert detect_role_level_by_years(4.9) == 'mid_level'

    def test_senior_range(self):
        assert detect_role_level_by_years(5) == 'senior'
        assert detect_role_level_by_years(7.5) == 'senior'
        assert detect_role_level_by_years(9.9) == 'senior'

    def test_principal_range(self):
        assert detect_role_level_by_years(10) == 'principal'
        assert detect_role_level_by_years(15) == 'principal'

    def test_boundary_2_years(self):
        """2 years must be mid_level, not junior — the original production bug."""
        assert detect_role_level_by_years(2.0) == 'mid_level'

    def test_boundary_5_years(self):
        assert detect_role_level_by_years(5.0) == 'senior'

    def test_boundary_10_years(self):
        assert detect_role_level_by_years(10.0) == 'principal'


class TestRoleSkillMatrix:
    """Test Chunk 3.3: Skill caps per role."""

    def test_skill_cap_junior(self):
        assert ROLE_SKILL_MATRIX['junior']['max_total_skills'] == 12

    def test_skill_cap_mid_level(self):
        """Mid-level cap must be 25, not the old incorrect 16/20."""
        assert ROLE_SKILL_MATRIX['mid_level']['max_total_skills'] == 25

    def test_skill_cap_senior(self):
        assert ROLE_SKILL_MATRIX['senior']['max_total_skills'] == 30

    def test_skill_cap_principal(self):
        assert ROLE_SKILL_MATRIX['principal']['max_total_skills'] == 40


class TestCalculateYearsExperience:
    """Test the real date-math fix (was: 1 year per job, regardless of duration)."""

    def test_single_job_two_years(self):
        resume = {'experience': [{'dates': 'Feb 2022 – Mar 2024'}]}
        years = calculate_years_experience(resume)
        assert 2.0 <= years <= 2.2, f"Expected ~2.1 years, got {years}"

    def test_two_jobs_summed(self):
        resume = {'experience': [
            {'dates': 'Feb 2022 – Mar 2024'},   # ~2.1 years
            {'dates': 'Jan 2021 – Nov 2021'},   # ~0.83 years
        ]}
        years = calculate_years_experience(resume)
        assert 2.7 <= years <= 3.1, f"Expected ~2.9 years, got {years}"

    def test_long_single_job_not_undercounted(self):
        """A single 8-year job must count as 8 years, not 1 (the old bug)."""
        resume = {'experience': [{'dates': 'Jan 2016 – Jan 2024'}]}
        years = calculate_years_experience(resume)
        assert years >= 7.9, f"Expected ~8 years, got {years}"

    def test_unparseable_dates_skipped(self):
        resume = {'experience': [{'dates': ''}, {'dates': 'garbage'}]}
        assert calculate_years_experience(resume) == 0

    def test_no_experience(self):
        assert calculate_years_experience({'experience': []}) == 0
        assert calculate_years_experience({}) == 0

    def test_present_handled(self):
        """'– Present' should use today's date, not a stale hardcoded year."""
        resume = {'experience': [{'dates': 'Jan 2020 – Present'}]}
        years = calculate_years_experience(resume)
        assert years >= 5, f"Job started Jan 2020 should be several years by now, got {years}"


class TestValidateRoleLevelConsistency:
    """Test Chunk 3.4: Validation gate."""

    def test_valid_2_years_mid_level(self):
        is_valid, msg = validate_role_level_consistency(2, 'mid_level')
        assert is_valid, msg

    def test_invalid_2_years_senior(self):
        """The production bug scenario: 2 years labeled senior must fail validation."""
        is_valid, msg = validate_role_level_consistency(2, 'senior')
        assert not is_valid
        assert 'senior' in msg.lower()

    def test_invalid_2_5_years_senior(self):
        is_valid, msg = validate_role_level_consistency(2.5, 'senior')
        assert not is_valid

    def test_valid_5_years_senior(self):
        is_valid, msg = validate_role_level_consistency(5, 'senior')
        assert is_valid, msg

    def test_valid_10_years_principal(self):
        is_valid, msg = validate_role_level_consistency(10, 'principal')
        assert is_valid, msg


class TestValidateRoleSkillCoherence:
    """Test skill-count coherence per role level."""

    def test_coherent_2_years_25_skills(self):
        resume = {'skills': [{'category': 'Languages', 'items': [f'Skill{i}' for i in range(25)]}]}
        result = validate_role_skill_coherence(resume, 'mid_level')
        assert result['status'] == 'PASS', result['issues']

    def test_incoherent_2_years_41_skills(self):
        """The exact production bug scenario: 41 skills for mid_level (cap 25)."""
        resume = {'skills': [{'category': 'Languages', 'items': [f'Skill{i}' for i in range(41)]}]}
        result = validate_role_skill_coherence(resume, 'mid_level')
        assert result['status'] == 'FAIL'
        assert len(result['issues']) > 0
        # Should recommend removing exactly 16 (41 - 25), not 21 (41 - 20)
        msg = result['issues'][0]['message']
        assert '41' in msg and '25' in msg


class TestAutoCorrection:
    """Test that validation failure now actually corrects the level
    (TASK 3 Problem 4: 'Validation Catches But Doesn't Fix')."""

    def test_wrong_level_gets_corrected_to_years_based_mapping(self):
        # Simulate what the tailor.py call site now does: detect, validate,
        # and if invalid, fall back to the pure years-based mapping.
        years_exp = 2.0
        detected = 'senior'  # deliberately wrong, as if from a bad JD-keyword override
        is_valid, _ = validate_role_level_consistency(years_exp, detected)
        assert not is_valid
        corrected = detect_role_level_by_years(years_exp)
        assert corrected == 'mid_level'


class TestDetectRoleLevelIntegration:
    """Test the real detect_role_level(resume_json, jd_text) end-to-end."""

    def test_no_seniority_keywords_uses_years(self):
        resume = {'experience': [{'dates': 'Feb 2022 – Mar 2024'}]}  # ~2.1 years
        level = detect_role_level(resume, 'We are hiring a backend developer.')
        assert level == 'mid_level'

    def test_empty_experience_returns_entry_level(self):
        assert detect_role_level({'experience': []}, 'some jd') == 'entry_level'
