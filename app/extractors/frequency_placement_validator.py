"""
Frequency + Placement Validator - "Approach 1" cross-check.

app/routes/tailor.py's Phase 0 (STEP 2) imports FrequencyPlacementValidator from this
module and calls validator.validate(all_keywords, jd_text) — this file previously did
not exist at all (ModuleNotFoundError on every /tailor/api/tailor request), even
though the call site, its usage of the returned dict shape, and the print
statements describing it ("Frequency + Placement Validation (Approach 1)",
"High confidence (both approaches)", "Approach 2 only") were all already written
and never exercised outside of that one broken import.

Approach 2 (SemanticKeywordExtractor) is structural/language-signal based: it tiers
a keyword by JD section type and phrases like "required"/"preferred". Approach 1
independently corroborates each of Approach 2's already-accepted candidates using
two orthogonal signals ExtractedKeyword already carries (app/extractors/
keyword_models.py): how many times the phrase actually appears in the JD
(frequency_in_jd) and whether it appears in a requirements-type section
(sections_found). This does NOT generate new candidates or discard any of
Approach 2's — every keyword passed in ends up in exactly one of the two returned
buckets, which tailor.py immediately re-unions (`high_confidence_keywords +
medium_confidence_keywords`); the split only changes what gets logged as
"high confidence" vs "Approach 2 only", not which keywords survive.

Note: ExtractedKeyword.placement_score is currently always 0 (see
SemanticKeywordExtractor._build_extraction_result — "Will be calculated", never
wired up), so the placement_score half of the placement signal below is
currently inert; sections_found is real and does vary.
"""

from typing import Dict, List

from .keyword_models import ExtractedKeyword


class FrequencyPlacementValidator:
    """
    Approach 1: Frequency + Placement cross-check for Approach 2's candidates.
    """

    # A phrase mentioned this many times or more in the JD text is considered
    # independently corroborated by frequency alone.
    MIN_FREQUENCY_FOR_HIGH_CONFIDENCE = 2

    # JD section names (as produced by JDStructureParser) that indicate a
    # requirement, not just incidental mention.
    REQUIREMENT_SECTIONS = {'requirements', 'must_have', 'qualifications'}

    def validate(self, keywords: List[ExtractedKeyword], jd_text: str) -> Dict:
        """
        Split Approach 2's keywords into high/medium confidence based on
        frequency + placement signals.

        Returns:
            {
                'high_confidence_keywords': List[ExtractedKeyword],
                'medium_confidence_keywords': List[ExtractedKeyword],
                'total_validated': int,
            }
        """
        high_confidence = []
        medium_confidence = []

        for keyword in keywords:
            if self._is_high_confidence(keyword):
                high_confidence.append(keyword)
            else:
                medium_confidence.append(keyword)

        return {
            'high_confidence_keywords': high_confidence,
            'medium_confidence_keywords': medium_confidence,
            'total_validated': len(high_confidence) + len(medium_confidence),
        }

    def _is_high_confidence(self, keyword: ExtractedKeyword) -> bool:
        """A keyword is high-confidence if EITHER frequency or placement
        independently corroborates Approach 2's pick — they're separate
        signals, not required to agree with each other."""
        frequency_signal = (keyword.frequency_in_jd or 0) >= self.MIN_FREQUENCY_FOR_HIGH_CONFIDENCE

        sections = keyword.sections_found or []
        placement_signal = (
            any(section in self.REQUIREMENT_SECTIONS for section in sections)
            or (keyword.placement_score or 0) >= 2
        )

        return frequency_signal or placement_signal
