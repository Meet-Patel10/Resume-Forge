# ============================================================================
# TASK 4: TEST SUITE - SKILLS VALIDATION & NONSENSE SKILLS REMOVAL
#
# Adapted from TASK_4_COMPLETE_SOLUTION.md's test suite to the REAL API in
# this codebase (module-level validate_skill(skill) -> (is_valid, reason),
# already wired into app/routes/tailor.py:4187), not the guide's fictional
# SkillValidator class, which would have broken that real call site if
# introduced with its 3-tuple return signature.
# ============================================================================

import pytest
from app.validators.skill_validator import (
    SKILL_VALIDATION_RULES,
    REJECT_PATTERNS,
    VALID_SKILL_PATTERNS,
    NON_SKILLS,
    validate_skill,
    validate_skill_with_confidence,
    calculate_skill_confidence,
    aggressive_cleanup,
)


class TestSkillValidationRules:
    """Test Chunk 4.1: Validation rules and patterns."""

    def test_reject_patterns_defined(self):
        assert len(REJECT_PATTERNS) > 20, "Should have 27+ rejection patterns"

    def test_valid_patterns_defined(self):
        assert len(VALID_SKILL_PATTERNS) > 10, "Should have 14+ valid patterns"

    def test_non_skills_defined(self):
        assert len(NON_SKILLS) > 10, "Should have 13+ non-skill words"


class TestRejectPatterns:
    """Test that bad skills are rejected — the exact production examples."""

    def test_reject_end_interfaces(self):
        is_valid, reason = validate_skill("end interfaces")
        assert not is_valid

    def test_reject_stack_or_backend(self):
        is_valid, reason = validate_skill("stack or backend")
        assert not is_valid

    def test_reject_product_teams(self):
        is_valid, reason = validate_skill("product teams")
        assert not is_valid

    def test_reject_and_implement_cloud(self):
        is_valid, reason = validate_skill("and implement cloud")
        assert not is_valid

    def test_reject_with_cloud_platforms(self):
        is_valid, reason = validate_skill("with cloud platforms")
        assert not is_valid

    def test_reject_functional_teams(self):
        is_valid, reason = validate_skill("functional teams")
        assert not is_valid

    def test_reject_team_and_what_we(self):
        is_valid, reason = validate_skill("team and what we")
        assert not is_valid

    def test_reject_focusing_on(self):
        is_valid, reason = validate_skill("Experienced with backend, focusing on")
        assert not is_valid

    def test_reject_too_many_words(self):
        skill = "word one word two word three word four word five"
        is_valid, reason = validate_skill(skill)
        assert not is_valid

    def test_reject_only_non_skills(self):
        is_valid, reason = validate_skill("the and or but")
        assert not is_valid

    def test_reject_too_long(self):
        long_skill = "A" * 51
        is_valid, reason = validate_skill(long_skill)
        assert not is_valid

    def test_reject_empty(self):
        is_valid, reason = validate_skill("")
        assert not is_valid

    def test_reject_ellipsis(self):
        is_valid, reason = validate_skill("Python integration...")
        assert not is_valid


class TestAcceptPatterns:
    """Test that good skills are accepted."""

    @pytest.mark.parametrize("skill", [
        "Python", "Java", "Docker", "Kubernetes", "REST APIs",
        "Microservices", "AWS", "Spring Boot", "React", "PostgreSQL", "CI/CD",
    ])
    def test_accept_known_skills(self, skill):
        is_valid, reason = validate_skill(skill)
        assert is_valid, f"Should accept '{skill}': {reason}"


class TestConfidenceScoring:
    """Test Chunk 4.2/8.2: Confidence scoring."""

    def test_high_confidence_known_language(self):
        conf = calculate_skill_confidence("Python")
        assert conf >= 0.9, "Known language should have high confidence"

    def test_low_confidence_suspicious(self):
        conf = calculate_skill_confidence("the and cloud")
        assert conf < 0.5, "Suspicious pattern should be low confidence"

    def test_validate_with_confidence_returns_triple(self):
        is_valid, reason, confidence = validate_skill_with_confidence("Docker")
        assert is_valid
        assert 0.0 <= confidence <= 1.0

    def test_validate_skill_still_returns_pair(self):
        """validate_skill() must keep its real 2-tuple signature — it's
        unpacked as `is_valid_skill, reject_reason = validate_skill(skill)`
        at app/routes/tailor.py:4187."""
        result = validate_skill("Python")
        assert len(result) == 2


class TestAggressiveCleanup:
    """Test Chunk 4.4: post-processing cleanup over real resume_json shape."""

    def test_removes_invalid_skills(self):
        resume = {
            'skills': [
                {'category': 'Languages', 'items': ['Python', 'end interfaces', 'Java', 'stack or backend']},
                {'category': 'Tools', 'items': ['Docker', 'product teams', 'Kubernetes']},
            ]
        }

        cleaned = aggressive_cleanup(resume)

        all_skills = [item for cat in cleaned['skills'] for item in cat['items']]
        assert 'Python' in all_skills
        assert 'Java' in all_skills
        assert 'Docker' in all_skills
        assert 'Kubernetes' in all_skills
        assert 'end interfaces' not in all_skills
        assert 'stack or backend' not in all_skills
        assert 'product teams' not in all_skills

    def test_preserves_structure(self):
        resume = {
            'skills': [
                {'category': 'Languages', 'items': ['Python', 'Java']},
                {'category': 'Tools', 'items': ['Docker', 'Kubernetes']},
            ]
        }
        cleaned = aggressive_cleanup(resume)
        assert len(cleaned['skills']) == 2
        for cat in cleaned['skills']:
            assert 'category' in cat and 'items' in cat

    def test_drops_empty_categories(self):
        resume = {'skills': [{'category': 'Junk', 'items': ['end interfaces', 'product teams']}]}
        cleaned = aggressive_cleanup(resume)
        assert cleaned['skills'] == []

    def test_no_skills_key_is_noop(self):
        resume = {'summary': 'hello'}
        assert aggressive_cleanup(resume) == resume

    def test_mutates_and_returns_same_dict(self):
        resume = {'skills': [{'category': 'Languages', 'items': ['Python']}]}
        result = aggressive_cleanup(resume)
        assert result is resume


class TestProductionScenarios:
    """Real-world mixed scenarios."""

    def test_production_nonsense_skills_all_removed(self):
        nonsense_skills = [
            'end interfaces', 'product teams', 'stack or backend',
            'and implement cloud', 'functional teams', 'with cloud platforms',
            'team and what we',
        ]
        resume = {'skills': [{'category': 'Junk', 'items': nonsense_skills}]}
        cleaned = aggressive_cleanup(resume)
        assert cleaned['skills'] == []

    def test_production_mixed_skills(self):
        good = ['Python', 'Java', 'JavaScript', 'Docker', 'Kubernetes', 'AWS',
                'Spring Boot', 'React', 'PostgreSQL', 'REST APIs', 'Microservices', 'CI/CD', 'Linux', 'Git']
        bad = ['end interfaces', 'product teams', 'stack or backend',
               'and implement cloud', 'functional teams']

        resume = {'skills': [{'category': 'Mixed', 'items': good + bad}]}
        cleaned = aggressive_cleanup(resume)
        all_skills = cleaned['skills'][0]['items'] if cleaned['skills'] else []

        for skill in good:
            assert skill in all_skills, f"Good skill '{skill}' should be kept"
        for skill in bad:
            assert skill not in all_skills, f"Bad skill '{skill}' should be removed"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
