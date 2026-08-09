from dataclasses import dataclass, field
from typing import List, Set, Dict, Optional
from enum import Enum

class KeywordType(Enum):
    HARD_SKILL = "hard_skill"                    # Languages, frameworks
    TOOL_PLATFORM = "tool_platform"              # AWS, Docker, Jira
    DOMAIN_TERM = "domain_term"                  # Capital Markets, FinTech
    RESPONSIBILITY = "responsibility"            # Verb + object tasks
    SOFT_SKILL = "soft_skill"                    # Communication, Leadership
    FLUFF = "fluff"                              # Innovative, dynamic

class Tier(Enum):
    MUST_HAVE = "must_have"                      # Priority 6-7
    IMPORTANT = "important"                      # Priority 4-5
    NICE_TO_HAVE = "nice_to_have"                # Priority 1-3
    EXCLUDE = "exclude"                          # Priority 0 or soft skills

class MatchLevel(Enum):
    STRONG_MATCH = "strong_match"                # Explicit in resume
    PARTIAL_MATCH = "partial_match"              # Related experience
    NO_MATCH = "no_match"                        # Not in resume

@dataclass
class JDSection:
    """Represents a section of the JD (Requirements, Responsibilities, etc.)"""
    name: str                                    # "requirements", "responsibilities", etc.
    weight: int                                  # 3=critical, 2=important, 1=nice, 0=fluff
    text: str                                    # Raw text from this section
    keywords: List[str] = field(default_factory=list)  # Keywords found in this section

@dataclass
class ExtractedKeyword:
    """A single keyword extracted from JD with full context"""
    text: str                                    # Exact phrase from JD
    keyword_type: KeywordType                    # Classification
    tier: Tier                                   # MUST_HAVE, IMPORTANT, NICE_TO_HAVE
    priority_score: int                          # 0-7 (for debugging)
    
    # Approach 1 data
    frequency_in_jd: int                         # How many times appears in JD
    sections_found: List[str]                    # ['requirements', 'responsibilities']
    placement_score: int                         # Score based on where it appears
    
    # Approach 2 data
    language_signals: List[str]                  # ["required", "essential", "critical"]
    signal_confidence: float                     # 0.0-1.0 (how confident Approach 2 is)
    
    # Resume matching
    resume_match_level: MatchLevel               # How well it matches resume
    resume_evidence: Optional[str]               # Actual quote from resume
    evidence_confidence: float                   # 0.0-1.0
    
    # Routing
    target_sections: List[str]                   # ['skills', 'experience']
    max_mentions: int                            # Max times to use this keyword
    
    # Metadata
    is_competitor_suppressed: bool = False       # True if competing tech, should be removed
    approached_agree: bool = False               # True if both Approach 1 & 2 agree
    overall_confidence: float = 0.0              # Aggregate confidence 0.0-1.0

@dataclass
class ExtractionResult:
    """Full extraction result from both approaches"""
    must_haves: List[ExtractedKeyword]
    important: List[ExtractedKeyword]
    nice_to_have: List[ExtractedKeyword]
    soft_skills_to_exclude: List[ExtractedKeyword]
    
    approach1_frequency_report: Dict                      # Frequency analysis data
    approach2_semantic_report: Dict                       # Semantic analysis data
    
    total_keywords_extracted: int
    unique_tiers_found: int
    confidence_average: float
    
    jd_structure_analysis: Dict                           # Which sections found, coverage
    resume_validation_summary: Dict                       # Match stats
    
    # For debugging
    skipped_keywords: Dict[str, str]                      # keyword → reason
    conflicts: List[Dict]                                 # Where Approach 1 & 2 disagree

@dataclass
class SectionTarget:
    """Target for placing a keyword in resume"""
    section_name: str                                     # 'skills', 'summary', 'experience'
    max_mentions: int
    rules: List[str]
