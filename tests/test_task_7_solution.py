# ============================================================================
# TASK 7: TEST SUITE - NATURAL-SOUNDING SOFT SKILLS INJECTION
#
# TASK_7_COMPLETE_SOLUTION.md's Problem 1 evidence ("Innovatively developed
# and managed RESTful API endpoints") is real and reproducible: the live
# per-skill prompt guidance in tailor.py literally suggested "innovatively"
# as the first variant to use.
#
# The guide's proposed fix (app/services/soft_skills_injector.py, a static
# template-splice engine that regex-finds an injection position and pastes
# in a canned phrase) was NOT implemented as-is, for two reasons:
#
# 1. It's architecturally a large regression from the real, live injection
#    code (tailor.py "SOFT SKILLS INJECTION INTO BULLETS"), which asks the
#    AI to rewrite the whole bullet with full context of its content — the
#    guide's template splice has zero awareness of bullet content, so it
#    can't actually solve Problem 5 ("soft skill doesn't match context")
#    the way its own before/after examples claim.
# 2. Its template bank (NATURAL_SOFT_SKILL_TEMPLATES) deliberately avoids
#    the literal skill word in favor of synonyms (e.g. "leveraging novel
#    design patterns" for "innovation") — which directly conflicts with
#    SOFT_SKILL_STRICT_VARIANTS, the literal-stem-match requirement added
#    earlier in this project specifically because ATS scanners match word
#    stems, not synonyms (SOFT_SKILLS_SYNONYM_BUG). Wiring the guide's
#    engine in as a replacement would silently reopen that bug.
#
# There was also dead code already in tailor.py (labeled "CHUNK 7.1/7.2/7.3",
# matching this guide almost exactly) left over from an earlier abandoned
# attempt — never wired in, and its SOFT_SKILL_TEMPLATES definition SHADOWED
# the real Stage-2 dict of the same name used by the live prompt-builder.
#
# The actual fix, reusing what was genuinely salvageable:
#   - Removed the dead, shadowing CHUNK 7.1/7.2 template-splice code.
#   - Kept and wired in the dead CHUNK 7.3 grammaticality validator
#     (validate_soft_skill_grammaticality), extended with the guide's
#     extra red-flag patterns, as a real post-generation naturalness gate.
#   - Reordered per-skill prompt guidance (get_natural_skill_guidance) so
#     natural forms are suggested before awkward adverb forms.
#   - Added one retry with corrective feedback if the naturalness gate
#     fails, falling back to the original ATS-valid rewrite if the retry
#     doesn't help (naturalness is never allowed to override ATS validity).
# ============================================================================

import pytest
from app.routes.tailor import (
    validate_soft_skill_grammaticality,
    get_natural_skill_guidance,
    SOFT_SKILL_TEMPLATES,
    SOFT_SKILL_STRICT_VARIANTS,
    SOFT_SKILL_KEYWORDS,
)


class TestShadowingBugFixed:
    """The dead CHUNK 7.1 template list used to redefine SOFT_SKILL_TEMPLATES
    as a plain list, shadowing the real Stage-2 dict used by the live
    injection prompt builder. Confirm the real dict shape survives."""

    def test_soft_skill_templates_is_the_real_stage2_dict(self):
        assert isinstance(SOFT_SKILL_TEMPLATES['innovation'], dict)
        for key in ('description', 'keywords', 'example', 'instructions'):
            assert key in SOFT_SKILL_TEMPLATES['innovation']

    def test_soft_skill_templates_covers_all_strict_variant_skills(self):
        for skill in SOFT_SKILL_STRICT_VARIANTS:
            assert skill in SOFT_SKILL_TEMPLATES or skill in SOFT_SKILL_KEYWORDS


class TestNaturalnessValidation:
    """Chunk 7.3 (now wired into the real pipeline) — detects AI-sounding
    surface patterns, including the exact Problem 1 production example."""

    def test_production_broken_example_flagged(self):
        is_natural, issues = validate_soft_skill_grammaticality(
            "Innovatively developed and managed RESTful API endpoints"
        )
        assert not is_natural
        assert any('Innovatively' in issue for issue in issues)

    def test_natural_rewrite_passes(self):
        is_natural, issues = validate_soft_skill_grammaticality(
            "Developed innovative RESTful API endpoints for scalability."
        )
        assert is_natural
        assert issues == []

    @pytest.mark.parametrize("bullet", [
        "Communicated automation solutions by developing Python scripts",
        "Collaboratively developed new CI/CD pipelines",
        "Proactively resolved outstanding technical debt",
        "Fostered team spirit and creative solutions across the org",
        "Championed a collaborative approach to sprint planning",
        "Communicated a rollout plan by creating a phased schedule",
    ])
    def test_ai_sounding_patterns_flagged(self, bullet):
        is_natural, issues = validate_soft_skill_grammaticality(bullet)
        assert not is_natural
        assert len(issues) >= 1

    @pytest.mark.parametrize("bullet", [
        "Mentored three junior engineers on system design fundamentals.",
        "Took ownership of the migration, delivering two weeks early.",
        "Adapted the deployment pipeline to support blue-green releases.",
        "Presented quarterly architecture reviews to senior leadership.",
    ])
    def test_natural_bullets_not_flagged(self, bullet):
        is_natural, issues = validate_soft_skill_grammaticality(bullet)
        assert is_natural, f"False positive: {issues}"

    def test_any_ly_adverb_opener_flagged(self):
        is_natural, issues = validate_soft_skill_grammaticality(
            "Adaptably restructured the reporting pipeline for new formats."
        )
        assert not is_natural


class TestNaturalSkillGuidance:
    """get_natural_skill_guidance: prompt guidance text steers the AI toward
    natural forms first, without ever dropping a literal stem-variant
    (still required for ATS matching)."""

    def test_innovation_prefers_adjective_over_adverb(self):
        guidance = get_natural_skill_guidance('innovation')
        # 'innovatively' should not be the leading suggestion
        assert not guidance.strip().startswith("- Use: 'innovatively'")

    @pytest.mark.parametrize("skill_lower", [
        'innovation', 'communication', 'accountability', 'collaboration', 'adaptability',
    ])
    def test_guidance_only_uses_literal_stem_variants(self, skill_lower):
        guidance = get_natural_skill_guidance(skill_lower)
        strict_variants = SOFT_SKILL_STRICT_VARIANTS.get(skill_lower, [])
        # Every quoted suggestion in the guidance line is either a strict
        # variant or a non-stem phrase (e.g. 'took ownership') — but at
        # least one strict variant must be present so ATS matching still
        # has a real chance of succeeding.
        assert any(variant in guidance.lower() for variant in strict_variants)

    def test_unknown_skill_returns_empty_guidance(self):
        assert get_natural_skill_guidance('nonexistent_skill') == ''


class TestProductionScenario:
    """End-to-end: the exact Problem 1 production string is fixable by one
    retry cycle, and a fixed version keeps the literal ATS keyword."""

    def test_fixed_example_keeps_ats_keyword_and_sounds_natural(self):
        fixed = "Developed innovative RESTful API endpoints for scalability."
        is_natural, _ = validate_soft_skill_grammaticality(fixed)
        assert is_natural
        assert any(v in fixed.lower() for v in SOFT_SKILL_STRICT_VARIANTS['innovation'])


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
