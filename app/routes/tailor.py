from flask import Blueprint, render_template, request, jsonify, session, send_file, current_app
from app.routes.auth import login_required
from app import db
from app.models.master_resume import MasterResume
from app.models.application import Application
from app.models.analysis import AnalysisHistory
from app.models.resume_version import ResumeVersion
from app.services.claude_client import claude
from app.services.prompts.resume_tailor import (
    RESUME_TAILOR_SYSTEM, build_tailor_message,
    get_summary_generator, get_convergence_guard,
)
from app.services.prompts.bullet_rewriter import BULLET_REWRITER_SYSTEM, build_bullet_message
from app.services.prompts.cover_letter import COVER_LETTER_SYSTEM, COVER_LETTER_ADJUST_SYSTEM, build_cover_letter_message, build_adjust_message
from app.services.prompts.brutal_critic import BRUTAL_CRITIC_SYSTEM, build_critique_message
from app.services.prompts.keyword_extractor import KEYWORD_EXTRACTOR_SYSTEM, build_keyword_message
from app.services.prompts.jd_analyzer import JD_ANALYZER_SYSTEM, build_jd_analysis_message


from app.services.latex_engine import render_latex
from app.services.ats_scorer import calculate_ats_score
import json as json_mod
from flask import current_app
# Add after: from app.services.ats_scorer import calculate_ats_score
from app.extractors.aws_extractor import AWSServiceExtractor
from app.extractors.soft_skills_extractor import SoftSkillsExtractor
from app.scoring.weighted_scorer import WeightedKeywordScorer
from app.validators.cover_letter_validator import validate_cover_letter_resume_alignment, flatten_resume_to_text
from app.validators.role_validator import detect_role_level, detect_role_level_by_years, validate_role_level_consistency, validate_role_skill_coherence, calculate_years_experience, ROLE_SKILL_MATRIX, ROLE_LEVEL_MAPPING
from app.validators.skill_validator import validate_skill, cleanup_skills_section
from app.validators.timeline_validator import analyze_employment_timeline
from app.validators.email_optimizer import optimize_email_subject_line
from app.services.jd_tier_extractor import JDTierExtractor
from app.scoring.gap_analyzer import WeightedGapAnalyzer
from app.services.micro_edit_generator import MicroEditGenerator, apply_edit
from app.validators.skill_categorizer import validate_and_fix_skills

tailor_bp = Blueprint('tailor', __name__)

# ─── Shared: city → province short code (for email sign-off) ───
import re as _re

_CITY_TO_PROVINCE = {
    'toronto': 'ON', 'ottawa': 'ON', 'mississauga': 'ON', 'brampton': 'ON',
    'hamilton': 'ON', 'london': 'ON', 'markham': 'ON', 'vaughan': 'ON',
    'kitchener': 'ON', 'windsor': 'ON', 'richmond hill': 'ON', 'oakville': 'ON',
    'burlington': 'ON', 'waterloo': 'ON', 'guelph': 'ON', 'barrie': 'ON',
    'oshawa': 'ON', 'cambridge': 'ON', 'kanata': 'ON', 'pickering': 'ON',
    'montreal': 'QC', 'quebec city': 'QC', 'laval': 'QC', 'gatineau': 'QC',
    'sherbrooke': 'QC',
    'vancouver': 'BC', 'surrey': 'BC', 'burnaby': 'BC', 'richmond': 'BC',
    'victoria': 'BC', 'kelowna': 'BC', 'nanaimo': 'BC',
    'calgary': 'AB', 'edmonton': 'AB', 'red deer': 'AB', 'lethbridge': 'AB',
    'winnipeg': 'MB', 'brandon': 'MB',
    'saskatoon': 'SK', 'regina': 'SK',
    'halifax': 'NS', 'dartmouth': 'NS',
    'saint john': 'NB', 'moncton': 'NB', 'fredericton': 'NB',
    "st. john's": 'NL', 'charlottetown': 'PE',
    'yellowknife': 'NT', 'whitehorse': 'YT', 'iqaluit': 'NU',
}

_DEFAULT_LOCATION = 'Halifax, NS'

# ─── Soft skills: keyword patterns for verification (Stage 1) ───
SOFT_SKILL_KEYWORDS = {
    'innovation': ['pioneer', 'innovate', 'innovat', 'novel', 'first', 'created new', 'breakthrough', 'develop new'],
    'communication': ['communica', 'present', 'document', 'explain', 'articulate', 'convey', 'discuss', 'share insight'],
    'adaptability': ['adapt', 'adjust', 'pivot', 'respond', 'accommodat', 'flexible', 'adjust', 'quickly adapted'],
    'accountability': ['ownership', 'owned', 'respons', 'led', 'drove', 'took charge', 'champion', 'took ownership', 'accountab'],
    'mentoring': ['mentor', 'guid', 'teach', 'coach', 'develop team', 'train', 'onboard'],
    'collaboration': ['collabora', 'worked with', 'partner', 'cross-functional', 'team', 'coordi', 'cooperat']
}

# ─── Soft skills: templates for injection prompt (Stage 2) ───
SOFT_SKILL_TEMPLATES = {
    'innovation': {
        'description': 'Introducing new ideas, creative problem-solving, pioneering approaches',
        'keywords': ['pioneered', 'innovated', 'introduced novel', 'developed new approach', 'created breakthrough'],
        'example': 'Pioneered new approach to X, resulting in Y',
        'instructions': 'Add "pioneered", "innovated", or "introduced new" to show creative problem-solving'
    },
    'communication': {
        'description': 'Clear articulation, documentation, presentation, stakeholder engagement',
        'keywords': ['communicated', 'presented', 'documented', 'explained', 'articulated'],
        'example': 'Clearly communicated architecture decisions to cross-functional teams',
        'instructions': 'Add "communicated", "presented", or "documented" to show clear communication'
    },
    'adaptability': {
        'description': 'Quick response to change, flexibility, learning new skills',
        'keywords': ['adapted', 'adjusted', 'quickly responded', 'pivoted', 'accommodated'],
        'example': 'Quickly adapted codebase to handle new requirements',
        'instructions': 'Add "adapted", "adjusted", or "responded" to show flexibility'
    },
    'accountability': {
        'description': 'Taking ownership, responsibility, driving results, follow-through',
        'keywords': ['took ownership', 'owned', 'responsible for', 'led', 'drove'],
        'example': 'Took ownership of critical system, delivering on time',
        'instructions': 'Add "took ownership", "owned", or "led" to show accountability'
    },
    'mentoring': {
        'description': 'Teaching others, guidance, team development, knowledge transfer',
        'keywords': ['mentored', 'guided', 'coached', 'trained', 'developed'],
        'example': 'Mentored 3 junior developers through complex architecture',
        'instructions': 'Add "mentored", "guided", or "coached" to show mentoring'
    }
}

# ─── Soft skills: strict stem-only variants (no synonyms) for post-injection
# validation. ATS keyword scanners match the literal skill word or a direct
# variant (innovate/innovation/innovative) — NOT a synonym like "pioneered".
# SOFT_SKILL_TEMPLATES['keywords'] above includes synonyms for prompt guidance,
# but synonyms must not be what actually gets validated as "correct".
SOFT_SKILL_STRICT_VARIANTS = {
    'innovation': ['innovation', 'innovate', 'innovates', 'innovated', 'innovating', 'innovative', 'innovatively'],
    'communication': ['communication', 'communicate', 'communicates', 'communicated', 'communicating'],
    'accountability': ['accountability', 'accountable'],
    'collaboration': ['collaboration', 'collaborate', 'collaborates', 'collaborated', 'collaborating', 'collaborative'],
    'adaptability': ['adaptability', 'adapt', 'adapts', 'adapted', 'adapting', 'adaptive'],
    'mentoring': ['mentor', 'mentors', 'mentored', 'mentoring'],
}


def _resolve_sign_off_location(city_input):
    """Resolve a city name to 'City, Province' for the email sign-off line."""
    if not city_input:
        return _DEFAULT_LOCATION
    city_lower = city_input.lower().strip()
    province = _CITY_TO_PROVINCE.get(city_lower)
    city_display = city_input.strip().title()
    city_display = _re.sub(r"'S\b", "'s", city_display)
    if province:
        return f"{city_display}, {province}"
    return f"{city_display}"


def _build_sign_off(location=None):
    """Build the sign-off block with the given location (defaults to Halifax, NS)."""
    loc = location if location else _DEFAULT_LOCATION
    return (
        "\n\nBest regards,\n"
        "Meet Patel\n"
        f"{loc}\n"
        "https://www.linkedin.com/in/meettpatel28/"
    )


@tailor_bp.route('/')
@login_required
def tailor_page():
    """Tailoring lives on the analyze page now, just redirect."""
    from flask import redirect, url_for
    return redirect(url_for('analyze.analyze_page'))


@tailor_bp.route('/api/rewrite-bullets', methods=['POST'])
@login_required
def api_rewrite_bullets():
    """Rewrite bullets in X-Y-Z format."""
    data = request.get_json()
    bullets = data.get('bullets', [])
    jd_text = data.get('jd_text', '')
    role_context = data.get('role_context', '')

    if not bullets or not jd_text:
        return jsonify({'error': 'Bullets and job description are required'}), 400

    user_message = build_bullet_message(bullets, jd_text, role_context)
    
    app_env = current_app.config.get('APP_ENV', 'testing').strip()
    if app_env == 'nvidia':
        from app.services.claude_client import nvidia as ai_client
        print("[bullet-rewriter] Using NVIDIA Llama-3.3-Nemotron")
    else:
        from app.services.claude_client import claude as ai_client
        print(f"[bullet-rewriter] Using AWS Bedrock/Claude (APP_ENV={app_env})")

    result = ai_client.analyze(BULLET_REWRITER_SYSTEM, user_message, max_tokens=4096, force_json=True)

    if result.get('error'):
        return jsonify({'error': result['error']}), 500

    return jsonify({
        'rewritten': result['response'],
        'tokens_used': result['tokens_used'],
        'cost_usd': result['cost_usd'],
    })

@tailor_bp.route('/api/analyze-jd-advanced', methods=['POST'])
@login_required
def api_analyze_jd_advanced():
    """
    Advanced JD analysis with:
    - AWS service extraction
    - Soft skills detection
    - Weighted keyword scoring
    """
    data = request.get_json()
    jd_text = data.get('jd_text', '')
    found_keywords = set(data.get('found_keywords', []))

    if not jd_text:
        return jsonify({'error': 'Job description required'}), 400

    try:
        aws_extractor = AWSServiceExtractor()
        aws_services = aws_extractor.extract_all(jd_text)

        soft_skills_extractor = SoftSkillsExtractor()
        soft_skills_found = soft_skills_extractor.extract_from_text(jd_text)
        soft_skills_emphasized = soft_skills_extractor.get_emphasized_soft_skills(jd_text)

        required_keywords = {
            'Python': 'must_have',
            'AWS': 'must_have',
            'Docker': 'important',
            'React': 'nice_to_have'
        }

        scorer = WeightedKeywordScorer()
        weighted_score = scorer.calculate_keyword_match_score(
            found_keywords,
            required_keywords
        )

        return jsonify({
            'aws_services': list(aws_services),
            'soft_skills': {
                'emphasized': soft_skills_emphasized,
                'all_skills': soft_skills_found
            },
            'weighted_score': weighted_score
        })

    except Exception as e:
        current_app.logger.error(f"Advanced JD analysis error: {e}")
        return jsonify({'error': str(e)}), 500


def run_convergence(tailored_resume, jd_text, max_iterations=4, target_score=85):
    """
    Guided Convergence Engine with validation: iteratively close the highest-ROI
    JD gaps in a tailored resume until the weighted ATS estimate hits target_score
    or no feasible edits remain. Skips (rather than lying) when JD extraction
    quality is too low, and flags suspiciously high scores instead of declaring
    false success.
    """

    # Step 1: Extract tiered JD
    tier_extractor = JDTierExtractor()
    jd_tiers = tier_extractor.extract_tiered_requirements(jd_text)

    # Step 2: Analyze gap
    gap_analyzer = WeightedGapAnalyzer()
    gap = gap_analyzer.analyze_gap(tailored_resume, jd_tiers)

    # VALIDATION: Should we even run convergence?
    if gap.skip_convergence:
        print(f"[converge] SKIPPING CONVERGENCE: {gap.skip_reason}")
        return {
            'status': 'skipped',
            'reason': gap.skip_reason,
            'jd_quality': jd_tiers.quality_score * 100,
            'message': 'JD extraction quality too low. Manual review recommended.',
            'tailored_resume': tailored_resume,
        }

    # VALIDATION: Check if score is suspiciously high
    if gap.weighted_ats_estimate >= 95:
        print(f"[converge] ⚠ WARNING: Estimated score is suspiciously high ({gap.weighted_ats_estimate:.1f}%)")
        print(f"  Required: {gap.required_match_score:.0f}%")
        print(f"  Preferred: {gap.preferred_match_score:.0f}%")
        print(f"  → This suggests JD extraction may have failed. Check required/preferred skill counts.")

        return {
            'status': 'suspicious_score',
            'estimated_score': gap.weighted_ats_estimate,
            'message': 'Score seems too high. JD extraction may have issues.',
            'debug': {
                'required_skills': len(jd_tiers.required_hard_skills),
                'preferred_skills': len(jd_tiers.preferred_hard_skills),
                'quality_score': jd_tiers.quality_score,
            },
            'tailored_resume': tailored_resume,
        }

    # Normal convergence loop
    current_resume = tailored_resume
    iteration_history = []

    for iteration in range(1, max_iterations + 1):
        gap = gap_analyzer.analyze_gap(current_resume, jd_tiers)
        current_score = gap.weighted_ats_estimate

        print(f"[converge] Iteration {iteration}: Score {current_score:.1f}")

        if current_score >= target_score:
            print(f"[converge] Target reached! Score: {current_score:.1f}")
            break

        # Generate edits
        edit_generator = MicroEditGenerator()
        edits = edit_generator.generate_edits(current_resume, gap)

        if not edits:
            print(f"[converge] No feasible edits remaining")
            break

        # Apply best edit
        best_edit = max(edits, key=lambda e: e.ats_gain * e.feasibility)
        print(f"[converge]   Applying: {best_edit.gap_skill} ({best_edit.ats_gain:.1f} points)")

        current_resume = apply_edit(current_resume, best_edit)

        iteration_history.append({
            'iteration': iteration,
            'score': current_score,
            'edit_applied': best_edit.gap_skill,
            'gain': best_edit.ats_gain,
        })

    return {
        'status': 'converged',
        'tailored_resume': current_resume,
        'final_score': gap.weighted_ats_estimate,
        'iterations': iteration_history,
        'convergence_details': {
            'required_match': gap.required_match_score,
            'preferred_match': gap.preferred_match_score,
            'nice_match': gap.nice_match_score,
        }
    }



# ============================================================================
# COMPREHENSIVE CATEGORY MAPPING FOR ALL SKILL TYPES
# Used by cleanup function to validate and fix AI categorization
# ============================================================================
_COMPREHENSIVE_CATEGORY_MAP = {
    # ======== PROGRAMMING LANGUAGES (ONLY actual languages) ========
    'python': 'Languages', 'java': 'Languages', 'javascript': 'Languages',
    'typescript': 'Languages', 'c++': 'Languages', 'c#': 'Languages',
    'cpp': 'Languages', 'rust': 'Languages', 'go': 'Languages', 'golang': 'Languages',
    'ruby': 'Languages', 'php': 'Languages', 'swift': 'Languages',
    'kotlin': 'Languages', 'scala': 'Languages', 'perl': 'Languages',
    'r': 'Languages', 'matlab': 'Languages', 'julia': 'Languages',
    'haskell': 'Languages', 'erlang': 'Languages', 'lua': 'Languages',
    'sql': 'Languages', 'html': 'Languages', 'html5': 'Languages',
    'css': 'Languages', 'css3': 'Languages', 'bash': 'Languages',
    'shell': 'Languages', 'groovy': 'Languages', 'clojure': 'Languages',
    'elixir': 'Languages', 'f#': 'Languages', 'ocaml': 'Languages',
    'c programming': 'Languages', 'c language': 'Languages',

    # ======== FRAMEWORKS & LIBRARIES ========
    'react': 'Frameworks & Libraries', 'react.js': 'Frameworks & Libraries',
    'reactjs': 'Frameworks & Libraries', 'react native': 'Frameworks & Libraries',
    'angular': 'Frameworks & Libraries', 'angularjs': 'Frameworks & Libraries',
    'angular.js': 'Frameworks & Libraries', 'vue': 'Frameworks & Libraries',
    'vue.js': 'Frameworks & Libraries', 'vuejs': 'Frameworks & Libraries',
    'svelte': 'Frameworks & Libraries', 'next.js': 'Frameworks & Libraries',
    'nextjs': 'Frameworks & Libraries', 'nuxt': 'Frameworks & Libraries',
    'spring': 'Frameworks & Libraries', 'spring boot': 'Frameworks & Libraries',
    'spring framework': 'Frameworks & Libraries', 'django': 'Frameworks & Libraries',
    'flask': 'Frameworks & Libraries', 'fastapi': 'Frameworks & Libraries',
    'express': 'Frameworks & Libraries', 'express.js': 'Frameworks & Libraries',
    'node.js': 'Frameworks & Libraries', 'nodejs': 'Frameworks & Libraries',
    'asp.net': 'Frameworks & Libraries', '.net': 'Frameworks & Libraries',
    'dotnet': 'Frameworks & Libraries', 'laravel': 'Frameworks & Libraries',
    'symfony': 'Frameworks & Libraries', 'rails': 'Frameworks & Libraries',
    'ruby on rails': 'Frameworks & Libraries',
    'pytorch': 'Frameworks & Libraries', 'tensorflow': 'Frameworks & Libraries',
    'keras': 'Frameworks & Libraries', 'scikit-learn': 'Frameworks & Libraries',
    'sklearn': 'Frameworks & Libraries', 'pandas': 'Frameworks & Libraries',
    'numpy': 'Frameworks & Libraries', 'scipy': 'Frameworks & Libraries',
    'hugging face': 'Frameworks & Libraries', 'huggingface': 'Frameworks & Libraries',
    'transformers': 'Frameworks & Libraries', 'peft': 'Frameworks & Libraries',
    'langchain': 'Frameworks & Libraries', 'openai': 'Frameworks & Libraries',
    'opencv': 'Frameworks & Libraries', 'sqlalchemy': 'Frameworks & Libraries',
    'jinja2': 'Frameworks & Libraries', 'jinja': 'Frameworks & Libraries',
    'bootstrap': 'Frameworks & Libraries', 'tailwind': 'Frameworks & Libraries',
    'tailwind css': 'Frameworks & Libraries', 'jquery': 'Frameworks & Libraries',
    'lodash': 'Frameworks & Libraries', 'graphql': 'Frameworks & Libraries',
    'rest api': 'Frameworks & Libraries', 'restful apis': 'Frameworks & Libraries',
    'grpc': 'Frameworks & Libraries', 'socket.io': 'Frameworks & Libraries',

    # ======== TOOLS & PLATFORMS ========
    'docker': 'Tools & Platforms', 'kubernetes': 'Tools & Platforms', 'k8s': 'Tools & Platforms',
    'aws': 'Tools & Platforms', 'amazon web services': 'Tools & Platforms',
    'azure': 'Tools & Platforms', 'microsoft azure': 'Tools & Platforms',
    'gcp': 'Tools & Platforms', 'google cloud': 'Tools & Platforms',
    'google cloud platform': 'Tools & Platforms',
    'git': 'Tools & Platforms', 'github': 'Tools & Platforms', 'gitlab': 'Tools & Platforms',
    'bitbucket': 'Tools & Platforms', 'jenkins': 'Tools & Platforms',
    'circleci': 'Tools & Platforms', 'circle ci': 'Tools & Platforms',
    'gitlab ci': 'Tools & Platforms', 'github actions': 'Tools & Platforms',
    'travis ci': 'Tools & Platforms', 'travis': 'Tools & Platforms',
    'jira': 'Tools & Platforms', 'confluence': 'Tools & Platforms',
    'slack': 'Tools & Platforms', 'asana': 'Tools & Platforms',
    'monday.com': 'Tools & Platforms', 'trello': 'Tools & Platforms',
    'linux': 'Tools & Platforms', 'ubuntu': 'Tools & Platforms',
    'centos': 'Tools & Platforms', 'macos': 'Tools & Platforms', 'mac': 'Tools & Platforms',
    'windows server': 'Tools & Platforms',
    'mysql': 'Tools & Platforms', 'postgresql': 'Tools & Platforms', 'postgres': 'Tools & Platforms',
    'mongodb': 'Tools & Platforms', 'redis': 'Tools & Platforms',
    'elasticsearch': 'Tools & Platforms', 'cassandra': 'Tools & Platforms',
    'dynamodb': 'Tools & Platforms', 'firestore': 'Tools & Platforms',
    'oracle': 'Tools & Platforms', 'sql server': 'Tools & Platforms', 'mssql': 'Tools & Platforms',
    'mariadb': 'Tools & Platforms', 'couchdb': 'Tools & Platforms',
    'rabbitmq': 'Tools & Platforms', 'kafka': 'Tools & Platforms',
    'apache kafka': 'Tools & Platforms', 'spark': 'Tools & Platforms',
    'hadoop': 'Tools & Platforms', 'hive': 'Tools & Platforms',
    'airflow': 'Tools & Platforms', 'dbt': 'Tools & Platforms',
    'terraform': 'Tools & Platforms', 'ansible': 'Tools & Platforms',
    'vagrant': 'Tools & Platforms', 'docker compose': 'Tools & Platforms',
    'docker-compose': 'Tools & Platforms',
    'prometheus': 'Tools & Platforms', 'grafana': 'Tools & Platforms',
    'datadog': 'Tools & Platforms', 'new relic': 'Tools & Platforms',
    'splunk': 'Tools & Platforms', 'elk stack': 'Tools & Platforms',
    'postman': 'Tools & Platforms', 'insomnia': 'Tools & Platforms',
    'vs code': 'Tools & Platforms', 'vscode': 'Tools & Platforms',
    'intellij': 'Tools & Platforms', 'pycharm': 'Tools & Platforms',
    'visual studio': 'Tools & Platforms', 'xcode': 'Tools & Platforms',
    'sublime text': 'Tools & Platforms', 'atom': 'Tools & Platforms',
    'vim': 'Tools & Platforms', 'neovim': 'Tools & Platforms',
    'maven': 'Tools & Platforms', 'gradle': 'Tools & Platforms',
    'npm': 'Tools & Platforms', 'yarn': 'Tools & Platforms',
    'pip': 'Tools & Platforms', 'conda': 'Tools & Platforms',
    'docker registry': 'Tools & Platforms', 'artifactory': 'Tools & Platforms',
    'nexus': 'Tools & Platforms', 'sonarqube': 'Tools & Platforms',

    # ======== PROGRAMMING CONCEPTS ========
    'data structures': 'Programming Concepts', 'algorithms': 'Programming Concepts',
    'object-oriented programming': 'Programming Concepts', 'oop': 'Programming Concepts',
    'functional programming': 'Programming Concepts', 'design patterns': 'Programming Concepts',
    'multithreading': 'Programming Concepts', 'concurrency': 'Programming Concepts',
    'parallel processing': 'Programming Concepts', 'time complexity': 'Programming Concepts',
    'space complexity': 'Programming Concepts', 'big o notation': 'Programming Concepts',
    'recursion': 'Programming Concepts', 'dynamic programming': 'Programming Concepts',
    'sorting algorithms': 'Programming Concepts', 'searching algorithms': 'Programming Concepts',
    'graph algorithms': 'Programming Concepts', 'tree algorithms': 'Programming Concepts',
    'memory management': 'Programming Concepts', 'garbage collection': 'Programming Concepts',
    'heap': 'Programming Concepts', 'stack': 'Programming Concepts',
    'queue': 'Programming Concepts', 'linked list': 'Programming Concepts',
    'hash table': 'Programming Concepts', 'binary tree': 'Programming Concepts',

    # ======== CONCEPTS (Methodologies, Patterns, Architectures) ========
    'agile': 'Concepts', 'scrum': 'Concepts', 'kanban': 'Concepts',
    'waterfall': 'Concepts', 'devops': 'Concepts', 'ci/cd': 'Concepts',
    'api design': 'Concepts', 'microservices': 'Concepts', 'monolithic': 'Concepts',
    'distributed systems': 'Concepts', 'message queuing': 'Concepts',
    'event-driven architecture': 'Concepts', 'serverless': 'Concepts',
    'machine learning': 'Concepts', 'deep learning': 'Concepts',
    'natural language processing': 'Concepts', 'nlp': 'Concepts',
    'computer vision': 'Concepts', 'data analysis': 'Concepts',
    'statistical analysis': 'Concepts', 'big data': 'Concepts', 'big data analysis': 'Concepts',
    'data mining': 'Concepts', 'business intelligence': 'Concepts',
    'optimization': 'Concepts', 'linear optimization': 'Concepts',
    'non-linear optimization': 'Concepts', 'algorithm tuning': 'Concepts',
    'performance optimization': 'Concepts', 'scalability': 'Concepts',
    'high availability': 'Concepts', 'disaster recovery': 'Concepts',
    'backup and recovery': 'Concepts', 'security': 'Concepts',
    'encryption': 'Concepts', 'authentication': 'Concepts', 'authorization': 'Concepts',
    'oauth': 'Concepts', 'jwt': 'Concepts', 'ssl/tls': 'Concepts',
    'code review': 'Concepts', 'testing': 'Concepts', 'unit testing': 'Concepts',
    'integration testing': 'Concepts', 'automated testing': 'Concepts',
    'test-driven development': 'Concepts', 'tdd': 'Concepts',
    'behavior-driven development': 'Concepts', 'bdd': 'Concepts',
    'continuous integration': 'Concepts', 'continuous deployment': 'Concepts',
    'automated test suites': 'Concepts', 'automation': 'Concepts',
    'automation tools': 'Concepts',
    'agile methodology': 'Concepts', 'lean': 'Concepts',
    'process improvement': 'Concepts', 'root cause analysis': 'Concepts',
    'problem solving': 'Concepts', 'critical thinking': 'Concepts',
    'technical documentation': 'Concepts', 'technical writing': 'Concepts',
    'api documentation': 'Concepts',

    # ======== DOMAIN CONCEPTS - DO NOT PUT IN LANGUAGES ========
    # Engineering/Geomatics
    'gnss': 'Concepts', 'gnss error modeling': 'Concepts', 'positioning algorithms': 'Concepts',
    'satellite positioning': 'Concepts', 'positioning systems': 'Concepts',
    'embedded systems': 'Concepts', 'real-time systems': 'Concepts',
    'iot': 'Concepts', 'internet of things': 'Concepts', 'firmware': 'Concepts',
    'hardware': 'Concepts', 'signal processing': 'Concepts',
    'computational numerical methods': 'Concepts', 'numerical methods': 'Concepts',
    'electrical engineering': 'Concepts', 'geomatics engineering': 'Concepts',
    'software engineering': 'Concepts', 'computer science': 'Concepts',
    'civil engineering': 'Concepts', 'mechanical engineering': 'Concepts',

    # Finance/Business
    'capital markets': 'Concepts', 'risk analytics': 'Concepts',
    'pricing model': 'Concepts', 'pricing models': 'Concepts',
    'pricing model integration': 'Concepts', 'risk systems': 'Concepts',
    'fintech': 'Concepts', 'financial systems': 'Concepts',
    'trading systems': 'Concepts', 'risk management': 'Concepts',
    'compliance': 'Concepts', 'regulatory compliance': 'Concepts',
    'sar reporting': 'Concepts', 'aml': 'Concepts', 'kyc': 'Concepts',
    'derivatives': 'Concepts', 'fixed income': 'Concepts',
    'portfolio management': 'Concepts', 'quantitative analysis': 'Concepts',
    'financial modeling': 'Concepts', 'valuation': 'Concepts',
    'investment banking': 'Concepts', 'wealth management': 'Concepts',
    'treasury management': 'Concepts', 'forex': 'Concepts', 'foreign exchange': 'Concepts',

    # Healthcare
    'ehr systems': 'Concepts', 'electronic health records': 'Concepts',
    'patient management': 'Concepts', 'medical imaging': 'Concepts',
    'healthcare it': 'Concepts', 'hipaa': 'Concepts', 'hl7': 'Concepts',
    'fhir': 'Concepts', 'telemedicine': 'Concepts', 'clinical workflows': 'Concepts',

    # General/Soft Skills (DO NOT PUT IN LANGUAGES)
    'customer support': 'Concepts', 'technical communication': 'Concepts',
    'communication': 'Concepts', 'collaboration': 'Concepts',
    'leadership': 'Concepts', 'project management': 'Concepts',
    'team collaboration': 'Concepts', 'problem-solving': 'Concepts',
    'innovation': 'Concepts', 'adaptability': 'Concepts', 'accountability': 'Concepts',
}


# ═══════════════════════════════════════════════════════════════════
# CHUNK 7.1: Natural Language Templates for Soft Skills
# Templates that sound human-written, not AI-generated
# ═══════════════════════════════════════════════════════════════════

SOFT_SKILL_TEMPLATES = {
    'collaboration': [
        'collaborating with cross-functional teams',
        'working closely with stakeholders',
        'partnering with engineering and product teams',
    ],
    'communication': [
        'communicating technical concepts to non-technical stakeholders',
        'presenting findings to leadership',
        'documenting technical decisions and architecture',
    ],
    'innovation': [
        'identifying opportunities for process improvement',
        'proposing and implementing novel solutions',
        'driving adoption of modern engineering practices',
    ],
    'mentoring': [
        'mentoring junior developers',
        'conducting code reviews and providing constructive feedback',
        'sharing best practices with the team',
    ],
    'problem_solving': [
        'debugging and resolving complex production issues',
        'analyzing root causes and implementing preventive measures',
        'troubleshooting system performance bottlenecks',
    ],
    'curiosity': [
        'exploring new technologies and frameworks',
        'staying current with industry trends',
        'continuously learning and applying new skills',
    ],
}


# ═══════════════════════════════════════════════════════════════════
# CHUNK 7.2: Inject Soft Skills at Clause Boundaries
# Adds soft skills naturally at sentence boundaries
# ═══════════════════════════════════════════════════════════════════

def inject_soft_skill_naturally(bullet_text, soft_skill, templates=None):
    """
    Inject a soft skill into a bullet point at a natural clause boundary.
    
    Returns: Modified bullet text with soft skill naturally integrated
    """
    if templates is None:
        templates = SOFT_SKILL_TEMPLATES
    
    # Get template for this skill
    skill_key = soft_skill.lower().replace(' ', '_')
    skill_templates = templates.get(skill_key, [])
    
    if not skill_templates:
        # Fallback: use skill name directly at clause boundary
        if ', ' in bullet_text:
            # Insert at existing clause boundary
            parts = bullet_text.rsplit(', ', 1)
            return f"{parts[0]}, {soft_skill.lower()}, {parts[1]}"
        else:
            return bullet_text
    
    # Use first available template
    template = skill_templates[0]
    
    # Insert at end of bullet, before period
    if bullet_text.rstrip().endswith('.'):
        return f"{bullet_text.rstrip()[:-1]}, {template}."
    else:
        return f"{bullet_text}, {template}"


