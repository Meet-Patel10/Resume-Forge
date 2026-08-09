# ============================================================================
# TASK 13: END-TO-END INTEGRATION TESTS
#
# TASK_13_COMPLETE_SOLUTION.md's proposed E2E tests call helper methods
# (`_extract_keywords`, `_tailor_resume`, `_validate_quality`, `_check_convergence`)
# that are hardcoded stubs returning constants regardless of input
# (`return ['Python', 'Docker', 'AWS']`, `return 85.0`, `return 0.95`) — every
# assertion in that file passes unconditionally, testing nothing about this
# codebase. This file chains the REAL functions instead: extractor → guarantee
# engine → role detection → quality gate, end to end, per persona — using this
# app's real schema and the real evidence-based extraction/guarantee semantics
# confirmed throughout Tasks 8-11 (a JD requirement only becomes a guaranteed
# must-have if the resume already evidences it — see
# docs/CODE_DOCUMENTATION.md#semantickeywordextractor).
#
# This is deliberately a different granularity from tests/test_task_11_solution.py
# ::TestCrossTaskIntegration, which chains exactly TWO components per test. The
# tests below chain three-to-four real components in a single continuous flow
# per persona — closer to what one real /tailor/api/tailor request actually
# does (minus the AI-tailoring call itself, which needs a live provider and is
# out of scope for a fast, offline test).
# ============================================================================

import pytest

from app.extractors.semantic_keyword_extractor import SemanticKeywordExtractor
from app.services.guarantee_engine.must_have_guarantee_engine import MustHaveGuaranteeEngine
from app.validators.role_validator import detect_role_level, validate_role_skill_coherence
from app.validators.quality_validator import run_quality_gates


def _run_pipeline(jd_text, resume_json, resume_evidence_text, confidence_threshold=0.75):
    """The real chain: extract → build registry → guarantee → role-detect →
    coherence-check → quality-gate. Returns everything a caller might want to
    assert on, rather than a single opaque result."""
    extractor = SemanticKeywordExtractor()
    extraction = extractor.extract(jd_text, resume_evidence_text)

    registry = {
        kw.text.lower(): {
            'original_text': kw.text,
            'tier': kw.tier.value,
            'keyword_type': kw.keyword_type.value,
            'confidence': max(kw.overall_confidence, 0.9),
            'sections_target': kw.target_sections,
        }
        for kw in extraction.must_haves + extraction.important
    }

    engine = MustHaveGuaranteeEngine()
    guarantee_result = engine.guarantee_injection_v2(resume_json, registry, confidence_threshold=confidence_threshold)
    guaranteed_resume = guarantee_result['resume_json']

    role = detect_role_level(guaranteed_resume, jd_text)
    coherence = validate_role_skill_coherence(guaranteed_resume, role)
    quality = run_quality_gates(guaranteed_resume, role)

    return {
        'extraction': extraction,
        'guarantee_metadata': guarantee_result['metadata'],
        'guaranteed_resume': guaranteed_resume,
        'role': role,
        'coherence': coherence,
        'quality': quality,
    }


# ============================================================================
# SECTION 1: END-TO-END PERSONA WORKFLOWS
# ============================================================================

