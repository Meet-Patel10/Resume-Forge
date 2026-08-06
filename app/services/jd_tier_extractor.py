# FILE: app/services/jd_tier_extractor.py

from typing import List, Dict
from dataclasses import dataclass, field
import json as json_mod
from app.services.claude_client import claude


@dataclass
class JDTierAnalysis:
    """Extracted JD requirements organized by priority tier."""
    required_hard_skills: List[str] = field(default_factory=list)
    preferred_hard_skills: List[str] = field(default_factory=list)
    nice_to_have_skills: List[str] = field(default_factory=list)
    job_title_patterns: List[str] = field(default_factory=list)
    certifications: List[str] = field(default_factory=list)
    years_of_experience: int = 0
    keyword_frequency: Dict[str, int] = field(default_factory=dict)
    quality_score: float = 0.0  # How confident we are in this extraction


class JDTierExtractor:

    REQUIRED_SCHEMA = """{
  "required_hard_skills": ["skill1", "skill2", ...],
  "preferred_hard_skills": ["skill1", ...],
  "nice_to_have_skills": ["skill1", ...],
  "job_title_patterns": ["Senior", "Lead", ...],
  "certifications": ["AWS", "GCP", ...],
  "years_of_experience": 3,
  "keyword_frequency": {"React": 7, "Node.js": 5, ...}
}"""

    SYSTEM_PROMPT = f"""You are an ATS expert analyzing a job description.
Your job: Extract requirements and organize them by priority tier.

CRITICAL: Return ONLY valid JSON matching this EXACT schema (no nested objects, only flat arrays):

{REQUIRED_SCHEMA}

Rules:
1. required_hard_skills: Skills in phrases like "must have", "required", "minimum", "critical"
2. preferred_hard_skills: Skills in phrases like "preferred", "nice to have", "bonus", "helpful"
3. nice_to_have_skills: Skills mentioned once, low emphasis, or "ideally"
4. job_title_patterns: Seniority levels (Senior, Lead, Principal, Staff, etc.)
5. certifications: AWS, Azure, GCP, PMP, etc. (look for "certifications required")
6. years_of_experience: Number extracted from "X+ years", "X-Y years"
7. keyword_frequency: Count how many times each skill appears

Return ONLY the JSON object. No explanations, no markdown fences, no additional text.
If the JSON is malformed, I will retry.
"""

    def extract_tiered_requirements(self, jd_text: str) -> JDTierAnalysis:
        """
        Extract JD requirements into priority tiers.
        Includes defensive parsing to handle Claude's creative responses.
        """

        # Call Claude with explicit schema demand
        result = claude.analyze(
            self.SYSTEM_PROMPT,
            f"JD to analyze:\n\n{jd_text}",
            max_tokens=2000,
            force_json=True,
            temperature=0.0  # No creativity, follow schema exactly
        )

        if result.get('error'):
            print(f"[jd-extractor] ERROR: {result['error']}")
            return self._empty_analysis()

        response = result['response']

        # Try to parse response
        parsed = self._parse_response(response)

        if not parsed:
            print("[jd-extractor] ⚠ Failed to parse response, returning empty")
            return self._empty_analysis()

        # Validate: at least some required skills must be found
        required_found = len(parsed.get('required_hard_skills', []))
        preferred_found = len(parsed.get('preferred_hard_skills', []))

        if required_found == 0 and preferred_found == 0:
            print("[jd-extractor] ⚠ WARNING: No required or preferred skills found!")
            print(f"  Nice-to-have: {len(parsed.get('nice_to_have_skills', []))}")
            # This is a real signal — don't call it success
            quality_score = 0.3  # Low confidence
        else:
            quality_score = 0.95  # High confidence

        # Build dataclass
        analysis = JDTierAnalysis(
            required_hard_skills=parsed.get('required_hard_skills', []),
            preferred_hard_skills=parsed.get('preferred_hard_skills', []),
            nice_to_have_skills=parsed.get('nice_to_have_skills', []),
            job_title_patterns=parsed.get('job_title_patterns', []),
            certifications=parsed.get('certifications', []),
            years_of_experience=parsed.get('years_of_experience', 0),
            keyword_frequency=parsed.get('keyword_frequency', {}),
            quality_score=quality_score,
        )

        print(f"[jd-extractor] Extracted: {required_found} required, {preferred_found} preferred, "
              f"{len(parsed.get('nice_to_have_skills', []))} nice-to-have "
              f"(confidence: {quality_score*100:.0f}%)")

        return analysis

    def _parse_response(self, response) -> dict:
        """
        Defensively parse Claude's response.
        Handles various malformations.
        """

        # If already a dict, return it
        if isinstance(response, dict):
            return response

        if not isinstance(response, str):
            return None

        raw = response.strip()

        # Try 1: Direct parse
        try:
            return json_mod.loads(raw)
        except Exception:
            pass

        # Try 2: Strip markdown fences
        if raw.startswith('```json'):
            raw = raw[7:]
        if raw.startswith('```'):
            raw = raw[3:]
        if raw.endswith('```'):
            raw = raw[:-3]

        try:
            return json_mod.loads(raw.strip())
        except Exception:
            pass

        # Try 3: Extract { ... } blob
        brace_start = raw.find('{')
        brace_end = raw.rfind('}')

        if brace_start != -1 and brace_end > brace_start:
            try:
                return json_mod.loads(raw[brace_start:brace_end + 1])
            except Exception:
                pass

        # Failed to parse
        print(f"[jd-extractor] ⚠ Could not parse response: {raw[:200]}")
        return None

    def _empty_analysis(self) -> JDTierAnalysis:
        """Return empty analysis with quality_score=0 to signal failure."""
        return JDTierAnalysis(quality_score=0.0)
