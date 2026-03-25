from flask import Blueprint, render_template, request, jsonify
from app import db
from app.models.master_resume import MasterResume
from app.models.application import Application
from app.models.analysis import AnalysisHistory
from app.services.claude_client import claude
from app.services.prompts.resume_tailor import RESUME_TAILOR_SYSTEM, build_tailor_message
from app.services.prompts.bullet_rewriter import BULLET_REWRITER_SYSTEM, build_bullet_message
from app.services.prompts.cover_letter import COVER_LETTER_SYSTEM, build_cover_letter_message
from app.services.prompts.brutal_critic import BRUTAL_CRITIC_SYSTEM, build_critique_message
from app.services.prompts.keyword_extractor import KEYWORD_EXTRACTOR_SYSTEM, build_keyword_message
from app.services.latex_engine import render_latex
from app.services.ats_scorer import calculate_ats_score
import json as json_mod

tailor_bp = Blueprint('tailor', __name__)


@tailor_bp.route('/')
def tailor_page():
    """Render the tailoring page."""
    resume = MasterResume.query.first()
    return render_template('tailor.html', resume=resume)


@tailor_bp.route('/api/rewrite-bullets', methods=['POST'])
def api_rewrite_bullets():
    """Rewrite bullet points using X-Y-Z formula."""
    data = request.get_json()
    bullets = data.get('bullets', [])
    jd_text = data.get('jd_text', '')
    role_context = data.get('role_context', '')

    if not bullets or not jd_text:
        return jsonify({'error': 'Bullets and job description are required'}), 400

    user_message = build_bullet_message(bullets, jd_text, role_context)
    result = claude.analyze(BULLET_REWRITER_SYSTEM, user_message, max_tokens=4096)

    if result.get('error'):
        return jsonify({'error': result['error']}), 500

    return jsonify({
        'rewritten': result['response'],
        'tokens_used': result['tokens_used'],
        'cost_usd': result['cost_usd'],
    })


