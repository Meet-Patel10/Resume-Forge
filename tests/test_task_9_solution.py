# ============================================================================
# TASK 9: TEST SUITE - GUARANTEE ENGINE (protected-keyword injection path)
#
# TASK_9_COMPLETE_SOLUTION.md proposes a brand-new app/services/
# guarantee_engine.py: a generic ConvergenceDetector/QualityValidator/
# GuaranteeEngine class hierarchy with its own 3-pass loop, run from a
# fictional TailorPipeline.run_guarantee_engine(). None of that exists in
# this codebase and it doesn't match the real architecture: the real
# guarantee system already lives in app/services/guarantee_engine/ (a
# package: audit_engine, injection_strategies, density_controller,
# deduplication_engine, evidence_validator, guarantee_verifier,
# must_have_guarantee_engine) and is called exactly once per tailor run
# from app/routes/tailor.py's "PHASE 3" block via
# MustHaveGuaranteeEngine.guarantee_injection_v2 — the "FIX #7" path used
# whenever protected_keywords_registry is available, which is the normal
# case in production.
#
# Comparing that real, single-call v2 path against the six problems the
# guide describes turned up three concrete, verifiable gaps (not the
# guide's fictional multi-pass loop, which doesn't exist here — the real
# engine is already single-pass per call):
#
#   1. Presence checks used a bare `json.dumps(resume).lower()` substring
#      match instead of the fuzzy word-match checker
#      (GuaranteeVerifier._keyword_present) that the OLDER v1 path
#      (guarantee_injection) already uses and this test file confirms
#      works correctly. A keyword present as a known variant (e.g. "REST
#      APIs" vs. resume text "RESTful APIs") was wrongly scored MISSING —
#      inaccurate convergence/coverage numbers (guide's Problems 2 & 3).
#   2. Deduplication ran, but nothing retried keywords whose injection
#      failed *before* dedup, even though dedup can free the exact
#      density room ("category full because of a duplicate") that caused
#      the failure — the real version of guide's Problem 4 ("fallback
#      tries once, gives up").
#   3. Per-keyword outcomes were tracked in self.injection_log /
#      self.skipped_log by the older _inject_keyword() codepath but
#      discarded by guarantee_injection_v2 — callers only saw aggregate
#      counts, no audit trail or failure-reason breakdown (guide's
#      Problems 5 & 6).
#
# Fixed in must_have_guarantee_engine.py by reusing the existing,
# already-tested GuaranteeVerifier methods instead of a second, weaker
# inline implementation, adding a genuine post-dedup retry, and returning
# the full injection/skip log plus a placement QA check in metadata.
# ============================================================================

import pytest
from app.services.guarantee_engine.must_have_guarantee_engine import MustHaveGuaranteeEngine


def _base_resume(skills=None, summary='Backend engineer.', experience=None, projects=None):
    return {
        'summary': summary,
        'skills': skills if skills is not None else [],
        'experience': experience if experience is not None else [],
        'projects': projects if projects is not None else [],
    }


def _registry(entries):
    """entries: dict of {normalized_key: (original_text, tier, confidence)}"""
    return {
        key: {
            'original_text': original,
            'tier': tier,
            'keyword_type': 'hard_skill',
            'confidence': confidence,
            'sections_target': ['skills'],
        }
        for key, (original, tier, confidence) in entries.items()
    }


class TestFuzzyPresenceCheck:
    """Gap #1: variant keywords must be recognized as present, not
    re-injected as duplicates."""

    def setup_method(self):
        self.engine = MustHaveGuaranteeEngine()

    def test_variant_already_present_not_reinjected(self):
        resume = _base_resume(
            summary='Engineer building RESTful APIs and microservices.',
            skills=[{'category': 'Frameworks & Libraries', 'items': ['RESTful APIs']}],
        )
        registry = _registry({'rest apis': ('REST APIs', 'must_have', 0.9)})

        result = self.engine.guarantee_injection_v2(resume, registry, confidence_threshold=0.75)

        assert result['metadata']['audit_details']['missing'] == []
        assert 'REST APIs' in result['metadata']['audit_details']['found']
        assert result['metadata']['injections_made'] == 0
        assert result['metadata']['must_have_coverage'] == 1.0

    def test_genuinely_missing_keyword_is_injected(self):
        resume = _base_resume(skills=[{'category': 'Languages', 'items': ['Python']}])
        registry = _registry({'docker': ('Docker', 'must_have', 0.9)})

        result = self.engine.guarantee_injection_v2(resume, registry, confidence_threshold=0.75)

        assert result['metadata']['all_protected_found'] is True
        assert result['metadata']['injections_made'] == 1
        skills_flat = [i for g in result['resume_json']['skills'] for i in g['items']]
        assert 'Docker' in skills_flat

    def test_low_confidence_keyword_skipped_not_injected(self):
        resume = _base_resume()
        registry = _registry({'kubernetes': ('Kubernetes', 'important', 0.5)})

        result = self.engine.guarantee_injection_v2(resume, registry, confidence_threshold=0.75)

        assert result['metadata']['injections_made'] == 0
        skipped = result['metadata']['audit_details']['missing']
        assert skipped[0]['action'] == 'SKIP'