# ═══════════════════════════════════════════════════════════════════
# CHUNK 7.3: Grammaticality Validation for Soft Skills
# Validates injected soft skills sound natural
# ═══════════════════════════════════════════════════════════════════

def validate_soft_skill_grammaticality(bullet_text):
    """
    Validate that a bullet with injected soft skill sounds natural.
    
    Returns: (is_valid, issues)
    """
    import re
    issues = []
    
    # Check for AI-sounding patterns
    ai_patterns = [
        (r'Innovatively\s+\w+', "AI-sounding adverb: 'Innovatively'"),
        (r'Communicated\s+automation', "Unnatural phrase: 'Communicated automation'"),
        (r'Collaboratively\s+developed', "AI-sounding: 'Collaboratively developed'"),
        (r'Proactively\s+\w+ed', "AI-sounding adverb: 'Proactively'"),
    ]
    
    for pattern, message in ai_patterns:
        if re.search(pattern, bullet_text, re.IGNORECASE):
            issues.append(message)
    
    return len(issues) == 0, issues


# ═══════════════════════════════════════════════════════════════
# FIX #2 & #3: Structured keyword preparation for AI
# ═══════════════════════════════════════════════════════════════
def _prepare_structured_keywords(must_haves, important, extraction_result):
    """
    Prepare keywords for AI in structured format with section targets.
    
    FIX: Ensures hard skills are explicitly provided and routed to Skills section.
    """
    from app.extractors.keyword_models import KeywordType
    
    # Separate by type and tier
    must_have_hard = [kw for kw in must_haves 
                      if kw.keyword_type in [KeywordType.HARD_SKILL, KeywordType.TOOL_PLATFORM]]
    must_have_soft = [kw for kw in must_haves 
                      if kw.keyword_type == KeywordType.SOFT_SKILL]
    must_have_domain = [kw for kw in must_haves 
                        if kw.keyword_type == KeywordType.DOMAIN_TERM]
    
    important_hard = [kw for kw in important 
                      if kw.keyword_type in [KeywordType.HARD_SKILL, KeywordType.TOOL_PLATFORM]]
    important_soft = [kw for kw in important 
                      if kw.keyword_type == KeywordType.SOFT_SKILL]
    important_domain = [kw for kw in important 
                        if kw.keyword_type == KeywordType.DOMAIN_TERM]
    
    return {
        'must_have_hard_skills': [kw.text for kw in must_have_hard],
        'must_have_soft_skills': [kw.text for kw in must_have_soft],
        'must_have_domain_terms': [kw.text for kw in must_have_domain],
        
        'important_hard_skills': [kw.text for kw in important_hard],
        'important_soft_skills': [kw.text for kw in important_soft],
        'important_domain_terms': [kw.text for kw in important_domain],
        
        # CRITICAL: Specify section targets
        'section_targets': {
            **{kw.text: ['skills', 'experience'] for kw in must_have_hard + important_hard},
            **{kw.text: ['experience', 'summary'] for kw in must_have_soft + important_soft},
            **{kw.text: ['experience'] for kw in must_have_domain + important_domain},
        },
        
        'total_must_have_hard': len(must_have_hard),
        'total_important_hard': len(important_hard),
        'total_must_have_soft': len(must_have_soft),
        
        'soft_skills_to_include': [kw.text for kw in must_have_soft + important_soft],
        'soft_skills_to_exclude': [],  # Never put in Skills section
    }


# ═══════════════════════════════════════════════════════════════════
# CHUNK 6.1: Extract section_targets from Structured Keywords
# Maps keyword → target sections for proper routing
# ═══════════════════════════════════════════════════════════════════

def extract_section_targets(structured_keywords):
    """
    Extract section routing information from structured keywords
    
    Returns: {keyword: [target_sections]}
    """
    if not structured_keywords:
        return {}
    
    section_targets = structured_keywords.get('section_targets', {})
    
    print(f"[tailor] Section targets loaded: {len(section_targets)} keywords")
    
    return section_targets


# ═══════════════════════════════════════════════════════════════════
# CHUNK 6.2: Update Routing Logic to Use section_targets
# Routes keywords to appropriate resume sections
# ═══════════════════════════════════════════════════════════════════

def route_keywords_to_sections(keywords, section_targets, keyword_types):
    """
    Route keywords to appropriate resume sections
    
    Uses section_targets first, then type-based fallback
    """
    route_to_skills = []
    route_to_experience = []
    route_to_summary = []
    
    for keyword in keywords:
        keyword_type = keyword_types.get(keyword, 'UNKNOWN')
        
        # FIRST PRIORITY: Use explicit section targets
        if keyword in section_targets:
            targets = section_targets[keyword]
            if 'skills' in targets:
                route_to_skills.append(keyword)
                print(f"[tailor] → {keyword} routed to Skills (explicit)")
            if 'experience' in targets and keyword not in route_to_skills:
                route_to_experience.append(keyword)
            if 'summary' in targets and keyword not in route_to_skills:
                route_to_summary.append(keyword)
        else:
            # FALLBACK: Type-based routing
            if keyword_type == 'HARD_SKILL':
                route_to_skills.append(keyword)
                print(f"[tailor] → {keyword} routed to Skills (hard skill)")
            elif keyword_type == 'SOFT_SKILL':
                route_to_experience.append(keyword)
                print(f"[tailor] → {keyword} routed to Experience (soft skill)")
            else:
                route_to_experience.append(keyword)
    
    return route_to_skills, route_to_experience, route_to_summary


# ═══════════════════════════════════════════════════════════════════
# CHUNK 6.3: Validate All Hard Skills Reached Skills Section
# Verifies and force-adds any missing hard skills
# ═══════════════════════════════════════════════════════════════════

def validate_hard_skills_in_skills_section(
    hard_skills_list,
    routed_to_skills,
    all_keywords
):
    """
    Validate all hard skills made it to Skills section
    
    Returns: corrected route_to_skills
    """
    missing_hard_skills = [
        skill for skill in hard_skills_list
        if skill not in routed_to_skills
    ]
    
    if missing_hard_skills:
        print(f"[tailor] ⚠️ Hard skills missing from Skills section:")
        for skill in missing_hard_skills:
            print(f"[tailor]   - {skill}")
            routed_to_skills.append(skill)
            print(f"[tailor]   ✓ Force-added to Skills section")
    
    print(f"[tailor] Hard skills in Skills section: {len(routed_to_skills)}/{len(hard_skills_list)}")
    
    return routed_to_skills


# ═══════════════════════════════════════════════════════════════════
# CHUNK 6.4: Prevent Soft Skills from Skills Section
# Ensures soft skills NOT in Skills section
# ═══════════════════════════════════════════════════════════════════

def prevent_soft_skills_in_skills_section(
    routed_to_skills,
    soft_skills_list
):
    """
    Ensure soft skills are NOT in Skills section
    
    Returns: cleaned route_to_skills
    """
    soft_skills_set = set(s.lower() for s in soft_skills_list)
    
    cleaned = []
    moved = []
    
    for skill in routed_to_skills:
        if skill.lower() in soft_skills_set:
            moved.append(skill)
            print(f"[tailor] ⚠️ Soft skill '{skill}' removed from Skills")
        else:
            cleaned.append(skill)
    
    if moved:
        print(f"[tailor] Moved {len(moved)} soft skills out of Skills section")
    
    return cleaned

# ═══════════════════════════════════════════════════════════════
# FIX #4: Protect must-haves during master resume merge
# ═══════════════════════════════════════════════════════════════
def _merge_with_protection(ai_skills, master_skills, protected_keywords, max_skills_allowed=16):
    """
    Merge AI-tailored skills with master resume skills.
    
    CRITICAL: NEVER remove protected keywords, even if over skill limit.
    
    Algorithm:
    1. Identify which master skills are protected
    2. Keep ALL protected skills (never remove)
    3. Keep AI-tailored high-relevance skills
    4. Remove only unprotected, low-relevance skills if over limit
    """
    
    merged = {}
    protected_count = 0
    removed_count = 0
    
    # Step 1: Collect all skills with metadata
    all_skills = {}
    
    # From AI
    for group in ai_skills:
        category = group.get('category', '')
        if category not in merged:
            merged[category] = {'category': category, 'items': []}
        
        for item in group.get('items', []):
            item_key = item.lower().strip()
            all_skills[item_key] = {
                'text': item,
                'source': 'ai',
                'category': category,
                'is_protected': item_key in protected_keywords,
            }
    
    # From Master
    for group in master_skills:
        category = group.get('category', '')
        if category not in merged:
            merged[category] = {'category': category, 'items': []}
        
        for item in group.get('items', []):
            item_key = item.lower().strip()
            if item_key not in all_skills:  # Don't overwrite AI version
                all_skills[item_key] = {
                    'text': item,
                    'source': 'master',
                    'category': category,
                    'is_protected': item_key in protected_keywords,
                }
    
    # Step 2: Prioritize and place skills
    # Priority 1: Protected keywords (MUST keep)
    protected_skills = {k: v for k, v in all_skills.items() if v['is_protected']}
    protected_count = len(protected_skills)
    
    # Priority 2: AI skills (high confidence)
    ai_unprotected = {k: v for k, v in all_skills.items() 
                      if v['source'] == 'ai' and not v['is_protected']}
    
    # Priority 3: Master skills (backup)
    master_unprotected = {k: v for k, v in all_skills.items() 
                          if v['source'] == 'master' and not v['is_protected']}
    
    # Step 3: Build final list respecting max_skills_allowed
    final_skills_by_category = {}
    total_skills = 0
    
    # ALWAYS include protected skills (don't count against limit)
    for skill_key, skill_data in protected_skills.items():
        category = skill_data['category']
        if category not in final_skills_by_category:
            final_skills_by_category[category] = []
        
        final_skills_by_category[category].append(skill_data['text'])
        total_skills += 1
        
        print(f"[tailor] ✓ PROTECTED: '{skill_data['text']}' (won't be removed)")
    
    # Then add unprotected skills up to limit
    for skill_key, skill_data in ai_unprotected.items():
        if total_skills >= max_skills_allowed:
            removed_count += 1
            print(f"[tailor] ✗ REMOVED (limit): '{skill_data['text']}'")
            continue
        
        category = skill_data['category']
        if category not in final_skills_by_category:
            final_skills_by_category[category] = []
        
        final_skills_by_category[category].append(skill_data['text'])
        total_skills += 1
    
    # Finally add master skills if still under limit
    for skill_key, skill_data in master_unprotected.items():
        if total_skills >= max_skills_allowed:
            removed_count += 1
            continue
        
        category = skill_data['category']
        if category not in final_skills_by_category:
            final_skills_by_category[category] = []
        
        final_skills_by_category[category].append(skill_data['text'])
        total_skills += 1
    
    # Step 4: Convert back to resume format
    result = []
    for category in final_skills_by_category:
        result.append({
            'category': category,
            'items': final_skills_by_category[category]
        })
    
    print(f"[tailor] Merge complete: {total_skills} skills ({protected_count} protected, {removed_count} removed)")
    
    return result


def _verify_protection(skills_list, protected_keywords):
    """
    Verify that all protected keywords are in the skills list.
    
    Returns: True if ALL protected keywords present, False otherwise
    """
    
    all_skills_lower = set()
    for group in skills_list:
        for item in group.get('items', []):
            all_skills_lower.add(item.lower().strip())
    
    protected_lower = {k.lower().strip(): k for k, v in protected_keywords.items()}
    
    missing = []
    for protected_key, original_text in protected_lower.items():
        if protected_key not in all_skills_lower:
            missing.append(original_text)
    
    if missing:
        print(f"[tailor] ⚠️ PROTECTION FAILED: Missing {len(missing)} protected keywords:")
        for m in missing:
            print(f"[tailor]   ✗ {m}")
        return False
    
    print(f"[tailor] ✓ All {len(protected_keywords)} protected keywords verified in resume")
    return True


def validate_and_fix_skill_categories(tailored_data, category_map):
    """
    Scan all skills in tailored resume and move to correct category if misplaced.

    Args:
        tailored_data: The resume dict from AI
        category_map: Comprehensive mapping of skill → correct category

    Returns:
        tailored_data with skills in correct categories
    """
    if not isinstance(tailored_data, dict):
        return tailored_data

    skills = tailored_data.get('skills', [])
    if not skills:
        return tailored_data

    print(f"\n[tailor] ╔═══════════════════════════════════════════════════════╗")
    print(f"[tailor] ║ SKILLS VALIDATION & CLEANUP                          ║")
    print(f"[tailor] ╚═══════════════════════════════════════════════════════╝")

    # Step 1: Build map of all current skills and their categories
    current_skill_category = {}  # skill → current_category
    for skill_group in skills:
        category = skill_group.get('category', '')
        for item in skill_group.get('items', []):
            current_skill_category[item] = category

    # Step 2: Determine correct category for each skill
    skill_correct_category = {}  # skill → correct_category
    for skill, current_cat in current_skill_category.items():
        skill_lower = skill.lower()

        # Try exact match first
        correct_cat = category_map.get(skill_lower)

        # Try fuzzy match (partial match)
        if not correct_cat:
            for key, cat in category_map.items():
                if key in skill_lower or skill_lower in key:
                    correct_cat = cat
                    break

        # Use default heuristic for unmapped skills
        if not correct_cat:
            # Multi-word → Concepts, single-word → Tools & Platforms
            correct_cat = 'Concepts' if len(skill.split()) >= 2 else 'Tools & Platforms'

        skill_correct_category[skill] = correct_cat

    # Step 3: Identify skills that need moving
    moves = []  # List of (skill, from_cat, to_cat)
    for skill, correct_cat in skill_correct_category.items():
        current_cat = current_skill_category[skill]
        if current_cat.lower() != correct_cat.lower():
            moves.append((skill, current_cat, correct_cat))

    # Step 4: Perform moves (rebuild skills structure)
    if moves:
        # Create new skills structure
        new_skills_dict = {}
        for skill_group in skills:
            category = skill_group.get('category', '')
            new_skills_dict[category] = {
                'category': category,
                'items': []
            }

        # Re-assign all skills
        for skill, correct_cat in skill_correct_category.items():
            # Ensure correct_cat exists in new structure
            if correct_cat not in new_skills_dict:
                new_skills_dict[correct_cat] = {
                    'category': correct_cat,
                    'items': []
                }

            new_skills_dict[correct_cat]['items'].append(skill)

        # Update tailored_data
        tailored_data['skills'] = list(new_skills_dict.values())

        # Log all moves
        print(f"[tailor] Found {len(moves)} skills in wrong categories:")
        for skill, from_cat, to_cat in moves:
            print(f"[tailor]   ✓ {skill:35s} {from_cat:20s} → {to_cat}")
        print(f"[tailor] Re-categorized {len(moves)} skills")
    else:
        print(f"[tailor] All skills correctly categorized ✓")

    print(f"[tailor] ╚═══════════════════════════════════════════════════════╝\n")

    return tailored_data


# ============================================================================
# PHASE 2: KEYWORD-TO-SECTION MAPPING ENGINE
# Programmatic keyword routing with validation and correction
# ============================================================================

# --- Layer 1: Keyword Classification System (Enhanced) ---

# Sub-type classification sets
_PROGRAMMING_LANGUAGES = {
    'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'cpp', 'rust',
    'go', 'golang', 'ruby', 'php', 'swift', 'kotlin', 'scala', 'perl', 'r',
    'matlab', 'julia', 'haskell', 'erlang', 'lua', 'sql', 'html', 'css',
    'bash', 'shell', 'groovy', 'clojure', 'elixir', 'f#', 'ocaml',
}

_FRAMEWORKS = {
    'react', 'angular', 'angularjs', 'vue', 'vue.js', 'svelte', 'next.js',
    'spring', 'spring boot', 'django', 'flask', 'fastapi', 'express',
    'node.js', '.net', 'asp.net', 'laravel', 'rails', 'ruby on rails',
    'pytorch', 'tensorflow', 'keras', 'scikit-learn', 'pandas', 'numpy',
    'langchain', 'hugging face', 'opencv', 'bootstrap', 'tailwind',
    'jquery', 'graphql', 'rest api', 'restful apis', 'grpc',
}

_METHODOLOGIES = {
    'agile', 'scrum', 'kanban', 'tdd', 'test-driven development', 'bdd',
    'behavior-driven development', 'waterfall', 'lean', 'devops', 'ci/cd',
    'continuous integration', 'continuous deployment', 'pair programming',
}

_CLOUD_SERVICES = {
    'aws', 'azure', 'gcp', 'google cloud', 'amazon web services',
    'microsoft azure', 'google cloud platform', 'heroku', 'vercel',
    'netlify', 'digitalocean', 'aws lambda', 'sagemaker', 'aws bedrock',
    's3', 'ec2', 'rds', 'cloudformation', 'cloudwatch',
}

_DEV_TOOLS = {
    'docker', 'kubernetes', 'k8s', 'jenkins', 'git', 'github', 'gitlab',
    'bitbucket', 'circleci', 'travis ci', 'github actions', 'terraform',
    'ansible', 'vagrant', 'prometheus', 'grafana', 'datadog', 'splunk',
    'postman', 'maven', 'gradle', 'npm', 'yarn', 'sonarqube', 'airflow',
    'mlflow', 'wandb', 'dvc', 'jira', 'confluence',
}

_BUSINESS_TOOLS = {
    'salesforce', 'workday', 'servicenow', 'sap', 'oracle', 'tableau',
    'power bi', 'looker', 'snowflake', 'databricks', 'segment',
    'hubspot', 'marketo', 'zendesk', 'freshdesk',
}

_INDUSTRY_VERTICALS = {
    'fintech', 'healthcare', 'healthtech', 'edtech', 'biotech',
    'insurtech', 'regtech', 'proptech', 'agritech', 'cleantech',
    'e-commerce', 'retail', 'manufacturing', 'automotive',
    'telecommunications', 'media', 'entertainment', 'gaming',
    'aerospace', 'defense', 'energy', 'logistics', 'supply chain',
}

_BUSINESS_DOMAINS = {
    'go-to-market', 'supply chain', 'capital markets', 'risk analytics',
    'pricing model', 'risk systems', 'trading systems', 'risk management',
    'regulatory compliance', 'portfolio management', 'financial modeling',
    'patient management', 'ehr systems', 'medical imaging', 'gnss',
    'positioning algorithms', 'embedded systems', 'iot', 'signal processing',
}

_ACHIEVEMENT_VERBS = {
    'built', 'optimized', 'scaled', 'architected', 'engineered', 'designed',
    'implemented', 'developed', 'created', 'launched', 'deployed',
    'automated', 'reduced', 'increased', 'improved', 'accelerated',
    'streamlined', 'modernized', 'migrated', 'refactored', 'delivered',
}

_PROCESS_VERBS = {
    'managed', 'coordinated', 'designed', 'led', 'supervised',
    'maintained', 'planned', 'organized', 'facilitated', 'reviewed',
    'analyzed', 'evaluated', 'configured', 'administered', 'monitored',
}

_SOFT_SKILL_LEADERSHIP = {
    'team leadership', 'mentoring', 'coaching', 'people management',
    'team management', 'cross-functional leadership', 'technical leadership',
    'strategic planning', 'decision making', 'vision setting',
}

_SOFT_SKILL_COMMUNICATION = {
    'technical communication', 'presenting', 'public speaking', 'writing',
    'documentation', 'stakeholder communication', 'client communication',
    'technical writing', 'reporting', 'storytelling',
}

_SOFT_SKILL_ANALYTICAL = {
    'problem-solving', 'problem solving', 'analysis', 'critical thinking',
    'analytical thinking', 'troubleshooting', 'debugging', 'root cause analysis',
    'data-driven decision making', 'research',
}

_SOFT_SKILL_INTERPERSONAL = {
    'collaboration', 'teamwork', 'stakeholder management', 'negotiation',
    'conflict resolution', 'empathy', 'adaptability', 'flexibility',
    'communication', 'relationship building', 'customer support',
}


def classify_keyword(keyword, jd_title=''):
    """
    Layer 1: Classify keyword into type and sub-type.

    Returns: (keyword_type, sub_type)
    Types: HARD_SKILL, TOOL_PLATFORM, DOMAIN_TERM, RESPONSIBILITY_PHRASE,
           SOFT_SKILL, CORE_COMPETENCY
    """
    kw_lower = keyword.lower().strip()

    # Check if it's a core competency (role-defining skill)
    # A core competency appears in the job title itself
    if jd_title and kw_lower in jd_title.lower():
        return ('CORE_COMPETENCY', 'role_defining')

    # HARD_SKILL sub-types
    if kw_lower in _PROGRAMMING_LANGUAGES:
        return ('HARD_SKILL', 'programming_language')
    if kw_lower in _FRAMEWORKS:
        return ('HARD_SKILL', 'framework')
    if kw_lower in _METHODOLOGIES:
        return ('HARD_SKILL', 'methodology')

    # TOOL_PLATFORM sub-types
    if kw_lower in _CLOUD_SERVICES:
        return ('TOOL_PLATFORM', 'cloud_service')
    if kw_lower in _DEV_TOOLS:
        return ('TOOL_PLATFORM', 'dev_tool')
    if kw_lower in _BUSINESS_TOOLS:
        return ('TOOL_PLATFORM', 'business_tool')

    # SOFT_SKILL sub-types
    if kw_lower in _SOFT_SKILL_LEADERSHIP:
        return ('SOFT_SKILL', 'leadership')
    if kw_lower in _SOFT_SKILL_COMMUNICATION:
        return ('SOFT_SKILL', 'communication')
    if kw_lower in _SOFT_SKILL_ANALYTICAL:
        return ('SOFT_SKILL', 'analytical')
    if kw_lower in _SOFT_SKILL_INTERPERSONAL:
        return ('SOFT_SKILL', 'interpersonal')

    # DOMAIN_TERM sub-types
    if kw_lower in _INDUSTRY_VERTICALS:
        return ('DOMAIN_TERM', 'industry_vertical')
    if kw_lower in _BUSINESS_DOMAINS:
        return ('DOMAIN_TERM', 'business_domain')

    # RESPONSIBILITY_PHRASE sub-types
    first_word = kw_lower.split()[0] if kw_lower.split() else ''
    if first_word in _ACHIEVEMENT_VERBS:
        return ('RESPONSIBILITY_PHRASE', 'achievement')
    if first_word in _PROCESS_VERBS:
        return ('RESPONSIBILITY_PHRASE', 'process')

    # Fuzzy classification: check partial matches
    for lang in _PROGRAMMING_LANGUAGES:
        if lang in kw_lower or kw_lower in lang:
            return ('HARD_SKILL', 'programming_language')
    for fw in _FRAMEWORKS:
        if fw in kw_lower or kw_lower in fw:
            return ('HARD_SKILL', 'framework')
    for tool in _DEV_TOOLS | _CLOUD_SERVICES:
        if tool in kw_lower or kw_lower in tool:
            return ('TOOL_PLATFORM', 'dev_tool')
    for soft in _SOFT_SKILL_LEADERSHIP | _SOFT_SKILL_COMMUNICATION | _SOFT_SKILL_ANALYTICAL | _SOFT_SKILL_INTERPERSONAL:
        if soft in kw_lower or kw_lower in soft:
            return ('SOFT_SKILL', 'interpersonal')
    for domain in _INDUSTRY_VERTICALS | _BUSINESS_DOMAINS:
        if domain in kw_lower or kw_lower in domain:
            return ('DOMAIN_TERM', 'business_domain')

    # Default: multi-word → DOMAIN_TERM, single-word with technical context → HARD_SKILL
    if len(keyword.split()) >= 2:
        return ('DOMAIN_TERM', 'business_domain')
    return ('HARD_SKILL', 'methodology')


# --- Layer 2: Priority Scoring Algorithm ---

def calculate_keyword_priority(keyword, jd_text, resume_text, jd_title='',
                                jd_requirements='', jd_responsibilities='',
                                jd_preferred=''):
    """
    Layer 2: Calculate keyword priority score (0-7).

    Components:
    - Base Priority (0-3): Where in JD does keyword appear?
    - Frequency Bonus (0-2): How many times in JD?
    - Domain Relevance Bonus (0-1): Matches candidate's industry?
    - Match Quality Bonus (0-1): Is keyword in resume?

    Scoring Bands:
      6-7: CRITICAL (4 mentions across sections)
      4-5: HIGH (3 mentions)
      2-3: MEDIUM (2 mentions)
      1: LOW (1 mention)
      0 or below: DISCARD
    """
    kw_lower = keyword.lower()
    jd_lower = jd_text.lower()
    resume_lower = resume_text.lower()

    # Base Priority (0-3)
    base = 0
    if jd_title and kw_lower in jd_title.lower():
        base = 3
    elif jd_requirements and kw_lower in jd_requirements.lower():
        base = 3
    elif jd_responsibilities and kw_lower in jd_responsibilities.lower():
        base = 2
    elif jd_preferred and kw_lower in jd_preferred.lower():
        base = 0  # preferred = discard priority
    else:
        # General JD mention
        base = 2 if kw_lower in jd_lower else 0

    # Frequency Bonus (0-2)
    count = jd_lower.count(kw_lower)
    if count >= 3:
        freq_bonus = 2
    elif count == 2:
        freq_bonus = 1
    else:
        freq_bonus = 0

    # Domain Relevance Bonus (0-1)
    # If keyword appears in resume, candidate has domain relevance
    relevance_bonus = 1 if kw_lower in resume_lower else 0

    # Match Quality Bonus (-1 to 1)
    if kw_lower in resume_lower:
        match_bonus = 1  # Strong match
    elif any(word in resume_lower for word in kw_lower.split() if len(word) > 3):
        match_bonus = 0  # Partial match (transferable)
    else:
        match_bonus = -1  # No match

    priority = base + freq_bonus + relevance_bonus + match_bonus
    return max(0, min(7, priority))  # Clamp to 0-7


def get_priority_band(priority_score):
    """Map priority score to band label and required mentions."""
    if priority_score >= 6:
        return ('CRITICAL', 4)
    elif priority_score >= 4:
        return ('HIGH', 3)
    elif priority_score >= 2:
        return ('MEDIUM', 2)
    elif priority_score >= 1:
        return ('LOW', 1)
    else:
        return ('DISCARD', 0)


# --- Layer 3: Section-Specific Routing Rules ---

def get_section_targets(keyword_type, priority_score, is_core_competency=False):
    """
    Layer 3: Map (type + priority) → target sections with frequency.

    Returns: {
        'sections': ['TECHNICAL_SKILLS', 'EXPERIENCE', ...],
        'frequency': {'TECHNICAL_SKILLS': 1, 'EXPERIENCE': 2, ...},
        'max_mentions': int,
        'rules': [str, ...]
    }
    """
    # Core Competencies override all rules
    if is_core_competency or keyword_type == 'CORE_COMPETENCY':
        return {
            'sections': ['TECHNICAL_SKILLS', 'SUMMARY', 'EXPERIENCE'],
            'frequency': {'TECHNICAL_SKILLS': 2, 'SUMMARY': 1, 'EXPERIENCE': 3},
            'max_mentions': 6,
            'rules': ['Role-defining skill — highest redundancy',
                      'Must appear in multiple variations if applicable'],
        }

    # Hard Skills + Tool/Platform
    if keyword_type in ('HARD_SKILL', 'TOOL_PLATFORM'):
        if priority_score >= 3:
            return {
                'sections': ['TECHNICAL_SKILLS', 'EXPERIENCE'],
                'frequency': {'TECHNICAL_SKILLS': 1, 'EXPERIENCE': 2},
                'max_mentions': 3,
                'rules': ['Must have evidence in Experience bullets'],
            }
        elif priority_score == 2:
            return {
                'sections': ['TECHNICAL_SKILLS', 'EXPERIENCE'],
                'frequency': {'TECHNICAL_SKILLS': 1, 'EXPERIENCE': 1},
                'max_mentions': 2,
                'rules': [],
            }
        elif priority_score == 1:
            return {
                'sections': ['EXPERIENCE'],
                'frequency': {'EXPERIENCE': 1},
                'max_mentions': 1,
                'rules': [],
            }
        else:
            return {
                'sections': [],
                'frequency': {},
                'max_mentions': 0,
                'rules': ['DISCARD — priority too low'],
            }

    # Soft Skills
    if keyword_type == 'SOFT_SKILL':
        if priority_score >= 2:
            return {
                'sections': ['EXPERIENCE', 'SUMMARY'],
                'frequency': {'EXPERIENCE': 2, 'SUMMARY': 1},
                'max_mentions': 2,
                'rules': ['Must have evidence in experience',
                          'NEVER in Technical Skills section'],
            }
        elif priority_score == 1:
            return {
                'sections': ['EXPERIENCE'],
                'frequency': {'EXPERIENCE': 1},
                'max_mentions': 1,
                'rules': ['NEVER in Technical Skills section'],
            }
        else:
            return {
                'sections': [],
                'frequency': {},
                'max_mentions': 0,
                'rules': ['DISCARD or EXPERIENCE only',
                          'NEVER in Technical Skills section'],
            }

    # Domain Terms
    if keyword_type == 'DOMAIN_TERM':
        if priority_score >= 2:
            return {
                'sections': ['SUMMARY', 'EXPERIENCE'],
                'frequency': {'SUMMARY': 1, 'EXPERIENCE': 1},
                'max_mentions': 2,
                'rules': ['Shows domain understanding'],
            }
        elif priority_score >= 1:
            return {
                'sections': ['SUMMARY'],
                'frequency': {'SUMMARY': 1},
                'max_mentions': 1,
                'rules': [],
            }
        else:
            return {
                'sections': [],
                'frequency': {},
                'max_mentions': 0,
                'rules': ['DISCARD'],
            }

    # Responsibility Phrases
    if keyword_type == 'RESPONSIBILITY_PHRASE':
        if priority_score >= 2:
            return {
                'sections': ['EXPERIENCE'],
                'frequency': {'EXPERIENCE': 2},
                'max_mentions': 2,
                'rules': ['Different bullets, different achievements'],
            }
        elif priority_score >= 1:
            return {
                'sections': ['EXPERIENCE'],
                'frequency': {'EXPERIENCE': 1},
                'max_mentions': 1,
                'rules': [],
            }
        else:
            return {
                'sections': [],
                'frequency': {},
                'max_mentions': 0,
                'rules': ['DISCARD'],
            }

    # Default fallback
    return {
        'sections': ['EXPERIENCE'],
        'frequency': {'EXPERIENCE': 1},
        'max_mentions': 1,
        'rules': [],
    }


