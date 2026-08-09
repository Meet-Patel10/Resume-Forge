# ============================================================================
# TASK 11: EXPANDED TEST SUITE & CROSS-TASK INTEGRATION TESTS
#
# TASK_11_COMPLETE_SOLUTION.md's proposed test_task_11_solution.py is ~30
# tests spread across 200+ described cases, but every single one asserts
# a tautology against a hardcoded local variable (e.g. `years = 2.0;
# assert years >= 2.0 and years <= 5.0`) — none of them import or call a
# single real function from this codebase. Copying it as-is would inflate
# the test count without testing anything: a real bug in detect_role_
# level, guarantee_injection_v2, or run_quality_gates would sail through
# every one of those tests unnoticed.
#
# This app already has real, function-calling coverage for each
# individual task (tests/test_task_{2..10}_solution.py), so "Problem 1"
# (insufficient coverage) is largely already addressed per-task. What was
# genuinely missing (confirmed by grepping tests/ before writing this
# file — no timing/benchmark tests existed anywhere, and every existing
# "Integration" test class exercises ONE task's internals, never two
# different tasks' real functions chained together) is:
#   - Problem 2: cross-task integration tests
#   - Problem 4: performance benchmarks on real (non-network) components
# This file adds those two, plus a compact real regression smoke-suite
# (Problem 3) and edge-case / messy-input tests (Problems 5 & 6) against
# real functions and this app's real resume schema.
#
# Writing test_task8_extraction_feeds_task9_guarantee below (chaining the
# REAL SemanticKeywordExtractor.extract() into the REAL guarantee engine,
# something no existing test did) surfaced an actual production bug:
# extract()'s candidate-generation regex required 2+ consecutive words,
# so single-word JD skills ("Python", "AWS", "Kubernetes"...) could NEVER
# become a candidate keyword, no matter how explicitly the JD asked for
# them — confirmed with a real JD returning zero must_haves before the
# fix. That's fixed in app/extractors/semantic_keyword_extractor.py (see
# tests/test_task_8_solution.py::TestSingleWordCandidateGeneration for
# the dedicated regression tests) and is exactly the kind of failure
# Problem 2 describes: "Task 8 → Task 9 guarantee... together they might
# fail" even though each passed its own isolated test suite.
# ============================================================================

import time
import pytest

from app.extractors.semantic_keyword_extractor import SemanticKeywordExtractor
from app.services.guarantee_engine.must_have_guarantee_engine import MustHaveGuaranteeEngine
from app.services.guarantee_engine.deduplication_engine import DeduplicationEngine
from app.validators.quality_validator import run_quality_gates, validate_summary_quality
from app.validators.skill_validator import validate_skill
from app.validators.role_validator import (
    detect_role_level, calculate_years_experience, validate_role_skill_coherence,
    ROLE_SKILL_MATRIX,
)


def _build_registry(keywords, tier='must_have', confidence=0.9):
    return {
        kw.lower(): {
            'original_text': kw, 'tier': tier, 'keyword_type': 'tool_platform',
            'confidence': confidence, 'sections_target': ['skills'],
        }
        for kw in keywords
    }


# ============================================================================
# SECTION 1: CROSS-TASK INTEGRATION (Problem 2 — the real gap)
# ============================================================================