@tailor_bp.route('/api/tailor', methods=['POST'])
def api_tailor():
    """Full resume tailoring pipeline — 3-step: Critique → Keywords → Tailor."""
    data = request.get_json()
    jd_text = data.get('jd_text', '')
    resume_text = data.get('resume_text', '')
    company_name = data.get('company_name', '')
    role_title = data.get('role_title', '')
    keyword_analysis = data.get('keyword_analysis', '')

    if not jd_text or not resume_text:
        return jsonify({'error': 'Both job description and resume text are required'}), 400

    total_tokens = 0
    total_cost = 0.0
    pipeline_steps = []

    # ── STEP 1: Brutal Critique (JD vs Master Resume) ────
    critique_data = None
    try:
        critique_msg = build_critique_message(resume_text, jd_text)
        critique_result = claude.analyze(BRUTAL_CRITIC_SYSTEM, critique_msg, max_tokens=3000)
        if not critique_result.get('error'):
            critique_data = critique_result['response']
            # Parse string response if needed
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
            print(f"[TAILOR] Step 1 done: Brutal Critique completed")
        else:
            print(f"[TAILOR] Step 1 skipped: {critique_result['error']}")
    except Exception as e:
        print(f"[TAILOR] Step 1 error: {e}")

    # ── STEP 2: Keyword Extraction (JD vs Master Resume) ──
    keyword_data = None
    try:
        kw_msg = build_keyword_message(resume_text, jd_text)
        kw_result = claude.analyze(KEYWORD_EXTRACTOR_SYSTEM, kw_msg, max_tokens=3000)
        if not kw_result.get('error'):
            keyword_data = kw_result['response']
            # Parse string response if needed
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
            print(f"[TAILOR] Step 2 done: Keyword extraction completed")
        else:
            print(f"[TAILOR] Step 2 skipped: {kw_result['error']}")
    except Exception as e:
        print(f"[TAILOR] Step 2 error: {e}")

    # ── STEP 3: Tailor the resume (with critique + keyword insights) ──
    user_message = build_tailor_message(
        resume_text, jd_text,
        keyword_analysis=keyword_analysis,
        critique_data=critique_data,
        keyword_data=keyword_data,
    )
    result = claude.analyze(RESUME_TAILOR_SYSTEM, user_message, max_tokens=16000)

    if result.get('error'):
        return jsonify({'error': result['error']}), 500

    total_tokens += result.get('tokens_used', 0)
    total_cost += result.get('cost_usd', 0)
    pipeline_steps.append('tailor')
    print(f"[TAILOR] Step 3 done: Resume tailored (pipeline: {pipeline_steps})")

    tailored_data = result['response']

    # ── Robust JSON extraction (handle various AI response formats) ──
    if isinstance(tailored_data, str):
        import re as re_mod2
        raw_str = tailored_data.strip()
        parsed = None

        # Strategy 1: Direct JSON parse
        try:
            parsed = json_mod.loads(raw_str)
        except Exception:
            pass

        # Strategy 2: Strip markdown code fences
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

        # Strategy 3: Extract first JSON object {...} from the string
        if parsed is None:
            brace_start = raw_str.find('{')
            brace_end = raw_str.rfind('}')
            if brace_start != -1 and brace_end > brace_start:
                try:
                    parsed = json_mod.loads(raw_str[brace_start:brace_end + 1])
                except Exception:
                    pass

        # Strategy 4: Repair truncated JSON (add missing closing brackets)
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
                    print(f"[TAILOR] JSON repaired (added {open_braces} braces, {open_brackets} brackets)")
                except Exception as repair_err:
                    print(f"[TAILOR] JSON repair failed: {repair_err}")

        if parsed and isinstance(parsed, dict):
            tailored_data = parsed
            print(f"[TAILOR] JSON extracted successfully ({len(str(parsed))} chars)")
        else:
            print(f"[TAILOR] Warning: All JSON extraction strategies failed ({len(raw_str)} chars)")
            print(f"[TAILOR] Raw response preview: {raw_str[:500]}...")

    # Step 2: Generate LaTeX
    latex_output = ''
    if isinstance(tailored_data, dict):
        try:
            latex_output = render_latex(tailored_data)
        except Exception as e:
            latex_output = f'% LaTeX generation error: {str(e)}\n% The AI response was received but LaTeX rendering failed.\n% Try again or check the server logs.'
            print(f"[TAILOR] LaTeX render error: {e}")
    else:
        raw_preview = str(tailored_data)[:2000]
        latex_output = '% ERROR: AI returned unstructured text. JSON parsing failed.\n% Please try again — the AI sometimes returns raw text.\n'
        for line in raw_preview.split('\n')[:50]:
            latex_output += f'% {line}\n'
        print(f"[TAILOR] tailored_data is not a dict, type={type(tailored_data)}")

    # Step 3: Calculate ATS score using AI's reported keyword usage
    resume_plain = resume_text  # Use the original for comparison
    keyword_matches = None
    if isinstance(tailored_data, dict):
        # Build comprehensive plain text from tailored data for scoring
        # Include section headers so ATS section detection works
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

        # Summary section
        parts.append('SUMMARY')
        parts.append(tailored_data.get('summary', ''))

        # Skills section
        parts.append('TECHNICAL SKILLS')
        for skill_group in tailored_data.get('skills', []):
            parts.append(skill_group.get('category', ''))
            parts.extend(skill_group.get('items', []))

        # Projects section
        if tailored_data.get('projects'):
            parts.append('PROJECTS')
            for proj in tailored_data.get('projects', []):
                parts.append(proj.get('name', ''))
                parts.extend(proj.get('bullets', []))

        # Experience section
        parts.append('PROFESSIONAL EXPERIENCE')
        for exp in tailored_data.get('experience', []):
            parts.append(exp.get('title', ''))
            parts.append(exp.get('company', ''))
            parts.extend(exp.get('bullets', []))

        # Education section
        parts.append('EDUCATION')
        for edu in tailored_data.get('education', []):
            parts.append(edu.get('degree', ''))
            parts.append(edu.get('school', ''))
            parts.append(edu.get('details', '') or '')

        # Other experience
        if tailored_data.get('other_experience'):
            parts.append('OTHER EXPERIENCE')
            for oexp in tailored_data.get('other_experience', []):
                parts.append(oexp.get('title', ''))
                parts.extend(oexp.get('bullets', []))

        resume_plain = ' '.join(parts)

        # Use AI's keyword list for accurate scoring
        kw_used = tailored_data.get('keywords_used', [])
        if kw_used:
            keyword_matches = []
            for kw in kw_used:
                status = 'strong_match' if kw.lower() in resume_plain.lower() else 'weak_match'
                keyword_matches.append({'keyword': kw, 'resume_status': status})

    ats = calculate_ats_score(resume_plain, jd_text, keyword_matches)

    # Step 4: Save application if company name provided
    app_record = None
    if company_name:
        app_record = Application(
            company_name=company_name,
            role_title=role_title or 'Untitled Role',
            jd_text=jd_text,
            ats_score=ats['total_score'],
        )
        if isinstance(tailored_data, dict):
            app_record.tailored_resume = tailored_data
        app_record.tailored_latex = latex_output
        db.session.add(app_record)
        db.session.commit()

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
        db.session.commit()

    return jsonify({
        'tailored_resume': tailored_data,
        'latex': latex_output,
        'ats_score': ats,
        'tokens_used': total_tokens,
        'cost_usd': total_cost,
        'pipeline_steps': pipeline_steps,
        'application_id': app_record.id if app_record else None,
    })


@tailor_bp.route('/api/cover-letter', methods=['POST'])
def api_cover_letter():
    """Generate a matching cover letter."""
    data = request.get_json()
    resume_text = data.get('resume_text', '')
    jd_text = data.get('jd_text', '')
    company_name = data.get('company_name', '')
    role_title = data.get('role_title', '')

    if not jd_text or not resume_text:
        return jsonify({'error': 'Both job description and resume text are required'}), 400

    user_message = build_cover_letter_message(resume_text, jd_text, company_name, role_title)
    result = claude.analyze(COVER_LETTER_SYSTEM, user_message, max_tokens=2048)

    if result.get('error'):
        return jsonify({'error': result['error']}), 500

    # Update application record if provided
    app_id = data.get('application_id')
    if app_id:
        app_record = Application.query.get(app_id)
        if app_record and isinstance(result['response'], dict):
            app_record.cover_letter = result['response'].get('cover_letter_text', '')
            db.session.commit()

    return jsonify({
        'cover_letter': result['response'],
        'tokens_used': result['tokens_used'],
        'cost_usd': result['cost_usd'],
    })


@tailor_bp.route('/api/ats-score', methods=['POST'])
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