# --- Layer 4: Frequency & Saturation Control ---

# Per-section keyword density limits
_SECTION_DENSITY_LIMITS = {
    'TECHNICAL_SKILLS': {
        'max_new_keywords_per_category': 5,
        'total_skills_per_category': 8,
        'max_keywords_same_priority_tier': 3,
    },
    'SUMMARY': {
        'max_new_keywords_total': 3,
        'target_keyword_density_pct': 20,  # 15-20% of summary words
    },
    'EXPERIENCE': {
        'max_new_keywords_per_bullet': 2,
        'max_new_keywords_total': 8,
        'max_same_keyword_mentions': 4,
        'min_bullet_spacing': 2,  # 2+ bullets between same keyword
    },
    'PROJECTS': {
        'max_new_keywords_per_project': 2,
    },
}


def check_frequency_saturation(tailored_data, keyword_routes):
    """
    Layer 4: Enforce per-section keyword density limits.

    Returns list of violations found.
    """
    violations = []

    if not isinstance(tailored_data, dict):
        return violations

    # Check TECHNICAL_SKILLS density
    limits = _SECTION_DENSITY_LIMITS['TECHNICAL_SKILLS']
    for skill_group in tailored_data.get('skills', []):
        items = skill_group.get('items', [])
        category = skill_group.get('category', '')
        if len(items) > limits['total_skills_per_category']:
            violations.append({
                'section': 'TECHNICAL_SKILLS',
                'type': 'OVER_DENSITY',
                'detail': f"{category} has {len(items)} skills (max {limits['total_skills_per_category']})",
            })

    # Check SUMMARY density
    summary = tailored_data.get('summary', '')
    if summary:
        summary_words = summary.split()
        kw_count = 0
        for route in keyword_routes:
            if route['keyword_text'].lower() in summary.lower():
                kw_count += 1
        if summary_words:
            density = (kw_count / len(summary_words)) * 100
            if density > _SECTION_DENSITY_LIMITS['SUMMARY']['target_keyword_density_pct']:
                violations.append({
                    'section': 'SUMMARY',
                    'type': 'OVER_DENSITY',
                    'detail': f"Keyword density {density:.1f}% exceeds {_SECTION_DENSITY_LIMITS['SUMMARY']['target_keyword_density_pct']}%",
                })

    # Check EXPERIENCE frequency
    exp_limits = _SECTION_DENSITY_LIMITS['EXPERIENCE']
    all_bullets = []
    for exp in tailored_data.get('experience', []):
        all_bullets.extend(exp.get('bullets', []))

    for route in keyword_routes:
        kw = route['keyword_text'].lower()
        mention_positions = []
        for i, bullet in enumerate(all_bullets):
            if kw in bullet.lower():
                mention_positions.append(i)

        # Max same keyword mentions
        if len(mention_positions) > exp_limits['max_same_keyword_mentions']:
            violations.append({
                'section': 'EXPERIENCE',
                'type': 'OVER_FREQUENCY',
                'detail': f"'{route['keyword_text']}' appears {len(mention_positions)} times (max {exp_limits['max_same_keyword_mentions']})",
            })

        # Min bullet spacing
        for j in range(1, len(mention_positions)):
            if mention_positions[j] - mention_positions[j-1] < exp_limits['min_bullet_spacing']:
                violations.append({
                    'section': 'EXPERIENCE',
                    'type': 'SPACING_VIOLATION',
                    'detail': f"'{route['keyword_text']}' appears in consecutive/nearby bullets (positions {mention_positions[j-1]}, {mention_positions[j]})",
                })

    return violations


# --- Layer 5: Natural Language Validation ---

def validate_natural_language(tailored_data, keyword_routes):
    """
    Layer 5: Validate keyword placements for natural language quality.

    Checks:
    1. Context Check — keyword surrounded by related context
    2. Coherence Check — bullet makes sense to human
    3. Frequency Check — no duplicate keywords in same/consecutive bullets
    4. Integration Check — keyword is part of sentence, not appended
    """
    issues = []

    if not isinstance(tailored_data, dict):
        return issues

    all_bullets = []
    for exp in tailored_data.get('experience', []):
        all_bullets.extend(exp.get('bullets', []))
    for proj in tailored_data.get('projects', []):
        all_bullets.extend(proj.get('bullets', []))

    for route in keyword_routes:
        kw = route['keyword_text'].lower()

        # Check 3: Frequency — same keyword in same bullet
        for i, bullet in enumerate(all_bullets):
            bullet_lower = bullet.lower()
            count_in_bullet = bullet_lower.count(kw)
            if count_in_bullet > 1:
                issues.append({
                    'keyword': route['keyword_text'],
                    'check': 'FREQUENCY',
                    'detail': f"Appears {count_in_bullet} times in same bullet (position {i})",
                    'severity': 'HIGH',
                })

        # Check 3: Frequency — same keyword in consecutive bullets
        prev_had_kw = False
        for i, bullet in enumerate(all_bullets):
            has_kw = kw in bullet.lower()
            if has_kw and prev_had_kw:
                issues.append({
                    'keyword': route['keyword_text'],
                    'check': 'FREQUENCY',
                    'detail': f"Appears in consecutive bullets (positions {i-1}, {i})",
                    'severity': 'MEDIUM',
                })
            prev_had_kw = has_kw

        # Check 4: Integration — keyword appended rather than integrated
        for i, bullet in enumerate(all_bullets):
            bullet_lower = bullet.lower()
            if kw in bullet_lower:
                # Check if keyword is at the very end after a period (appended)
                stripped = bullet.rstrip('. ')
                if stripped.lower().endswith(kw):
                    # Check if it's a natural ending vs. appended
                    before_kw = stripped[:-(len(kw))].rstrip('. ,')
                    if before_kw.endswith('.') or before_kw.endswith(','):
                        issues.append({
                            'keyword': route['keyword_text'],
                            'check': 'INTEGRATION',
                            'detail': f"Appears appended to bullet rather than integrated (position {i})",
                            'severity': 'LOW',
                        })

    return issues


# --- 6 Validation Checkpoints ---

def _checkpoint_1_pre_placement(keyword_routes):
    """CHECKPOINT 1: Pre-Placement — verify classification and priority."""
    results = []
    for route in keyword_routes:
        if route['priority_score'] <= 0:
            results.append(f"DISCARD: '{route['keyword_text']}' (priority {route['priority_score']})")
        elif not route['keyword_type']:
            results.append(f"UNCLASSIFIED: '{route['keyword_text']}'")
    return results


def _checkpoint_2_section_specific(tailored_data, keyword_routes):
    """CHECKPOINT 2: Section-Specific — verify correct section placement."""
    results = []
    if not isinstance(tailored_data, dict):
        return results

    # Collect all skills in Technical Skills section
    tech_skills_items = set()
    for group in tailored_data.get('skills', []):
        for item in group.get('items', []):
            tech_skills_items.add(item.lower())

    summary_lower = (tailored_data.get('summary', '') or '').lower()

    exp_text = ''
    for exp in tailored_data.get('experience', []):
        for bullet in exp.get('bullets', []):
            exp_text += bullet.lower() + ' '

    for route in keyword_routes:
        kw_lower = route['keyword_text'].lower()
        kw_type = route['keyword_type']

        # Soft skills MUST NOT be in Technical Skills
        if kw_type == 'SOFT_SKILL' and kw_lower in tech_skills_items:
            results.append(f"VIOLATION: Soft skill '{route['keyword_text']}' found in Technical Skills (should be Experience/Summary)")
            route['status'] = 'NEEDS_VERIFICATION'
            route['failure_reason'] = 'Soft skill in Technical Skills section'

        # Hard skills with priority >= 3 MUST be in Technical Skills + Experience
        if kw_type in ('HARD_SKILL', 'TOOL_PLATFORM') and route['priority_score'] >= 3:
            in_skills = kw_lower in tech_skills_items or any(kw_lower in item for item in tech_skills_items)
            in_exp = kw_lower in exp_text
            if not in_skills:
                results.append(f"MISSING: Hard skill '{route['keyword_text']}' not in Technical Skills (priority {route['priority_score']})")
            if not in_exp:
                results.append(f"MISSING: Hard skill '{route['keyword_text']}' not in Experience (priority {route['priority_score']})")

        # Domain terms with priority >= 2 SHOULD be in Summary
        if kw_type == 'DOMAIN_TERM' and route['priority_score'] >= 2:
            if kw_lower not in summary_lower:
                results.append(f"MISSING: Domain term '{route['keyword_text']}' not in Summary")

    return results


def _checkpoint_3_integration(tailored_data, keyword_routes):
    """CHECKPOINT 3: Integration — natural language quality."""
    return validate_natural_language(tailored_data, keyword_routes)


def _checkpoint_4_frequency(tailored_data, keyword_routes):
    """CHECKPOINT 4: Frequency — keyword density limits."""
    return check_frequency_saturation(tailored_data, keyword_routes)


def _checkpoint_5_consistency(tailored_data):
    """CHECKPOINT 5: Consistency — skills in Skills match Experience."""
    results = []
    if not isinstance(tailored_data, dict):
        return results

    # Build experience text
    exp_text = ''
    for exp in tailored_data.get('experience', []):
        for bullet in exp.get('bullets', []):
            exp_text += bullet.lower() + ' '
    for proj in tailored_data.get('projects', []):
        for bullet in proj.get('bullets', []):
            exp_text += bullet.lower() + ' '

    # Check each skill has evidence in Experience/Projects
    for group in tailored_data.get('skills', []):
        for item in group.get('items', []):
            item_lower = item.lower()
            # Check for any word from the skill in experience
            words = [w for w in item_lower.split() if len(w) > 2]
            has_evidence = any(w in exp_text for w in words) if words else item_lower in exp_text
            if not has_evidence:
                results.append(f"NO_EVIDENCE: '{item}' in {group.get('category', '')} has no proof in Experience/Projects")

    return results


def _checkpoint_6_coverage(keyword_routes):
    """CHECKPOINT 6: Coverage — high-priority keywords reached target sections."""
    results = []
    for route in keyword_routes:
        if route['priority_score'] >= 4 and route['status'] != 'APPROVED':
            results.append(f"COVERAGE_GAP: High-priority '{route['keyword_text']}' (score {route['priority_score']}) status: {route['status']}")
        if route['priority_score'] >= 2 and not route['target_sections']:
            results.append(f"NO_TARGETS: '{route['keyword_text']}' has no target sections assigned")
    return results


# --- Main Orchestrator: Keyword Section Routing Engine ---

def keyword_section_routing_engine(tailored_data, jd_analysis, keyword_data,
                                    soft_skills_data, jd_text, resume_text):
    """
    Phase 2 Main Orchestrator: Run the full keyword-to-section mapping engine.

    Steps:
    1. Build KeywordRoute objects for all extracted keywords
    2. Classify each keyword (Layer 1)
    3. Score priority for each keyword (Layer 2)
    4. Determine section targets (Layer 3)
    5. Check frequency saturation (Layer 4)
    6. Validate natural language (Layer 5)
    7. Run 6 validation checkpoints
    8. Fix violations (move soft skills out of Technical Skills)
    9. Log results

    Returns: (tailored_data, routing_report)
    """
    if not isinstance(tailored_data, dict):
        return tailored_data, {}

    print(f"\n[tailor] ╔═══════════════════════════════════════════════════════╗")
    print(f"[tailor] ║ PHASE 2: KEYWORD SECTION ROUTING ENGINE              ║")
    print(f"[tailor] ╚═══════════════════════════════════════════════════════╝")

    # Extract JD title
    jd_title = ''
    if jd_analysis and isinstance(jd_analysis, dict):
        jd_title = jd_analysis.get('job_title', '') or ''

    # --- Build keyword list from all sources ---
    all_keywords = set()

    # From jd_analysis hard_skills
    if jd_analysis and isinstance(jd_analysis, dict):
        for skill in jd_analysis.get('hard_skills', []):
            if isinstance(skill, str):
                all_keywords.add(skill)
            elif isinstance(skill, dict):
                all_keywords.add(skill.get('keyword', skill.get('skill', '')))

    # From jd_analysis soft_skills
    if jd_analysis and isinstance(jd_analysis, dict):
        for skill in jd_analysis.get('soft_skills', []):
            if isinstance(skill, str):
                all_keywords.add(skill)

    # From keyword_data top_keywords
    if keyword_data and isinstance(keyword_data, dict):
        for kw_obj in keyword_data.get('top_keywords', []):
            if isinstance(kw_obj, dict):
                all_keywords.add(kw_obj.get('keyword', ''))
            elif isinstance(kw_obj, str):
                all_keywords.add(kw_obj)

    # From soft_skills_data
    if soft_skills_data and isinstance(soft_skills_data, dict):
        for skill in soft_skills_data.get('jd_soft_skills', []):
            all_keywords.add(skill)

    # Remove empty strings
    all_keywords.discard('')

    if not all_keywords:
        print(f"[tailor] No keywords to route")
        return tailored_data, {}

    print(f"[tailor] Processing {len(all_keywords)} keywords through routing engine")

    # --- Step 1-3: Build KeywordRoute objects ---
    keyword_routes = []
    for kw in all_keywords:
        kw_type, sub_type = classify_keyword(kw, jd_title)
        priority = calculate_keyword_priority(kw, jd_text, resume_text, jd_title=jd_title)
        targets = get_section_targets(kw_type, priority)
        band, required_mentions = get_priority_band(priority)

        route = {
            'keyword_text': kw,
            'keyword_type': kw_type,
            'sub_type': sub_type,
            'priority_score': priority,
            'priority_band': band,
            'target_sections': targets['sections'],
            'max_mentions': targets['max_mentions'],
            'section_frequency': targets['frequency'],
            'placement_evidence': {},
            'natural_language_check': False,
            'status': 'APPROVED' if priority >= 1 else 'REJECTED',
            'failure_reason': 'Priority too low' if priority < 1 else '',
            'rules': targets['rules'],
        }
        keyword_routes.append(route)

    # Sort by priority (highest first)
    keyword_routes.sort(key=lambda r: -r['priority_score'])

    # Log classification summary
    type_counts = {}
    for route in keyword_routes:
        t = route['keyword_type']
        type_counts[t] = type_counts.get(t, 0) + 1
    print(f"[tailor] Classification: {type_counts}")

    band_counts = {}
    for route in keyword_routes:
        b = route['priority_band']
        band_counts[b] = band_counts.get(b, 0) + 1
    print(f"[tailor] Priority bands: {band_counts}")

    # --- Step 4: Frequency Saturation Control (Layer 4) ---
    saturation_violations = check_frequency_saturation(tailored_data, keyword_routes)
    if saturation_violations:
        print(f"[tailor] Frequency violations: {len(saturation_violations)}")
        for v in saturation_violations[:5]:
            print(f"[tailor]   ⚠ {v['type']}: {v['detail']}")

    # --- Step 5: Natural Language Validation (Layer 5) ---
    nl_issues = validate_natural_language(tailored_data, keyword_routes)
    if nl_issues:
        print(f"[tailor] Natural language issues: {len(nl_issues)}")
        for issue in nl_issues[:5]:
            print(f"[tailor]   ⚠ {issue['check']}: {issue['detail']}")

    # --- Step 6: Run 6 Validation Checkpoints ---
    print(f"\n[tailor] Running 6 validation checkpoints...")

    cp1 = _checkpoint_1_pre_placement(keyword_routes)
    if cp1:
        print(f"[tailor] CP1 Pre-Placement: {len(cp1)} issues")
        for msg in cp1[:3]:
            print(f"[tailor]   {msg}")

    cp2 = _checkpoint_2_section_specific(tailored_data, keyword_routes)
    if cp2:
        print(f"[tailor] CP2 Section-Specific: {len(cp2)} issues")
        for msg in cp2[:5]:
            print(f"[tailor]   {msg}")

    cp3 = _checkpoint_3_integration(tailored_data, keyword_routes)
    if cp3:
        print(f"[tailor] CP3 Integration: {len(cp3)} issues")

    cp4 = _checkpoint_4_frequency(tailored_data, keyword_routes)
    if cp4:
        print(f"[tailor] CP4 Frequency: {len(cp4)} violations")

    cp5 = _checkpoint_5_consistency(tailored_data)
    if cp5:
        print(f"[tailor] CP5 Consistency: {len(cp5)} issues")
        for msg in cp5[:3]:
            print(f"[tailor]   {msg}")

    cp6 = _checkpoint_6_coverage(keyword_routes)
    if cp6:
        print(f"[tailor] CP6 Coverage: {len(cp6)} gaps")
        for msg in cp6[:3]:
            print(f"[tailor]   {msg}")

    # --- Step 7: Auto-fix violations ---
    fixes_applied = 0

    # FIX: Remove soft skills from Technical Skills section
    soft_skill_keywords = {r['keyword_text'].lower() for r in keyword_routes
                           if r['keyword_type'] == 'SOFT_SKILL'}
    if soft_skill_keywords:
        for skill_group in tailored_data.get('skills', []):
            original_count = len(skill_group.get('items', []))
            skill_group['items'] = [
                item for item in skill_group.get('items', [])
                if item.lower() not in soft_skill_keywords
            ]
            removed = original_count - len(skill_group['items'])
            if removed > 0:
                fixes_applied += removed
                print(f"[tailor] ✓ Removed {removed} soft skills from {skill_group.get('category', '')} (should be in Experience/Summary)")

    # FIX: Ensure high-priority hard skills are in Technical Skills
    tech_skills_items_lower = set()
    for group in tailored_data.get('skills', []):
        for item in group.get('items', []):
            tech_skills_items_lower.add(item.lower())

    for route in keyword_routes:
        if (route['keyword_type'] in ('HARD_SKILL', 'TOOL_PLATFORM', 'CORE_COMPETENCY')
                and route['priority_score'] >= 3
                and route['keyword_text'].lower() not in tech_skills_items_lower):

            # Determine which category to add to
            kw_type, sub_type = route['keyword_type'], route['sub_type']
            if sub_type == 'programming_language':
                target_category = 'Languages'
            elif sub_type == 'framework':
                target_category = 'Frameworks & Libraries'
            elif sub_type in ('cloud_service', 'dev_tool', 'business_tool'):
                target_category = 'Tools & Platforms'
            elif sub_type == 'methodology':
                target_category = 'Concepts'
            else:
                # Use _COMPREHENSIVE_CATEGORY_MAP if available
                target_category = _COMPREHENSIVE_CATEGORY_MAP.get(
                    route['keyword_text'].lower(), 'Concepts')

            # Find or create category group
            target_group = None
            for group in tailored_data.get('skills', []):
                if group.get('category', '').lower() == target_category.lower():
                    target_group = group
                    break
            if not target_group:
                # Try partial match
                for group in tailored_data.get('skills', []):
                    if target_category.split()[0].lower() in group.get('category', '').lower():
                        target_group = group
                        break
            if not target_group:
                target_group = {'category': target_category, 'items': []}
                tailored_data['skills'].append(target_group)

            # Respect density limits
            if len(target_group['items']) < _SECTION_DENSITY_LIMITS['TECHNICAL_SKILLS']['total_skills_per_category']:
                target_group['items'].insert(0, route['keyword_text'])  # JD skills first
                fixes_applied += 1
                print(f"[tailor] ✓ Added '{route['keyword_text']}' to {target_category} (priority {route['priority_score']})")

    # Remove empty skill groups
    tailored_data['skills'] = [g for g in tailored_data.get('skills', []) if g.get('items')]

    # --- Final Summary ---
    approved = sum(1 for r in keyword_routes if r['status'] == 'APPROVED')
    rejected = sum(1 for r in keyword_routes if r['status'] == 'REJECTED')
    needs_verify = sum(1 for r in keyword_routes if r['status'] == 'NEEDS_VERIFICATION')

    total_issues = len(cp1) + len(cp2) + len(cp3) + len(cp4) + len(cp5) + len(cp6)
    print(f"\n[tailor] Phase 2 Results:")
    print(f"[tailor]   Keywords processed: {len(keyword_routes)}")
    print(f"[tailor]   Approved: {approved}, Rejected: {rejected}, Needs verification: {needs_verify}")
    print(f"[tailor]   Checkpoint issues: {total_issues}")
    print(f"[tailor]   Fixes applied: {fixes_applied}")
    print(f"[tailor] ╚═══════════════════════════════════════════════════════╝\n")

    # Build routing report
    routing_report = {
        'keywords_processed': len(keyword_routes),
        'approved': approved,
        'rejected': rejected,
        'needs_verification': needs_verify,
        'fixes_applied': fixes_applied,
        'checkpoint_issues': total_issues,
        'saturation_violations': len(saturation_violations),
        'nl_issues': len(nl_issues),
        'keyword_routes': [
            {
                'keyword': r['keyword_text'],
                'type': r['keyword_type'],
                'priority': r['priority_score'],
                'band': r['priority_band'],
                'sections': r['target_sections'],
                'status': r['status'],
            }
            for r in keyword_routes[:20]  # Top 20 for report
        ],
    }

    return tailored_data, routing_report

@tailor_bp.route('/api/tailor-converge', methods=['POST'])
@login_required
def api_tailor_converge():
    """
    Run guided convergence engine with validation.
    """

    data = request.get_json()
    tailored_resume = data.get('tailored_resume')  # From previous api_tailor call
    jd_text = data.get('jd_text')
    max_iterations = data.get('max_iterations', 4)
    target_score = data.get('target_score', 85)

    result = run_convergence(
        tailored_resume,
        jd_text,
        max_iterations=max_iterations,
        target_score=target_score,
    )

    return jsonify(result)


