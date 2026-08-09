# ============================================================================
# TASK 8: TEST SUITE - KEYWORD EXTRACTION & VALIDATION
#
# TASK_8_COMPLETE_SOLUTION.md's Problem 1 evidence includes several JD
# fragments. Checked against the REAL extractor (app/extractors/
# semantic_keyword_extractor.py's SemanticKeywordExtractor._validate_keyword,
# a real "FIX #6" rejection gate already wired into the live extract()
# pipeline, predating this conversation's Task 2-7 work): the long (>4-word)
# fragments were ALREADY rejected by the existing Rule 3. The real,
# confirmed gap was SHORT fragments (2-3 words, e.g. "with cloud platforms",
# "end interfaces", "product teams", "stack or backend", "functional
# teams") — Rule 3's word-count gate only fires above 4 words, so these
# passed through as "Valid".
#
# Rather than the guide's proposed app/extractors/semantic_keyword_
# extractor.py "EnhancedSemanticKeywordExtractor" (a parallel, disconnected
# class + REJECTION_PATTERNS/KNOWN_SKILL_PATTERNS/CONFIDENCE_SCORING module
# classes, wired only into a fictional TailorPipeline that doesn't exist),
# this fix extends the REAL, already-wired _validate_keyword directly:
#   - Rule 3b: the guide's fragment/connector regex patterns (safety-
#     checked against real multi-word skills already used in this app —
#     Spring Boot, REST APIs, Machine Learning, CI/CD, Full Stack, etc. —
#     to confirm zero false positives).
#   - A real confidence score (_calculate_extraction_confidence, 0.0-1.0)
#     wired as a genuine reject gate (Rule 6), but calibrated to reuse the
#     EXISTING known-pattern sources (Rule 4's domain/tech vocabulary +
#     the Task 6 hard-skill/tool classifier patterns) rather than the
#     guide's separate 14-pattern whitelist — the guide's own whitelist,
#     tested directly, would have wrongly rejected real terms like
#     "Terraform" and "Machine Learning" that aren't on its finite list
#     but ARE already recognized elsewhere in this codebase.
# ============================================================================

import pytest
from app.extractors.semantic_keyword_extractor import SemanticKeywordExtractor


class TestRejectionPatterns:
    """Rule 3b: short JD-connector/fragment patterns — the real gap."""

    def setup_method(self):
        self.extractor = SemanticKeywordExtractor()

    @pytest.mark.parametrize("fragment", [
        "end interfaces",
        "with cloud platforms",
        "product teams",
        "stack or backend",
        "functional teams",
        "team and what we",
        "alongside talented developers",
    ])
    def test_reject_short_jd_fragments(self, fragment):
        """These previously passed _validate_keyword as 'Valid' — confirmed
        against the real (pre-Task-8) code before this fix."""
        is_valid, reason = self.extractor._validate_keyword(fragment, 'HARD_SKILL', [])
        assert not is_valid, f"Should reject '{fragment}'"

    @pytest.mark.parametrize("fragment", [
        "enabled systems and intelligent automation to transform how content",
        "and delivered to hundreds of thousands of",
        "ll contribute to the next generation of",
    ])
    def test_reject_long_jd_fragments(self, fragment):
        """These were already rejected by the pre-existing Rule 3."""
        is_valid, reason = self.extractor._validate_keyword(fragment, 'HARD_SKILL', [])
        assert not is_valid, f"Should reject '{fragment}'"

    @pytest.mark.parametrize("skill", [
        "Python", "Docker", "Kubernetes", "REST APIs", "Microservices",
        "Spring Boot", "Machine Learning", "CI/CD", "Node.js", "Full Stack",
    ])
    def test_accept_real_skills(self, skill):
        is_valid, reason = self.extractor._validate_keyword(skill, 'HARD_SKILL', [])
        assert is_valid, f"Should accept '{skill}': {reason}"


class TestConfidenceScoring:
    """_calculate_extraction_confidence: known terms trusted outright,
    unknown terms scored heuristically."""

    def setup_method(self):
        self.extractor = SemanticKeywordExtractor()

    def test_known_skill_high_confidence(self):
        assert self.extractor._calculate_extraction_confidence("Python") >= 0.8

    def test_known_multiword_skill_not_penalized_for_word_count(self):
        """The guide's own formula (word-count penalty applied AFTER the
        known-pattern confidence) would score 'Machine Learning' at
        0.85 * 0.8 = 0.68 — below its own 0.7 threshold. This app's
        version treats known-pattern matches as trusted outright,
        skipping the word-count penalty entirely."""
        conf = self.extractor._calculate_extraction_confidence("Machine Learning")
        assert conf >= 0.7

    def test_unlisted_but_real_single_word_tool_not_penalized(self):
        """Terraform, Kafka, etc. aren't on the guide's finite 14-pattern
        whitelist but are real tools — must not be killed by the gate."""
        for term in ("Terraform", "Kafka", "Snowflake", "Grafana"):
            conf = self.extractor._calculate_extraction_confidence(term)
            assert conf >= 0.7, f"'{term}' scored too low: {conf}"

    def test_long_fragment_low_confidence(self):
        conf = self.extractor._calculate_extraction_confidence(
            "enabled systems and intelligent automation to transform how content"
        )
        assert conf < 0.5

    def test_confidence_clamped_0_to_1(self):
        for text in ("Python", "", "a", "x" * 100):
            conf = self.extractor._calculate_extraction_confidence(text)
            assert 0.0 <= conf <= 1.0


