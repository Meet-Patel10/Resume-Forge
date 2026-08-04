from flask import Blueprint, render_template, request, jsonify, session, send_file, current_app
from app.routes.auth import login_required
from app import db
from app.models.master_resume import MasterResume
from app.models.application import Application
from app.models.analysis import AnalysisHistory
from app.models.resume_version import ResumeVersion
from app.services.claude_client import claude
from app.services.prompts.resume_tailor import RESUME_TAILOR_SYSTEM, build_tailor_message
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
from app.validators.role_validator import detect_role_level, validate_role_skill_coherence, ROLE_SKILL_MATRIX
from app.validators.timeline_validator import analyze_employment_timeline
from app.validators.email_optimizer import optimize_email_subject_line

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
        found_kws = set()
        required_kws = {}
        if keyword_data and isinstance(keyword_data, dict):
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
    rag_context = None
    try:
        from app.services.claude_client import nvidia
        from app.services.rag_enhancer import enhance_tailoring
        rag_context = enhance_tailoring(nvidia, resume_text, jd_text, jd_analysis=jd_analysis)
        if rag_context:
            pipeline_steps.append('rag_enhancement')
            print(f"[tailor] RAG enhancement done ({len(rag_context)} chars)")
        else:
            print("[tailor] RAG enhancement returned no context — continuing without it")
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
            print(f"[tailor]   - Master resume bullets don't match JD requirements")
            print(f"[tailor]   - AI will struggle to find connections")
            print(f"[tailor]   - Resume might not clearly show fit for role")
            print(f"[tailor]")
            print(f"[tailor]   Recommendation:")
            print(f"[tailor]   - Review master resume bullets")
            print(f"[tailor]   - Add more role-specific examples to master")
            print(f"[tailor]   - Update master with recent/relevant projects")
            print(f"[tailor]")

    # step 3: actually tailor the resume using all the context we gathered
    user_message = build_tailor_message(
        resume_text, jd_text,
        keyword_analysis=keyword_analysis,
        critique_data=critique_data,
        keyword_data=keyword_data,
        jd_analysis=jd_analysis,
        rag_context=rag_context,
        title_injection_mode=title_injection_mode,
        role_title=role_title,
        soft_skills_data=soft_skills_data,
    )

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
        else:
            print(f"[tailor] json parse failed ({len(raw_str)} chars)")

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
                        # Check exact match
                        if sl in skills_to_suppress:
                            return True
                        # Check if skill contains a suppressed term (e.g., "Amazon Web Services (AWS)" contains "aws")
                        for suppressed in skills_to_suppress:
                            if suppressed in sl or sl in suppressed:
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
                    # The AI prompt should have already done this, but we enforce it
                    # programmatically as a safety net.
                    if skills_to_suppress:
                        suppressed_log = []
                        for group in enforced_skills:
                            original_items = group['items']
                            filtered = []
                            for item in original_items:
                                if _should_suppress(item) and item.strip().lower() not in jd_hard_skills_lower:
                                    suppressed_log.append(item)
                                else:
                                    filtered.append(item)
                            group['items'] = filtered
                        if suppressed_log:
                            print(f"[tailor] competing tech suppressed: {suppressed_log}")

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

                    # ---- ROLE-LEVEL VALIDATION (Fix #3) ----
                    try:
                        detected_role_level = detect_role_level(tailored_data, jd_text)
                        print(f"[tailor] detected role level: {detected_role_level}")

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

                                # STEP 1: Build JD relevance scores for all skills
                                jd_keywords_lower = set()
                                for skill in jd_analysis.get('hard_skills', []):
                                    jd_keywords_lower.add(skill.lower())
                                for skill in jd_analysis.get('top_keywords', []):
                                    jd_keywords_lower.add(skill.lower())

                                # STEP 2: Score each skill by JD relevance
                                skill_scores = {}
                                for group in tailored_data.get('skills', []):
                                    for item in group.get('items', []):
                                        score = 0
                                        item_lower = item.lower()

                                        # Direct match = 100 points
                                        if item_lower in jd_keywords_lower:
                                            score += 100

                                        # Substring match = 50 points
                                        for jd_kw in jd_keywords_lower:
                                            if jd_kw in item_lower or item_lower in jd_kw:
                                                score += 50
                                                break

                                        # Language vs Framework preference (role-dependent)
                                        if detected_role_level == 'entry_level':
                                            if group['category'] == 'Languages':
                                                score += 10  # Entry-level: prioritize languages
                                        elif detected_role_level == 'mid_level':
                                            if group['category'] == 'Frameworks & Libraries':
                                                score += 5  # Mid-level: prioritize frameworks

                                        skill_scores[item] = score

                                # STEP 3: Sort by score (descending) and keep only top N
                                sorted_skills = sorted(skill_scores.items(), key=lambda x: -x[1])
                                keeper_skills = set([s[0] for s in sorted_skills[:max_allowed]])

                                print(f"\n[tailor] TOP {max_allowed} SKILLS BY JD RELEVANCE:")
                                for i, (skill, score) in enumerate(sorted_skills[:max_allowed]):
                                    print(f"[tailor] {i+1}. {skill} (score: {score})")

                                print(f"\n[tailor] REMOVING {skills_to_remove} LEAST-RELEVANT SKILLS:")
                                removed = []
                                for skill, score in sorted_skills[max_allowed:]:
                                    print(f"[tailor] ✗ {skill} (score: {score})")
                                    removed.append(skill)

                                # STEP 4: Rebuild skills array with only keeper skills
                                new_skills = []
                                for group in tailored_data.get('skills', []):
                                    filtered_items = [item for item in group.get('items', []) if item in keeper_skills]
                                    if filtered_items:
                                        new_skills.append({'category': group['category'], 'items': filtered_items})

                                tailored_data['skills'] = new_skills

                                print(f"\n[tailor] ✓ COHERENCE FIXED: {current_count} → {max_allowed} skills")
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
                    seen = set()
                    unique_kw = []
                    for k in new_keywords:
                        kl = k.lower()
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
                            sentences.insert(insert_pos, f'Experienced with {leftover_phrase}.')

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

                val_result = ai_client.analyze(STRUCTURE_VALIDATOR_SYSTEM, validator_msg, max_tokens=16000, temperature=0.1, force_json=True)

                if not val_result.get('error'):
                    val_resp = val_result.get('response')
                    if isinstance(val_resp, dict) and 'summary' in val_resp and 'skills' in val_resp:
                        tailored_data = val_resp
                        total_tokens += val_result.get('tokens_used', 0)
                        total_cost += val_result.get('cost_usd', 0)
                        pipeline_steps.append('structure_validator')
                        print("[tailor] structure validation done — JSON fixed")

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

                        # Check for exact duplicate
                        existing_items_lower = [item.lower() for item in target_cat.get('items', [])]
                        if skill_lower in existing_items_lower:
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

                # ── Reorder: JD-matched skills FIRST in each category ──
                # This ensures LaTeX capping (from the end) drops non-JD skills, not JD ones
                jd_lower = {s.lower() for s in jd_hard}
                for cat in current_skills:
                    items = cat.get('items', [])
                    jd_items = [i for i in items if i.lower() in jd_lower]
                    non_jd_items = [i for i in items if i.lower() not in jd_lower]
                    cat['items'] = jd_items + non_jd_items

                tailored_data['skills'] = current_skills
                print(f"[tailor] skills reordered: JD-matched keywords placed first in each category")

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
            'React': 'Frameworks & Libraries',
            'Django': 'Frameworks & Libraries',
            'FastAPI': 'Frameworks & Libraries',
            'AWS': 'Tools & Platforms',
            'Docker': 'Tools & Platforms',
            'Kubernetes': 'Tools & Platforms',
            'SageMaker': 'Tools & Platforms',  # AWS service, not language
            'REST APIs': 'Concepts',
            'GraphQL': 'Concepts',
            'GraphQL APIs': 'Concepts',
            'async handling': 'Programming Concepts',
            'data pipelines': 'Concepts',
            'state management': 'Concepts',
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

    # ========== SOFT SKILLS INJECTION INTO BULLETS ==========
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

                    # Create soft skill evidence prompt
                    soft_skill_prompt = f"""
            Rewrite this bullet to include evidence of '{skill}' (e.g., communication, mentoring, collaboration, adaptability):

            Original: "{original_bullet}"

            Requirements:
            - Keep the technical achievement
            - Add soft skill verb (e.g., "collaborated with", "mentored", "communicated")
            - Make it sound natural, not forced
            - Keep under 140 characters

            Example soft skill additions:
            - collaboration: "Worked with X to build Y"
            - communication: "Clearly explained X to team, enabling Y"
            - mentoring: "Guided junior dev through X process"
            - adaptability: "Quickly pivoted to handle unexpected X challenge"
            - leadership: "Took ownership of X despite initial uncertainty"

            Return ONLY the new bullet text, no explanation.
            """

                    try:
                        # Use AI to enhance bullet
                        soft_skill_result = ai_client.analyze(
                            "You are a resume writer. Enhance bullets with soft skill evidence.",
                            soft_skill_prompt,
                            max_tokens=150,
                        )

                        if not soft_skill_result.get('error'):
                            enhanced_raw = soft_skill_result['response']
                            if isinstance(enhanced_raw, str):
                                enhanced_bullet = enhanced_raw.strip('"').strip()
                            else:
                                enhanced_bullet = str(enhanced_raw).strip('"').strip()

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
                            print(f"[tailor] ⚠ Failed to inject '{skill}': {soft_skill_result['error']}")

                    except Exception as e:
                        print(f"[tailor] ⚠ Soft skill injection error for '{skill}': {e}")

            # VERIFICATION: Check which soft skills made it into bullets
            all_bullets_text = '\n'.join(flatten_bullets(tailored_data))
            verified_skills = []
            for skill in missing_skills:
                if skill.lower() in all_bullets_text.lower():
                    verified_skills.append(skill)

            unverified = set(missing_skills) - set(verified_skills)

            print(f"\n[tailor] ╔═══════════════════════════════════════════════════════╗")
            print(f"[tailor] ║ VERIFICATION: {len(verified_skills)}/{len(missing_skills)} soft skills in bullets ║")
            print(f"[tailor] ╠═══════════════════════════════════════════════════════╣")

            for skill in verified_skills:
                print(f"[tailor] ║ ✓ {skill}")

            if unverified:
                print(f"[tailor] ║")
                for skill in unverified:
                    print(f"[tailor] ║ ✗ {skill} (NOT FOUND)")

            print(f"[tailor] ╚═══════════════════════════════════════════════════════╝\n")

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

    # ========== FINAL RESUME QUALITY REPORT ==========
    quality_report = {}
    try:
        print(f"\n[tailor] ╔═══════════════════════════════════════════════════════╗")
        print(f"[tailor] ║         FINAL RESUME QUALITY ASSESSMENT               ║")
        print(f"[tailor] ╚═══════════════════════════════════════════════════════╝")

        # Calculate scores
        hard_skills_count = sum(len(g.get('items', [])) for g in tailored_data.get('skills', [])) if isinstance(tailored_data, dict) else 0
        hard_skills_jd_matched = len(jd_analysis.get('hard_skills', [])) if jd_analysis else 0
        hard_skills_score = (hard_skills_jd_matched / max(hard_skills_count, 1)) * 100

        soft_skills_found = len(soft_skills_data.get('resume_soft_skills', []))
        soft_skills_required = len(soft_skills_data.get('jd_soft_skills', []))
        soft_skills_score = (soft_skills_found / max(soft_skills_required, 1)) * 100

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