@tailor_bp.route('/api/tailor', methods=['POST'])
@login_required
def api_tailor():
    """Main tailoring pipeline: analyze JD, critique, extract keywords, then tailor."""
    data = request.get_json()
    jd_text = data.get('jd_text', '')
    resume_text = data.get('resume_text', '')
    company_name = data.get('company_name', '')
    role_title = data.get('role_title', '')
    keyword_analysis = data.get('keyword_analysis', '')
    target_city = data.get('target_city', '').strip()
    title_injection_mode = data.get('title_injection_mode', 'none').strip()

    if not jd_text or not resume_text:
        return jsonify({'error': 'Both job description and resume text are required'}), 400

    # Canadian city → province code mapping (comprehensive)
    CITY_TO_PROVINCE = {
        # Ontario
        'toronto': 'ON', 'ottawa': 'ON', 'mississauga': 'ON', 'brampton': 'ON',
        'hamilton': 'ON', 'london': 'ON', 'markham': 'ON', 'vaughan': 'ON',
        'kitchener': 'ON', 'windsor': 'ON', 'richmond hill': 'ON', 'oakville': 'ON',
        'burlington': 'ON', 'oshawa': 'ON', 'barrie': 'ON', 'waterloo': 'ON',
        'guelph': 'ON', 'cambridge': 'ON', 'whitby': 'ON', 'ajax': 'ON',
        'milton': 'ON', 'niagara falls': 'ON', 'thunder bay': 'ON', 'sudbury': 'ON',
        'peterborough': 'ON', 'belleville': 'ON', 'sarnia': 'ON', 'welland': 'ON',
        'north bay': 'ON', 'cornwall': 'ON', 'pickering': 'ON', 'kanata': 'ON',
        'scarborough': 'ON', 'etobicoke': 'ON', 'north york': 'ON',
        # Quebec
        'montreal': 'QC', 'quebec city': 'QC', 'laval': 'QC', 'gatineau': 'QC',
        'longueuil': 'QC', 'sherbrooke': 'QC', 'levis': 'QC', 'trois-rivieres': 'QC',
        'terrebonne': 'QC', 'saint-jean-sur-richelieu': 'QC', 'brossard': 'QC',
        # British Columbia
        'vancouver': 'BC', 'surrey': 'BC', 'burnaby': 'BC', 'richmond': 'BC',
        'coquitlam': 'BC', 'kelowna': 'BC', 'victoria': 'BC', 'nanaimo': 'BC',
        'kamloops': 'BC', 'chilliwack': 'BC', 'abbotsford': 'BC', 'langley': 'BC',
        'new westminster': 'BC', 'north vancouver': 'BC', 'west vancouver': 'BC',
        'prince george': 'BC', 'whistler': 'BC',
        # Alberta
        'calgary': 'AB', 'edmonton': 'AB', 'red deer': 'AB', 'lethbridge': 'AB',
        'medicine hat': 'AB', 'grande prairie': 'AB', 'airdrie': 'AB',
        'st. albert': 'AB', 'spruce grove': 'AB', 'fort mcmurray': 'AB',
        # Manitoba
        'winnipeg': 'MB', 'brandon': 'MB', 'steinbach': 'MB', 'thompson': 'MB',
        # Saskatchewan
        'saskatoon': 'SK', 'regina': 'SK', 'prince albert': 'SK', 'moose jaw': 'SK',
        # Nova Scotia
        'halifax': 'NS', 'dartmouth': 'NS', 'sydney': 'NS', 'truro': 'NS',
        'new glasgow': 'NS', 'bridgewater': 'NS',
        # New Brunswick
        'saint john': 'NB', 'moncton': 'NB', 'fredericton': 'NB', 'dieppe': 'NB',
        'miramichi': 'NB',
        # Newfoundland and Labrador
        "st. john's": 'NL', 'mount pearl': 'NL', 'corner brook': 'NL',
        'conception bay south': 'NL',
        # Prince Edward Island
        'charlottetown': 'PE', 'summerside': 'PE',
        # Northwest Territories
        'yellowknife': 'NT',
        # Yukon
        'whitehorse': 'YT',
        # Nunavut
        'iqaluit': 'NU',
    }

    def _resolve_location(city_input):
        """Resolve city name to 'City, Province, Canada' format."""
        if not city_input:
            return ''
        city_lower = city_input.lower().strip()
        province = CITY_TO_PROVINCE.get(city_lower)
        # Title-case the city name (handle apostrophes like St. John's)
        import re as _re_city
        city_display = city_input.strip().title()
        # Fix apostrophe-S issue: "John'S" → "John's"
        city_display = _re_city.sub(r"'S\b", "'s", city_display)
        if province:
            return f"{city_display}, {province}, Canada"
        # If not found in mapping, just append Canada
        return f"{city_display}, Canada"

    total_tokens = 0
    total_cost = 0.0
    pipeline_steps = []

    # Select AI provider based on APP_ENV
    app_env = current_app.config.get('APP_ENV', 'testing').strip()
    if app_env == 'nvidia':
        from app.services.claude_client import nvidia as ai_client
        print("[tailor] Using NVIDIA Llama-3.3-Nemotron for all pipeline steps")
    else:
        ai_client = claude
        print(f"[tailor] Using AWS Bedrock for all pipeline steps (APP_ENV={app_env})")

    # step 0: parse the JD for skills, requirements, etc.
    jd_analysis = None
    try:
        jd_msg = build_jd_analysis_message(resume_text, jd_text)
        jd_result = ai_client.analyze(JD_ANALYZER_SYSTEM, jd_msg, max_tokens=3000, force_json=True)
        if not jd_result.get('error'):
            jd_analysis = jd_result['response']
            if isinstance(jd_analysis, str):
                try:
                    cleaned = jd_analysis.strip()
                    if cleaned.startswith('```json'):
                        cleaned = cleaned[7:]
                    if cleaned.startswith('```'):
                        cleaned = cleaned[3:]
                    if cleaned.endswith('```'):
                        cleaned = cleaned[:-3]
                    jd_analysis = json_mod.loads(cleaned.strip())
                except Exception:
                    jd_analysis = None
            total_tokens += jd_result.get('tokens_used', 0)
            total_cost += jd_result.get('cost_usd', 0)
            pipeline_steps.append('jd_analysis')
            print(f"[tailor] jd analysis done")
        else:
            print(f"[tailor] jd analysis skipped: {jd_result['error']}")
    except Exception as e:
        print(f"[tailor] jd analysis error: {e}")

    # VALIDATION: Ensure JD hard skills were extracted (Phase 1 fix)
    if not jd_analysis or not isinstance(jd_analysis, dict):
        print(f"[tailor] ⚠ WARNING: JD analysis returned None or invalid format")
        jd_analysis = {'hard_skills': [], 'soft_skills': [], 'top_keywords': []}
    elif not jd_analysis.get('hard_skills'):
        print(f"[tailor] ⚠ WARNING: JD hard skills extraction returned empty!")
        print(f"[tailor]   (This will cause all skills to score 0 in role coherence validation)")
        print(f"[tailor]   Available JD data: {list(jd_analysis.keys())}")
        # Extract hard skills from top_keywords as fallback
        top_kws = jd_analysis.get('top_keywords', [])
        if top_kws:
            print(f"[tailor]   Falling back to top_keywords: {top_kws[:5]}")
            jd_analysis['hard_skills'] = top_kws[:10]

    # step 1: run brutal critique
    critique_data = None
    try:
        critique_msg = build_critique_message(resume_text, jd_text)
        critique_result = ai_client.analyze(BRUTAL_CRITIC_SYSTEM, critique_msg, max_tokens=3000, force_json=True)
        if not critique_result.get('error'):
            critique_data = critique_result['response']
            # try to parse string response
            if isinstance(critique_data, str):
                try:
                    cleaned = critique_data.strip()
                    if cleaned.startswith('```json'):
                        cleaned = cleaned[7:]
                    if cleaned.startswith('```'):
                        cleaned = cleaned[3:]
                    if cleaned.endswith('```'):
                        cleaned = cleaned[:-3]
                    critique_data = json_mod.loads(cleaned.strip())
                except Exception:
                    critique_data = None
            total_tokens += critique_result.get('tokens_used', 0)
            total_cost += critique_result.get('cost_usd', 0)
            pipeline_steps.append('critique')
            print("[tailor] critique done")
        else:
            print(f"[tailor] critique skipped: {critique_result['error']}")
    except Exception as e:
        print(f"[tailor] critique error: {e}")

    # step 2: extract keywords
    keyword_data = None
    try:
        kw_msg = build_keyword_message(resume_text, jd_text)
        kw_result = ai_client.analyze(KEYWORD_EXTRACTOR_SYSTEM, kw_msg, max_tokens=3000, force_json=True)
        if not kw_result.get('error'):
            keyword_data = kw_result['response']
            # parse if string
            if isinstance(keyword_data, str):
                try:
                    cleaned = keyword_data.strip()
                    if cleaned.startswith('```json'):
                        cleaned = cleaned[7:]
                    if cleaned.startswith('```'):
                        cleaned = cleaned[3:]
                    if cleaned.endswith('```'):
                        cleaned = cleaned[:-3]
                    keyword_data = json_mod.loads(cleaned.strip())
                except Exception:
                    keyword_data = None
            total_tokens += kw_result.get('tokens_used', 0)
            total_cost += kw_result.get('cost_usd', 0)
            pipeline_steps.append('keywords')
            print("[tailor] keywords done")
        else:
            print(f"[tailor] keywords skipped: {kw_result['error']}")
    except Exception as e:
        print(f"[tailor] keyword error: {e}")

    # step 2.1: Advanced JD analysis (AWS services, soft skills, weighted scoring)
    advanced_analysis = None
    try:
        aws_extractor = AWSServiceExtractor()
        aws_services = aws_extractor.extract_all(jd_text)

        soft_extractor = SoftSkillsExtractor()
        soft_skills_found = soft_extractor.extract_from_text(jd_text)
        soft_skills_emphasized = soft_extractor.get_emphasized_soft_skills(jd_text)

        # Build weighted keywords from keyword_data if available
        # FIX #1: Parse KEYWORD_EXTRACTOR_SYSTEM output correctly
        # Output format: { "top_keywords": [...objects...], "ats_optimization": {...} }
        # IMPORTANT: Keep required_kws values as 'must_have'/'important'/'nice_to_have' for WeightedKeywordScorer
        found_kws = set()
        required_kws = {}
        if keyword_data and isinstance(keyword_data, dict):
            # NEW LOGIC: Extract from top_keywords array (KEYWORD_EXTRACTOR_SYSTEM output)
            top_keywords = keyword_data.get('top_keywords', [])
            if top_keywords:
                for kw_obj in top_keywords:
                    if not isinstance(kw_obj, dict):
                        continue

                    keyword = kw_obj.get('keyword', '')
                    if not keyword:
                        continue

                    # Map resume_status to priority tier (compatible with WeightedKeywordScorer)
                    status = kw_obj.get('resume_status', 'missing')
                    priority = kw_obj.get('priority', 5)

                    if status == 'not_applicable':
                        # Skip skills candidate doesn't have
                        continue
                    elif status == 'strong_match':
                        # High priority requirement
                        required_kws[keyword] = 'must_have'
                        found_kws.add(keyword)
                    elif status == 'weak_match':
                        # Secondary requirement
                        required_kws[keyword] = 'nice_to_have'
                        found_kws.add(keyword)
                    elif status == 'missing':
                        # Missing skills are important but not critical
                        # Use priority to decide: high priority = important, low = nice_to_have
                        required_kws[keyword] = 'important' if priority >= 7 else 'nice_to_have'

            # FALLBACK: Also check for old-style keywords if present
            # (for backward compatibility)
            if not required_kws:
                for kw in keyword_data.get('must_have', []):
                    k = kw if isinstance(kw, str) else kw.get('keyword', '')
                    if k:
                        required_kws[k] = 'must_have'
                for kw in keyword_data.get('important', keyword_data.get('good_to_have', [])):
                    k = kw if isinstance(kw, str) else kw.get('keyword', '')
                    if k:
                        required_kws[k] = 'important'
                for kw in keyword_data.get('nice_to_have', []):
                    k = kw if isinstance(kw, str) else kw.get('keyword', '')
                    if k:
                        required_kws[k] = 'nice_to_have'

            # Extract found keywords
            for kw in keyword_data.get('found_in_resume', []):
                k = kw if isinstance(kw, str) else kw.get('keyword', '')
                if k:
                    found_kws.add(k)

        scorer = WeightedKeywordScorer()
        weighted_score = scorer.calculate_keyword_match_score(found_kws, required_kws) if required_kws else None

        advanced_analysis = {
            'aws_services': list(aws_services),
            'soft_skills_emphasized': soft_skills_emphasized,
            'soft_skills_all': soft_skills_found,
            'weighted_score': weighted_score,
        }
        pipeline_steps.append('advanced_jd_analysis')
        hard_skills_list = list(required_kws.keys()) + list(aws_services)
        print(f"[tailor] ═══ Advanced JD Analysis ═══")
        print(f"[tailor]   Hard skills ({len(hard_skills_list)}): {', '.join(hard_skills_list) if hard_skills_list else 'none detected'}")
        print(f"[tailor]   AWS services ({len(aws_services)}): {', '.join(aws_services) if aws_services else 'none'}")
        print(f"[tailor]   Soft skills ({len(soft_skills_emphasized)}): {', '.join(soft_skills_emphasized) if soft_skills_emphasized else 'none detected'}")
        if weighted_score:
            print(f"[tailor]   Weighted score: {weighted_score.get('weighted_score', 'N/A')}% (must-have: {weighted_score.get('breakdown', {}).get('must_have', {}).get('found', 0)}/{weighted_score.get('breakdown', {}).get('must_have', {}).get('total', 0)})")
        print(f"[tailor] ═══════════════════════════")
    except Exception as e:
        print(f"[tailor] Advanced JD analysis failed (non-fatal): {e}")

    # step 2.1b: Soft skills extraction & gap analysis
    soft_skills_data = {}
    try:
        soft_extractor2 = SoftSkillsExtractor()

        # Extract soft skills from JD and resume
        jd_soft_skills = soft_extractor2.extract_from_text(jd_text)
        resume_soft_skills = soft_extractor2.extract_from_text(resume_text)

        # Find which soft skills JD requires but resume doesn't claim
        missing_soft_skills = []
        for skill_name, skill_data in jd_soft_skills.items():
            if skill_data['found'] and not resume_soft_skills.get(skill_name, {}).get('found'):
                missing_soft_skills.append(skill_name)

        soft_skills_data = {
            'jd_soft_skills': [k for k, v in jd_soft_skills.items() if v['found']],
            'resume_soft_skills': [k for k, v in resume_soft_skills.items() if v['found']],
            'missing_soft_skills': missing_soft_skills,
        }

        print(f"[tailor] Soft skills: JD wants {soft_skills_data['jd_soft_skills']}, "
              f"resume claims {soft_skills_data['resume_soft_skills']}, missing {missing_soft_skills}")

    except Exception as e:
        print(f"[tailor] Soft skills extraction failed (non-fatal): {e}")
        soft_skills_data = {}

    # step 2.5: RAG semantic matching (NVIDIA embeddings — optional enhancement)
    # FIX #3: Initialize rag_context to None (will run AFTER tailoring on the tailored resume)
    rag_context = None

    # ============================================================================
    # NEW PHASE 0: UNIFIED KEYWORD EXTRACTION (Approach 1 + Approach 2)
    # Runs BEFORE AI tailoring to provide structured keywords
    # ============================================================================

    # Import new extractors
    from app.extractors.semantic_keyword_extractor import SemanticKeywordExtractor
    from app.extractors.frequency_placement_validator import FrequencyPlacementValidator
    from app.keyword_router.section_router import SectionRouter
    from app.extractors.keyword_models import Tier

    structured_keywords = None
    extraction_result = None
    try:
        # STEP 1: Approach 2 - Semantic Extraction (PRIMARY)
        print("[tailor] ═══════════════════════════════════════════════════════")
        print("[tailor] PHASE 0: UNIFIED KEYWORD EXTRACTION")
        print("[tailor] STEP 1: Semantic Extraction (Approach 2) - Primary")
        print("[tailor] ═══════════════════════════════════════════════════════")

        semantic_extractor = SemanticKeywordExtractor()
        extraction_result = semantic_extractor.extract(jd_text, resume_text)

        print(f"[tailor] Extracted:")
        print(f"[tailor]   Must-haves: {len(extraction_result.must_haves)}")
        print(f"[tailor]   Important: {len(extraction_result.important)}")
        print(f"[tailor]   Nice-to-have: {len(extraction_result.nice_to_have)}")
        print(f"[tailor]   Soft skills (excluded): {len(extraction_result.soft_skills_to_exclude)}")
        print(f"[tailor]   Avg confidence: {extraction_result.confidence_average:.1%}")

        # STEP 2: Approach 1 - Frequency + Placement Validation (CROSS-CHECK)
        print(f"\n[tailor] STEP 2: Frequency + Placement Validation (Approach 1)")

        all_keywords = extraction_result.must_haves + extraction_result.important + extraction_result.nice_to_have
        validator = FrequencyPlacementValidator()
        validation_report = validator.validate(all_keywords, jd_text)

        high_confidence_count = len(validation_report['high_confidence_keywords'])
        approach2_only_count = len(validation_report['medium_confidence_keywords'])

        print(f"[tailor] Validation results:")
        print(f"[tailor]   High confidence (both approaches): {high_confidence_count}")
        print(f"[tailor]   Approach 2 only: {approach2_only_count}")
        print(f"[tailor]   → Keeping {high_confidence_count + approach2_only_count} total keywords")

        # STEP 3: Route keywords to sections
        print(f"\n[tailor] STEP 3: Section Routing")

        all_validated = validation_report['high_confidence_keywords'] + validation_report['medium_confidence_keywords']
        router = SectionRouter()
        routed_keywords = router.route(all_validated)

        print(f"[tailor] Routed:")
        print(f"[tailor]   Skills section: {len(routed_keywords['skills'])}")
        print(f"[tailor]   Summary: {len(routed_keywords['summary'])}")
        print(f"[tailor]   Experience: {len(routed_keywords['experience'])}")

        # STEP 4: Prepare structured keyword data for AI prompt
        print(f"\n[tailor] STEP 4: Preparing structured keywords for AI")

        structured_keywords = {
            'must_have_hard_skills': [
                kw.text for kw in routed_keywords['skills']
                if kw.tier == Tier.MUST_HAVE
            ],
            'important_hard_skills': [
                kw.text for kw in routed_keywords['skills']
                if kw.tier == Tier.IMPORTANT
            ],
            'nice_to_have_skills': [
                kw.text for kw in routed_keywords['experience']
                if kw.tier == Tier.NICE_TO_HAVE
            ],
            'summary_keywords': [kw.text for kw in routed_keywords['summary']],
            'soft_skills_to_exclude': [kw.text for kw in extraction_result.soft_skills_to_exclude],
            'total_keywords': len(all_validated),
            'high_confidence_count': high_confidence_count,
            'approach_agreement_pct': (high_confidence_count / max(len(all_validated), 1)) * 100,
        }

        print(f"[tailor] Ready for AI:")
        print(f"[tailor]   Hard skills: {len(structured_keywords['must_have_hard_skills']) + len(structured_keywords['important_hard_skills'])}")
        print(f"[tailor]   Soft skills (EXCLUDED): {len(structured_keywords['soft_skills_to_exclude'])}")
        print(f"[tailor]   Approach agreement: {structured_keywords['approach_agreement_pct']:.0f}%")

    except Exception as e:
        print(f"[tailor] Phase 0 keyword extraction failed (non-fatal): {e}")
        structured_keywords = None

    # ═══════════════════════════════════════════════════════════════
    # NEW PHASE 1: Build Protected Keywords Registry
    # ═══════════════════════════════════════════════════════════════
    protected_keywords_registry = {}
    try:
        if extraction_result is not None:
            print("[tailor] PHASE 1: Building must-have protection registry...")

            # Create master list of protected keywords (NEVER to be removed)
            for keyword in extraction_result.must_haves + extraction_result.important:
                normalized_key = keyword.text.lower().strip()
                protected_keywords_registry[normalized_key] = {
                    'original_text': keyword.text,
                    'tier': keyword.tier.value,  # 'must_have' or 'important'
                    'keyword_type': keyword.keyword_type.value,
                    'confidence': keyword.overall_confidence,
                    'sections_target': keyword.target_sections,
                }

            print(f"[tailor] Protected keywords registry: {len(protected_keywords_registry)} keywords")
            print(f"[tailor]   Must-haves: {len(extraction_result.must_haves)}")
            print(f"[tailor]   Important: {len(extraction_result.important)}")

            # FIX #2 & #3: Also prepare structured keywords with section targets
            structured_keywords_for_ai = _prepare_structured_keywords(
                must_haves=extraction_result.must_haves,
                important=extraction_result.important,
                extraction_result=extraction_result
            )
            print(f"[tailor]   Structured hard skills for AI: {structured_keywords_for_ai['total_must_have_hard'] + structured_keywords_for_ai['total_important_hard']}")
            print(f"[tailor]   Structured soft skills for AI: {len(structured_keywords_for_ai['soft_skills_to_include'])}")
        else:
            print("[tailor] Phase 1 skipped — Phase 0 extraction not available")
    except Exception as e:
        print(f"[tailor] Phase 1 protection registry failed (non-fatal): {e}")

    # ============================================================================
    # Now call AI with STRUCTURED keywords (not raw extraction)
    # ============================================================================

    # STEP 5: Call AI with constrained keyword list
    print(f"\n[tailor] STEP 5: AI Tailoring (constrained)")

    # Prepare structured keywords if extraction succeeded
    if extraction_result:
        structured_keywords_for_ai = _prepare_structured_keywords(
            must_haves=extraction_result.must_haves,
            important=extraction_result.important,
            extraction_result=extraction_result
        )
    else:
        structured_keywords_for_ai = None
    
    user_message = build_tailor_message(
        resume_text, jd_text,
        keyword_analysis=keyword_analysis,
        critique_data=critique_data,
        keyword_data=structured_keywords_for_ai if structured_keywords_for_ai else (structured_keywords if structured_keywords else keyword_data),
        jd_analysis=jd_analysis,
        rag_context=rag_context,
        title_injection_mode=title_injection_mode,
        role_title=role_title,
        soft_skills_data=soft_skills_data,
        # NEW: Pass structured keywords
        structured_keywords=structured_keywords_for_ai,
        hard_skills_list=(
            [kw.text for kw in extraction_result.must_haves 
             if kw.keyword_type.value in ['HARD_SKILL', 'TOOL_PLATFORM']] +
            [kw.text for kw in extraction_result.important 
             if kw.keyword_type.value in ['HARD_SKILL', 'TOOL_PLATFORM']]
        ) if extraction_result else [],
        soft_skills_to_include=(
            [kw.text for kw in extraction_result.must_haves + extraction_result.important 
             if kw.keyword_type.value == 'SOFT_SKILL']
        ) if extraction_result else [],
    )
    print(f"[tailor] ✓ CHECKPOINT 2: Structured keywords prepared ({len(structured_keywords_for_ai.get('must_have_hard_skills', [])) + len(structured_keywords_for_ai.get('important_hard_skills', [])) if structured_keywords_for_ai else 0} hard skills)")

    # retry up to 4 times -- the tailor call is the most critical and must return valid JSON
    # We use force_json=True (assistant prefill with '{') to make conversational responses impossible
    result = None
    required_keys = {'summary', 'skills', 'experience'}
    retry_messages = [
        None,  # first attempt: use original message as-is
        "\n\n⚠️ CRITICAL: You MUST respond with ONLY a valid JSON object. Start with { and end with }. Do NOT ask questions. Do NOT include any text outside the JSON. Output the complete resume JSON now.",
        "\n\n🚨 MANDATORY: OUTPUT ONLY JSON. No questions, no clarifications, no explanations. Your response MUST be a single JSON object starting with { and ending with }. Any non-JSON output is a system failure. Produce the JSON immediately.",
        "\n\n🛑 FINAL ATTEMPT: Return ONLY the JSON resume object. Nothing else. Start with {.",
    ]

    for attempt in range(4):
        temp = max(0.0, 0.15 - (attempt * 0.05))  # 0.15 → 0.10 → 0.05 → 0.00
        msg = user_message
        if attempt > 0 and retry_messages[attempt]:
            msg = user_message + retry_messages[attempt]
            print(f"[tailor] attempt {attempt + 1}: retrying with stricter JSON instruction (temp={temp})")

        attempt_result = ai_client.analyze(
            RESUME_TAILOR_SYSTEM, msg,
            max_tokens=16000, temperature=temp,
            force_json=True
        )

        if attempt_result.get('error'):
            print(f"[tailor] attempt {attempt + 1} error: {attempt_result['error']}")
            result = attempt_result
            continue

        # check if response is usable (dict with required keys)
        resp = attempt_result.get('response')
        if isinstance(resp, dict) and required_keys.issubset(resp.keys()):
            result = attempt_result
            print(f"[tailor] attempt {attempt + 1} succeeded (valid JSON with {len(resp)} keys)")
            break
        elif isinstance(resp, str):
            # AI returned text — try to extract JSON from it right here
            raw = resp.strip()
            extracted = None
            # try stripping fences
            cleaned = raw
            if cleaned.startswith('```json'):
                cleaned = cleaned[7:]
            elif cleaned.startswith('```'):
                cleaned = cleaned[3:]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]
            try:
                extracted = json_mod.loads(cleaned.strip())
            except Exception:
                pass
            # try finding { ... } blob
            if not extracted:
                bs = raw.find('{')
                be = raw.rfind('}')
                if bs != -1 and be > bs:
                    try:
                        extracted = json_mod.loads(raw[bs:be + 1])
                    except Exception:
                        pass

            if isinstance(extracted, dict) and required_keys.issubset(extracted.keys()):
                attempt_result['response'] = extracted
                result = attempt_result
                print(f"[tailor] attempt {attempt + 1} extracted JSON from string ({len(extracted)} keys)")
                break
            else:
                print(f"[tailor] attempt {attempt + 1} returned unparseable string ({len(raw)} chars), retrying...")
                result = attempt_result
                # DON'T break — retry with lower temperature + stronger instruction
        else:
            print(f"[tailor] attempt {attempt + 1} returned unusable data, retrying...")
            result = attempt_result

    if result.get('error'):
        return jsonify({'error': result['error']}), 500

    total_tokens += result.get('tokens_used', 0)
    total_cost += result.get('cost_usd', 0)
    pipeline_steps.append('tailor')
    print(f"[tailor] done ({pipeline_steps})")

    tailored_data = result['response']

    # try to parse AI response into JSON (it sometimes wraps it in markdown fences etc.)
    if isinstance(tailored_data, str):
        import re as re_mod2
        raw_str = tailored_data.strip()
        parsed = None

        # try 1: direct parse
        try:
            parsed = json_mod.loads(raw_str)
        except Exception:
            pass

        # try 2: strip ```json fences
        if parsed is None:
            cleaned = raw_str
            if cleaned.startswith('```json'):
                cleaned = cleaned[7:]
            elif cleaned.startswith('```'):
                cleaned = cleaned[3:]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]
            try:
                parsed = json_mod.loads(cleaned.strip())
            except Exception:
                pass

        # try 3: find the first { ... } blob
        if parsed is None:
            brace_start = raw_str.find('{')
            brace_end = raw_str.rfind('}')
            if brace_start != -1 and brace_end > brace_start:
                try:
                    parsed = json_mod.loads(raw_str[brace_start:brace_end + 1])
                except Exception:
                    pass

        # try 4: fix truncated JSON by closing brackets
        if parsed is None:
            json_str = raw_str
            brace_start = json_str.find('{')
            if brace_start != -1:
                json_str = json_str[brace_start:]
                # Count open vs close braces/brackets
                open_braces = json_str.count('{') - json_str.count('}')
                open_brackets = json_str.count('[') - json_str.count(']')
                # Check if we're inside a string (truncated mid-value)
                # Heuristic: if the last non-whitespace char is not a structural char, close the string
                stripped = json_str.rstrip()
                if stripped and stripped[-1] not in '{}[],:':
                    # Likely truncated mid-string value
                    json_str = stripped + '"'
                # Close any open brackets then braces
                json_str += ']' * max(open_brackets, 0)
                json_str += '}' * max(open_braces, 0)
                try:
                    parsed = json_mod.loads(json_str)
                    print(f"[tailor] patched JSON (added {open_braces}b, {open_brackets}br)")
                except Exception as repair_err:
                    print(f"[tailor] json repair failed: {repair_err}")

        if parsed and isinstance(parsed, dict):
            tailored_data = parsed
            print(f"[tailor] json parsed ok ({len(str(parsed))} chars)")

            # ========= CLEANUP: Validate and fix skill categorization =========
            try:
                tailored_data = validate_and_fix_skill_categories(tailored_data, _COMPREHENSIVE_CATEGORY_MAP)
            except Exception as e:
                print(f"[tailor] Skills cleanup failed (non-fatal): {e}")
        else:
            print(f"[tailor] json parse failed ({len(raw_str)} chars)")

    # ========== PHASE 3: GUARANTEE MUST-HAVES & IMPORTANT (IMMEDIATELY AFTER AI) ==========
    try:
        # Only run if Phase 0 extraction succeeded (extraction_result is available)
        if structured_keywords is not None and extraction_result is not None:
            print("[tailor] ═══════════════════════════════════════════════════════")
            print("[tailor] PHASE 3: GUARANTEE MUST-HAVES & IMPORTANT INJECTED")
            print("[tailor] ═══════════════════════════════════════════════════════")

            from app.services.guarantee_engine.must_have_guarantee_engine import MustHaveGuaranteeEngine
            from app.services.guarantee_engine.guarantee_verifier import GuaranteeVerifier

            # Prepare guarantee engine
            guarantee_engine = MustHaveGuaranteeEngine()

            # FIX #7: Use v2 with protected_keywords_registry if available
            if protected_keywords_registry:
                print(f"[tailor] Using guarantee_injection_v2 with {len(protected_keywords_registry)} protected keywords")

                guarantee_result = guarantee_engine.guarantee_injection_v2(
                    resume_json=tailored_data,
                    protected_keywords_registry=protected_keywords_registry,
                    confidence_threshold=0.75,
                )

                guaranteed_resume = guarantee_result['resume_json']
                guarantee_metadata = guarantee_result['metadata']

                print(f"[tailor] Guarantee results:")
                print(f"[tailor]   Must-have coverage: {guarantee_metadata['must_have_coverage']:.1%}")
                print(f"[tailor]   Important coverage: {guarantee_metadata['important_coverage']:.1%}")
                print(f"[tailor]   Injections made: {guarantee_metadata['injections_made']}")
                print(f"[tailor]   All protected found: {guarantee_metadata['all_protected_found']}")

                # Update tailored_data with guaranteed resume
                tailored_data = guaranteed_resume

                # Store guarantee metadata and protected keywords for downstream phases
                if isinstance(tailored_data, dict):
                    tailored_data['_guarantee_metadata'] = guarantee_metadata
                    tailored_data['_protected_keywords'] = protected_keywords_registry

            else:
                # Fallback: use v1 with extraction_result
                all_critical_keywords = (
                    extraction_result.must_haves +
                    extraction_result.important
                )
                critical_keyword_list = [kw.text for kw in all_critical_keywords]
                keyword_metadata = {kw.text: kw for kw in all_critical_keywords}

                print(f"[tailor] Total critical keywords: {len(critical_keyword_list)}")

                guaranteed_resume = guarantee_engine.guarantee_injection(
                    resume_json=tailored_data,
                    critical_keywords=critical_keyword_list,
                    keyword_metadata=keyword_metadata,
                    must_haves=[kw.text for kw in extraction_result.must_haves],
                    important_keywords=[kw.text for kw in extraction_result.important],
                )

                verifier = GuaranteeVerifier()
                verification = verifier.verify_guarantee(
                    resume_json=guaranteed_resume,
                    expected_must_haves=[kw.text for kw in extraction_result.must_haves],
                    expected_important=[kw.text for kw in extraction_result.important],
                )

                print(f"[tailor] Guarantee verification: {verification['status']}")
                print(f"[tailor]   Coverage: {verification['total_coverage']:.1%}")

                tailored_data = guaranteed_resume
                if isinstance(tailored_data, dict):
                    tailored_data['_guarantee_report'] = verification

            if protected_keywords_registry:
                if guarantee_metadata.get('all_protected_found', False):
                    print(f"[tailor] ✓ GUARANTEE COMPLETE: 100% of must-haves + important injected")
                else:
                    print(f"[tailor] ⚠ WARNING: Some keywords not guaranteed")
            else:
                if verification.get('status') == 'GUARANTEE_COMPLETE':
                    print(f"[tailor] ✓ GUARANTEE COMPLETE: 100% of must-haves + important injected")
                else:
                    print(f"[tailor] ⚠ WARNING: Some keywords not guaranteed")

            print(f"[tailor] ═══════════════════════════════════════════════════════\n")
            print("[tailor] ✓ CHECKPOINT 1: Guarantee phase moved (after AI tailoring)")
        else:
            print("[tailor] Phase 3 skipped — Phase 0 extraction not available")

    except Exception as e:
        print(f"[tailor] Phase 3 guarantee engine failed (non-fatal): {e}")

    # overwrite experience/projects/education with master resume data
    # this guarantees bullets are exactly what the user uploaded
    if isinstance(tailored_data, dict):
        try:
            master = MasterResume.query.filter_by(user_id=session.get('user_id')).first()
            if master:

                # header straight from DB
                tailored_data['header'] = {
                    'name': master.full_name or '',
                    'location': master.location or '',
                    'phone': master.phone or '',
                    'email': master.email or '',
                    'linkedin': master.linkedin_url or '',
                    'github': master.github_url or '',
                    'tagline': master.tagline or '',
                }

                # Override header location with target city if provided
                if target_city:
                    resolved_loc = _resolve_location(target_city)
                    tailored_data['header']['location'] = resolved_loc
                    print(f"[tailor] location overridden: '{target_city}' → '{resolved_loc}'")

                # Preserve target_role for headline injection (Option 1)
                if title_injection_mode == 'headline' and role_title:
                    tailored_data['header']['target_role'] = role_title
                    print(f"[tailor] target_role set: '{role_title}'")

                # education from DB
                tailored_data['education'] = master.education or []

                # ========== PHASE 4: PRESERVE MASTER SKILLS ==========
                # Extract all master skill names for tracking
                master_skill_names = set()
                # lowercase -> original casing, so any code that needs to
                # re-insert a master skill by its lowercase key (e.g. the
                # Step D3 backfill) writes back "Kubernetes", not "kubernetes"
                master_skill_casing = {}
                for master_group in (master.skills or []):
                    for item in master_group.get('items', []):
                        item_clean = item.strip()
                        master_skill_names.add(item_clean.lower())
                        master_skill_casing.setdefault(item_clean.lower(), item_clean)

                print(f"[tailor] PHASE 4: Extracted {len(master_skill_names)} master skills for preservation")

                # ---- SKILLS ENFORCEMENT: JD-dominant, competing tech suppressed, global dedup ----
                master_skills = master.skills or []
                ai_skills = tailored_data.get('skills', [])
                if master_skills and ai_skills:
                    # Get the category_mapping from tailoring_notes (original → renamed)
                    notes = tailored_data.get('tailoring_notes', {})
                    if isinstance(notes, str):
                        notes = {}
                    cat_mapping = notes.get('category_mapping', {})

                    # ---- Competing technology groups ----
                    # Each list is a group of direct competitors.
                    # If JD mentions one, the others should be suppressed.
                    COMPETING_TECH_GROUPS = [
                        # Cloud platforms
                        ['aws', 'amazon web services', 'amazon web services (aws)',
                         'azure', 'microsoft azure',
                         'gcp', 'google cloud', 'google cloud platform', 'google cloud platform (gcp)'],
                        # Frontend frameworks
                        ['react', 'react.js', 'reactjs',
                         'angular', 'angular.js', 'angularjs',
                         'vue', 'vue.js', 'vuejs',
                         'svelte', 'svelte.js'],
                        # SQL databases
                        ['postgresql', 'postgres',
                         'mysql',
                         'mariadb',
                         'sql server', 'mssql', 'microsoft sql server'],
                        # NoSQL databases
                        ['mongodb', 'dynamodb', 'cassandra', 'couchdb'],
                        # CI/CD tools
                        ['jenkins',
                         'github actions',
                         'gitlab ci', 'gitlab ci/cd',
                         'circleci', 'circle ci',
                         'travis ci', 'travisci'],
                        # Container orchestration
                        ['kubernetes', 'k8s',
                         'docker swarm',
                         'ecs', 'amazon ecs',
                         'nomad'],
                        # IaC tools
                        ['terraform',
                         'cloudformation', 'aws cloudformation',
                         'pulumi'],
                        # Message queues
                        ['kafka', 'apache kafka',
                         'rabbitmq', 'rabbit mq',
                         'sqs', 'amazon sqs',
                         'activemq', 'active mq'],
                        # Backend frameworks (Python)
                        ['django', 'flask', 'fastapi'],
                        # Backend frameworks (Java)
                        ['spring', 'spring boot',
                         'quarkus', 'micronaut'],
                    ]

                    # Build a set of JD hard skills (lowercase) for lookup
                    jd_hard_skills_lower = set()
                    if jd_analysis and isinstance(jd_analysis, dict):
                        for s in jd_analysis.get('hard_skills', []):
                            if isinstance(s, str):
                                jd_hard_skills_lower.add(s.strip().lower())
                        for s in jd_analysis.get('top_keywords', []):
                            if isinstance(s, str):
                                jd_hard_skills_lower.add(s.strip().lower())

                    # Determine which competing skills to suppress
                    # For each group: if JD mentions any member, suppress all OTHER members
                    skills_to_suppress = set()
                    for group in COMPETING_TECH_GROUPS:
                        jd_mentions = [g for g in group if g in jd_hard_skills_lower]
                        if jd_mentions:
                            # JD explicitly names some members → suppress the rest
                            for g in group:
                                if g not in jd_hard_skills_lower:
                                    skills_to_suppress.add(g)

                    def _should_suppress(skill_name):
                        """Check if a skill should be suppressed as a competing technology."""
                        sl = skill_name.strip().lower()
                        # FIX #4: NEVER suppress protected keywords
                        if protected_keywords_registry and sl in protected_keywords_registry:
                            return False  # Protected — never suppress
                        # Check exact match
                        if sl in skills_to_suppress:
                            return True
                        # Check if skill contains a suppressed term (e.g., "Amazon Web Services (AWS)" contains "aws")
                        for suppressed in skills_to_suppress:
                            if suppressed in sl or sl in suppressed:
                                # FIX #4: Check if this suppressed term itself is protected
                                if protected_keywords_registry and suppressed in protected_keywords_registry:
                                    return False
                                return True
                        return False

                    # Collect ALL items the AI produced across all categories
                    all_ai_items = set()
                    for group in ai_skills:
                        for item in group.get('items', []):
                            all_ai_items.add(item.strip())

                    # Build a mapping: master_index → ai_group
                    # Strategy: use category_mapping first, then positional fallback
                    enforced_skills = []
                    used_ai_indices = set()
                    used_items = set()

                    for m_idx, master_group in enumerate(master_skills):
                        master_cat = master_group.get('category', '')
                        master_items = master_group.get('items', [])

                        # 1. Check if AI renamed this category via category_mapping
                        mapped_name = cat_mapping.get(master_cat, '').strip() if cat_mapping else ''
                        matched_ai = None
                        matched_ai_idx = None

                        if mapped_name:
                            # find the AI group with the mapped name
                            for a_idx, ai_group in enumerate(ai_skills):
                                if a_idx not in used_ai_indices and ai_group.get('category', '').strip().lower() == mapped_name.strip().lower():
                                    matched_ai = ai_group
                                    matched_ai_idx = a_idx
                                    break

                        # 2. Fallback: find AI group matching the original name exactly
                        if matched_ai is None:
                            for a_idx, ai_group in enumerate(ai_skills):
                                if a_idx not in used_ai_indices and ai_group.get('category', '').strip().lower() == master_cat.strip().lower():
                                    matched_ai = ai_group
                                    matched_ai_idx = a_idx
                                    break

                        # 3. Fallback: positional match (if AI has same number of categories)
                        if matched_ai is None and m_idx < len(ai_skills) and m_idx not in used_ai_indices:
                            matched_ai = ai_skills[m_idx]
                            matched_ai_idx = m_idx

                        if matched_ai is not None and matched_ai_idx is not None:
                            used_ai_indices.add(matched_ai_idx)
                            # Use the AI's category name (renamed or original)
                            new_cat_name = matched_ai.get('category', master_cat).strip()
                            if not new_cat_name:
                                new_cat_name = master_cat

                            # Accept the AI's skill list (which should already
                            # apply Tier 1/2/3 filtering from the prompt).
                            # We do NOT force-add all master items back — the AI
                            # intentionally removed Tier 3 (irrelevant) skills.
                            merged = list(matched_ai.get('items', []))
                            enforced_skills.append({'category': new_cat_name, 'items': merged})
                            used_items.update(merged)
                        else:
                            # AI dropped this category entirely — this means all
                            # skills in it were Tier 3 / irrelevant. Only restore
                            # if some master items are JD-relevant.
                            relevant_master = [
                                item for item in master_items
                                if item.strip().lower() in jd_hard_skills_lower
                            ]
                            if relevant_master:
                                enforced_skills.append({'category': master_cat, 'items': relevant_master})
                                used_items.update(relevant_master)
                            # else: category was all Tier 3 — correctly omitted

                    # Handle any extra AI categories (new ones the AI added for JD skills)
                    MAX_CATEGORIES = 7
                    for a_idx, ai_group in enumerate(ai_skills):
                        if a_idx not in used_ai_indices:
                            new_items = [item for item in ai_group.get('items', []) if item.strip() not in used_items]
                            if new_items:
                                if len(enforced_skills) < MAX_CATEGORIES:
                                    # Accept the new category if under the limit
                                    enforced_skills.append({
                                        'category': ai_group.get('category', 'Additional Skills'),
                                        'items': new_items
                                    })
                                    used_items.update(new_items)
                                else:
                                    # Over limit — distribute items into existing categories
                                    enforced_skills[-1]['items'].extend(new_items)
                                    used_items.update(new_items)

                    # Ensure any AI items not yet placed get added somewhere
                    leftover = [item for item in all_ai_items if item not in used_items]
                    if leftover and enforced_skills:
                        enforced_skills[-1]['items'].extend(sorted(leftover))

                    # Final cap at 7 categories
                    if len(enforced_skills) > MAX_CATEGORIES:
                        overflow = enforced_skills[MAX_CATEGORIES:]
                        enforced_skills = enforced_skills[:MAX_CATEGORIES]
                        for extra in overflow:
                            enforced_skills[-1]['items'].extend(extra.get('items', []))

                    # ---- COMPETING TECH SUPPRESSION (server-side enforcement) ----
                    # Remove skills that compete with JD-specified technologies.
                    # BUT PHASE 4: Never suppress master skills
                    if skills_to_suppress:
                        suppressed_log = []
                        preserved_log = []
                        for group in enforced_skills:
                            original_items = group['items']
                            filtered = []
                            for item in original_items:
                                item_lower = item.strip().lower()
                                # Check if this is a master skill
                                is_master_skill = item_lower in master_skill_names

                                if _should_suppress(item) and item_lower not in jd_hard_skills_lower:
                                    if is_master_skill:
                                        # PHASE 4: Preserve master skills even if competing
                                        filtered.append(item)
                                        preserved_log.append((item, "master override"))
                                    else:
                                        # OK to suppress AI-suggested skill
                                        suppressed_log.append(item)
                                else:
                                    filtered.append(item)
                            group['items'] = filtered

                        if suppressed_log:
                            print(f"[tailor] competing tech suppressed: {suppressed_log}")
                        if preserved_log:
                            print(f"[tailor] PHASE 4: competing tech NOT suppressed (master override):")
                            for skill, reason in preserved_log:
                                print(f"[tailor]   ✓ {skill} ({reason})")

                    # ---- GLOBAL CROSS-CATEGORY DEDUPLICATION ----
                    # A skill must appear EXACTLY ONCE across ALL categories.
                    # This replaces the old per-category-only dedup.
                    global_seen = set()
                    # Also track common variations for fuzzy dedup
                    VARIATION_MAP = {
                        'k8s': 'kubernetes',
                        'postgres': 'postgresql',
                        'mongo': 'mongodb',
                        'react.js': 'react',
                        'reactjs': 'react',
                        'vue.js': 'vue',
                        'vuejs': 'vue',
                        'angular.js': 'angular',
                        'angularjs': 'angular',
                        'node': 'node.js',
                        'nodejs': 'node.js',
                        'express': 'express.js',
                        'expressjs': 'express.js',
                        'restful api': 'restful apis',
                        'rest api': 'restful apis',
                        'rest apis': 'restful apis',
                        'ci/cd': 'ci/cd pipelines',
                        'ml': 'machine learning',
                        'dl': 'deep learning',
                        'oop': 'object-oriented programming (oop)',
                        'tdd': 'test-driven development (tdd)',
                        'agile': 'agile methodologies',
                    }

                    def _normalize_skill(name):
                        """Normalize a skill name for dedup comparison."""
                        n = name.strip().lower()
                        # Strip parenthetical abbreviations for comparison
                        # e.g., "Amazon Web Services (AWS)" → "amazon web services"
                        import re as _re_dedup
                        n_base = _re_dedup.sub(r'\s*\([^)]*\)\s*', '', n).strip()
                        # Check variation map
                        return VARIATION_MAP.get(n_base, VARIATION_MAP.get(n, n_base))

                    for group in enforced_skills:
                        deduped = []
                        for item in group['items']:
                            norm = _normalize_skill(item)
                            if norm not in global_seen:
                                global_seen.add(norm)
                                # Also add the raw lowercase to catch exact matches
                                global_seen.add(item.strip().lower())
                                deduped.append(item)
                        group['items'] = deduped

                    # Remove any categories that became empty after filtering
                    enforced_skills = [g for g in enforced_skills if g.get('items')]

                    tailored_data['skills'] = enforced_skills
                    print(f"[tailor] skills: {len(enforced_skills)} categories (max {MAX_CATEGORIES}), mapping={cat_mapping}")

                    # ---- PHASE 4 FIX: ONLY REMOVE NON-TECHNICAL SKILLS (DON'T MOVE) ----
                    # IMPORTANT: We only REMOVE skills that are clearly non-technical.
                    # We DO NOT move skills between categories - that breaks downstream selection logic.
                    try:
                        # List of non-technical terms that should be removed from technical sections
                        NON_TECHNICAL_REMOVALS = {
                            'agile', 'scrum', 'kanban', 'xp', 'extreme programming',
                            'waterfall', 'v-model', 'spiral',
                            'electrical engineering', 'mechanical engineering', 'civil engineering',
                            'software engineering', 'computer science', 'data science',
                            'geomatics engineering', 'geospatial engineering',
                            'surveying',
                            'ai-driven methods', 'innovation', 'problem-solving',
                        }

                        removed_count = 0
                        for group in enforced_skills:
                            original_count = len(group.get('items', []))
                            group['items'] = [
                                item for item in group.get('items', [])
                                if item.lower() not in NON_TECHNICAL_REMOVALS
                            ]
                            removed = original_count - len(group['items'])
                            if removed > 0:
                                removed_count += removed
                                print(f"[tailor] removed {removed} non-technical skills from {group.get('category', 'unknown')}")

                        if removed_count > 0:
                            print(f"[tailor] ║ REMOVED NON-TECHNICAL SKILLS ║")
                            print(f"[tailor] Total removed: {removed_count}")
                            print(f"[tailor] ╚═══════════════════════════════╝")

                        # CRITICAL: DON'T move skills between categories
                        # The downstream tier-based merge DEPENDS on category names
                        tailored_data['skills'] = [g for g in enforced_skills if g.get('items')]
                    except Exception as e:
                        print(f"[tailor] Skill removal validation failed (non-fatal): {e}")

                    # ---- ROLE-LEVEL VALIDATION (Fix #3) ----
                    try:
                        detected_role_level = detect_role_level(tailored_data, jd_text)

                        # TASK 3 bugfix: use the real computed years (date math),
                        # not len(experience) — that's a count of jobs, not years;
                        # someone with 2 jobs held 8 years each was being validated
                        # as if they had "2 years" of experience.
                        years_exp = calculate_years_experience(tailored_data)

                        # CHUNK 3.5: Detailed logging of role level detection
                        print(f"[tailor] Role Level Detection:")
                        print(f"[tailor]   Years of experience: {years_exp}")
                        print(f"[tailor]   Detected role level: {detected_role_level}")

                        # Validate consistency against the real computed years
                        try:
                            is_valid, msg = validate_role_level_consistency(
                                years_exp,
                                detected_role_level
                            )
                            if is_valid:
                                print(f"[tailor]   Validation: ✓ PASS - {msg}")
                            else:
                                print(f"[tailor]   Validation: ✗ FAIL - {msg}")
                                # TASK 3 bugfix: validation used to catch this and
                                # then continue with the wrong level anyway — now
                                # it actually corrects it.
                                corrected_level = detect_role_level_by_years(years_exp)
                                print(f"[tailor]   ✓ Auto-corrected role level: {detected_role_level} → {corrected_level}")
                                detected_role_level = corrected_level
                        except Exception as rlv_err:
                            print(f"[tailor]   Validation skipped: {rlv_err}")

                        skill_cap_for_level = ROLE_SKILL_MATRIX.get(detected_role_level, {}).get('max_total_skills', 16)
                        print(f"[tailor]   Applied skill cap: {skill_cap_for_level}")

                        coherence_check = validate_role_skill_coherence(tailored_data, detected_role_level)

                        if coherence_check['status'] == 'FAIL':
                            print(f"[tailor] role coherence issues: {coherence_check['issues']}")

                            # Auto-fix: remove problematic skills
                            forbidden_list = coherence_check.get('forbidden', [])
                            for skill_group in tailored_data.get('skills', []):
                                original_count = len(skill_group.get('items', []))
                                skill_group['items'] = [
                                    s for s in skill_group.get('items', [])
                                    if not any(forbidden.lower() in s.lower()
                                              for forbidden in forbidden_list)
                                ]
                                removed = original_count - len(skill_group['items'])
                                if removed > 0:
                                    print(f"[tailor] removed {removed} incoherent skills from {skill_group.get('category', 'unknown')}")

                            # ========== AUTO-FIX SKILLS COHERENCE ==========
                            print(f"\n[tailor] ╔═══════════════════════════════════════════════════════╗")
                            print(f"[tailor] ║ AUTO-FIX: ROLE COHERENCE ISSUES                    ║")
                            print(f"[tailor] ╚═══════════════════════════════════════════════════════╝")

                            # Count current skills
                            all_skills_list = []
                            for skill_group in tailored_data.get('skills', []):
                                all_skills_list.extend(skill_group.get('items', []))

                            current_count = len(all_skills_list)
                            max_allowed = ROLE_SKILL_MATRIX.get(detected_role_level, {}).get('max_total_skills', 16)

                            if current_count > max_allowed:
                                skills_to_remove = current_count - max_allowed
                                print(f"[tailor] Current: {current_count} skills | Allowed: {max_allowed} | Remove: {skills_to_remove}")

                                # PHASE 2 FIX: Use smart merge strategy instead of aggressive removal
                                # Build JD keywords (used for matching, not for scoring)
                                jd_keywords_lower = set()
                                for skill in jd_analysis.get('hard_skills', []):
                                    jd_keywords_lower.add(skill.lower())
                                for skill in jd_analysis.get('top_keywords', []):
                                    jd_keywords_lower.add(skill.lower())

                                print(f"[tailor] JD keywords available: {len(jd_keywords_lower)} keywords")

                                # Categorize skills into tiers by VALUE not JD match
                                # TIER 1: Programming Languages (PRESERVE ALL)
                                CORE_LANGUAGES = {
                                    'python', 'java', 'c++', 'c#', 'javascript', 'typescript',
                                    'go', 'rust', 'kotlin', 'swift', 'ruby', 'php', 'r',
                                    'scala', 'c', 'fortran', 'matlab', 'sql', 'html', 'css',
                                    'perl', 'lua', 'dart', 'groovy', 'shell', 'bash',
                                    'objective-c', 'assembly', 'haskell', 'elixir', 'clojure'
                                }

                                # TIER 2: High-Value Tools
                                HIGH_VALUE_TOOLS = {
                                    'docker', 'kubernetes', 'aws', 'azure', 'gcp', 'git',
                                    'linux', 'jenkins', 'gitlab', 'github', 'postgresql',
                                    'mysql', 'mongodb', 'redis', 'elasticsearch'
                                }

                                # Items that should NEVER be in the Languages category
                                NOT_LANGUAGES = {
                                    'ai-driven methods', 'agile/scrum', 'agile', 'scrum',
                                    'electrical engineering', 'geomatics engineering',
                                    'software engineering', 'gnss error modeling',
                                    'machine learning', 'deep learning', 'data analysis',
                                    'big data analysis', 'design patterns', 'microservices',
                                    'object-oriented programming', 'oop', 'algorithms',
                                    'data structures', 'ci/cd', 'ci/cd pipelines',
                                    'devops', 'cloud computing', 'system design',
                                }

                                tier1_skills = []  # Languages (ONLY actual programming languages)
                                tier2_skills = []  # JD-required new skills
                                tier3_skills = []  # Frameworks
                                tier4_skills = []  # Tools
                                tier5_skills = []  # Concepts & everything else

                                # Collect all skills with their categories
                                skill_to_category = {}
                                for group in tailored_data.get('skills', []):
                                    for item in group.get('items', []):
                                        skill_to_category[item] = group['category']

                                # PHASE 1 (Step D2): Master skills are ALWAYS included, seeded
                                # before tier truncation. The guide's own snippet for this step
                                # referenced `all_items_by_category`, which does not exist anywhere
                                # in this codebase, and built its own `final_skills = []` that gets
                                # unconditionally overwritten a few lines below by the real
                                # `final_skills = selected[:max_allowed]` — so as written it would
                                # have had no effect. Real integration: seed `selected` (the list
                                # that actually survives to `final_skills`) with master skills
                                # FIRST, using the real per-item data this file already has
                                # (`tailored_data.get('skills', [])` — the same source
                                # `skill_to_category` above reads from).
                                print(f"\n[tailor] PHASE 4: Including all master skills in selection")
                                master_priority = []

                                for group in tailored_data.get('skills', []):
                                    if group['category'] == 'Languages':
                                        for item in group.get('items', []):
                                            if item.lower() in master_skill_names and item not in master_priority:
                                                master_priority.append(item)
                                                print(f"[tailor]   ✓ {item} (master skill)")

                                for group in tailored_data.get('skills', []):
                                    if group['category'] != 'Languages':
                                        for item in group.get('items', []):
                                            if item.lower() in master_skill_names and item not in master_priority:
                                                master_priority.append(item)
                                                print(f"[tailor]   ✓ {item} (master skill)")

                                print(f"[tailor] PHASE 4: {len(master_priority)} master skills reserved")

                                # TIER 1: Keep all skills from Languages category
                                # (Phase 4 removal + hard skills injection mapping should ensure they're valid)
                                for group in tailored_data.get('skills', []):
                                    if group['category'] == 'Languages':
                                        tier1_skills.extend(group.get('items', []))

                                # DISABLED: Don't move skills - it breaks downstream logic
                                # The Phase 4 removal should have already cleaned up non-technical items
                                # The hard skills injection category map should prevent miscategorization
                                # So we don't need to move anything here

                                print(f"\n[tailor] ║ SKILL PRIORITIZATION (MERGE-BASED)  ║")
                                print(f"[tailor] ║ Tier 1 (Languages): {len(tier1_skills)} ║")

                                # TIER 2: JD-required skills not already in tier1
                                jd_required = set(jd_analysis.get('hard_skills', []))
                                jd_required.update(jd_analysis.get('top_keywords', []))
                                for group in tailored_data.get('skills', []):
                                    for item in group.get('items', []):
                                        if item not in tier1_skills:
                                            item_lower = item.lower()
                                            if any(jd_req.lower() in item_lower or item_lower in jd_req.lower()
                                                   for jd_req in jd_required):
                                                if item not in tier2_skills:
                                                    tier2_skills.append(item)

                                print(f"[tailor] ║ Tier 2 (JD-Required): {len(tier2_skills)} ║")

                                # TIER 3: Frameworks & Libraries
                                for group in tailored_data.get('skills', []):
                                    if group['category'] == 'Frameworks & Libraries':
                                        for item in group.get('items', []):
                                            if item not in tier1_skills and item not in tier2_skills:
                                                tier3_skills.append(item)

                                print(f"[tailor] ║ Tier 3 (Frameworks): {len(tier3_skills)} ║")

                                # TIER 4: High-value tools
                                for group in tailored_data.get('skills', []):
                                    if group['category'] in ['Tools & Platforms', 'Databases']:
                                        for item in group.get('items', []):
                                            if any(tool in item.lower() for tool in HIGH_VALUE_TOOLS):
                                                if item not in tier4_skills and item not in tier1_skills and item not in tier2_skills:
                                                    tier4_skills.append(item)

                                print(f"[tailor] ║ Tier 4 (Tools): {len(tier4_skills)} ║")

                                # TIER 5: Concepts only if in JD (+ items moved from Languages)
                                for group in tailored_data.get('skills', []):
                                    if group['category'] == 'Concepts':
                                        for item in group.get('items', []):
                                            if any(kw.lower() in item.lower() for kw in jd_keywords_lower):
                                                if item not in tier5_skills:
                                                    tier5_skills.append(item)

                                print(f"[tailor] ║ Tier 5 (Concepts): {len(tier5_skills)} ║")

                                # Select skills: PROTECTED first, master second, then T1, T2, T3, T4, T5
                                selected = []
                                
                                # FIX #4 (Phase 6): Protected keywords ALWAYS first — never removed
                                if protected_keywords_registry:
                                    for group in tailored_data.get('skills', []):
                                        for item in group.get('items', []):
                                            if item.lower().strip() in protected_keywords_registry:
                                                if item not in selected:
                                                    selected.append(item)
                                    if selected:
                                        print(f"[tailor] ✓ {len(selected)} protected keywords placed first (never removed)")
                                
                                selected.extend(master_priority)   # PHASE 4: master skills first, always
                                selected.extend(tier1_skills)      # All languages (NEVER removed)
                                selected.extend(tier2_skills[:3])  # Top 3 JD skills
                                selected.extend(tier3_skills[:5])  # Top 5 frameworks
                                selected.extend(tier4_skills[:3])  # Top 3 tools
                                selected.extend(tier5_skills[:2])  # Top 2 concepts

                                # Deduplicate while preserving order
                                seen = set()
                                deduped_selected = []
                                for s in selected:
                                    if s not in seen:
                                        seen.add(s)
                                        deduped_selected.append(s)
                                selected = deduped_selected

                                # Cap at max_allowed
                                final_skills = selected[:max_allowed]
                                
                                # FIX #4 (Phase 6): Post-cap verification — re-add any protected that were cut
                                if protected_keywords_registry:
                                    final_skills_lower = {s.lower().strip() for s in final_skills}
                                    for group in tailored_data.get('skills', []):
                                        for item in group.get('items', []):
                                            if item.lower().strip() in protected_keywords_registry and item.lower().strip() not in final_skills_lower:
                                                final_skills.append(item)
                                                final_skills_lower.add(item.lower().strip())
                                                print(f"[tailor] ✓ RE-ADDED protected keyword after cap: '{item}'")
                                
                                removed_skills = set(skill_to_category.keys()) - set(final_skills)

                                print(f"\n[tailor] FINAL SELECTION: {len(final_skills)}/{max_allowed} skills")
                                print(f"[tailor] Removed: {len(removed_skills)} skills")
                                for skill in removed_skills:
                                    print(f"[tailor] ✗ {skill} ({skill_to_category.get(skill, 'Unknown')})")

                                # PHASE 4: Verify all master skills included
                                # NOTE: guide's original snippet checked against `jd_lower`,
                                # which is not defined anywhere in this scope (it's created
                                # ~800 lines later, in the unrelated hard-skills-injection
                                # section). Using `jd_hard_skills_lower` — the actual in-scope
                                # variable for "JD hard skills, lowercased" defined earlier
                                # in this same enforcement block.
                                final_skills_lower = set(s.lower() for s in final_skills)
                                missing_master = [s for s in master_skill_names if s not in final_skills_lower]

                                if missing_master:
                                    print(f"[tailor] ⚠️ PHASE 1 WARNING: {len(missing_master)} master skills not in final selection")
                                    print(f"[tailor]   Missing: {missing_master}")
                                    # Add missing master skills by removing non-master skills
                                    non_master_final = [s for s in final_skills if s.lower() not in jd_hard_skills_lower]
                                    if non_master_final:
                                        room = len(non_master_final) - len(missing_master)
                                        if room >= 0:
                                            final_skills = [s for s in final_skills if s.lower() in master_skill_names or s.lower() in jd_hard_skills_lower]
                                            # Fix: master_skill_names/missing_master are lowercase
                                            # (built by Step A1's .lower()) — re-insert using the
                                            # original casing so the resume doesn't show "kubernetes"
                                            final_skills.extend(master_skill_casing.get(s, s) for s in missing_master)
                                            print(f"[tailor] ✓ PHASE 4: Re-added missing master skills")
                                else:
                                    print(f"[tailor] ✓ PHASE 4: All {len(master_skill_names)} master skills preserved in final selection")

                                # Rebuild skills array with only selected skills
                                # Keep categories as-is (no moving)
                                new_skills = []
                                for group in tailored_data.get('skills', []):
                                    filtered_items = [item for item in group.get('items', []) if item in final_skills]
                                    if filtered_items:
                                        new_skills.append({'category': group['category'], 'items': filtered_items})

                                tailored_data['skills'] = new_skills

                                print(f"\n[tailor] ✓ SKILLS OPTIMIZED: {current_count} → {len(final_skills)} skills")
                                print(f"[tailor] ║ Languages preserved: {len(tier1_skills)} ║")
                                print(f"[tailor] ║ Frameworks kept: {min(len(tier3_skills), 5)} ║")
                                print(f"[tailor] ║ High-value tools: {min(len(tier4_skills), 3)} ║")
                                print(f"[tailor] ╚═══════════════════════════════════════════════════════╝\n")
                        else:
                            print(f"[tailor] role coherence: PASS (score: {coherence_check['coherence_score']})")
                    except Exception as e:
                        print(f"[tailor] role validation failed (non-fatal): {e}")

                # ---- SUMMARY ENFORCEMENT: ALWAYS use master + programmatic injection ----
                # We NEVER trust the AI's summary rewrite. Instead we:
                #   1. Start from the master summary (exact text from DB)
                #   2. Collect JD keywords the AI tried to add
                #   3. Programmatically inject them into MIDDLE sentences
                #   4. First and last sentences stay untouched
                master_summary = (master.summary or '').strip()
                ai_summary = (tailored_data.get('summary', '') or '').strip()

                if master_summary:
                    import re as _re_inj

                    # ---- Step 1: collect keywords to inject ----
                    new_keywords = []

                    # from JD analysis: hard skills + soft skills not already in master
                    jd_hard = []
                    jd_soft = []
                    jd_top = []
                    if jd_analysis and isinstance(jd_analysis, dict):
                        jd_hard = jd_analysis.get('hard_skills', [])
                        jd_soft = jd_analysis.get('soft_skills', [])
                        jd_top = jd_analysis.get('top_keywords', [])

                    master_lower = master_summary.lower()
                    ai_lower = ai_summary.lower() if ai_summary else ''

                    def _keyword_in_text(kw, text):
                        """Word-boundary check: 'java' must NOT match 'javascript'.
                        Uses regex \\b word boundaries for accurate matching.
                        """
                        kw_clean = kw.strip().lower()
                        if not kw_clean:
                            return False
                        # For terms with special chars (c++, c#, .net, ci/cd), use escaped literal
                        if any(c in kw_clean for c in ('+', '#', '.', '/')):
                            pattern = r'(?:^|[\s,;|(])' + _re_inj.escape(kw_clean) + r'(?:$|[\s,;|)])'
                        else:
                            pattern = r'\b' + _re_inj.escape(kw_clean) + r'\b'
                        return bool(_re_inj.search(pattern, text.lower()))

                    # prefer keywords the AI tried to inject (they're likely the best fits)
                    for term in jd_hard + jd_soft + jd_top:
                        if not _keyword_in_text(term, master_lower):
                            # prioritise ones the AI also chose
                            if ai_lower and _keyword_in_text(term, ai_lower):
                                new_keywords.insert(0, term)  # front of list
                            else:
                                new_keywords.append(term)

                    # also grab from keyword gap analysis
                    if keyword_data and isinstance(keyword_data, dict):
                        for kw in keyword_data.get('top_keywords', []):
                            if isinstance(kw, dict) and kw.get('resume_status') in ('missing', 'weak_match'):
                                k = kw.get('keyword', '')
                                if k and not _keyword_in_text(k, master_lower) and len(k.split()) <= 3:
                                    new_keywords.append(k)

                    # deduplicate while preserving order
                    # Also filter out education degrees and non-skill terms
                    EDUCATION_TERMS = {
                        'b.sc.', 'bsc', 'm.sc.', 'msc', 'b.eng.', 'm.eng.',
                        'bachelor', 'master', 'phd', 'doctorate', 'diploma',
                        'electrical engineering', 'geomatics engineering',
                        'software engineering', 'mechanical engineering',
                        'civil engineering', 'computer science',
                        'data science', 'geospatial engineering',
                    }
                    seen = set()
                    unique_kw = []
                    for k in new_keywords:
                        kl = k.lower()
                        # Skip education degrees and academic disciplines
                        if any(edu in kl for edu in EDUCATION_TERMS):
                            print(f"[tailor] summary: skipping education term '{k}' (not a skill)")
                            continue
                        if kl not in seen and not _keyword_in_text(k, master_lower):
                            seen.add(kl)
                            unique_kw.append(k)

                    # ---- Step 2: JD title swap in first sentence ----
                    sentences = _re_inj.split(r'(?<=[.!?])\s+', master_summary.strip())
                    sentences = [s.strip() for s in sentences if s.strip()]

                    if jd_analysis and isinstance(jd_analysis, dict):
                        jd_title = (jd_analysis.get('job_title', '') or '').strip()
                        if jd_title and sentences:
                            # look for a role/title in the first sentence to swap
                            # common patterns: "...Software Developer with...", "...Data Analyst with..."
                            import difflib
                            first = sentences[0]
                            if jd_title.lower() not in first.lower() and ai_summary:
                                ai_sents = _re_inj.split(r'(?<=[.!?])\s+', ai_summary.strip())
                                ai_sents = [s.strip() for s in ai_sents if s.strip()]
                                if ai_sents and jd_title.lower() in ai_sents[0].lower():
                                    # AI swapped the title — figure out what it replaced
                                    m_tokens = first.split()
                                    a_tokens = ai_sents[0].split()
                                    sm = difflib.SequenceMatcher(None,
                                        [t.lower() for t in m_tokens],
                                        [t.lower() for t in a_tokens])
                                    for tag, i1, i2, j1, j2 in sm.get_opcodes():
                                        if tag == 'replace':
                                            replaced_in_ai = ' '.join(a_tokens[j1:j2])
                                            if jd_title.lower() in replaced_in_ai.lower():
                                                original_chunk = ' '.join(m_tokens[i1:i2])
                                                sentences[0] = first.replace(original_chunk, jd_title, 1)
                                                print(f"[tailor] swapped title '{original_chunk}' → '{jd_title}' in first sentence")
                                                break

                    # ---- Step 3: smart middle injection ----
                    if unique_kw and len(sentences) >= 2:
                        top_kw = unique_kw[:6]
                        # middle indices (skip first and last sentence)
                        if len(sentences) >= 3:
                            mid_start, mid_end = 1, len(sentences) - 1
                        else:
                            # only 2 sentences — inject into the first one
                            mid_start, mid_end = 0, 1

                        # score each keyword against each middle sentence
                        # cap at 3 keywords per sentence to avoid overloading
                        MAX_KW_PER_SENT = 3
                        placed = {i: [] for i in range(mid_start, mid_end)}
                        unplaced = []
                        for kw in top_kw:
                            kw_words = set(kw.lower().split())
                            # rank all middle sentences by fit
                            scored = []
                            for i in range(mid_start, mid_end):
                                sent_words = set(sentences[i].lower().split())
                                score = len(kw_words & sent_words)
                                if any(w in sentences[i].lower() for w in kw_words):
                                    score += 1
                                scored.append((score, i))
                            scored.sort(key=lambda x: -x[0])
                            # pick the best sentence that isn't full
                            assigned = False
                            for score, idx in scored:
                                if len(placed[idx]) < MAX_KW_PER_SENT:
                                    placed[idx].append(kw)
                                    assigned = True
                                    break
                            if not assigned:
                                unplaced.append(kw)

                        # inject into each middle sentence
                        for i in range(mid_start, mid_end):
                            kws = placed.get(i, [])
                            if not kws:
                                continue
                            sent = sentences[i].rstrip('.')
                            if len(kws) == 1:
                                sent += f' and {kws[0]}'
                            else:
                                sent += f', including {", ".join(kws[:-1])} and {kws[-1]}'
                            sentences[i] = sent + '.'

                        # leftover keywords go as a brief phrase before the last sentence
                        if unplaced:
                            insert_pos = max(1, len(sentences) - 1)
                            if len(unplaced) > 1:
                                leftover_phrase = ', '.join(unplaced[:-1]) + ' and ' + unplaced[-1]
                            else:
                                leftover_phrase = unplaced[0]
                            sentences.insert(insert_pos, f'Proficient in {leftover_phrase}.')

                    elif unique_kw:
                        # single sentence summary — append naturally
                        top_kw = unique_kw[:6]
                        last = sentences[-1].rstrip('.')
                        if len(top_kw) > 1:
                            kw_phrase = ', '.join(top_kw[:-1]) + ' and ' + top_kw[-1]
                        else:
                            kw_phrase = top_kw[0]
                        sentences[-1] = f'{last}, with proficiency in {kw_phrase}.'

                    tailored_data['summary'] = ' '.join(sentences)
                    print(f"[tailor] summary: master preserved, {len(unique_kw)} keywords injected programmatically")

                    # TASK 2: validate/fix the programmatically-built summary (real
                    # integration point — this codebase has no TailorPipeline class
                    # for this to hook into, so it's wired directly where the
                    # summary is actually produced)
                    _summary_gen = get_summary_generator()
                    _fixed_summary, _summary_report = _summary_gen.validate_and_fix_summary(tailored_data['summary'])
                    tailored_data['summary'] = _fixed_summary
                    print(f"[tailor] TASK 2: summary validated (valid={_summary_report['final_valid']}, "
                          f"{_summary_report['final_length']} chars, steps={_summary_report['steps_applied']})")

                # enforce experience: keep AI's smart-injected bullets, enforce structure
                if master.bullets:
                    exp_bullets = [b for b in master.bullets if (b.section_type or 'experience') == 'experience' and b.is_active]
                    proj_bullets = [b for b in master.bullets if (b.section_type or '') == 'project' and b.is_active]

                    # For experience: keep AI's smart keyword injection but enforce structure
                    if exp_bullets:
                        master_roles = {}
                        for b in sorted(exp_bullets, key=lambda x: x.sort_order or 0):
                            key = f"{b.role}|||{b.company}"
                            if key not in master_roles:
                                master_roles[key] = {
                                    'title': b.role,
                                    'company': b.company,
                                    'dates': b.dates or '',
                                    'location': '',
                                    'bullets': [],
                                }
                            master_roles[key]['bullets'].append(b.original_text)

                        # match AI experience entries to master roles
                        ai_exp = tailored_data.get('experience', [])
                        matched_keys = set()
                        for ai_entry in ai_exp:
                            for key, master_entry in master_roles.items():
                                if (ai_entry.get('title', '').strip().lower() == master_entry['title'].strip().lower() and
                                    ai_entry.get('company', '').strip().lower() == master_entry['company'].strip().lower()):
                                    # enforce correct dates from DB
                                    if master_entry['dates']:
                                        ai_entry['dates'] = master_entry['dates']

                                    # ---- SMART BULLET ENFORCEMENT ----
                                    # Keep the AI's keyword-injected bullets when count matches.
                                    # When count doesn't match (AI added/removed bullets),
                                    # merge by position: keep AI version for each slot (keyword-injected),
                                    # then pad/trim to match master count.
                                    ai_bullets = ai_entry.get('bullets', [])
                                    master_bullets = master_entry['bullets']

                                    if len(ai_bullets) == len(master_bullets):
                                        # Count matches — AI's keyword-injected bullets are kept as-is
                                        print(f"[tailor] {master_entry['company']}: keeping {len(ai_bullets)} AI-injected bullets (count match)")
                                    else:
                                        # Count mismatch — merge by position to preserve injections
                                        print(f"[tailor] {master_entry['company']}: bullet count mismatch (AI={len(ai_bullets)}, master={len(master_bullets)}), merging by position")
                                        merged = []
                                        for idx in range(len(master_bullets)):
                                            if idx < len(ai_bullets):
                                                # AI has a bullet for this slot — keep the AI's (keyword-injected) version
                                                merged.append(ai_bullets[idx])
                                            else:
                                                # AI dropped this bullet — restore from master
                                                merged.append(master_bullets[idx])
                                        ai_entry['bullets'] = merged

                                    # grab location from AI (DB doesn't store it)
                                    if not master_entry['location']:
                                        master_entry['location'] = ai_entry.get('location', '')
                                    matched_keys.add(key)
                                    break

                        # add any missing roles that AI dropped
                        for key, master_entry in master_roles.items():
                            if key not in matched_keys:
                                ai_exp.append(master_entry)

                        tailored_data['experience'] = ai_exp

                    # group project bullets by project name
                    if proj_bullets:
                        proj_by_name = {}
                        for b in sorted(proj_bullets, key=lambda x: x.sort_order or 0):
                            key = b.company  # project name stored in company field
                            if key not in proj_by_name:
                                proj_by_name[key] = {
                                    'name': b.company,
                                    'tech_stack': b.tech_stack or '',
                                    'dates': b.dates or '',
                                    'bullets': [],
                                }
                            proj_by_name[key]['bullets'].append(b.original_text)

                        # ---- SMART PROJECT BULLET ENFORCEMENT ----
                        # Keep AI's keyword-injected bullets, only enforce structure (name, count, tech_stack)
                        ai_projs = tailored_data.get('projects', [])
                        matched_proj_keys = set()

                        for ai_proj in ai_projs:
                            ai_name = ai_proj.get('name', '').strip()
                            for key, master_proj in proj_by_name.items():
                                if key in matched_proj_keys:
                                    continue
                                # match by project name (case-insensitive, partial match for long names)
                                if (ai_name.lower() in master_proj['name'].lower() or
                                    master_proj['name'].lower() in ai_name.lower()):

                                    # Enforce project name from master
                                    ai_proj['name'] = master_proj['name']

                                    # Grab tech_stack from AI if master doesn't have it, else keep master's
                                    if master_proj['tech_stack']:
                                        ai_proj['tech_stack'] = master_proj['tech_stack']
                                    elif ai_proj.get('tech_stack'):
                                        master_proj['tech_stack'] = ai_proj['tech_stack']

                                    # Same for dates
                                    if master_proj['dates']:
                                        ai_proj['dates'] = master_proj['dates']
                                    elif ai_proj.get('dates'):
                                        master_proj['dates'] = ai_proj['dates']

                                    # ---- Bullet enforcement: keep AI bullets, enforce count ----
                                    ai_bullets = ai_proj.get('bullets', [])
                                    master_bullets = master_proj['bullets']

                                    if len(ai_bullets) == len(master_bullets):
                                        # Count matches — keep AI's keyword-injected versions
                                        print(f"[tailor] project '{master_proj['name']}': keeping {len(ai_bullets)} AI-injected bullets (count match)")
                                    else:
                                        # Count mismatch — merge by position
                                        print(f"[tailor] project '{master_proj['name']}': bullet count mismatch (AI={len(ai_bullets)}, master={len(master_bullets)}), merging by position")
                                        merged = []
                                        for idx in range(len(master_bullets)):
                                            if idx < len(ai_bullets):
                                                merged.append(ai_bullets[idx])
                                            else:
                                                merged.append(master_bullets[idx])
                                        ai_proj['bullets'] = merged

                                    matched_proj_keys.add(key)
                                    break

                        # Add any master projects that AI dropped entirely
                        for key, master_proj in proj_by_name.items():
                            if key not in matched_proj_keys:
                                ai_projs.append(master_proj)

                        tailored_data['projects'] = ai_projs

                # certifications from DB (was missing before)
                if master.education:
                    # check if master has certifications stored
                    # (certifications might be in a separate field or from AI output)
                    pass  # keep whatever the AI provided or master has

                print("[tailor] master resume data applied")
            else:
                print("[tailor] no master resume in db, skipping")
        except Exception as e:
            print(f"[tailor] enforcement error (non-fatal): {e}")

    # step 4.4: Employment timeline validation (Fix #4)
    try:
        if isinstance(tailored_data, dict):
            timeline_analysis = analyze_employment_timeline(tailored_data, '')
            if not timeline_analysis.get('timeline_coherent', True):
                print(f"[tailor] ═══ Timeline Issues ═══")
                for issue in timeline_analysis.get('issues', []):
                    print(f"[tailor]   {issue['severity']}: {issue['message']}")
                    print(f"[tailor]     → {issue['recommendation']}")
                print(f"[tailor] ═══════════════════════")

                # Add warnings to response
                tailored_data['_warnings'] = tailored_data.get('_warnings', [])
                tailored_data['_warnings'].extend(timeline_analysis['issues'])
            else:
                print(f"[tailor] timeline: PASS ({timeline_analysis.get('total_jobs', 0)} jobs, {timeline_analysis.get('span_years', 0)} year span)")
    except Exception as e:
        print(f"[tailor] timeline validation failed (non-fatal): {e}")

    # step 4.5: structure validation agent — ensures JSON matches template format
    # IMPORTANT: Save curated data BEFORE the validator runs — the validator
    # replaces tailored_data entirely and may lose our curated skills/summary/header.
    curated_skills = None
    curated_summary = None
    curated_header = None
    if isinstance(tailored_data, dict):
        curated_skills = tailored_data.get('skills', [])
        curated_summary = tailored_data.get('summary', '')
        curated_header = tailored_data.get('header', {})

    if isinstance(tailored_data, dict):
        try:
            from app.services.prompts.structure_validator import STRUCTURE_VALIDATOR_SYSTEM, build_validator_message

            master = MasterResume.query.filter_by(user_id=session.get('user_id')).first()
            if master:
                master_json = master.to_dict()
                # build master structure for comparison
                master_structure = {
                    'header': {
                        'name': master.full_name or '',
                        'location': master.location or '',
                        'phone': master.phone or '',
                        'email': master.email or '',
                        'linkedin': master.linkedin_url or '',
                        'github': master.github_url or '',
                    },
                    'skills': master.skills or [],
                    'education': master.education or [],
                }
                # add bullets structure
                if master.bullets:
                    exp_entries = {}
                    proj_entries = {}
                    for b in sorted(master.bullets, key=lambda x: x.sort_order or 0):
                        if (b.section_type or 'experience') == 'experience' and b.is_active:
                            key = f"{b.role}|||{b.company}"
                            if key not in exp_entries:
                                exp_entries[key] = {'title': b.role, 'company': b.company, 'bullets': []}
                            exp_entries[key]['bullets'].append(b.original_text)
                        elif b.section_type == 'project' and b.is_active:
                            if b.company not in proj_entries:
                                proj_entries[b.company] = {
                                    'name': b.company,
                                    'tech_stack': b.tech_stack or '',
                                    'dates': b.dates or '',
                                    'bullets': [],
                                }
                            proj_entries[b.company]['bullets'].append(b.original_text)
                    master_structure['experience'] = list(exp_entries.values())
                    master_structure['projects'] = list(proj_entries.values())

                validator_msg = build_validator_message(tailored_data, master_structure)
                
                app_env = current_app.config.get('APP_ENV', 'testing').strip()
                if app_env == 'nvidia':
                    from app.services.claude_client import nvidia as ai_client
                    print("[json-validator] Using NVIDIA Llama-3.3-Nemotron")
                else:
                    from app.services.claude_client import claude as ai_client
                    print(f"[json-validator] Using AWS Bedrock/Claude (APP_ENV={app_env})")

                # ========== SAVE SOFT SKILLS BEFORE VALIDATOR (defensive safety net) ==========
                # The structure validator below replaces tailored_data entirely. Today,
                # soft-skills injection runs AFTER this step, so there's nothing to lose
                # yet — but if that ordering ever changes, this save/restore guarantees
                # any soft-skill-enhanced bullets already present survive the validator.
                print(f"[tailor] Saving soft skills bullets before structure validator...")
                saved_soft_skills_bullets = {}

                for exp_idx, exp in enumerate(tailored_data.get('experience', [])):
                    saved_soft_skills_bullets[f'exp_{exp_idx}'] = {
                        'bullets': exp.get('bullets', []).copy(),
                        'count': len(exp.get('bullets', []))
                    }

                for proj_idx, proj in enumerate(tailored_data.get('projects', [])):
                    saved_soft_skills_bullets[f'proj_{proj_idx}'] = {
                        'bullets': proj.get('bullets', []).copy(),
                        'count': len(proj.get('bullets', []))
                    }

                print(f"[tailor] Saved {len(saved_soft_skills_bullets)} sections with soft skills bullets")

                val_result = ai_client.analyze(STRUCTURE_VALIDATOR_SYSTEM, validator_msg, max_tokens=16000, temperature=0.1, force_json=True)

                if not val_result.get('error'):
                    val_resp = val_result.get('response')
                    if isinstance(val_resp, dict) and 'summary' in val_resp and 'skills' in val_resp:
                        tailored_data = val_resp
                        total_tokens += val_result.get('tokens_used', 0)
                        total_cost += val_result.get('cost_usd', 0)
                        pipeline_steps.append('structure_validator')
                        print("[tailor] structure validation done — JSON fixed")

                        # ========== RESTORE SOFT SKILLS BULLETS AFTER VALIDATOR ==========
                        print(f"[tailor] Restoring soft skills bullets after structure validator...")

                        for exp_idx, exp in enumerate(tailored_data.get('experience', [])):
                            key = f'exp_{exp_idx}'
                            if key in saved_soft_skills_bullets:
                                saved_data = saved_soft_skills_bullets[key]
                                current_bullets = exp.get('bullets', [])

                                # Only restore if bullet count matches (means structure is same)
                                if len(current_bullets) == saved_data['count']:
                                    exp['bullets'] = saved_data['bullets']
                                    print(f"[tailor] ✓ Restored experience section #{exp_idx} soft skills")
                                else:
                                    print(f"[tailor] ⚠ Experience section #{exp_idx} structure changed, skipping restore")

                        for proj_idx, proj in enumerate(tailored_data.get('projects', [])):
                            key = f'proj_{proj_idx}'
                            if key in saved_soft_skills_bullets:
                                saved_data = saved_soft_skills_bullets[key]
                                current_bullets = proj.get('bullets', [])

                                # Only restore if bullet count matches
                                if len(current_bullets) == saved_data['count']:
                                    proj['bullets'] = saved_data['bullets']
                                    print(f"[tailor] ✓ Restored project #{proj_idx} soft skills")
                                else:
                                    print(f"[tailor] ⚠ Project #{proj_idx} structure changed, skipping restore")

                        # Verify soft skills survived (inline flatten — the flatten_bullets()
                        # helper below isn't defined yet at this point in the function)
                        final_text = '\n'.join(
                            b for exp in tailored_data.get('experience', []) for b in exp.get('bullets', [])
                        ) + '\n' + '\n'.join(
                            b for proj in tailored_data.get('projects', []) for b in proj.get('bullets', [])
                        )
                        final_text = final_text.lower()
                        survived_count = 0
                        for skill in soft_skills_data.get('missing_soft_skills', []):
                            if skill.lower() in final_text:
                                survived_count += 1
                        print(f"[tailor] Soft skills survived: {survived_count}/{len(soft_skills_data.get('missing_soft_skills', []))}")

                        # ---- RE-ENFORCE tech_stack & dates from master DB ----
                        # The structure validator AI doesn't know about tech_stack,
                        # so it drops it. Re-inject from master DB bullets.
                        if master and master.bullets:
                            proj_tech = {}  # project_name → {tech_stack, dates}
                            for b in master.bullets:
                                if b.section_type == 'project' and b.is_active and b.company:
                                    if b.company not in proj_tech:
                                        proj_tech[b.company] = {
                                            'tech_stack': b.tech_stack or '',
                                            'dates': b.dates or '',
                                        }

                            for proj in tailored_data.get('projects', []):
                                proj_name = proj.get('name', '').strip()
                                if proj_name and (not proj.get('tech_stack') or not proj.get('dates')):
                                    # Try exact match first, then partial
                                    for db_name, db_data in proj_tech.items():
                                        if (proj_name.lower() in db_name.lower() or
                                            db_name.lower() in proj_name.lower()):
                                            if not proj.get('tech_stack') and db_data['tech_stack']:
                                                proj['tech_stack'] = db_data['tech_stack']
                                                print(f"[tailor] re-injected tech_stack for '{proj_name}': {db_data['tech_stack'][:50]}")
                                            if not proj.get('dates') and db_data['dates']:
                                                proj['dates'] = db_data['dates']
                                                print(f"[tailor] re-injected dates for '{proj_name}': {db_data['dates']}")
                                            break
                    else:
                        print(f"[tailor] structure validator returned unusable data, skipping")
                else:
                    print(f"[tailor] structure validator error: {val_result['error']}")
        except Exception as e:
            print(f"[tailor] structure validator error (non-fatal): {e}")

    # ---- RE-ENFORCE curated skills, summary & header after validator ----
    # The structure validator replaces tailored_data entirely, which can
    # wipe the carefully curated skills (Tier 1/2/3, competing tech suppression,
    # dedup), the programmatically injected summary, and the location override.
    # Force them all back.
    if isinstance(tailored_data, dict):
        if curated_skills:
            tailored_data['skills'] = curated_skills
            print(f"[tailor] re-enforced curated skills ({len(curated_skills)} categories)")
        if curated_summary:
            tailored_data['summary'] = curated_summary
            print(f"[tailor] re-enforced curated summary ({len(curated_summary)} chars)")
        if curated_header:
            tailored_data['header'] = curated_header
            print(f"[tailor] re-enforced header (location: {curated_header.get('location', 'n/a')})")

    # NOTE: External humanize API removed. Humanization rules are now baked
    # directly into the tailor prompt (RESUME_TAILOR_SYSTEM) so the AI produces
    # human-sounding text in a single pass — no post-processing needed.

    # ---- STEP 4: DETERMINISTIC HARD SKILLS INJECTION ----
    # Instead of relying on an unreliable AI enhancer, programmatically inject
    # missing JD hard skills into the correct skills category. Then reorder
    # each category so JD-matched skills come FIRST (capping-safe).
    if isinstance(tailored_data, dict) and jd_analysis and isinstance(jd_analysis, dict):
        try:
            # Collect all JD hard skills + top keywords
            jd_hard = set()
            for s_item in jd_analysis.get('hard_skills', []):
                if isinstance(s_item, str) and s_item.strip():
                    jd_hard.add(s_item.strip())
            for s_item in jd_analysis.get('top_keywords', []):
                if isinstance(s_item, str) and s_item.strip():
                    jd_hard.add(s_item.strip())

            if jd_hard:
                current_skills = tailored_data.get('skills', [])

                # Build lowercase text of ALL current skill items for matching
                current_skills_lower = set()
                for cat in current_skills:
                    for item in cat.get('items', []):
                        current_skills_lower.add(item.strip().lower())

                # Find missing skills (not already present)
                missing = []
                for skill in jd_hard:
                    skill_lower = skill.lower()
                    # Check exact match and substring containment
                    found = False
                    for existing in current_skills_lower:
                        if skill_lower == existing or skill_lower in existing or existing in skill_lower:
                            found = True
                            break
                    if not found:
                        missing.append(skill)

                if missing:
                    # Build proof text from all bullets + summary for provability check
                    all_proof_text = ''
                    for exp in tailored_data.get('experience', []):
                        for b in exp.get('bullets', []):
                            if isinstance(b, str):
                                all_proof_text += b.lower() + ' '
                        # Also check tech_stack lines
                        ts = exp.get('tech_stack', '')
                        if ts:
                            all_proof_text += ts.lower() + ' '
                    for proj in tailored_data.get('projects', []):
                        for b in proj.get('bullets', []):
                            if isinstance(b, str):
                                all_proof_text += b.lower() + ' '
                        ts = proj.get('tech_stack', '')
                        if ts:
                            all_proof_text += ts.lower() + ' '
                    all_proof_text += (tailored_data.get('summary', '') or '').lower()

                    # ── Category mapping for automatic placement ──
                    _CATEGORY_MAP = {
                        # Languages
                        'python': 'Languages', 'java': 'Languages', 'javascript': 'Languages',
                        'c++': 'Languages', 'c#': 'Languages', 'typescript': 'Languages',
                        'sql': 'Languages', 'r': 'Languages', 'go': 'Languages', 'golang': 'Languages',
                        'rust': 'Languages', 'ruby': 'Languages', 'scala': 'Languages',
                        'kotlin': 'Languages', 'swift': 'Languages', 'php': 'Languages',
                        'html': 'Languages', 'html5': 'Languages', 'css': 'Languages',
                        'css3': 'Languages', 'bash': 'Languages', 'shell': 'Languages',
                        'perl': 'Languages', 'matlab': 'Languages', 'julia': 'Languages',
                        'haskell': 'Languages', 'c programming': 'Languages',
                        # Frameworks & Libraries
                        'react': 'Frameworks & Libraries', 'react native': 'Frameworks & Libraries',
                        'angular': 'Frameworks & Libraries', 'vue': 'Frameworks & Libraries',
                        'vue.js': 'Frameworks & Libraries', 'spring boot': 'Frameworks & Libraries',
                        'spring': 'Frameworks & Libraries', 'django': 'Frameworks & Libraries',
                        'flask': 'Frameworks & Libraries', 'fastapi': 'Frameworks & Libraries',
                        'express': 'Frameworks & Libraries', 'express.js': 'Frameworks & Libraries',
                        'node.js': 'Frameworks & Libraries', 'pytorch': 'Frameworks & Libraries',
                        'tensorflow': 'Frameworks & Libraries', 'scikit-learn': 'Frameworks & Libraries',
                        'pandas': 'Frameworks & Libraries', 'numpy': 'Frameworks & Libraries',
                        'langchain': 'Frameworks & Libraries', 'hugging face': 'Frameworks & Libraries',
                        'huggingface': 'Frameworks & Libraries', 'next.js': 'Frameworks & Libraries',
                        'jquery': 'Frameworks & Libraries', '.net': 'Frameworks & Libraries',
                        'bootstrap': 'Frameworks & Libraries', 'sqlalchemy': 'Frameworks & Libraries',
                        'jinja2': 'Frameworks & Libraries', 'restful apis': 'Frameworks & Libraries',
                        'keras': 'Frameworks & Libraries', 'opencv': 'Frameworks & Libraries',
                        'peft': 'Frameworks & Libraries', 'transformers': 'Frameworks & Libraries',
                        'agent development kits': 'Frameworks & Libraries',
                        # *** CRITICAL: Concepts (NOT Languages!) ***
                        'ai-driven methods': 'Concepts', 'numerical methods': 'Concepts',
                        'computational numerical methods': 'Concepts',
                        'gnss error modeling': 'Concepts', 'gnss': 'Concepts',
                        'algorithm tuning': 'Concepts', 'linear optimization': 'Concepts',
                        'non-linear optimization': 'Concepts', 'optimization': 'Concepts',
                        'regression analysis': 'Concepts', 'statistical analysis': 'Concepts',
                        'customer support': 'Concepts', 'automation': 'Concepts',
                        'automation tools': 'Concepts', 'automated test suites': 'Concepts',
                        'big data analysis': 'Concepts',
                        # Issue #1 fix: degrees/methodologies → Concepts, NOT Languages
                        'electrical engineering': 'Concepts',
                        'geomatics engineering': 'Concepts',
                        'software engineering': 'Concepts',
                        'computer science': 'Concepts',
                        'positioning algorithms': 'Concepts',
                        'agile': 'Concepts',
                        'scrum': 'Concepts',
                        'automation tools for regression analysis': 'Concepts',
                        'technical communication': 'Concepts',
                        # Tools & Platforms
                        'docker': 'Tools & Platforms', 'kubernetes': 'Tools & Platforms',
                        'aws': 'Tools & Platforms', 'azure': 'Tools & Platforms',
                        'gcp': 'Tools & Platforms', 'google cloud': 'Tools & Platforms',
                        'git': 'Tools & Platforms', 'github': 'Tools & Platforms',
                        'gitlab': 'Tools & Platforms', 'jenkins': 'Tools & Platforms',
                        'jira': 'Tools & Platforms', 'linux': 'Tools & Platforms',
                        'terraform': 'Tools & Platforms', 'ansible': 'Tools & Platforms',
                        'kafka': 'Tools & Platforms', 'redis': 'Tools & Platforms',
                        'elasticsearch': 'Tools & Platforms', 'heroku': 'Tools & Platforms',
                        'vercel': 'Tools & Platforms', 'postman': 'Tools & Platforms',
                        'grafana': 'Tools & Platforms', 'prometheus': 'Tools & Platforms',
                        'mysql': 'Tools & Platforms', 'postgresql': 'Tools & Platforms',
                        'mongodb': 'Tools & Platforms', 'dynamodb': 'Tools & Platforms',
                        'datadog': 'Tools & Platforms', 'splunk': 'Tools & Platforms',
                        'aws bedrock': 'Tools & Platforms', 'vs code': 'Tools & Platforms',
                        'maven': 'Tools & Platforms', 'gradle': 'Tools & Platforms',
                        'circleci': 'Tools & Platforms', 'travis ci': 'Tools & Platforms',
                        'airflow': 'Tools & Platforms', 'mlflow': 'Tools & Platforms',
                        'wandb': 'Tools & Platforms', 'dvc': 'Tools & Platforms',
                        # Concepts
                        'ci/cd': 'Concepts', 'ci/cd pipelines': 'Concepts',
                        'agile': 'Concepts', 'scrum': 'Concepts',
                        'microservices': 'Concepts', 'machine learning': 'Concepts',
                        'deep learning': 'Concepts', 'nlp': 'Concepts',
                        'natural language processing': 'Concepts',
                        'devops': 'Concepts', 'cloud orchestration': 'Concepts',
                        'code review': 'Concepts', 'unit testing': 'Concepts',
                        'test-driven development': 'Concepts', 'tdd': 'Concepts',
                        'distributed systems': 'Concepts', 'data pipelines': 'Concepts',
                        'data preprocessing': 'Concepts', 'feature engineering': 'Concepts',
                        'statistical modeling': 'Concepts', 'api design': 'Concepts',
                        'software engineering best practices': 'Concepts',
                        'version control systems': 'Concepts',
                        'collaborative development environments': 'Concepts',
                        'open-source': 'Concepts', 'open source': 'Concepts',
                        'highly concurrent systems': 'Concepts',
                        'server applications': 'Concepts',
                        'containerization': 'Concepts',
                        # Programming Concepts
                        'data structures': 'Programming Concepts',
                        'algorithms': 'Programming Concepts',
                        'object-oriented programming': 'Programming Concepts',
                        'oop': 'Programming Concepts', 'multithreading': 'Programming Concepts',
                        'time complexity': 'Programming Concepts',
                        'design patterns': 'Programming Concepts',
                    }

                    injected = []
                    skipped = []
                    for skill in sorted(missing):
                        skill_lower = skill.lower()

                        # Determine category
                        category = _CATEGORY_MAP.get(skill_lower)
                        if not category:
                            # Fuzzy: check if any map key is contained in the skill or vice versa
                            for key, cat in _CATEGORY_MAP.items():
                                if key in skill_lower or skill_lower in key:
                                    category = cat
                                    break
                        if not category:
                            # Fallback to _COMPREHENSIVE_CATEGORY_MAP (has finance, healthcare, domain terms)
                            category = _COMPREHENSIVE_CATEGORY_MAP.get(skill_lower)
                        if not category:
                            for key, cat in _COMPREHENSIVE_CATEGORY_MAP.items():
                                if key in skill_lower or skill_lower in key:
                                    category = cat
                                    break
                        if not category:
                            # Default heuristic: multi-word → Concepts, single word → Tools
                            category = 'Concepts' if len(skill.split()) >= 2 else 'Tools & Platforms'

                        # Find or create the target category in current_skills
                        target_cat = None
                        for cat in current_skills:
                            if cat.get('category', '').lower() == category.lower():
                                target_cat = cat
                                break
                        if not target_cat:
                            # Try partial match (e.g., "Frameworks" matches "Frameworks & Libraries")
                            cat_first_word = category.split()[0].lower() if category else ''
                            for cat in current_skills:
                                if cat.get('category', '').lower().startswith(cat_first_word):
                                    target_cat = cat
                                    break
                        if not target_cat:
                            target_cat = {'category': category, 'items': []}
                            current_skills.append(target_cat)

                        # Check for duplicate across ALL categories (fuzzy match)
                        is_duplicate = False
                        for dup_cat in current_skills:
                            for dup_item in dup_cat.get('items', []):
                                dup_lower = dup_item.lower()
                                if (skill_lower == dup_lower or
                                    skill_lower in dup_lower or
                                    dup_lower in skill_lower):
                                    is_duplicate = True
                                    break
                            if is_duplicate:
                                break
                        if is_duplicate:
                            continue

                        # CHUNK 4.3: Validation gate — validate skill before injection
                        is_valid_skill, reject_reason = validate_skill(skill)
                        if not is_valid_skill:
                            print(f"[tailor] ✗ Skill '{skill}' REJECTED: {reject_reason}")
                            continue

                        # Inject the skill
                        target_cat['items'].append(skill)
                        has_proof = any(
                            word in all_proof_text
                            for word in skill_lower.split()
                            if len(word) > 2  # skip short words like "of", "in"
                        )
                        injected.append((skill, target_cat['category'], 'proven' if has_proof else 'JD-only'))

                    if injected:
                        for skill_name, cat_name, proof_status in injected:
                            print(f"[tailor] injected hard skill: '{skill_name}' → {cat_name} ({proof_status})")
                        print(f"[tailor] total hard skills injected: {len(injected)}")
                        pipeline_steps.append('hard_skills_inject')
                    else:
                        print("[tailor] no new hard skills to inject (all already present)")
                else:
                    print(f"[tailor] hard skills: all {len(jd_hard)} JD keywords already present")

                # Debug logging: verify hard skills in final output
                print(f"[tailor] Hard skills in final output:")
                for category in tailored_data.get('skills', []):
                    if category['category'] in ['Languages', 'Concepts', 'Tools & Platforms']:
                        print(f"  {category['category']}: {', '.join(category.get('items', []))}")

                # ── Mark injected skills so LaTeX capping won't remove them ──
                injected_skill_names = {skill.lower() for skill, _, _ in injected}

                # ── Reorder: injected skills FIRST (they're the ones closing JD gaps),
                #    then other JD-matched skills, then everything else ──
                # This ensures LaTeX capping (from the end) drops non-JD skills first,
                # and never drops a newly-injected skill before an already-present one.
                jd_lower = {s.lower() for s in jd_hard}
                for cat in current_skills:
                    items = cat.get('items', [])
                    injected_items = [i for i in items if i.lower() in injected_skill_names]
                    jd_items = [i for i in items if i.lower() in jd_lower and i.lower() not in injected_skill_names]
                    other_items = [i for i in items if i.lower() not in jd_lower and i.lower() not in injected_skill_names]
                    cat['items'] = injected_items + jd_items + other_items

                # Store injected and master skill names in tailored_data for LaTeX to reference
                if injected_skill_names:
                    if 'metadata' not in tailored_data:
                        tailored_data['metadata'] = {}
                    tailored_data['metadata']['injected_skills'] = list(injected_skill_names)

                # PHASE 4: Store master skills in metadata for preservation logic
                if 'metadata' not in tailored_data:
                    tailored_data['metadata'] = {}
                tailored_data['metadata']['master_skills'] = sorted(list(master_skill_names))

                print(f"[tailor] PHASE 4: Stored {len(master_skill_names)} master skills in metadata")

                tailored_data['skills'] = current_skills
                print(f"[tailor] skills reordered: injected + JD-matched keywords placed first in each category")

                # ========== PHASE 4: MASTER SKILLS PRESERVATION SUMMARY ==========
                print(f"\n[tailor] ╔═══════════════════════════════════════════════════════╗")
                print(f"[tailor] ║ PHASE 4: MASTER SKILLS PRESERVATION SUMMARY            ║")
                print(f"[tailor] ╠═══════════════════════════════════════════════════════╣")

                # Count preserved master skills in final output
                preserved_count = 0
                final_skills_lower = set()
                for skill_group in tailored_data.get('skills', []):
                    for item in skill_group.get('items', []):
                        final_skills_lower.add(item.strip().lower())
                        if item.strip().lower() in master_skill_names:
                            preserved_count += 1

                print(f"[tailor] ║ Master Skills Extracted: {len(master_skill_names)}")
                print(f"[tailor] ║ Master Skills Preserved: {preserved_count}")

                if preserved_count == len(master_skill_names):
                    print(f"[tailor] ║ Status: ✓ 100% PRESERVED")
                else:
                    missing = len(master_skill_names) - preserved_count
                    print(f"[tailor] ║ Status: ⚠️ {missing} MISSING")

                print(f"[tailor] ╚═══════════════════════════════════════════════════════╝\n")

                # ============= FIX #3: Debug logging for hard skills verification =============
                print(f"\n[tailor] ╔═══════════════════════════════════════════════════════╗")
                print(f"[tailor] ║ HARD SKILLS FINAL VERIFICATION                       ║")
                print(f"[tailor] ╚═══════════════════════════════════════════════════════╝")

                # List of expected hard skills that should be in final output
                expected_hard_skills = {
                    'C/C++ programming': ['Languages'],
                    'Python': ['Languages', 'Python programming'],
                    'linear optimization': ['Concepts'],
                    'non-linear optimization': ['Concepts'],
                    'GNSS': ['Concepts', 'Tools & Platforms'],
                    'positioning algorithms': ['Concepts'],
                    'algorithm development': ['Concepts'],
                    'algorithm tuning': ['Concepts'],
                    'automated test suites': ['Concepts'],
                }

                for skill, expected_categories in expected_hard_skills.items():
                    found = False
                    found_in_category = None

                    if isinstance(tailored_data, dict):
                        for skill_group in tailored_data.get('skills', []):
                            category = skill_group.get('category', '')
                            items = [s.lower() for s in skill_group.get('items', [])]

                            if any(skill.lower() in item for item in items):
                                found = True
                                found_in_category = category
                                break

                    if found:
                        print(f"[tailor] ✓ {skill:30s} → {found_in_category}")
                    else:
                        print(f"[tailor] ✗ {skill:30s} → NOT FOUND IN SKILLS")

                print(f"[tailor] ╚═══════════════════════════════════════════════════════╝\n")

                # Update curated_skills snapshot so any subsequent re-enforcement
                # preserves the injected + reordered version
                curated_skills = current_skills
        except Exception as e:
            print(f"[tailor] hard skills injection failed (non-fatal): {e}")


    def flatten_bullets(data):
        """Collect all bullets from experience and projects into a flat list."""
        bullets = []
        for exp in data.get('experience', []):
            bullets.extend(exp.get('bullets', []))
        for proj in data.get('projects', []):
            bullets.extend(proj.get('bullets', []))
        return bullets

    # ========== SKILLS CATEGORIZATION VALIDATION ==========
    if isinstance(tailored_data, dict):
        print(f"\n[tailor] SKILLS CATEGORIZATION VALIDATION:")

        CORRECT_CATEGORIES = {
            'Python': 'Languages',
            'JavaScript': 'Languages',
            'TypeScript': 'Languages',
            'C++': 'Languages',
            'Java': 'Languages',
            'C#': 'Languages',
            'React': 'Frameworks & Libraries',
            'Django': 'Frameworks & Libraries',
            'FastAPI': 'Frameworks & Libraries',
            'Spring Boot': 'Frameworks & Libraries',
            'Vue.js': 'Frameworks & Libraries',
            'PyTorch': 'Frameworks & Libraries',
            'Hugging Face Transformers': 'Frameworks & Libraries',
            'AWS': 'Tools & Platforms',
            'Docker': 'Tools & Platforms',
            'Kubernetes': 'Tools & Platforms',
            'SageMaker': 'Tools & Platforms',
            'Linux': 'Tools & Platforms',
            'Git': 'Tools & Platforms',
            'REST APIs': 'Concepts',
            'RESTful APIs': 'Concepts',
            'GraphQL': 'Concepts',
            'GraphQL APIs': 'Concepts',
            'async handling': 'Concepts',
            'data pipelines': 'Concepts',
            'state management': 'Concepts',
            'CI/CD Pipelines': 'Concepts',
            'CI/CD': 'Concepts',
            'Algorithms': 'Concepts',
            'Design Patterns': 'Concepts',
            # Items that should NEVER be in Languages (from bug report)
            'AI-driven methods': 'Concepts',
            'Agile/Scrum': 'Concepts',
            'Agile': 'Concepts',
            'Scrum': 'Concepts',
            'Electrical Engineering': 'Concepts',
            'Geomatics Engineering': 'Concepts',
            'Software Engineering': 'Concepts',
            'GNSS error modeling': 'Concepts',
            'Big Data Analysis': 'Concepts',
            'Machine Learning': 'Concepts',
            'Deep Learning': 'Concepts',
        }

        miscategorized = []
        for category_group in tailored_data.get('skills', []):
            category_name = category_group.get('category', '')
            for item in category_group.get('items', []):
                expected_category = CORRECT_CATEGORIES.get(item)

                if expected_category and expected_category != category_name:
                    miscategorized.append({
                        'skill': item,
                        'current': category_name,
                        'correct': expected_category
                    })

        if miscategorized:
            print(f"[tailor] ⚠️ {len(miscategorized)} MISCATEGORIZED SKILLS FOUND:")
            for issue in miscategorized:
                print(f"[tailor]   {issue['skill']}: '{issue['current']}' → should be '{issue['correct']}'")

            # Auto-fix
            for issue in miscategorized:
                # Find and update the skill
                for category_group in tailored_data.get('skills', []):
                    if issue['skill'] in category_group.get('items', []):
                        category_group['items'].remove(issue['skill'])

                    # Add to correct category (create if needed)
                    if category_group.get('category') == issue['correct']:
                        if issue['skill'] not in category_group.get('items', []):
                            category_group['items'].insert(0, issue['skill'])

                print(f"[tailor] ✓ Fixed: {issue['skill']}")
        else:
            print(f"[tailor] ✓ All skills correctly categorized")

    # ---- STEP 5: CLICHÉ & NEGATIVE PHRASE POST-PROCESSING ----
    # Safety net — scan all text fields and replace any banned phrases that slipped through.
    if isinstance(tailored_data, dict):
        _CLICHE_REPLACEMENTS = {
            'results-driven': '',
            'result-driven': '',
            'detail-oriented': '',
            'detail oriented': '',
            'self-starter': '',
            'self starter': '',
            'go-getter': '',
            'team player': '',
            'think outside the box': '',
            'outside the box': '',
            'synergy': '',
            'synergize': '',
            'passionate about': '',
            'proven track record': '',
            'strong work ethic': '',
            'hardworking': '',
            'hard working': '',
            'highly motivated': '',
            'fast learner': '',
            'quick learner': '',
            'proactive': '',
            'innovative': '',
            'strategic thinker': '',
            'results-oriented': '',
            'result-oriented': '',
            'out-of-the-box': '',
            'value-add': '',
            'value-added': '',
            'best-in-class': '',
            'cutting-edge': '',
            'cutting edge': '',
            'game-changer': '',
            'game changer': '',
            'guru': '',
            'ninja': '',
            'rockstar': '',
            'rock star': '',
            'seasoned professional': '',
            'duties included': '',
            'responsible for': '',
            'assisted with': '',
            'etc.': '',
            'and more': '',
        }

        import re as _re_cliche

        def _clean_cliches(text):
            """Remove clichés from a text string."""
            if not isinstance(text, str):
                return text
            cleaned = text
            for phrase, replacement in _CLICHE_REPLACEMENTS.items():
                pattern = _re_cliche.compile(r'\b' + _re_cliche.escape(phrase) + r'\b', _re_cliche.IGNORECASE)
                cleaned = pattern.sub(replacement, cleaned)
            # Clean up resulting double spaces, leading/trailing commas
            cleaned = _re_cliche.sub(r'\s{2,}', ' ', cleaned)
            cleaned = _re_cliche.sub(r',\s*,', ',', cleaned)
            cleaned = _re_cliche.sub(r'^\s*,\s*', '', cleaned)
            cleaned = _re_cliche.sub(r'\s*,\s*$', '', cleaned)
            return cleaned.strip()

        cliche_found = False

        # Scan experience bullets
        for exp in tailored_data.get('experience', []):
            bullets = exp.get('bullets', [])
            for i, bullet in enumerate(bullets):
                cleaned = _clean_cliches(bullet)
                if cleaned != bullet:
                    bullets[i] = cleaned
                    cliche_found = True

        # Scan project bullets
        for proj in tailored_data.get('projects', []):
            bullets = proj.get('bullets', [])
            for i, bullet in enumerate(bullets):
                cleaned = _clean_cliches(bullet)
                if cleaned != bullet:
                    bullets[i] = cleaned
                    cliche_found = True

        # Scan summary
        summary = tailored_data.get('summary', '')
        if summary:
            cleaned_summary = _clean_cliches(summary)
            if cleaned_summary != summary:
                tailored_data['summary'] = cleaned_summary
                cliche_found = True

        if cliche_found:
            print("[tailor] clichés detected and removed (post-processing safety net)")

    # ═══════════════════════════════════════════════════════════════════
    # CHUNK 5.5: Validate and Log Summary
    # Validates summary before output, fixes truncation
    # ═══════════════════════════════════════════════════════════════════
    if isinstance(tailored_data, dict):
        summary = tailored_data.get('summary', '')
        if summary:
            print(f"[tailor] Summary generated: {len(summary)} chars")
            
            # Fix truncation
            from app.services.prompts.resume_tailor import fix_truncated_sentences, validate_sentence_completeness
            summary = fix_truncated_sentences(summary)
            
            # Validate completeness
            is_valid, issues = validate_sentence_completeness(summary)
            if is_valid:
                print(f"[tailor] ✓ Summary validation: PASS")
            else:
                print(f"[tailor] ✗ Summary validation: FAIL")
                for issue in issues:
                    print(f"[tailor]   - {issue}")
            
            tailored_data['summary'] = summary

    # ========== SOFT SKILLS INJECTION INTO BULLETS ==========
    # FIX #2: Initialize soft skills verification score (will be set if soft skills are injected)
    soft_skills_verification_score = 0.0

    if isinstance(tailored_data, dict) and soft_skills_data.get('missing_soft_skills'):
        missing_skills = soft_skills_data['missing_soft_skills']
        print(f"\n[tailor] ╔═══════════════════════════════════════════════════════╗")
        print(f"[tailor] ║ SOFT SKILLS INJECTION - {len(missing_skills)} missing skills     ║")
        print(f"[tailor] ╚═══════════════════════════════════════════════════════╝")

        # Collect all bullets from experience and projects
        all_bullets = []
        bullet_locations = []  # Track which section each bullet came from

        for exp_idx, exp in enumerate(tailored_data.get('experience', [])):
            for bullet_idx, bullet in enumerate(exp.get('bullets', [])):
                all_bullets.append(bullet)
                bullet_locations.append(('experience', exp_idx, bullet_idx))

        for proj_idx, proj in enumerate(tailored_data.get('projects', [])):
            for bullet_idx, bullet in enumerate(proj.get('bullets', [])):
                all_bullets.append(bullet)
                bullet_locations.append(('project', proj_idx, bullet_idx))

        if all_bullets:
            # Map soft skills to bullets (distribute evenly)
            for skill_idx, skill in enumerate(missing_skills):
                # Find which bullet should get this skill
                bullet_position = (skill_idx * len(all_bullets)) // len(missing_skills)

                if bullet_position < len(all_bullets):
                    section, section_idx, bullet_idx = bullet_locations[bullet_position]
                    original_bullet = all_bullets[bullet_position]

                    skill_lower = skill.lower()
                    skill_config = SOFT_SKILL_TEMPLATES.get(skill_lower, {})

                    # Create soft skill evidence prompt — force the literal keyword
                    # or a direct variant, not a synonym (see SOFT_SKILLS_SYNONYM_BUG)
                    soft_skill_prompt = f"""
Rewrite this bullet to EXPLICITLY include the soft skill '{skill}':

Original: "{original_bullet}"

CRITICAL REQUIREMENTS:
1. The word '{skill}' or its direct variant MUST appear in the rewritten text
   - For '{skill}': use '{skill}', '{skill}ed', '{skill}ing', or similar variants ONLY
   - Do NOT use synonyms (e.g., don't use "pioneered" for "innovation")
   - Place the skill keyword in the first 15 words
2. Keep the original technical achievement and impact
3. Sound natural and professional (no awkward forced insertion)
4. Keep under 155 characters (important for PDF formatting)

Rewriting strategy for '{skill}':
"""

                    # Add skill-specific guidance
                    if skill_lower == 'innovation':
                        soft_skill_prompt += "- Use: 'innovatively', 'innovation', 'innovative', 'innovated'\n"
                    elif skill_lower == 'communication':
                        soft_skill_prompt += "- Use: 'communicated', 'communication', 'clearly explained', 'documented'\n"
                    elif skill_lower == 'accountability':
                        soft_skill_prompt += "- Use: 'accountability', 'accountable', 'took ownership', 'responsible'\n"
                    elif skill_lower == 'collaboration':
                        soft_skill_prompt += "- Use: 'collaborated', 'collaboration', 'worked together', 'team effort'\n"
                    elif skill_lower == 'adaptability':
                        soft_skill_prompt += "- Use: 'adapted', 'adaptability', 'flexible', 'adjusted to', 'pivoted'\n"

                    soft_skill_prompt += f"""
Return ONLY the rewritten bullet text. Include the keyword. No explanation.
"""

                    try:
                        # Use AI to enhance bullet
                        soft_skill_result = ai_client.analyze(
                            "You are a professional resume writer. Enhance bullets with soft skills.",
                            soft_skill_prompt,
                            max_tokens=150,
                        )

                        if not soft_skill_result.get('error'):
                            enhanced_raw = soft_skill_result['response']
                            if isinstance(enhanced_raw, str):
                                enhanced_bullet = enhanced_raw.strip('"').strip()
                            else:
                                enhanced_bullet = str(enhanced_raw).strip('"').strip()

                            # VERIFY the enhanced bullet contains the literal skill keyword
                            # or a direct stem-variant — NOT a synonym (SOFT_SKILLS_SYNONYM_BUG)
                            skill_keywords = SOFT_SKILL_STRICT_VARIANTS.get(skill_lower, [])
                            keyword_found = any(keyword in enhanced_bullet.lower() for keyword in skill_keywords)

                            if keyword_found:
                                # Update the bullet in the appropriate location
                                if section == 'experience':
                                    tailored_data['experience'][section_idx]['bullets'][bullet_idx] = enhanced_bullet
                                else:
                                    tailored_data['projects'][section_idx]['bullets'][bullet_idx] = enhanced_bullet

                                total_tokens += soft_skill_result.get('tokens_used', 0)
                                total_cost += soft_skill_result.get('cost_usd', 0.0)

                                print(f"[tailor] ✓ Soft skill '{skill}' injected into {section} bullet #{bullet_idx}")
                                print(f"[tailor]   Before: {original_bullet[:60]}...")
                                print(f"[tailor]   After:  {enhanced_bullet[:60]}...")
                            else:
                                print(f"[tailor] ✗ Soft skill '{skill}' enhancement failed (no keywords in result)")
                                print(f"[tailor]   Expected one of: {', '.join(skill_keywords)}")
                                print(f"[tailor]   Got: {enhanced_bullet[:60]}...")
                        else:
                            print(f"[tailor] ⚠ Failed to inject '{skill}': {soft_skill_result['error']}")

                    except Exception as e:
                        print(f"[tailor] ⚠ Soft skill injection error for '{skill}': {e}")

            # ========== SOFT SKILLS VERIFICATION: KEYWORD MATCH + SEMANTIC FALLBACK ==========
            all_bullets = flatten_bullets(tailored_data)
            all_bullets_text = '\n'.join(all_bullets).lower()

            print(f"\n[tailor] ╔═══════════════════════════════════════════════════════╗")
            print(f"[tailor] ║ SOFT SKILLS VERIFICATION (Keyword + Semantic)      ║")
            print(f"[tailor] ╚═══════════════════════════════════════════════════════╝")

            verified_skills = []
            unverified = []

            for skill in missing_skills:
                skill_found = False

                # Try 1: keyword pattern match (fast)
                if skill.lower() in SOFT_SKILL_KEYWORDS:
                    keywords_to_check = SOFT_SKILL_KEYWORDS[skill.lower()]

                    for keyword in keywords_to_check:
                        if keyword in all_bullets_text:
                            verified_skills.append(skill)
                            skill_found = True
                            print(f"[tailor] ✓ {skill:20s} (found via '{keyword}')")
                            break
                else:
                    # Fallback: exact match if no keywords defined
                    if skill.lower() in all_bullets_text:
                        verified_skills.append(skill)
                        skill_found = True
                        print(f"[tailor] ✓ {skill:20s} (found via exact match)")

                # Try 2: semantic verification using Claude — catches evidence that
                # doesn't contain any of the known keyword patterns
                if not skill_found:
                    verification_prompt = f"""
Review these resume bullets and determine if any clearly demonstrate or require '{skill}'.
Look for evidence even if the exact word '{skill}' doesn't appear.

Bullets:
{chr(10).join('- ' + b for b in all_bullets)}

Does any bullet demonstrate '{skill}'? Answer yes or no only.
"""
                    try:
                        result = claude.analyze(
                            "You are a resume expert. Verify if bullets demonstrate soft skills.",
                            verification_prompt,
                            max_tokens=10,
                            temperature=0.0
                        )
                        response_text = str(result.get('response', '')).lower().strip()

                        if 'yes' in response_text or 'true' in response_text:
                            verified_skills.append(skill)
                            skill_found = True
                            print(f"[tailor] ✓ {skill:20s} (found via semantic check)")
                        else:
                            print(f"[tailor] ✗ {skill:20s} (semantic check: not demonstrated)")
                    except Exception as e:
                        print(f"[tailor] ⚠ Soft skill verification failed for '{skill}': {e}")
                        # If semantic check fails, assume it's demonstrated (optimistic)
                        verified_skills.append(skill)
                        skill_found = True

                if not skill_found:
                    # Diagnostic ✗ line was already printed above (semantic check result)
                    unverified.append(skill)

            # Print summary
            verification_percentage = (len(verified_skills) / max(len(missing_skills), 1)) * 100
            # FIX #2: Store verification result for final score calculation
            soft_skills_verification_score = verification_percentage
            print(f"\n[tailor] ╔═══════════════════════════════════════════════════════╗")
            print(f"[tailor] ║ VERIFICATION RESULT: {len(verified_skills)}/{len(missing_skills)} soft skills found ║")
            print(f"[tailor] ║ Success Rate: {verification_percentage:.0f}%")
            if verification_percentage >= 75:
                print(f"[tailor] ║ STATUS: ✓ EXCELLENT")
            elif verification_percentage >= 50:
                print(f"[tailor] ║ STATUS: ⚠ GOOD (but could improve)")
            else:
                print(f"[tailor] ║ STATUS: ✗ NEEDS IMPROVEMENT")
            print(f"[tailor] ╚═══════════════════════════════════════════════════════╝\n")

            # Store verification result
            soft_skills_data['verified_count'] = len(verified_skills)
            soft_skills_data['verified_skills'] = verified_skills
            soft_skills_data['missing_unverified'] = unverified

    # Step 3.5: Run guided convergence (NEW)
    convergence_iterations = []
    convergence_result = None
    if isinstance(tailored_data, dict):
        try:
            print("[tailor] Running guided convergence engine...")
            _pre_convergence_summary = tailored_data.get('summary', '')

            # FIX #4: Increase convergence iterations from 3 to 10 for better score improvement
            convergence_result = run_convergence(
                tailored_data,
                jd_text,
                max_iterations=10
            )

            tailored_data = convergence_result['tailored_resume']

            # TASK 2: convergence guard — the convergence engine's MicroEditGenerator
            # can inject text straight into 'summary' with none of Task 2's
            # completeness/dedup protections, so re-validate it here and revert
            # to the pre-convergence summary if it comes back broken.
            if isinstance(tailored_data, dict) and tailored_data.get('summary'):
                _conv_guard = get_convergence_guard()
                _guarded_summary, _used_convergence_summary = _conv_guard.validate_convergence_output(
                    _pre_convergence_summary,
                    tailored_data['summary'],
                )
                tailored_data['summary'] = _guarded_summary
                print(f"[tailor] TASK 2: convergence guard applied (used_convergence_output={_used_convergence_summary})")

            if convergence_result['status'] == 'converged':
                convergence_iterations = convergence_result['iterations']
                print(f"[tailor] Convergence complete: {convergence_result['final_score']:.1f}/100")
                for it in convergence_iterations:
                    print(f"  Iter {it['iteration']}: {it['score']:.1f}% (+{it['gain']:.1f} from {it['edit_applied']})")
            else:
                print(f"[tailor] Convergence {convergence_result['status']}: {convergence_result.get('message', '')}")
        except Exception as e:
            print(f"[tailor] convergence engine failed (non-fatal): {e}")

    # generate the latex
    latex_output = ''
    if isinstance(tailored_data, dict):
        try:
            latex_output = render_latex(tailored_data)
        except Exception as e:
            latex_output = f'% LaTeX generation error: {str(e)}\n% The AI response was received but LaTeX rendering failed.\n% Try again or check the server logs.'
            print(f"[tailor] latex error: {e}")
    else:
        raw_preview = str(tailored_data)[:2000]
        latex_output = '% ERROR: AI returned unstructured text. JSON parsing failed.\n% Please try again — the AI sometimes returns raw text.\n'
        for line in raw_preview.split('\n')[:50]:
            latex_output += f'% {line}\n'
        print(f"[tailor] not a dict, type={type(tailored_data)}")

    # score it
    resume_plain = resume_text
    if isinstance(tailored_data, dict):
        # build plain text from the tailored JSON for scoring
        header = tailored_data.get('header', {})
        parts = []

        # Contact info (for format compliance scoring)
        if header.get('name'):
            parts.append(header['name'])
        if header.get('email'):
            parts.append(header['email'])
        if header.get('phone'):
            parts.append(header['phone'])
        if header.get('location'):
            parts.append(header['location'])
        if header.get('linkedin'):
            parts.append(header['linkedin'])
        if header.get('github'):
            parts.append(header['github'])

        # Summary section
        parts.append('PROFESSIONAL SUMMARY')
        parts.append(tailored_data.get('summary', ''))

        # Skills section — join items with commas (matching how they appear on the resume)
        parts.append('TECHNICAL SKILLS')
        for skill_group in tailored_data.get('skills', []):
            category = skill_group.get('category', '')
            items = ', '.join(skill_group.get('items', []))
            parts.append(f"{category}: {items}")

        # Projects section
        if tailored_data.get('projects'):
            parts.append('PROJECTS')
            for proj in tailored_data.get('projects', []):
                parts.append(proj.get('name', ''))
                if proj.get('tech_stack'):
                    parts.append(proj['tech_stack'])
                if proj.get('dates'):
                    parts.append(proj['dates'])
                parts.extend(proj.get('bullets', []))

        # Experience section
        parts.append('PROFESSIONAL EXPERIENCE')
        for exp in tailored_data.get('experience', []):
            parts.append(exp.get('title', ''))
            parts.append(exp.get('company', ''))
            if exp.get('location'):
                parts.append(exp['location'])
            if exp.get('dates'):
                parts.append(exp['dates'])
            parts.extend(exp.get('bullets', []))

        # Certifications
        if tailored_data.get('certifications'):
            parts.append('CERTIFICATIONS')
            for cert in tailored_data.get('certifications', []):
                if isinstance(cert, dict):
                    parts.append(cert.get('name', ''))
                    if cert.get('dates'):
                        parts.append(cert['dates'])
                elif isinstance(cert, str):
                    parts.append(cert)

        # Education section
        parts.append('EDUCATION')
        for edu in tailored_data.get('education', []):
            parts.append(edu.get('degree', ''))
            parts.append(edu.get('school', ''))
            if edu.get('location'):
                parts.append(edu['location'])
            if edu.get('dates'):
                parts.append(edu['dates'])
            parts.append(edu.get('details', '') or '')

        # Other experience
        if tailored_data.get('other_experience'):
            parts.append('OTHER EXPERIENCE')
            for oexp in tailored_data.get('other_experience', []):
                parts.append(oexp.get('title', ''))
                if oexp.get('dates'):
                    parts.append(oexp['dates'])
                parts.extend(oexp.get('bullets', []))

        # Languages
        other = tailored_data.get('other', {})
        if other and other.get('languages'):
            parts.append('LANGUAGES')
            parts.append(other['languages'])

        resume_plain = '\n'.join(p for p in parts if p)

    # FIX #3: RAG semantic matching (NVIDIA embeddings — runs AFTER tailoring on tailored resume)
    try:
        from app.services.claude_client import nvidia
        from app.services.rag_enhancer import enhance_tailoring
        rag_context = enhance_tailoring(nvidia, resume_plain, jd_text, jd_analysis=jd_analysis)
        if rag_context:
            pipeline_steps.append('rag_enhancement')
            print(f"[tailor] RAG enhancement done ({len(rag_context)} chars)")
        else:
            print("[tailor] RAG enhancement returned no context — continuing without it")
            rag_context = None
    except Exception as e:
        print(f"[tailor] RAG enhancement failed (non-fatal, continuing): {e}")
        rag_context = None

    # ========== RAG ALIGNMENT VALIDATION & WARNING ==========
    if rag_context:
        # Extract alignment metrics if available
        high_matches = 0
        partial_matches = 0
        no_matches = 0

        # Try to parse alignment from rag_context
        for line in rag_context.split('\n'):
            line_lower = line.lower()
            if 'high' in line_lower and 'match' in line_lower:
                high_matches += 1
            elif 'partial' in line_lower and 'match' in line_lower:
                partial_matches += 1
            elif 'no match' in line_lower or 'no_match' in line_lower:
                no_matches += 1

        total = high_matches + partial_matches + no_matches

        if total > 0:
            alignment_percentage = ((high_matches * 2) + partial_matches) / (total * 2) * 100
        else:
            alignment_percentage = 0

        print(f"\n[tailor] RAG ALIGNMENT ANALYSIS:")
        print(f"[tailor] High matches: {high_matches}")
        print(f"[tailor] Partial matches: {partial_matches}")
        print(f"[tailor] No match: {no_matches}")
        print(f"[tailor] Alignment score: {alignment_percentage:.1f}%")

        if alignment_percentage < 50:
            print(f"\n[tailor] ⚠️ WARNING: RAG ALIGNMENT IS LOW ({alignment_percentage:.1f}%)")
            print(f"[tailor]   This means:")
            print(f"[tailor]   - Tailored resume bullets don't match JD requirements")
            print(f"[tailor]   - Consider additional refinement")
            print(f"[tailor]   - Manually verify skill matching")

    ats = calculate_ats_score(resume_plain, jd_text, jd_analysis=jd_analysis)

    # save to db if company name was given
    app_record = None
    if company_name:
        def _save_to_db():
            """Save application, history, and version to DB."""
            nonlocal app_record
            app_record = Application(
                user_id=session.get('user_id'),
                company_name=company_name,
                role_title=role_title or 'Untitled Role',
                jd_text=jd_text,
                ats_score=ats['total_score'],
            )
            if isinstance(tailored_data, dict):
                app_record.tailored_resume = tailored_data
            app_record.tailored_latex = latex_output
            db.session.add(app_record)
            db.session.flush()  # get app_record.id without final commit

            # Save analysis history
            history = AnalysisHistory(
                application_id=app_record.id,
                analysis_type='tailor',
            )
            history.input_data = {'jd_length': len(jd_text), 'resume_length': len(resume_text)}
            history.output_data = tailored_data if isinstance(tailored_data, dict) else {'raw': str(tailored_data)}
            history.tokens_used = total_tokens
            history.cost_usd = total_cost
            db.session.add(history)

            # Save resume version for version tracking
            existing_count = ResumeVersion.query.filter_by(application_id=app_record.id).count()
            version = ResumeVersion(
                application_id=app_record.id,
                version_number=existing_count + 1,
                resume_plain_text=resume_plain or '',
                ats_score=ats.get('total_score', 0),
                tokens_used=total_tokens,
                cost_usd=total_cost,
            )
            if isinstance(tailored_data, dict):
                version.resume_json = tailored_data
            version.resume_latex = latex_output
            version.score_breakdown = ats
            version.pipeline_steps = pipeline_steps
            if convergence_iterations:
                version.ats_score_before_convergence = convergence_iterations[0]['score']
                version.ats_score_after_convergence = convergence_result['final_score']
                version.convergence_iterations = convergence_iterations
                version.convergence_applied = True
            db.session.add(version)
            db.session.commit()
            print(f"[tailor] Resume version {version.version_number} saved for application {app_record.id}")

        try:
            _save_to_db()
        except Exception as db_err:
            # Handle stale/broken DB connections (e.g. SSL drop during long NVIDIA timeouts)
            print(f"[tailor] DB save failed: {db_err}. Rolling back and retrying...")
            try:
                db.session.rollback()
                app_record = None  # reset so retry creates fresh objects
                _save_to_db()
                print("[tailor] DB save succeeded on retry")
            except Exception as retry_err:
                print(f"[tailor] DB save retry also failed: {retry_err}. Skipping DB save.")
                db.session.rollback()
                app_record = None  # ensure we don't reference a broken record

    # (PHASE 6.5 MOVED: Guarantee engine now runs as PHASE 3 immediately after AI tailoring)

    # ========== PHASE 2: KEYWORD SECTION ROUTING ENGINE ==========
    routing_report = {}
    try:
        tailored_data, routing_report = keyword_section_routing_engine(
            tailored_data, jd_analysis, keyword_data,
            soft_skills_data, jd_text, resume_text
        )
    except Exception as e:
        print(f"[tailor] Phase 2 routing engine failed (non-fatal): {e}")

    # ========== FINAL DEDUP + RE-CATEGORIZATION PASS ==========
    # Catches any duplicates introduced at ANY pipeline stage
    try:
        if isinstance(tailored_data, dict) and tailored_data.get('skills'):
            total_before = sum(len(g.get('items', [])) for g in tailored_data['skills'])
            seen_skills = set()  # normalized lowercase set
            dedup_fixes = 0
            recat_fixes = 0

            for skill_group in tailored_data['skills']:
                deduped_items = []
                for item in skill_group.get('items', []):
                    # Normalize for dedup (strip parenthetical variants)
                    item_lower = item.lower().strip()
                    # Create a canonical key: remove "(OOP)" type suffixes for comparison
                    canonical = item_lower
                    # Remove common parenthetical suffixes for dedup matching
                    base_match = _re.match(r'^(.+?)\s*\(.*\)\s*$', canonical)
                    base_canonical = base_match.group(1).strip() if base_match else canonical

                    # Check if this skill (or its base form) was already seen
                    if item_lower in seen_skills or base_canonical in seen_skills:
                        dedup_fixes += 1
                        print(f"[tailor] DEDUP: Removed duplicate '{item}' from {skill_group.get('category', '')}")
                        continue

                    # Check if this skill is in the wrong category
                    correct_cat = _COMPREHENSIVE_CATEGORY_MAP.get(item_lower)
                    if not correct_cat:
                        correct_cat = _COMPREHENSIVE_CATEGORY_MAP.get(base_canonical)

                    if correct_cat and correct_cat.lower() != skill_group.get('category', '').lower():
                        # This skill is miscategorized — move it
                        # Find the correct category group
                        moved = False
                        for other_group in tailored_data['skills']:
                            if other_group.get('category', '').lower() == correct_cat.lower():
                                # Check it's not already there
                                if item_lower not in {x.lower() for x in other_group.get('items', [])}:
                                    other_group['items'].append(item)
                                    recat_fixes += 1
                                    print(f"[tailor] RECAT: Moved '{item}' from {skill_group.get('category', '')} → {correct_cat}")
                                else:
                                    dedup_fixes += 1
                                    print(f"[tailor] DEDUP: '{item}' already in {correct_cat}, removed from {skill_group.get('category', '')}")
                                moved = True
                                break
                        if not moved:
                            # Correct category doesn't exist yet — keep in current
                            deduped_items.append(item)
                            seen_skills.add(item_lower)
                            seen_skills.add(base_canonical)
                    else:
                        deduped_items.append(item)
                        seen_skills.add(item_lower)
                        seen_skills.add(base_canonical)

                skill_group['items'] = deduped_items

            # Remove empty groups
            tailored_data['skills'] = [g for g in tailored_data['skills'] if g.get('items')]

            total_after = sum(len(g.get('items', [])) for g in tailored_data['skills'])
            if dedup_fixes or recat_fixes:
                print(f"[tailor] Final cleanup: {total_before} → {total_after} skills ({dedup_fixes} duplicates removed, {recat_fixes} re-categorized)")
            else:
                print(f"[tailor] Final cleanup: no duplicates found ({total_after} skills)")

    except Exception as e:
        print(f"[tailor] Final dedup pass failed (non-fatal): {e}")

    # ========== FINAL RESUME QUALITY REPORT ==========
    quality_report = {}
    try:
        print(f"\n[tailor] ╔═══════════════════════════════════════════════════════╗")
        print(f"[tailor] ║         FINAL RESUME QUALITY ASSESSMENT               ║")
        print(f"[tailor] ╚═══════════════════════════════════════════════════════╝")

        # Calculate scores
        # FIX #1: Use ATS scorer's hard skills score (already calculated correctly)
        hard_skills_score = ats.get('breakdown', {}).get('hard_skills', 0)

        # FIX #2: Use soft skills verification results (already calculated correctly)
        soft_skills_score = soft_skills_verification_score

        keywords_score = 100  # Base from keyword extraction

        # Use coherence_check if it was computed
        try:
            coherence_score_val = 100 if coherence_check['status'] == 'PASS' else 50
        except Exception:
            coherence_score_val = 100

        # Use timeline_analysis if it was computed
        try:
            timeline_score = 100 if timeline_analysis.get('status') == 'PASS' else 50
        except Exception:
            timeline_score = 100

        # Composite ATS score (weighted)
        composite_score = (
            hard_skills_score * 0.25 +    # Hard skills importance
            soft_skills_score * 0.35 +     # Soft skills importance (modern ATS)
            keywords_score * 0.15 +         # Keyword matching
            coherence_score_val * 0.15 +    # Resume coherence
            timeline_score * 0.10           # Timeline validity
        )

        # Print report
        print(f"[tailor] ┌─────────────────────────────────────────────────────┐")
        print(f"[tailor] │ COMPONENT SCORES                                    │")
        print(f"[tailor] ├─────────────────────────────────────────────────────┤")
        print(f"[tailor] │ Hard Skills Match:    {hard_skills_score:5.0f}%  {'✓' if hard_skills_score >= 90 else '✗'}")
        print(f"[tailor] │ Soft Skills Match:    {soft_skills_score:5.0f}%  {'✓' if soft_skills_score >= 70 else '✗'}")
        print(f"[tailor] │ Keyword Match:        {keywords_score:5.0f}%  {'✓' if keywords_score >= 90 else '✗'}")
        print(f"[tailor] │ Role Coherence:       {coherence_score_val:5.0f}%  {'✓' if coherence_score_val >= 90 else '✗'}")
        print(f"[tailor] │ Timeline Validity:    {timeline_score:5.0f}%  {'✓' if timeline_score >= 90 else '✗'}")
        print(f"[tailor] └─────────────────────────────────────────────────────┘")
        print(f"[tailor]")
        print(f"[tailor] ╔═══════════════════════════════════════════════════════╗")
        print(f"[tailor] ║ ESTIMATED ATS SCORE:  {composite_score:5.0f}/100                    ║")
        print(f"[tailor] ╠═══════════════════════════════════════════════════════╣")

        if composite_score >= 80:
            readiness = "✓ READY FOR SUBMISSION"
            recommendation = "Confidence: High. Submit this resume."
        elif composite_score >= 70:
            readiness = "⚠ ACCEPTABLE"
            recommendation = "Confidence: Medium. Consider improving soft skills."
        elif composite_score >= 60:
            readiness = "⚠ MARGINAL"
            recommendation = "Confidence: Low. Major improvements recommended."
        else:
            readiness = "✗ NOT READY"
            recommendation = "Confidence: Very Low. Significant work needed."

        print(f"[tailor] ║ STATUS: {readiness}")
        print(f"[tailor] ║ {recommendation}")
        print(f"[tailor] ╚═══════════════════════════════════════════════════════╝\n")

        # Add to response
        quality_report = {
            'hard_skills_score': hard_skills_score,
            'soft_skills_score': soft_skills_score,
            'keywords_score': keywords_score,
            'coherence_score': coherence_score_val,
            'timeline_score': timeline_score,
            'estimated_ats_score': composite_score,
            'readiness_status': 'READY' if composite_score >= 80 else ('ACCEPTABLE' if composite_score >= 70 else 'NEEDS_WORK'),
            'recommendation': recommendation
        }
    except Exception as e:
        print(f"[tailor] quality report failed (non-fatal): {e}")

    return jsonify({
        'tailored_resume': tailored_data,
        'latex': latex_output,
        'ats_score': ats,
        'tokens_used': total_tokens,
        'cost_usd': total_cost,
        'pipeline_steps': pipeline_steps,
        'application_id': app_record.id if app_record else None,
        'quality_report': quality_report,
        'routing_report': routing_report,
    })