class TestEmergencyRetryAfterDedup:
    """Gap #2: a keyword that fails injection because every skills
    category is full must be retried after dedup frees room — not
    dropped after a single attempt."""

    def setup_method(self):
        self.engine = MustHaveGuaranteeEngine()

    def _seven_full_categories_with_one_duplicate(self):
        """7 categories (the max skills_injection_strategy/fallback will
        create beyond) each with 8 items — one category holds a
        normalized duplicate (AWS / Amazon Web Services) so dedup frees
        exactly one slot."""
        return [
            {'category': 'Languages', 'items': ['Python', 'Java', 'C++', 'Go', 'Ruby', 'PHP', 'Scala', 'Kotlin']},
            {'category': 'Frameworks & Libraries', 'items': ['React', 'Angular', 'Vue', 'Django', 'Flask', 'Spring', 'Express', 'Next.js']},
            {'category': 'Tools & Platforms', 'items': ['AWS', 'Amazon Web Services', 'Git', 'Linux', 'Jenkins', 'Postman', 'Grafana', 'Terraform']},
            {'category': 'Programming Concepts', 'items': ['OOP', 'Algorithms', 'Data Structures', 'Design Patterns', 'Memory Management', 'Recursion', 'Big O', 'Heap']},
            {'category': 'Concepts', 'items': ['Agile', 'Scrum', 'CI/CD', 'Microservices', 'TDD', 'SDLC', 'DevOps', 'Serverless']},
            {'category': 'Databases', 'items': ['MySQL', 'PostgreSQL', 'MongoDB', 'Redis', 'Cassandra', 'Elasticsearch', 'DynamoDB', 'Oracle']},
            {'category': 'Testing', 'items': ['Unit Testing', 'Integration Testing', 'Mocking', 'Pytest', 'JUnit', 'Selenium', 'Cypress', 'Load Testing']},
        ]

    def test_keyword_succeeds_only_after_dedup_frees_room(self):
        resume = _base_resume(skills=self._seven_full_categories_with_one_duplicate())
        registry = _registry({'kubernetes': ('Kubernetes', 'must_have', 0.9)})

        result = self.engine.guarantee_injection_v2(resume, registry, confidence_threshold=0.75)

        assert result['metadata']['all_protected_found'] is True
        assert result['metadata']['injections_made'] == 1
        assert result['metadata']['still_missing'] == []

        # The successful attempt must be recorded as the post-dedup retry,
        # proving it did NOT succeed on the first (pre-dedup) attempt.
        strategies = [log['strategy'] for log in result['metadata']['injection_log']
                      if log['keyword'] == 'Kubernetes']
        assert strategies == ['emergency_retry_post_dedup']

    def test_truly_impossible_keyword_ends_up_in_skipped_log(self):
        """No duplicates to free room and no projects section — injection
        must fail cleanly and be logged with a reason, not silently
        dropped."""
        no_dup_categories = self._seven_full_categories_with_one_duplicate()
        no_dup_categories[2]['items'] = ['AWS', 'Docker', 'Git', 'Linux', 'Jenkins', 'Postman', 'Grafana', 'Terraform']
        resume = _base_resume(skills=no_dup_categories)
        registry = _registry({'kubernetes': ('Kubernetes', 'must_have', 0.9)})

        result = self.engine.guarantee_injection_v2(resume, registry, confidence_threshold=0.75)

        assert result['metadata']['all_protected_found'] is False
        assert 'Kubernetes' in result['metadata']['still_missing']
        skipped_keywords = [s['keyword'] for s in result['metadata']['skipped_log']]
        assert 'Kubernetes' in skipped_keywords


class TestAuditTrailAndQAMetrics:
    """Gaps #3: full injection/skip audit trail and placement QA must be
    returned in metadata, not discarded."""

    def setup_method(self):
        self.engine = MustHaveGuaranteeEngine()

    def test_injection_log_and_skipped_log_present_in_metadata(self):
        resume = _base_resume(skills=[{'category': 'Languages', 'items': ['Python']}])
        registry = _registry({
            'docker': ('Docker', 'must_have', 0.9),
            'kubernetes': ('Kubernetes', 'important', 0.4),  # below threshold -> skipped
        })

        result = self.engine.guarantee_injection_v2(resume, registry, confidence_threshold=0.75)
        meta = result['metadata']

        assert 'injection_log' in meta
        assert 'skipped_log' in meta
        assert 'placement_check' in meta
        assert any(log['keyword'] == 'Docker' for log in meta['injection_log'])

    def test_placement_check_flags_soft_skill_in_skills_section(self):
        resume = _base_resume(
            skills=[{'category': 'Concepts', 'items': ['communication']}],
        )
        registry = _registry({})

        result = self.engine.guarantee_injection_v2(resume, registry, confidence_threshold=0.75)

        assert result['metadata']['placement_check']['soft_skills_in_skills'] == 1

    def test_coverage_metrics_consistent_with_all_protected_found(self):
        """must_have_coverage/important_coverage must agree with
        all_protected_found — both now derived from the same fuzzy
        matcher, so they can't drift apart."""
        resume = _base_resume(skills=[{'category': 'Languages', 'items': ['Python']}])
        registry = _registry({'docker': ('Docker', 'must_have', 0.9)})

        result = self.engine.guarantee_injection_v2(resume, registry, confidence_threshold=0.75)
        meta = result['metadata']

        assert meta['all_protected_found'] is True
        assert meta['must_have_coverage'] == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