class TestCrossTaskIntegration:
    """Chains real functions from DIFFERENT tasks together, the way
    production actually calls them — not one task's internals in
    isolation."""

    def test_task8_extraction_feeds_task9_guarantee(self, sample_jd):
        """Task 8's extractor finds must-haves already evidenced in the
        resume; Task 9's guarantee engine must report them as covered
        (this is the exact chain that used to silently produce zero
        must_haves — see module docstring)."""
        resume_text = "Built backend services using Python and Docker."
        resume_json = {
            'summary': 'Backend engineer.',
            'skills': [{'category': 'Languages', 'items': ['Python']}],
            'experience': [{'bullets': [resume_text]}],
            'projects': [],
        }

        extractor = SemanticKeywordExtractor()
        result = extractor.extract(sample_jd, resume_text)
        assert result.must_haves, "Extractor should find at least one must-have from the sample JD"

        registry = {
            kw.text.lower(): {
                'original_text': kw.text,
                'tier': kw.tier.value,
                'keyword_type': kw.keyword_type.value,
                'confidence': max(kw.overall_confidence, 0.9),
                'sections_target': kw.target_sections,
            }
            for kw in result.must_haves
        }

        engine = MustHaveGuaranteeEngine()
        guarantee_result = engine.guarantee_injection_v2(resume_json, registry, confidence_threshold=0.75)

        assert guarantee_result['metadata']['all_protected_found'] is True

    def test_task9_guarantee_output_survives_task10_quality_gate(self, sample_resume):
        """A resume just processed by the Task 9 guarantee engine must
        still be a valid input to the Task 10 quality gate — no crash,
        no schema mismatch."""
        registry = _build_registry(['Kubernetes', 'AWS'])
        engine = MustHaveGuaranteeEngine()
        guaranteed = engine.guarantee_injection_v2(sample_resume, registry, confidence_threshold=0.75)['resume_json']

        report = run_quality_gates(guaranteed, 'senior')

        assert 'overall_score' in report
        assert 0.0 <= report['overall_score'] <= 100.0

    def test_task3_role_detection_feeds_own_skill_cap_lookup(self, sample_resume):
        """Task 3's role detection result must be a valid key into Task
        3's own ROLE_SKILL_MATRIX/skill-coherence check."""
        role_level = detect_role_level(sample_resume, "Senior backend role.")
        assert role_level in ROLE_SKILL_MATRIX

        coherence = validate_role_skill_coherence(sample_resume, role_level)
        assert coherence['status'] in ('PASS', 'FAIL')

    def test_guarantee_engine_unaware_of_role_skill_cap(self):
        """
        REAL FINDING, documented rather than silently hidden:
        guarantee_injection_v2 (Task 9) has no knowledge of
        ROLE_SKILL_MATRIX (Task 3). An entry-level resume with headroom
        under its 12-skill cap can be pushed OVER that cap by guaranteeing
        enough must-have keywords, since the guarantee engine only checks
        per-category density (8 items/category), never the role-level
        total cap.

        This does not necessarily reach production wrong — a separate,
        not-yet-unit-tested block further down app/routes/tailor.py
        re-trims skills against ROLE_SKILL_MATRIX after the guarantee
        engine runs, using a DIFFERENT keyword source (jd_analysis, not
        protected_keywords_registry) — but guarantee_injection_v2 itself
        provides no such protection, so this test pins down that fact as
        a known follow-up instead of leaving it undiscovered.
        """
        resume = {
            'summary': 'Entry level developer.',
            'skills': [{'category': 'Languages', 'items': ['Python', 'Java', 'C++']}],
            'experience': [{'bullets': ['Built small apps.']}],
            'projects': [],
        }
        must_haves = ['Docker', 'Kubernetes', 'Terraform', 'Jenkins', 'Grafana',
                      'Ansible', 'Vagrant', 'Prometheus', 'Datadog', 'Splunk',
                      'Airflow', 'Kafka']
        registry = _build_registry(must_haves)

        engine = MustHaveGuaranteeEngine()
        result = engine.guarantee_injection_v2(resume, registry, confidence_threshold=0.75)

        total_skills = sum(len(g['items']) for g in result['resume_json']['skills'])
        entry_level_cap = ROLE_SKILL_MATRIX['entry_level']['max_total_skills']

        assert result['metadata']['all_protected_found'] is True
        assert total_skills > entry_level_cap, (
            "This assertion documents the CURRENT gap: guarantee_injection_v2 "
            "exceeded the entry_level cap while still reporting "
            "all_protected_found=True. If this starts failing, the gap has "
            "been fixed — update/remove this test."
        )


# ============================================================================
# SECTION 2: PERFORMANCE BENCHMARKS (Problem 4 — zero existed before)
# ============================================================================

class TestPerformanceBenchmarks:
    """Real timing on real (non-network) components. These three
    specifically don't call any AI/network API, so a real wall-clock SLA
    is meaningful and won't flake on network latency."""

    def test_keyword_extraction_speed(self, sample_jd):
        extractor = SemanticKeywordExtractor()
        start = time.perf_counter()
        extractor.extract(sample_jd, "Python and Docker experience.")
        elapsed = time.perf_counter() - start
        assert elapsed < 3.0, f"Extraction took {elapsed:.2f}s (SLA: <3s)"

    def test_guarantee_engine_speed(self, sample_resume):
        registry = _build_registry(['Docker', 'Kubernetes', 'AWS', 'Terraform', 'Redis',
                                     'PostgreSQL', 'Jenkins', 'Grafana', 'Ansible', 'Kafka'])
        engine = MustHaveGuaranteeEngine()
        start = time.perf_counter()
        engine.guarantee_injection_v2(sample_resume, registry, confidence_threshold=0.75)
        elapsed = time.perf_counter() - start
        assert elapsed < 5.0, f"Guarantee injection took {elapsed:.2f}s (SLA: <5s)"

    def test_quality_validation_speed(self, sample_resume):
        start = time.perf_counter()
        run_quality_gates(sample_resume, 'mid_level')
        elapsed = time.perf_counter() - start
        assert elapsed < 2.0, f"Quality validation took {elapsed:.2f}s (SLA: <2s)"


# ============================================================================
# SECTION 3: EDGE CASES (Problem 5) — real functions, boundary inputs
# ============================================================================