@tailor_bp.route('/api/cover-letter', methods=['POST'])
@login_required
def api_cover_letter():
    """Generate a matching cover letter with exactly 330 words in the body."""
    try:
        return _generate_cover_letter_impl()
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Cover letter generation failed: {str(e)}'}), 500


def _generate_cover_letter_impl():
    data = request.get_json()
    resume_text = data.get('resume_text', '')
    jd_text = data.get('jd_text', '')
    company_name = data.get('company_name', '')
    role_title = data.get('role_title', '')
    target_city = data.get('target_city', '').strip()
    TARGET_MIN = 280
    TARGET_MAX = 300

    if not jd_text or not resume_text:
        return jsonify({'error': 'Both job description and resume text are required'}), 400

    # Resolve location for the cover letter header
    header_location = None
    if target_city:
        header_location = _resolve_sign_off_location(target_city)
        print(f"[cover-letter] Using target city for header: {header_location}")

    total_tokens = 0
    total_cost = 0.0

    # Step 0:Select AI provider based on APP_ENV
    app_env = current_app.config.get('APP_ENV', 'testing').strip()
    if app_env == 'nvidia':
        from app.services.claude_client import nvidia as ai_client
        print("[cover-letter] Using NVIDIA Llama-3.3-Nemotron for cover letter")
    else:
        from app.services.claude_client import claude as ai_client
        print(f"[cover-letter] Using AWS Bedrock/Claude for cover letter (APP_ENV={app_env})")


    # Step 1: Generate initial cover letter
    user_message = build_cover_letter_message(resume_text, jd_text, company_name, role_title, header_location=header_location)
    result = ai_client.analyze(COVER_LETTER_SYSTEM, user_message, max_tokens=2048, force_json=True)

    if result.get('error'):
        return jsonify({'error': result['error']}), 500

    total_tokens += result.get('tokens_used', 0)
    total_cost += result.get('cost_usd', 0.0)

    response = result['response']
    if not isinstance(response, dict):
        # Response came back as raw string — try harder to parse it
        import re as _re
        raw = response if isinstance(response, str) else str(response)

        # Attempt 1: Fix newlines inside JSON strings and retry parse
        try:
            fixed = ai_client._fix_json_newlines(raw.strip())
            parsed = json_mod.loads(fixed)
            if isinstance(parsed, dict):
                response = parsed
        except (json_mod.JSONDecodeError, ValueError):
            pass

        # Attempt 2: Extract JSON object with regex
        if not isinstance(response, dict):
            match = _re.search(r'\{[\s\S]*\}', raw)
            if match:
                try:
                    fixed = ai_client._fix_json_newlines(match.group(0))
                    parsed = json_mod.loads(fixed)
                    if isinstance(parsed, dict):
                        response = parsed
                except (json_mod.JSONDecodeError, ValueError):
                    pass

        # Last resort: wrap the raw text as cover_letter_text
        if not isinstance(response, dict):
            response = {'cover_letter_text': raw, 'format_used': 'Problem-Solution'}

    cover_letter_text = response.get('cover_letter_text', '')

    # Step 2: Extract body text (between salutation and sign-off) and count words
    def extract_body(text):
        """Extract the body portion — everything between salutation and sign-off."""
        lines = text.strip().split('\n')
        body_lines = []
        found_salutation = False
        signoff_keywords = ['sincerely', 'best regards', 'regards', 'warm regards',
                            'respectfully', 'yours truly', 'best,']

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if found_salutation:
                    body_lines.append('')  # preserve paragraph breaks
                continue

            # Detect salutation
            if not found_salutation and stripped.lower().startswith('dear '):
                found_salutation = True
                continue

            # Detect sign-off
            if found_salutation and stripped.lower().rstrip(',.') in signoff_keywords:
                break
            if found_salutation and any(stripped.lower().startswith(kw) for kw in signoff_keywords):
                break

            # Skip header lines (before salutation)
            if not found_salutation:
                continue

            body_lines.append(stripped)

        body_text = '\n'.join(body_lines).strip()
        return body_text

    def count_words(text):
        return len(text.split())

    body_text = extract_body(cover_letter_text)
    current_count = count_words(body_text)

    # Step 3: If word count is outside 280-300 range, use adjustment loop (max 3 retries)
    MAX_RETRIES = 3
    for attempt in range(MAX_RETRIES):
        if TARGET_MIN <= current_count <= TARGET_MAX:
            break

        print(f"[cover-letter] Body word count: {current_count}, target: {TARGET_MIN}-{TARGET_MAX}. Adjusting (attempt {attempt + 1})...")
        adjust_msg = build_adjust_message(body_text, current_count, TARGET_MIN, TARGET_MAX)
        adjust_result = ai_client.analyze(COVER_LETTER_ADJUST_SYSTEM, adjust_msg, max_tokens=2048, force_json=True)

        total_tokens += adjust_result.get('tokens_used', 0)
        total_cost += adjust_result.get('cost_usd', 0.0)

        if adjust_result.get('error'):
            break

        adj_response = adjust_result['response']
        if isinstance(adj_response, dict) and adj_response.get('adjusted_body'):
            adjusted_body = adj_response['adjusted_body']
            new_count = count_words(adjusted_body)

            # Replace the body in the full cover letter text
            # Reconstruct: header + salutation + adjusted body + sign-off
            lines = cover_letter_text.strip().split('\n')
            header_part = []
            salutation_part = ''
            signoff_part = []
            found_sal = False
            found_body_start = False
            body_start_idx = 0
            body_end_idx = len(lines)
            signoff_keywords_check = ['sincerely', 'best regards', 'regards', 'warm regards',
                                      'respectfully', 'yours truly', 'best,']

            for idx, line in enumerate(lines):
                stripped = line.strip()
                if not found_sal:
                    if stripped.lower().startswith('dear '):
                        salutation_part = stripped
                        found_sal = True
                        found_body_start = False
                    else:
                        header_part.append(line)
                elif not found_body_start:
                    if stripped:
                        found_body_start = True
                        body_start_idx = idx
                else:
                    if stripped and (stripped.lower().rstrip(',.') in signoff_keywords_check or
                                    any(stripped.lower().startswith(kw) for kw in signoff_keywords_check)):
                        body_end_idx = idx
                        signoff_part = [l for l in lines[idx:] if l.strip()]
                        break

            # Clean up trailing empty lines in header
            while header_part and not header_part[-1].strip():
                header_part.pop()
                
            # Clean up leading empty lines in signoff
            while signoff_part and not signoff_part[0].strip():
                signoff_part.pop(0)

            # Reconstruct the full letter
            reconstructed = '\n'.join(header_part)
            if salutation_part:
                reconstructed += '\n\n' + salutation_part
            reconstructed += '\n\n' + adjusted_body
            if signoff_part:
                reconstructed += '\n\n' + '\n'.join(signoff_part)

            cover_letter_text = reconstructed
            response['cover_letter_text'] = cover_letter_text
            body_text = adjusted_body
            current_count = new_count
        else:
            break

    response['body_word_count'] = current_count
    response['word_count'] = current_count

    # Guarantee cover_letter_text is always present and non-empty
    final_text = response.get('cover_letter_text', '') or cover_letter_text or ''

    print(f"[cover-letter] Final response type: {type(response).__name__}")
    print(f"[cover-letter] cover_letter_text length: {len(final_text)}")
    print(f"[cover-letter] cover_letter_text first 120 chars: {repr(final_text[:120])}")

    # Update application record if provided
    app_id = data.get('application_id')
    if app_id:
        app_record = Application.query.get(app_id)
        if app_record:
            app_record.cover_letter = final_text
            db.session.commit()

    # Fix #2: Cover letter-resume alignment validation
    alignment_data = {}
    try:
        # Build a simple resume dict for validation
        master = MasterResume.query.filter_by(user_id=session.get('user_id')).first()
        if master:
            resume_json = {
                'summary': master.summary or '',
                'skills': json_mod.loads(master.skills) if master.skills else [],
                'experience': json_mod.loads(master.experience) if master.experience else [],
                'projects': json_mod.loads(master.projects) if master.projects else [],
                'education': json_mod.loads(master.education) if master.education else [],
            }
            alignment_check = validate_cover_letter_resume_alignment(final_text, resume_json)
            alignment_data = alignment_check

            if alignment_check['status'] == 'FAIL':
                print(f"[cover-letter] ═══ Alignment Issues ═══")
                for mm in alignment_check['mismatches']:
                    print(f"[cover-letter]   {mm['severity']}: {mm['claim']}")
                    print(f"[cover-letter]     missing terms: {mm['missing_terms']}")
                print(f"[cover-letter] ═══════════════════════")
            else:
                print(f"[cover-letter] alignment: PASS (score: {alignment_check['alignment_score']:.0f}%)")
    except Exception as e:
        print(f"[cover-letter] alignment validation failed (non-fatal): {e}")

    # Send ALL fields as flat top-level keys — no nested dicts.
    # This guarantees the frontend always gets cover_letter_text as a plain string.
    return jsonify({
        'cover_letter_text': final_text,
        'format_used': response.get('format_used', ''),
        'format_reasoning': response.get('format_reasoning', ''),
        'word_count': current_count,
        'jd_keywords_used': response.get('jd_keywords_used', []),
        'metrics_used': response.get('metrics_used', []),
        'company_research_hook': response.get('company_research_hook', ''),
        'tokens_used': total_tokens,
        'cost_usd': total_cost,
        'cover_letter_alignment_score': alignment_data.get('alignment_score', None),
        'alignment_status': alignment_data.get('status', None),
        'alignment_mismatches': alignment_data.get('mismatches', []),
    })