class TestKnownTechnicalOrDomainTerm:
    """Reuses Rule 4's domain vocabulary + Task 6's hard-skill/tool
    classifier patterns instead of a third separate skill list."""

    def setup_method(self):
        self.extractor = SemanticKeywordExtractor()

    @pytest.mark.parametrize("term", [
        "python", "docker", "kubernetes", "spring boot", "machine learning",
        "capital market", "fintech", "risk", "data science",
    ])
    def test_known_terms_recognized(self, term):
        assert self.extractor._is_known_technical_or_domain_term(term)

    def test_generic_fragment_not_known(self):
        assert not self.extractor._is_known_technical_or_domain_term(
            "alongside talented developers"
        )


class TestExtractIntegration:
    """End-to-end through the real extract() pipeline (STEP 2.5)."""

    def test_validate_keyword_rejects_production_fragments(self):
        extractor = SemanticKeywordExtractor()
        production_fragments = [
            "enabled systems and intelligent automation to transform",
            "and delivered to hundreds of thousands of",
            "ll contribute to the next generation of",
            "team and what we",
            "with cloud platforms",
            "end interfaces",
            "product teams",
        ]
        for fragment in production_fragments:
            is_valid, _ = extractor._validate_keyword(fragment, 'HARD_SKILL', [])
            assert not is_valid, f"Should reject '{fragment}'"

    def test_validate_keyword_accepts_production_skills(self):
        extractor = SemanticKeywordExtractor()
        real_skills = [
            "Python", "Java", "Docker", "Kubernetes", "AWS",
            "REST APIs", "Microservices", "CI/CD",
        ]
        for skill in real_skills:
            is_valid, reason = extractor._validate_keyword(skill, 'HARD_SKILL', [])
            assert is_valid, f"Should accept '{skill}': {reason}"


# ============================================================================
# TASK 11 fix (found while writing tests/test_task_11_solution.py's
# cross-task integration tests, not a Task 8 problem originally):
# _extract_all_keywords()'s phrase regex requires TWO OR MORE consecutive
# words of matching case, so a lone technical term ("Python", "AWS",
# "SQL", "Kubernetes"...) was NEVER proposed as an extraction candidate —
# confirmed by running extract() on a realistic JD and getting zero
# must_haves back despite the JD explicitly requiring "Kubernetes and
# AWS". HARD_SKILL_KEYWORDS existed for exactly this gap but was dead
# code, never referenced. Fixed by reusing the already-curated, word-
# boundary-safe _TOOL_PATTERNS/_HARD_SKILL_PATTERNS (built for
# classification, Task 6) to also scan jd_text directly for single/short
# known-technical-term mentions.
# ============================================================================

class TestSingleWordCandidateGeneration:
    """_extract_all_keywords() must propose single-word technical terms
    as candidates, not just 2+-word phrases."""

    def setup_method(self):
        self.extractor = SemanticKeywordExtractor()

    def test_lone_technical_terms_extracted_as_candidates(self):
        jd_sections = self.extractor.parser.parse(
            "Requires Python, Docker, Kubernetes, AWS, and Redis experience."
        )
        candidates = {
            kw['text'].lower()
            for kw in self.extractor._extract_all_keywords(
                "Requires Python, Docker, Kubernetes, AWS, and Redis experience.",
                jd_sections,
            )
        }
        for term in ('python', 'docker', 'kubernetes', 'aws', 'redis'):
            assert term in candidates, f"'{term}' should be a candidate on its own"

    def test_no_duplicate_candidates_for_same_term(self):
        text = "Python and Python and Python."
        jd_sections = self.extractor.parser.parse(text)
        candidates = [kw['text'] for kw in self.extractor._extract_all_keywords(text, jd_sections)]
        assert candidates.count('Python') == 1, (
            f"'Python' should be deduplicated to a single candidate, got {candidates}"
        )

    def test_end_to_end_must_have_now_reaches_result(self):
        """Regression: this exact JD used to return zero must_haves."""
        jd = (
            "Senior Backend Engineer. Requirements: Required: strong "
            "knowledge of Kubernetes and AWS. 5+ years of experience with "
            "Python and Docker."
        )
        resume = "Built backend systems using Python, Docker, Kubernetes, and AWS."
        result = self.extractor.extract(jd, resume)
        must_have_texts = {kw.text.lower() for kw in result.must_haves}
        for term in ('python', 'docker', 'kubernetes', 'aws'):
            assert term in must_have_texts, f"'{term}' should reach must_haves"

    def test_short_english_words_not_falsely_matched(self):
        """The word-boundary anchors in _TOOL_PATTERNS/_HARD_SKILL_PATTERNS
        must not fire on ordinary prose containing short substrings."""
        jd_sections = self.extractor.parser.parse(
            "We go to market fast and go the extra mile for customers."
        )
        candidates = {
            kw['text'].lower() for kw in
            self.extractor._extract_all_keywords(
                "We go to market fast and go the extra mile for customers.",
                jd_sections,
            )
        }
        assert 'go' not in candidates


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
