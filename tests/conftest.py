# ============================================================================
# PYTEST CONFIGURATION & FIXTURES
#
# TASK_11_COMPLETE_SOLUTION.md's proposed conftest.py fixtures assume a
# resume schema this app doesn't use (`skills: List[str]`,
# `experience[].description`). This app's real schema (used everywhere in
# app/routes/tailor.py and app/services/guarantee_engine/) is
# `skills: [{category, items}]` and `experience[].bullets` — the fixtures
# below use the real shape so they're actually usable by real functions,
# not just by other fictional test code.
# ============================================================================

import pytest


@pytest.fixture
def sample_jd():
    """A realistic job description, used by cross-task integration and
    performance tests in tests/test_task_11_solution.py."""
    return """
    Senior Backend Engineer

    Requirements:
    - 5+ years of experience with Python and Docker
    - Required: strong knowledge of Kubernetes and AWS
    - Experience with PostgreSQL and Redis is essential

    Preferred:
    - Familiarity with Terraform and CI/CD pipelines
    - Nice to have: Kafka experience

    Strong communication and leadership skills required.
    """


@pytest.fixture
def sample_resume():
    """A realistic resume in this app's real schema."""
    return {
        'summary': 'Backend engineer with five years of experience building '
                    'scalable distributed systems in Python for production '
                    'environments serving millions of requests.',
        'skills': [
            {'category': 'Languages', 'items': ['Python', 'Java', 'SQL']},
            {'category': 'Tools & Platforms', 'items': ['Git', 'Linux']},
        ],
        'experience': [
            {'bullets': [
                'Built REST APIs with Python serving 1M+ requests per day.',
                'Deployed services using Docker across production environments.',
            ]}
        ],
        'projects': [],
    }


@pytest.fixture
def sample_keywords():
    """Sample must-have/important keyword texts."""
    return ['Python', 'Docker', 'Kubernetes', 'AWS', 'PostgreSQL']