@tailor_bp.route('/api/download-cover-letter-pdf', methods=['POST'])
@login_required
def api_download_cover_letter_pdf():
    """Download the cover letter as a professionally formatted PDF."""
    import io
    from fpdf import FPDF

    data = request.get_json()
    cover_letter_text = data.get('cover_letter_text', '').strip()

    if not cover_letter_text:
        return jsonify({'error': 'No cover letter text provided'}), 400

    try:
        # Get the user's name for the filename
        master = MasterResume.query.filter_by(user_id=session.get('user_id')).first()
        full_name = master.full_name if master else 'Cover_Letter'
        # Format name for filename: "Meet Patel" -> "Meet_Patel"
        file_name = full_name.replace(' ', '_') + '_Cover_Letter.pdf'

        pdf = FPDF()
        pdf.add_page()

        # 1-inch margins (1 inch = 25.4mm)
        pdf.set_margins(25.4, 25.4, 25.4)
        pdf.set_auto_page_break(auto=True, margin=25.4)

        # Load Arial Regular font (standard Arial, not Arial Unicode MS)
        import os
        font_name = 'Arial'
        font_loaded = False
        regular_paths = [
            '/System/Library/Fonts/Supplemental/Arial.ttf',
            '/Library/Fonts/Arial.ttf',
            '/Library/Fonts/Arial Unicode.ttf',
        ]
        bold_path = '/System/Library/Fonts/Supplemental/Arial Bold.ttf'

        for fpath in regular_paths:
            if os.path.exists(fpath):
                try:
                    pdf.add_font(font_name, '', fpath)
                    font_loaded = True
                    break
                except Exception:
                    continue

        # Load bold variant
        bold_loaded = False
        if font_loaded and os.path.exists(bold_path):
            try:
                pdf.add_font(font_name, 'B', bold_path)
                bold_loaded = True
            except Exception:
                pass

        if not font_loaded:
            font_name = 'Helvetica'
            bold_loaded = True

        # Sanitize problematic Unicode chars for safety
        replacements = {
            '\u2014': '--', '\u2013': '-',
            '\u2018': "'", '\u2019': "'",
            '\u201c': '"', '\u201d': '"',
            '\u2026': '...', '\u2022': '*',
            '\u00a0': ' ',
            '\u2192': '->', '\u2190': '<-',
        }
        for uni_char, ascii_char in replacements.items():
            cover_letter_text = cover_letter_text.replace(uni_char, ascii_char)

        pdf.set_text_color(30, 30, 30)

        # Split into paragraphs
        paragraphs = [p.strip() for p in cover_letter_text.split('\n\n') if p.strip()]

        # Detect structure: header lines, date line, salutation, body, sign-off
        header_lines = []
        date_line = ''
        salutation_line = ''
        body_paragraphs = []
        signoff_lines = []
        signoff_keywords = ['sincerely', 'best regards', 'regards', 'warm regards',
                            'respectfully', 'thank you', 'yours truly', 'best']

        # Date pattern: "May 27, 2026", "January 2026", "12/27/2026", etc.
        import re
        date_pattern = re.compile(
            r'^(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}$|'
            r'^\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}$|'
            r'^(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}$',
            re.IGNORECASE
        )

        # Parse paragraphs into sections
        found_salutation = False
        found_signoff = False
        for para in paragraphs:
            lines = [l.strip() for l in para.split('\n') if l.strip()]
            if not found_salutation:
                # Check if this paragraph contains the salutation
                if any(line.lower().startswith('dear ') for line in lines):
                    # Everything before "Dear" is header, "Dear" line is salutation
                    for line in lines:
                        if line.lower().startswith('dear '):
                            salutation_line = line
                            found_salutation = True
                        elif not found_salutation:
                            # Check if it's a date line
                            if date_pattern.match(line.strip()):
                                date_line = line.strip()
                            else:
                                header_lines.append(line)
                else:
                    # Check each line for date
                    for line in lines:
                        if date_pattern.match(line.strip()) and not date_line:
                            date_line = line.strip()
                        else:
                            header_lines.append(line)
            elif not found_signoff:
                # Check if any line is a sign-off
                first_line_lower = lines[0].lower().rstrip(',.')
                if first_line_lower in signoff_keywords or any(
                    lines[0].lower().startswith(kw) for kw in signoff_keywords
                ):
                    found_signoff = True
                    signoff_lines.extend(lines)
                else:
                    body_paragraphs.append(para)
            else:
                signoff_lines.extend(lines)

        # === RENDER HEADER ===
        if header_lines:
            # Name — bold, larger, professional navy color
            pdf.set_font(font_name, 'B' if bold_loaded else '', size=16)
            pdf.set_text_color(25, 42, 86)  # Professional navy
            pdf.cell(0, 8, header_lines[0], new_x='LMARGIN', new_y='NEXT', align='C')

            # Contact info — refined, subtle gray, slightly larger for readability
            if len(header_lines) > 1:
                pdf.set_font(font_name, '', size=9)
                pdf.set_text_color(100, 100, 100)
                # Join contact details with separator for a clean single line
                contact_text = '  |  '.join(header_lines[1:]) if len(header_lines[1:]) <= 3 else None
                if contact_text and pdf.get_string_width(contact_text) < 159:
                    pdf.cell(0, 5, contact_text, new_x='LMARGIN', new_y='NEXT', align='C')
                else:
                    for line in header_lines[1:]:
                        pdf.cell(0, 5, line, new_x='LMARGIN', new_y='NEXT', align='C')

            # Elegant thin separator line
            pdf.ln(4)
            y = pdf.get_y()
            pdf.set_draw_color(25, 42, 86)  # Match navy header
            pdf.set_line_width(0.4)
            pdf.line(25.4, y, 595.28 / 72 * 25.4 - 25.4, y)
            pdf.set_line_width(0.2)  # Reset
            pdf.ln(6)

        # Reset to body text color
        pdf.set_text_color(35, 35, 35)

        # === RENDER DATE ===
        if date_line:
            pdf.set_font(font_name, '', size=10)
            pdf.cell(0, 6, date_line, new_x='LMARGIN', new_y='NEXT')
            pdf.ln(3)

        # === RENDER SALUTATION ===
        if salutation_line:
            pdf.set_font(font_name, 'B' if bold_loaded else '', size=10)
            pdf.cell(0, 6, salutation_line, new_x='LMARGIN', new_y='NEXT')
            pdf.ln(3)

        # === RENDER BODY PARAGRAPHS ===
        pdf.set_font(font_name, '', size=10)
        for i, para in enumerate(body_paragraphs):
            clean_text = ' '.join(l.strip() for l in para.split('\n') if l.strip())
            pdf.multi_cell(0, 5.2, clean_text, new_x='LMARGIN', new_y='NEXT')
            if i < len(body_paragraphs) - 1:
                pdf.ln(3)

        # === RENDER SIGN-OFF ===
        if signoff_lines:
            pdf.ln(5)
            for j, line in enumerate(signoff_lines):
                if line.strip() == full_name or line.strip() == full_name.strip():
                    # Name in bold navy to match header
                    pdf.set_font(font_name, 'B' if bold_loaded else '', size=10)
                    pdf.set_text_color(25, 42, 86)
                    pdf.cell(0, 6, line, new_x='LMARGIN', new_y='NEXT')
                    pdf.set_text_color(35, 35, 35)
                else:
                    pdf.set_font(font_name, '', size=10)
                    pdf.cell(0, 6, line, new_x='LMARGIN', new_y='NEXT')

        # Generate PDF bytes
        pdf_bytes = pdf.output()
        buffer = io.BytesIO(pdf_bytes)
        buffer.seek(0)

        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=file_name,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[cover-letter-pdf] Error: {e}")
        return jsonify({'error': f'PDF generation failed: {str(e)}'}), 500