class TestE2EWorkflows:

    def test_e2e_junior_developer_workflow(self):
        jd = """
        Junior Python Developer
        Requirements:
        - Required: Python and GitHub experience
        """
        resume = {
            'summary': (
                'Recent computer science graduate with one year of hands-on Python '
                'development experience building small internal tools and useful '
                'automation scripts.'
            ),
            'skills': [{'category': 'Languages', 'items': ['Python']}],
            'experience': [{
                'dates': 'Jan 2023 – Jan 2024',
                'bullets': ['Developed Python scripts and used GitHub for version control.'],
            }],
            'projects': [],
        }
        evidence_text = resume['experience'][0]['bullets'][0]

        result = _run_pipeline(jd, resume, evidence_text)

        assert result['extraction'].must_haves, "Should find at least one must-have"
        assert result['guarantee_metadata']['all_protected_found'] is True
        assert result['role'] == 'junior'
        assert result['coherence']['status'] == 'PASS'
        assert result['quality']['overall_score'] >= 70

    def test_e2e_senior_developer_workflow(self):
        jd = """
        Senior Python Developer
        Requirements:
        - 7+ years of experience
        - Docker, Kubernetes, and AWS mandatory
        - Leadership and mentoring required
        """
        resume = {
            'summary': (
                'Senior Python developer with seven years of experience building '
                'scalable backend systems and successfully leading engineering '
                'teams across multiple products.'
            ),
            'skills': [
                {'category': 'Languages', 'items': ['Python']},
                {'category': 'Tools & Platforms', 'items': ['Docker', 'Kubernetes', 'AWS']},
            ],
            'experience': [{
                'dates': 'Jan 2017 – Jan 2024',
                'bullets': [
                    'Led a team of five engineers designing microservices using Python.',
                    'Deployed services to AWS using Docker and Kubernetes.',
                    'Mentored junior developers on best practices.',
                ],
            }],
            'projects': [],
        }
        evidence_text = ' '.join(resume['experience'][0]['bullets'])

        result = _run_pipeline(jd, resume, evidence_text)

        assert result['role'] == 'senior'
        assert result['guarantee_metadata']['must_have_coverage'] == 1.0
        assert result['coherence']['status'] == 'PASS'
        assert result['quality']['overall_score'] >= 80, (
            f"Senior persona with strong evidence should score high: {result['quality']}"
        )

    def test_e2e_convergence_high_when_resume_has_evidence(self):
        """The real analog of the guide's fictional _check_convergence(): when
        the resume already evidences what the JD needs, must_have_coverage
        should be at/near 100% after the guarantee pass."""
        jd = "Requirements: Python, Docker, and AWS are required for this role."
        resume = {
            'summary': (
                'Backend engineer with strong hands-on experience across Python, '
                'Docker, and AWS in production environments for several years.'
            ),
            'skills': [{'category': 'Languages', 'items': ['Python']}],
            'experience': [{
                'dates': 'Jan 2019 – Jan 2024',
                'bullets': ['Built and deployed Python services on AWS using Docker containers.'],
            }],
            'projects': [],
        }
        evidence_text = resume['experience'][0]['bullets'][0]

        result = _run_pipeline(jd, resume, evidence_text)

        assert result['guarantee_metadata']['must_have_coverage'] >= 0.90

    def test_e2e_quality_gate_fail_on_thin_resume(self):
        """A genuinely thin resume should fail the real quality gate — not
        because we hardcoded 'quality < 80', but because run_quality_gates
        really does flag it."""
        jd = "Senior Python Developer needed with 7+ years experience."
        resume = {
            'summary': 'Dev',
            'skills': [{'category': 'Languages', 'items': ['A']}],
            'experience': [],
            'projects': [],
        }

        extractor = SemanticKeywordExtractor()
        extraction = extractor.extract(jd, resume['summary'])
        role = detect_role_level(resume, jd)
        quality = run_quality_gates(resume, role)

        assert role == 'entry_level'  # no experience entries at all
        assert quality['overall_pass'] is False
        assert quality['summary']['is_valid'] is False


# ============================================================================
# SECTION 2: PRODUCTION SCENARIOS — messy real-world input, chained further
# than tests/test_task_11_solution.py's single-component messy-JD test
# ============================================================================

class TestProductionScenarios:

    def test_messy_jd_with_typos_does_not_break_the_full_chain(self):
        messy_jd = """
        SENIOR PYTHON DEVELOPR

        We are looking for an expirienced Python developer.

        Requirments:
        - 5+ years expierence
        - Docker & Kubernetes expierence
        - AWS a plus

        Salary: $150k-$180k. Location: Remote.
        """
        resume = {
            'summary': (
                'Backend engineer with five years of production experience using '
                'Python, Docker, and Kubernetes across several large-scale projects.'
            ),
            'skills': [{'category': 'Languages', 'items': ['Python']}],
            'experience': [{
                'dates': 'Jan 2019 – Jan 2024',
                'bullets': ['Built backend services with Python, Docker, and Kubernetes.'],
            }],
            'projects': [],
        }
        evidence_text = resume['experience'][0]['bullets'][0]

        # Should not raise despite the typos ("DEVELOPR", "expirienced", "Requirments")
        result = _run_pipeline(messy_jd, resume, evidence_text)

        assert result['guarantee_metadata']['all_protected_found'] is True
        assert 'overall_score' in result['quality']

    def test_incomplete_resume_processes_without_crashing(self):
        resume = {
            'summary': 'Engineer',
            'skills': [{'category': 'Languages', 'items': ['Python']}],
            'experience': [],
            'projects': [],
        }
        # Should not raise — just score low, which is the correct behavior
        quality = run_quality_gates(resume, 'entry_level')
        assert 'overall_score' in quality

    def test_special_characters_survive_the_full_chain(self):
        jd = "Requirements: C++, C#, and Node.js experience preferred."
        resume = {
            'summary': (
                'Systems engineer with strong hands-on experience in C++, C#, and '
                '.NET, plus recent Node.js work on internal tooling projects.'
            ),
            'skills': [{'category': 'Languages', 'items': ['C++', 'C#', '.NET', 'Node.js']}],
            'experience': [{
                'dates': 'Jan 2020 – Jan 2024',
                'bullets': ['Developed systems using C++/C# on Windows and Node.js tooling.'],
            }],
            'projects': [],
        }
        evidence_text = resume['experience'][0]['bullets'][0]

        result = _run_pipeline(jd, resume, evidence_text)
        skills_flat = [i for g in result['guaranteed_resume']['skills'] for i in g['items']]
        assert 'C++' in skills_flat and 'C#' in skills_flat


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