class TestEdgeCases:
    """Boundary conditions against real validators, not hardcoded
    tautologies."""

    def test_zero_years_no_experience_history(self):
        resume = {'experience': []}
        assert calculate_years_experience(resume) == 0.0
        assert detect_role_level(resume, "Any JD") == 'entry_level'

    def test_fifty_plus_skills_flagged_incoherent(self):
        resume = {'skills': [{'category': 'Languages', 'items': [f'Skill{i}' for i in range(55)]}]}
        coherence = validate_role_skill_coherence(resume, 'entry_level')
        assert coherence['status'] == 'FAIL'
        assert any(i['severity'] == 'HIGH' for i in coherence['issues'])

    def test_one_character_summary_rejected(self):
        result = validate_summary_quality('X')
        assert result['is_valid'] is False

    def test_duplicate_keywords_deduplicated(self):
        resume = {'skills': [{'category': 'Languages', 'items': ['Python', 'Python', 'python', 'Docker']}]}
        dedup = DeduplicationEngine()
        cleaned, removed_count = dedup.deduplicate_skills(resume)
        assert removed_count >= 2
        remaining = [i for g in cleaned['skills'] for i in g['items']]
        assert sum(1 for s in remaining if s.lower() == 'python') == 1

    def test_special_characters_in_skills_accepted(self):
        for skill in ('C++', 'C#', '.NET', 'Node.js'):
            is_valid, reason = validate_skill(skill)
            assert is_valid, f"'{skill}' should be a valid skill: {reason}"

    def test_garbage_special_characters_rejected(self):
        is_valid, _ = validate_skill('!!!@@@###')
        assert not is_valid


# ============================================================================
# SECTION 4: REGRESSION SMOKE SUITE (Problem 3)
#
# Compact, fast re-check of the highest-impact already-fixed production
# bugs — one real assertion each. Not a duplicate of the exhaustive
# per-task suites (tests/test_task_{2..10}_solution.py already cover
# these in depth) — meant to run first and fail loudly if a refactor
# reopens any of them.
# ============================================================================

class TestRegressionSmokeSuite:

    def test_jd_fragments_still_rejected(self):
        extractor = SemanticKeywordExtractor()
        is_valid, _ = extractor._validate_keyword('end interfaces', 'HARD_SKILL', [])
        assert not is_valid

    def test_two_years_still_mid_level(self):
        resume = {'experience': [{'dates': 'Jan 2022 – Jan 2024', 'bullets': ['Worked.']}]}
        assert detect_role_level(resume, "Backend role.") == 'mid_level'

    def test_guarantee_still_single_call_when_feasible(self):
        resume = {'summary': 'Engineer.', 'skills': [{'category': 'Languages', 'items': ['Python']}],
                  'experience': [], 'projects': []}
        registry = _build_registry(['Docker'])
        engine = MustHaveGuaranteeEngine()
        result = engine.guarantee_injection_v2(resume, registry, confidence_threshold=0.75)
        assert result['metadata']['all_protected_found'] is True

    def test_quality_gate_still_wired_and_flags_ai_phrasing(self):
        resume = {'summary': ('Innovatively developed cutting-edge platforms leveraging '
                               'cutting-edge tools for many years running.'),
                  'skills': [], 'experience': [], 'projects': []}
        report = run_quality_gates(resume)
        assert report['naturalness']['is_valid'] is False

    def test_single_word_jd_skills_still_extracted(self):
        """Regression for the Task 11 extraction fix — see module
        docstring and test_task_8_solution.py::TestSingleWordCandidateGeneration."""
        extractor = SemanticKeywordExtractor()
        result = extractor.extract(
            "Requirements:\n- Required: strong knowledge of Kubernetes and AWS",
            "Worked with Kubernetes and AWS in production.",
        )
        must_have_texts = {kw.text.lower() for kw in result.must_haves}
        assert 'kubernetes' in must_have_texts
        assert 'aws' in must_have_texts


# ============================================================================
# SECTION 5: PRODUCTION SCENARIOS (Problem 6) — messy, realistic input
# ============================================================================

class TestProductionScenarios:

    def test_messy_jd_with_typos_and_inconsistent_formatting(self):
        messy_jd = """
        we're looking for a Python dev!! must have docker & kubernetes exp.
        AWS/Azure a PLUS. some SQL knowledge helpfull.
        Communication skills a MUST have too
        """
        extractor = SemanticKeywordExtractor()
        result = extractor.extract(messy_jd, "Python developer with some cloud experience.")
        # Should not crash, and soft skills must never leak into hard-skill tiers
        all_hard = [kw.text.lower() for kw in result.must_haves + result.important]
        assert 'communication' not in all_hard

    def test_resume_missing_optional_sections_does_not_crash_quality_gate(self):
        minimal_resume = {'summary': 'Engineer with several years of backend development experience overall.'}
        report = run_quality_gates(minimal_resume)
        assert 'overall_score' in report


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