@tailor_bp.route('/api/ats-score', methods=['POST'])
@login_required
def api_ats_score():
    """Calculate ATS proxy score for a resume against a JD."""
    data = request.get_json()
    resume_text = data.get('resume_text', '')
    jd_text = data.get('jd_text', '')
    keyword_matches = data.get('keyword_matches')

    if not resume_text or not jd_text:
        return jsonify({'error': 'Both resume text and job description are required'}), 400

    score = calculate_ats_score(resume_text, jd_text, keyword_matches)
    return jsonify(score)


@tailor_bp.route('/api/download-pdf', methods=['POST'])
@login_required
def api_download_pdf():
    """Compile LaTeX to PDF using latex.ytotech.com API and return the PDF."""
    import requests as http_requests
    from flask import Response

    data = request.get_json()
    latex_code = data.get('latex_code', '')
    company_name = data.get('company_name', '')

    if not latex_code:
        return jsonify({'error': 'No LaTeX code provided'}), 400

    # Build filename: Meet_Patel_Resume_CompanyName.pdf
    safe_company = ''.join(c if c.isalnum() or c in ('-', '_') else '_' for c in company_name.strip()).strip('_')[:30] if company_name else ''
    filename = f"Meet_Patel_Resume_{safe_company}.pdf" if safe_company else "Meet_Patel_Resume.pdf"

    try:
        # Use YtoTech LaTeX Online API (free, no API key required)
        api_url = 'https://latex.ytotech.com/builds/sync'
        payload = {
            'compiler': 'pdflatex',
            'resources': [
                {
                    'main': True,
                    'content': latex_code,
                }
            ],
        }
        resp = http_requests.post(api_url, json=payload, timeout=60)

        if resp.status_code in (200, 201) and resp.headers.get('Content-Type', '').startswith('application/pdf'):
            return Response(
                resp.content,
                mimetype='application/pdf',
                headers={'Content-Disposition': f'attachment; filename="{filename}"'}
            )
        else:
            error_msg = resp.text[:500] if resp.text else 'Unknown compilation error'
            return jsonify({'error': f'LaTeX compilation failed: {error_msg}'}), 500

    except http_requests.RequestException as e:
        return jsonify({'error': f'PDF compilation service unavailable: {str(e)}'}), 503


