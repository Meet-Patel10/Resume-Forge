from flask import Blueprint, render_template, request, jsonify, session, send_file
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

tailor_bp = Blueprint('tailor', __name__)


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
    result = claude.analyze(BULLET_REWRITER_SYSTEM, user_message, max_tokens=4096, force_json=True)

    if result.get('error'):
        return jsonify({'error': result['error']}), 500

    return jsonify({
        'rewritten': result['response'],
        'tokens_used': result['tokens_used'],
        'cost_usd': result['cost_usd'],
    })


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

    if not jd_text or not resume_text:
        return jsonify({'error': 'Both job description and resume text are required'}), 400

    total_tokens = 0
    total_cost = 0.0
    pipeline_steps = []

    # step 0: parse the JD for skills, requirements, etc.
    jd_analysis = None
    try:
        jd_msg = build_jd_analysis_message(resume_text, jd_text)
        jd_result = claude.analyze(JD_ANALYZER_SYSTEM, jd_msg, max_tokens=3000, force_json=True)
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
        critique_result = claude.analyze(BRUTAL_CRITIC_SYSTEM, critique_msg, max_tokens=3000, force_json=True)
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
        kw_result = claude.analyze(KEYWORD_EXTRACTOR_SYSTEM, kw_msg, max_tokens=3000, force_json=True)
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

    # step 3: actually tailor the resume using all the context we gathered
    user_message = build_tailor_message(
        resume_text, jd_text,
        keyword_analysis=keyword_analysis,
        critique_data=critique_data,
        keyword_data=keyword_data,
        jd_analysis=jd_analysis,
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

        attempt_result = claude.analyze(
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

                # education from DB
                tailored_data['education'] = master.education or []

                # ---- SKILLS ENFORCEMENT: accept JD-aligned renaming, enforce max 7, no skills lost ----
                master_skills = master.skills or []
                ai_skills = tailored_data.get('skills', [])
                if master_skills and ai_skills:
                    # Get the category_mapping from tailoring_notes (original → renamed)
                    notes = tailored_data.get('tailoring_notes', {})
                    if isinstance(notes, str):
                        notes = {}
                    cat_mapping = notes.get('category_mapping', {})

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

                            # Use AI's items + ensure all master items are present
                            merged = list(matched_ai.get('items', []))
                            for orig in master_items:
                                if orig not in merged:
                                    merged.append(orig)
                            enforced_skills.append({'category': new_cat_name, 'items': merged})
                            used_items.update(merged)
                        else:
                            # AI dropped this category entirely — restore from master
                            enforced_skills.append({'category': master_cat, 'items': list(master_items)})
                            used_items.update(master_items)

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
                                    # Put them in the last category as a catch-all
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

                    # Deduplicate items within each category
                    for group in enforced_skills:
                        seen = set()
                        deduped = []
                        for item in group['items']:
                            key = item.strip().lower()
                            if key not in seen:
                                seen.add(key)
                                deduped.append(item)
                        group['items'] = deduped

                    tailored_data['skills'] = enforced_skills
                    print(f"[tailor] skills: {len(enforced_skills)} categories (max {MAX_CATEGORIES}), mapping={cat_mapping}")

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

                    # prefer keywords the AI tried to inject (they're likely the best fits)
                    for term in jd_hard + jd_soft + jd_top:
                        term_lower = term.lower()
                        if term_lower not in master_lower:
                            # prioritise ones the AI also chose
                            if ai_lower and term_lower in ai_lower:
                                new_keywords.insert(0, term)  # front of list
                            else:
                                new_keywords.append(term)

                    # also grab from keyword gap analysis
                    if keyword_data and isinstance(keyword_data, dict):
                        for kw in keyword_data.get('top_keywords', []):
                            if isinstance(kw, dict) and kw.get('resume_status') in ('missing', 'weak_match'):
                                k = kw.get('keyword', '')
                                if k and k.lower() not in master_lower and len(k.split()) <= 3:
                                    new_keywords.append(k)

                    # deduplicate while preserving order
                    seen = set()
                    unique_kw = []
                    for k in new_keywords:
                        kl = k.lower()
                        if kl not in seen and kl not in master_lower:
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
                                    # enforce bullet count — if AI added/removed bullets, restore from DB
                                    if len(ai_entry.get('bullets', [])) != len(master_entry['bullets']):
                                        ai_entry['bullets'] = master_entry['bullets']
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

                        # grab tech_stack and dates from AI output since DB bullets may not store them
                        ai_projs = tailored_data.get('projects', [])
                        for ai_proj in ai_projs:
                            ai_name = ai_proj.get('name', '').strip()
                            for key, master_proj in proj_by_name.items():
                                # match by project name (case-insensitive, partial match for long names)
                                if (ai_name.lower() in master_proj['name'].lower() or
                                    master_proj['name'].lower() in ai_name.lower()):
                                    if not master_proj['tech_stack'] and ai_proj.get('tech_stack'):
                                        master_proj['tech_stack'] = ai_proj['tech_stack']
                                    if not master_proj['dates'] and ai_proj.get('dates'):
                                        master_proj['dates'] = ai_proj['dates']
                                    break

                        tailored_data['projects'] = list(proj_by_name.values())

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

    # step 4.5: structure validation agent — ensures JSON matches template format
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
                                proj_entries[b.company] = {'name': b.company, 'bullets': []}
                            proj_entries[b.company]['bullets'].append(b.original_text)
                    master_structure['experience'] = list(exp_entries.values())
                    master_structure['projects'] = list(proj_entries.values())

                validator_msg = build_validator_message(tailored_data, master_structure)
                val_result = claude.analyze(STRUCTURE_VALIDATOR_SYSTEM, validator_msg, max_tokens=16000, temperature=0.1, force_json=True)

                if not val_result.get('error'):
                    val_resp = val_result.get('response')
                    if isinstance(val_resp, dict) and 'summary' in val_resp and 'skills' in val_resp:
                        tailored_data = val_resp
                        total_tokens += val_result.get('tokens_used', 0)
                        total_cost += val_result.get('cost_usd', 0)
                        pipeline_steps.append('structure_validator')
                        print("[tailor] structure validation done — JSON fixed")
                    else:
                        print(f"[tailor] structure validator returned unusable data, skipping")
                else:
                    print(f"[tailor] structure validator error: {val_result['error']}")
        except Exception as e:
            print(f"[tailor] structure validator error (non-fatal): {e}")

    # NOTE: External humanize API removed. Humanization rules are now baked
    # directly into the tailor prompt (RESUME_TAILOR_SYSTEM) so the AI produces
    # human-sounding text in a single pass — no post-processing needed.

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
@login_required
def api_cover_letter():
    """Generate a matching cover letter with exactly 330 words in the body."""
    data = request.get_json()
    resume_text = data.get('resume_text', '')
    jd_text = data.get('jd_text', '')
    company_name = data.get('company_name', '')
    role_title = data.get('role_title', '')
    TARGET_WORDS = 300

    if not jd_text or not resume_text:
        return jsonify({'error': 'Both job description and resume text are required'}), 400

    total_tokens = 0
    total_cost = 0.0

    # Step 1: Generate initial cover letter
    user_message = build_cover_letter_message(resume_text, jd_text, company_name, role_title)
    result = claude.analyze(COVER_LETTER_SYSTEM, user_message, max_tokens=2048, force_json=True)

    if result.get('error'):
        return jsonify({'error': result['error']}), 500

    total_tokens += result.get('tokens_used', 0)
    total_cost += result.get('cost_usd', 0.0)

    response = result['response']
    if not isinstance(response, dict):
        return jsonify({'cover_letter': response, 'tokens_used': total_tokens, 'cost_usd': total_cost})

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

    # Step 3: If word count is off, use adjustment loop (max 3 retries)
    MAX_RETRIES = 3
    for attempt in range(MAX_RETRIES):
        if current_count == TARGET_WORDS:
            break

        print(f"[cover-letter] Body word count: {current_count}, target: {TARGET_WORDS}. Adjusting (attempt {attempt + 1})...")
        adjust_msg = build_adjust_message(body_text, current_count, TARGET_WORDS)
        adjust_result = claude.analyze(COVER_LETTER_ADJUST_SYSTEM, adjust_msg, max_tokens=2048, force_json=True)

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
    # Keep word_count for backward compatibility in the frontend
    response['word_count'] = current_count

    # Update application record if provided
    app_id = data.get('application_id')
    if app_id:
        app_record = Application.query.get(app_id)
        if app_record and isinstance(response, dict):
            app_record.cover_letter = response.get('cover_letter_text', '')
            db.session.commit()

    return jsonify({
        'cover_letter': response,
        'tokens_used': total_tokens,
        'cost_usd': total_cost,
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
            # First line = name (bold, larger)
            pdf.set_font(font_name, 'B' if bold_loaded else '', size=14)
            pdf.cell(0, 7, header_lines[0], new_x='LMARGIN', new_y='NEXT', align='C')

            # Remaining header lines (contact info — smaller, centered)
            if len(header_lines) > 1:
                pdf.set_font(font_name, '', size=10)
                pdf.set_text_color(80, 80, 80)
                for line in header_lines[1:]:
                    pdf.cell(0, 5, line, new_x='LMARGIN', new_y='NEXT', align='C')
                pdf.set_text_color(30, 30, 30)

            # Separator line
            pdf.ln(3)
            y = pdf.get_y()
            pdf.set_draw_color(180, 180, 180)
            pdf.line(25.4, y, 595.28 / 72 * 25.4 - 25.4, y)
            pdf.ln(6)

        # === RENDER DATE ===
        if date_line:
            pdf.set_font(font_name, '', size=10)
            pdf.cell(0, 6, date_line, new_x='LMARGIN', new_y='NEXT')
            pdf.ln(4)

        # === RENDER SALUTATION ===
        if salutation_line:
            pdf.set_font(font_name, '', size=10)
            pdf.cell(0, 6, salutation_line, new_x='LMARGIN', new_y='NEXT')
            pdf.ln(4)

        # === RENDER BODY PARAGRAPHS ===
        for i, para in enumerate(body_paragraphs):
            pdf.set_font(font_name, '', size=10)
            clean_text = ' '.join(l.strip() for l in para.split('\n') if l.strip())
            pdf.multi_cell(0, 5.5, clean_text, new_x='LMARGIN', new_y='NEXT')
            if i < len(body_paragraphs) - 1:
                pdf.ln(4)

        # === RENDER SIGN-OFF ===
        if signoff_lines:
            pdf.ln(6)
            for j, line in enumerate(signoff_lines):
                if line.strip() == full_name or line.strip() == full_name.strip():
                    pdf.set_font(font_name, 'B' if bold_loaded else '', size=10)
                    pdf.cell(0, 6, line, new_x='LMARGIN', new_y='NEXT')
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

    if not latex_code:
        return jsonify({'error': 'No LaTeX code provided'}), 400

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
                headers={'Content-Disposition': 'attachment; filename=tailored_resume.pdf'}
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

    if not resume_json:
        return jsonify({'error': 'No resume data provided'}), 400

    try:
        from app.services.docx_engine import render_docx
        docx_bytes = render_docx(resume_json)
        return Response(
            docx_bytes,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            headers={'Content-Disposition': 'attachment; filename=tailored_resume.docx'}
        )
    except ImportError:
        return jsonify({'error': 'python-docx is not installed. Run: pip install python-docx'}), 500
    except Exception as e:
        return jsonify({'error': f'DOCX generation failed: {str(e)}'}), 500
