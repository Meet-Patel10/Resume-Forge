# ============================================================================
# TASK 6: TEST SUITE - HARD SKILLS ROUTING TO SKILLS SECTION
#
# TASK_6_COMPLETE_SOLUTION.md's Problem 1 evidence ("[tailor] STEP 3: Section
# Routing ... Skills section: 0") is real and matches actual code in this
# repo (tailor.py:2374-2384, using app/keyword_router/section_router.py's
# SectionRouter). But the routing RULES in SectionRouter were already
# correct (hard_skill/tool_platform + must_have/important -> skills;
# soft_skill -> never skills). The real bug was upstream, in
# SemanticKeywordExtractor._classify_single_keyword(): it only recognized 5
# hardcoded languages, 4 tools, and 3 soft-skill words, so any multi-word
# hard skill ("Spring Boot", "REST API", "Machine Learning", "CI/CD") fell
# through to the "len(words)>=2 -> DOMAIN_TERM" heuristic, and DOMAIN_TERM
# never routes to Skills.
#
# Rather than the guide's proposed app/keyword_router/hard_skills_router.py
# (a parallel HardSkillsRoutingEngine with its own KeywordType/RoutingTarget
# enums, disconnected from the real app.extractors.keyword_models.KeywordType
# already used throughout the Phase 0-3 pipeline), this fixes the actual
# classifier and adds a routing audit warning, reusing the real types.
# ============================================================================

import pytest
from app.extractors.semantic_keyword_extractor import SemanticKeywordExtractor
from app.extractors.keyword_models import ExtractedKeyword, KeywordType, Tier, MatchLevel
from app.keyword_router.section_router import SectionRouter


def make_keyword(text, keyword_type, tier, target_sections=None):
    """Minimal ExtractedKeyword builder for routing tests."""
    return ExtractedKeyword(
        text=text,
        keyword_type=keyword_type,
        tier=tier,
        priority_score=7 if tier == Tier.MUST_HAVE else 5,
        frequency_in_jd=1,
        sections_found=['requirements'],
        placement_score=0,
        language_signals=[],
        signal_confidence=0.9,
        resume_match_level=MatchLevel.NO_MATCH,
        resume_evidence=None,
        evidence_confidence=0.0,
        target_sections=target_sections or [],
        max_mentions=4,
    )


class TestClassifierFixMultiWordHardSkills:
    """The actual production bug: multi-word hard skills misclassified as
    DOMAIN_TERM, which SectionRouter never routes to Skills."""

    def setup_method(self):
        self.extractor = SemanticKeywordExtractor()

    @pytest.mark.parametrize("term", [
        "spring boot", "rest api", "machine learning", "deep learning",
        "data structures", "design patterns", "next.js", "node.js",
    ])
    def test_multiword_hard_skills_no_longer_domain_term(self, term):
        result = self.extractor._classify_single_keyword(term)
        assert result != KeywordType.DOMAIN_TERM, f"'{term}' still misclassified as DOMAIN_TERM"
        assert result in (KeywordType.HARD_SKILL, KeywordType.TOOL_PLATFORM)

    @pytest.mark.parametrize("term,expected", [
        ("python", KeywordType.HARD_SKILL),
        ("java", KeywordType.HARD_SKILL),
        ("postgresql", KeywordType.HARD_SKILL),
        ("docker", KeywordType.TOOL_PLATFORM),
        ("kubernetes", KeywordType.TOOL_PLATFORM),
        ("aws", KeywordType.TOOL_PLATFORM),
        ("terraform", KeywordType.TOOL_PLATFORM),
        ("communication", KeywordType.SOFT_SKILL),
        ("teamwork", KeywordType.SOFT_SKILL),
        ("leadership", KeywordType.SOFT_SKILL),
    ])
    def test_known_terms_classified_correctly(self, term, expected):
        assert self.extractor._classify_single_keyword(term) == expected

    def test_genuine_domain_term_still_domain_term(self):
        """Multi-word business/domain phrases that AREN'T skills should
        still fall through to DOMAIN_TERM — the fix shouldn't over-match."""
        result = self.extractor._classify_single_keyword("go to market strategy")
        assert result == KeywordType.DOMAIN_TERM

    def test_soft_skill_never_reclassified_as_hard(self):
        """Soft skills must be checked first — a soft-skill phrase should
        never fall through to a hard/tool pattern match."""
        result = self.extractor._classify_single_keyword("innovation")
        assert result == KeywordType.SOFT_SKILL


class TestSectionRouterAlreadyCorrect:
    """Confirm the real (unmodified) SectionRouter routing rules are what
    the guide wants — Problems 2, 3, 5 don't need new code, just correctly
    classified input, which the fix above now provides."""

    def setup_method(self):
        self.router = SectionRouter()

    def test_must_have_hard_skill_routes_to_skills(self):
        kw = make_keyword("Spring Boot", KeywordType.HARD_SKILL, Tier.MUST_HAVE)
        routed = self.router.route([kw])
        assert kw in routed['skills']

    def test_important_tool_routes_to_skills(self):
        kw = make_keyword("Terraform", KeywordType.TOOL_PLATFORM, Tier.IMPORTANT)
        routed = self.router.route([kw])
        assert kw in routed['skills']

    def test_soft_skill_never_routes_to_skills(self):
        """CRITICAL: soft skills must never appear in the skills bucket,
        regardless of tier."""
        for tier in (Tier.MUST_HAVE, Tier.IMPORTANT, Tier.NICE_TO_HAVE):
            kw = make_keyword("Communication", KeywordType.SOFT_SKILL, tier)
            routed = self.router.route([kw])
            assert kw not in routed['skills']

    def test_nice_to_have_hard_skill_not_in_skills(self):
        """Low-priority hard skills go to experience only, per the real
        routing rules (skills section reserved for must_have/important)."""
        kw = make_keyword("Groovy", KeywordType.HARD_SKILL, Tier.NICE_TO_HAVE)
        routed = self.router.route([kw])
        assert kw not in routed['skills']
        assert kw in routed['experience']


class TestProductionScenario:
    """End-to-end: the exact 'Skills section: 0' scenario, fixed."""

    def test_realistic_jd_keyword_set_populates_skills(self):
        extractor = SemanticKeywordExtractor()
        router = SectionRouter()

        # A realistic mix — several genuinely multi-word hard skills, which
        # is exactly what used to produce "Skills section: 0"
        raw_terms = [
            ("Python", Tier.MUST_HAVE),
            ("Spring Boot", Tier.MUST_HAVE),
            ("REST API", Tier.MUST_HAVE),
            ("Docker", Tier.IMPORTANT),
            ("Machine Learning", Tier.IMPORTANT),
            ("Communication", Tier.MUST_HAVE),  # soft skill — must stay out of skills
        ]

        keywords = []
        for text, tier in raw_terms:
            ktype = extractor._classify_single_keyword(text.lower())
            keywords.append(make_keyword(text, ktype, tier))

        routed = router.route(keywords)

        skills_texts = {kw.text for kw in routed['skills']}
        assert 'Python' in skills_texts
        assert 'Spring Boot' in skills_texts
        assert 'REST API' in skills_texts
        assert 'Docker' in skills_texts
        assert 'Machine Learning' in skills_texts
        assert 'Communication' not in skills_texts
        assert len(routed['skills']) >= 5, "Skills section must not be empty for this keyword mix"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