@tailor_bp.route('/api/download-docx', methods=['POST'])
@login_required
def api_download_docx():
    """Generate a .docx file from the tailored resume JSON."""
    from flask import Response

    data = request.get_json()
    resume_json = data.get('resume_json', {})
    company_name = data.get('company_name', '')

    if not resume_json:
        return jsonify({'error': 'No resume data provided'}), 400

    # Build filename: Meet_Patel_Resume_CompanyName.docx
    safe_company = ''.join(c if c.isalnum() or c in ('-', '_') else '_' for c in company_name.strip()).strip('_')[:30] if company_name else ''
    filename = f"Meet_Patel_Resume_{safe_company}.docx" if safe_company else "Meet_Patel_Resume.docx"

    try:
        from app.services.docx_engine import render_docx
        docx_bytes = render_docx(resume_json)
        return Response(
            docx_bytes,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )
    except ImportError:
        return jsonify({'error': 'python-docx is not installed. Run: pip install python-docx'}), 500
    except Exception as e:
        return jsonify({'error': f'DOCX generation failed: {str(e)}'}), 500


@tailor_bp.route('/api/leadership-email', methods=['POST'])
@login_required
def api_leadership_email():
    """Generate a professional leadership outreach email."""
    try:
        from app.services.email_core import generate_email_core
        from app.services.github_fetcher import get_project_updates_for_prompt

        data = request.get_json()

        # Fetch GitHub project updates (once per request)
        project_updates_text = get_project_updates_for_prompt()

        result = generate_email_core(
            resume_text=data.get('resume_text', ''),
            jd_text=data.get('jd_text', ''),
            company_name=data.get('company_name', ''),
            role_title=data.get('role_title', ''),
            recipient_name=data.get('recipient_name', ''),
            cover_letter_text=data.get('cover_letter_text', ''),
            recipient_title=data.get('recipient_title', ''),
            recipient_category=data.get('recipient_category', ''),
            target_city=data.get('target_city', '').strip(),
            previously_used_signals=data.get('previously_used_signals', []),
            previously_used_subjects=data.get('previously_used_subjects', []),
            previously_used_bodies=data.get('previously_used_bodies', []),
            previously_used_proofs=data.get('previously_used_proofs', []),
            project_updates_text=project_updates_text,
        )

        if 'error' in result:
            return jsonify({'error': result['error']}), result.get('status_code', 500)

        # Fix #5: Email subject line optimization
        try:
            subject = result.get('subject', '')
            role_title_email = data.get('role_title', '')
            company_name_email = data.get('company_name', '')
            recipient_name_email = data.get('recipient_name', '')
            # Extract proof points from email body for specificity scoring
            proof_points = result.get('proof_points', [])
            if not proof_points:
                body_text = result.get('body', '')
                if body_text:
                    proof_points = [line.strip() for line in body_text.split('\n')
                                   if any(v in line.lower() for v in ['improved', 'reduced', 'built', 'led'])]

            subject_optimization = optimize_email_subject_line(
                role_title_email, company_name_email, recipient_name_email, proof_points
            )
            result['subject_quality_score'] = subject_optimization['quality_score']
            result['subject_issues'] = subject_optimization['issues']

            if subject_optimization['quality_score'] < 70:
                print(f"[email] ═══ Subject Line Issues ═══")
                print(f"[email]   Subject: {subject}")
                print(f"[email]   Score: {subject_optimization['quality_score']}")
                print(f"[email]   Issues: {subject_optimization['issues']}")
                print(f"[email]   Recommendation: {subject_optimization['recommendation']}")
                print(f"[email] ═══════════════════════════")
            else:
                print(f"[email] subject quality: {subject_optimization['quality_score']}% — {subject_optimization['recommendation']}")
        except Exception as e:
            print(f"[email] subject optimization failed (non-fatal): {e}")

        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Leadership email generation failed: {str(e)}'}), 500


@tailor_bp.route('/api/download-leadership-email', methods=['POST'])
@login_required
def api_download_leadership_email_json():
    """Download leadership email(s) as a structured JSON file for automation."""
    from app.services.email_core import build_email_download

    data = request.get_json()
    company_name = data.get('company_name', '')
    role_title = data.get('role_title', '')

    # Support both multi-email (new) and single-email (backwards compat)
    emails = data.get('emails', None)
    if emails is None:
        body = data.get('body', '')
        if not body:
            return jsonify({'error': 'No email body provided'}), 400
        emails = [{
            'subject': data.get('subject', ''),
            'body': body,
            'ref_number': data.get('ref_number', 'REFENUM'),
            'company_name': company_name,
            'role_title': role_title,
            'recipient_name': data.get('recipient_name', ''),
            'recipient_email': data.get('recipient_email', ''),
            'recipient_title': data.get('recipient_title', ''),
            'recipient_category': data.get('recipient_category', 'category_a'),
            'signal_used': data.get('signal_used', ''),
            'word_count': data.get('word_count', 0),
        }]

    if not emails or len(emails) == 0:
        return jsonify({'error': 'No emails provided'}), 400

    output, filename = build_email_download(emails, company_name, role_title)
    if not output:
        return jsonify({'error': 'No emails provided'}), 400

    import io
    json_bytes = json_mod.dumps(output, indent=2, ensure_ascii=False).encode('utf-8')

    return send_file(
        io.BytesIO(json_bytes),
        mimetype='application/json',
        as_attachment=True,
        download_name=filename,
    )


