# ============================================================================
# Regression test: app/routes/tailor.py's Phase 0 (STEP 2) imports
# FrequencyPlacementValidator from app/extractors/frequency_placement_validator.py
# — that module didn't exist at all, so EVERY POST to /tailor/api/tailor 500'd
# with ModuleNotFoundError the moment api_tailor() reached that import. Caught
# via manual testing of the running app, not by the test suite (every existing
# test imports the individual pipeline pieces directly, none exercised this
# exact Phase 0 import chain the way tailor.py actually does it).
# ============================================================================

import pytest

from app.extractors.semantic_keyword_extractor import SemanticKeywordExtractor
from app.extractors.frequency_placement_validator import FrequencyPlacementValidator
from app.keyword_router.section_router import SectionRouter


class TestFrequencyPlacementValidator:

    def setup_method(self):
        self.validator = FrequencyPlacementValidator()

    def test_import_matches_tailor_py_call_site(self):
        """This is the exact import + call sequence app/routes/tailor.py's
        Phase 0 uses — if this import ever breaks again, every tailoring
        request breaks with it."""
        assert FrequencyPlacementValidator is not None

    def test_validate_returns_expected_shape(self):
        extractor = SemanticKeywordExtractor()
        jd = "Requirements:\n- Required: Python and Docker experience\n- 5+ years required"
        result = extractor.extract(jd, "Built systems using Python and Docker for five years.")
        all_keywords = result.must_haves + result.important + result.nice_to_have

        report = self.validator.validate(all_keywords, jd)

        assert set(report.keys()) >= {'high_confidence_keywords', 'medium_confidence_keywords', 'total_validated'}
        assert report['total_validated'] == len(all_keywords)

    def test_no_keyword_is_dropped(self):
        """validate() must partition, never discard — tailor.py immediately
        re-unions both buckets (`high + medium`), so dropping one here would
        silently lose keywords Approach 2 already accepted."""
        extractor = SemanticKeywordExtractor()
        jd = "Requirements:\n- Required: Kubernetes and AWS\n- Preferred: Terraform"
        result = extractor.extract(jd, "Worked with Kubernetes, AWS, and Terraform in production.")
        all_keywords = result.must_haves + result.important + result.nice_to_have

        report = self.validator.validate(all_keywords, jd)
        combined = report['high_confidence_keywords'] + report['medium_confidence_keywords']

        assert {kw.text for kw in combined} == {kw.text for kw in all_keywords}

    def test_frequent_keyword_is_high_confidence(self):
        from app.extractors.keyword_models import ExtractedKeyword, KeywordType, Tier, MatchLevel
        kw = ExtractedKeyword(
            text='Python', keyword_type=KeywordType.HARD_SKILL, tier=Tier.MUST_HAVE,
            priority_score=7, frequency_in_jd=3, sections_found=[], placement_score=0,
            language_signals=[], signal_confidence=0.9, resume_match_level=MatchLevel.STRONG_MATCH,
            resume_evidence=None, evidence_confidence=0.9, target_sections=['skills'], max_mentions=4,
        )
        report = self.validator.validate([kw], "Python Python Python required.")
        assert kw in report['high_confidence_keywords']

    def test_full_phase_0_chain_does_not_crash(self):
        """The real chain tailor.py runs: extract -> validate (Approach 1) ->
        route. This is what silently broke in production."""
        extractor = SemanticKeywordExtractor()
        jd = "Requirements:\n- Required: Python and Docker experience"
        result = extractor.extract(jd, "Built systems using Python and Docker.")
        all_keywords = result.must_haves + result.important + result.nice_to_have

        report = self.validator.validate(all_keywords, jd)
        all_validated = report['high_confidence_keywords'] + report['medium_confidence_keywords']

        router = SectionRouter()
        routed = router.route(all_validated)  # must not raise
        assert isinstance(routed, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
