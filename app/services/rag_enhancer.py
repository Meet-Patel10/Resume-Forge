"""RAG-enhanced resume tailoring using NVIDIA embedding + generation models.

This module provides semantic matching between JD requirements and resume bullets
using vector embeddings. It produces a structured alignment map that tells the
tailoring AI exactly WHERE to inject each keyword for maximum ATS alignment.

This is an OPTIONAL enhancement layer. If any step fails, it returns None and
the existing tailoring pipeline continues unchanged.
"""

import re
import math


def extract_resume_bullets(resume_text):
    """Parse resume text into individual bullets with metadata.

    Returns a list of dicts:
    [
        {
            'text': 'Owned backend development and maintenance of 4 Spring Boot microservices',
            'section': 'experience',
            'context': 'Capgemini',  # role/project name if detectable
            'index': 0,
        },
        ...
    ]
    """
    bullets = []

    # Split into lines and identify sections
    lines = resume_text.split('\n')
    current_section = 'unknown'
    current_context = ''

    # Section detection patterns
    section_patterns = {
        'experience': re.compile(r'(?i)^\s*(professional\s+)?experience\s*$'),
        'projects': re.compile(r'(?i)^\s*(academic\s+|personal\s+)?projects?\s*$'),
        'education': re.compile(r'(?i)^\s*education\s*$'),
        'skills': re.compile(r'(?i)^\s*(technical\s+)?skills?\s*$'),
        'summary': re.compile(r'(?i)^\s*(professional\s+)?summary\s*$'),
        'certifications': re.compile(r'(?i)^\s*certifications?\s*$'),
    }

    # Bullet pattern: lines starting with bullet markers or dashes
    bullet_pattern = re.compile(r'^\s*[•\-–—*]\s*(.+)')
    # Context pattern: company/project names (usually bold or preceding bullets)
    context_pattern = re.compile(r'^[A-Z][A-Za-z\s&.,\-]+(?:\s*[|—–]\s*.+)?$')

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Check for section headers
        section_found = False
        for sec_name, pattern in section_patterns.items():
            if pattern.match(stripped):
                current_section = sec_name
                section_found = True
                break
        if section_found:
            continue

        # Check for context (company/project names)
        if (current_section in ('experience', 'projects') and
                len(stripped) < 100 and
                not bullet_pattern.match(stripped) and
                context_pattern.match(stripped)):
            current_context = stripped[:80]
            continue

        # Check for bullets
        bullet_match = bullet_pattern.match(stripped)
        if bullet_match and current_section in ('experience', 'projects'):
            bullet_text = bullet_match.group(1).strip()
            if len(bullet_text) > 20:  # skip very short fragments
                bullets.append({
                    'text': bullet_text,
                    'section': current_section,
                    'context': current_context,
                    'index': len(bullets),
                })

    return bullets


def extract_jd_requirements(jd_text, jd_analysis=None):
    """Parse JD into individual requirements with priority.

    Uses jd_analysis (from the JD analyzer step) if available for structured
    extraction. Falls back to raw text parsing.

    Returns a list of dicts:
    [
        {
            'text': 'Strong proficiency in JavaScript/TypeScript',
            'type': 'hard_skill',  # or 'soft_skill', 'responsibility', 'domain'
            'priority': 'required',  # or 'preferred', 'nice_to_have'
            'source_section': 'requirements',
        },
        ...
    ]
    """
    requirements = []

    # Use structured JD analysis if available
    if jd_analysis and isinstance(jd_analysis, dict):
        # Hard skills (highest priority)
        for skill in jd_analysis.get('hard_skills', []):
            requirements.append({
                'text': skill,
                'type': 'hard_skill',
                'priority': 'required',
                'source_section': 'requirements',
            })

        # Soft skills
        for skill in jd_analysis.get('soft_skills', []):
            requirements.append({
                'text': skill,
                'type': 'soft_skill',
                'priority': 'required',
                'source_section': 'requirements',
            })

        # Top keywords
        for kw in jd_analysis.get('top_keywords', []):
            # Avoid duplicates with hard_skills
            if not any(r['text'].lower() == kw.lower() for r in requirements):
                requirements.append({
                    'text': kw,
                    'type': 'hard_skill',
                    'priority': 'required',
                    'source_section': 'requirements',
                })

    # Also extract from raw text for completeness (critical when jd_analysis is None)
    lines = jd_text.split('\n')
    current_section = 'general'
    section_map = {
        'requirements': re.compile(r'(?i)(requirements|qualifications|what you.ll bring|must.have|minimum|about you|skills|experience needed)'),
        'responsibilities': re.compile(r'(?i)(responsibilities|what you.ll do|your role|key duties|day.to.day|in this role)'),
        'preferred': re.compile(r'(?i)(preferred|nice.to.have|bonus|plus|ideal|good to have)'),
    }

    # Match bullets (•, -, –, —, *) AND numbered items (1., 2., a., b.)
    bullet_pattern = re.compile(r'^\s*(?:[•\-–—*]|\d+[.)]\s*|[a-z][.)]\s*)\s*(.+)')

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Detect section
        for sec_name, pattern in section_map.items():
            if pattern.search(stripped) and len(stripped) < 80:
                current_section = sec_name
                break

        # Extract bullet-point or numbered-list requirements from raw JD text
        bullet_match = bullet_pattern.match(stripped)
        if bullet_match:
            req_text = bullet_match.group(1).strip()
            if len(req_text) > 15:
                # Check if this requirement is already covered by jd_analysis
                is_duplicate = any(
                    r['text'].lower() in req_text.lower() or
                    req_text.lower() in r['text'].lower()
                    for r in requirements
                )
                if not is_duplicate:
                    priority = 'required' if current_section == 'requirements' else (
                        'preferred' if current_section == 'preferred' else 'required'
                    )
                    requirements.append({
                        'text': req_text,
                        'type': 'responsibility' if current_section == 'responsibilities' else 'hard_skill',
                        'priority': priority,
                        'source_section': current_section,
                    })
        elif current_section in ('requirements', 'preferred') and len(stripped) > 20 and len(stripped) < 200:
            # Plain sentence under a requirements heading — also counts as a requirement
            is_duplicate = any(
                r['text'].lower() in stripped.lower() or
                stripped.lower() in r['text'].lower()
                for r in requirements
            )
            # Skip lines that look like section headers themselves
            is_header = section_map['requirements'].search(stripped) or section_map['preferred'].search(stripped)
            if not is_duplicate and not is_header:
                priority = 'required' if current_section == 'requirements' else 'preferred'
                requirements.append({
                    'text': stripped,
                    'type': 'hard_skill',
                    'priority': priority,
                    'source_section': current_section,
                })

    return requirements


def _cosine_similarity(vec_a, vec_b):
    """Compute cosine similarity between two vectors."""
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    magnitude_a = math.sqrt(sum(a * a for a in vec_a))
    magnitude_b = math.sqrt(sum(b * b for b in vec_b))
    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0
    return dot_product / (magnitude_a * magnitude_b)


def compute_alignment_map(nvidia_client, jd_requirements, resume_bullets):
    """Embed JD requirements and resume bullets, compute semantic alignment.

    Args:
        nvidia_client: NvidiaClient instance with embed() method
        jd_requirements: List of requirement dicts from extract_jd_requirements()
        resume_bullets: List of bullet dicts from extract_resume_bullets()

    Returns:
        List of alignment entries sorted by similarity score:
        [
            {
                'jd_requirement': { ... },
                'best_bullet': { ... },
                'similarity': 0.89,
                'match_tier': 'high',  # 'high' (≥0.75), 'partial' (0.50-0.75), 'none' (<0.50)
                'action': 'inject',  # 'inject', 'strengthen', 'skip'
            },
            ...
        ]
    """
    if not jd_requirements or not resume_bullets:
        return []

    # Prepare texts for embedding
    jd_texts = [req['text'] for req in jd_requirements]
    bullet_texts = [b['text'] for b in resume_bullets]

    # Embed JD requirements (as queries — we're searching FOR these)
    print(f"[rag] Embedding {len(jd_texts)} JD requirements...")
    jd_embed_result = nvidia_client.embed(jd_texts, input_type='query')
    if jd_embed_result.get('error') or not jd_embed_result.get('embeddings'):
        print(f"[rag] JD embedding failed: {jd_embed_result.get('error', 'no embeddings')}")
        return []

    # Embed resume bullets (as passages — these are the documents to search through)
    print(f"[rag] Embedding {len(bullet_texts)} resume bullets...")
    bullet_embed_result = nvidia_client.embed(bullet_texts, input_type='passage')
    if bullet_embed_result.get('error') or not bullet_embed_result.get('embeddings'):
        print(f"[rag] Bullet embedding failed: {bullet_embed_result.get('error', 'no embeddings')}")
        return []

    jd_embeddings = jd_embed_result['embeddings']
    bullet_embeddings = bullet_embed_result['embeddings']

    print(f"[rag] Computing {len(jd_embeddings)} x {len(bullet_embeddings)} similarity matrix...")

    # Compute similarity matrix and find best match for each JD requirement
    alignment = []
    for i, jd_req in enumerate(jd_requirements):
        best_score = -1.0
        best_bullet_idx = -1

        for j, bullet in enumerate(resume_bullets):
            score = _cosine_similarity(jd_embeddings[i], bullet_embeddings[j])
            if score > best_score:
                best_score = score
                best_bullet_idx = j

        # Classify match tier
        if best_score >= 0.75:
            match_tier = 'high'
            action = 'inject'
        elif best_score >= 0.50:
            match_tier = 'partial'
            action = 'strengthen'
        else:
            match_tier = 'none'
            action = 'skip'

        # Check if the keyword is already present in the best bullet
        if best_bullet_idx >= 0:
            best_bullet = resume_bullets[best_bullet_idx]
            if jd_req['text'].lower() in best_bullet['text'].lower():
                action = 'already_present'
        else:
            best_bullet = None

        alignment.append({
            'jd_requirement': jd_req,
            'best_bullet': best_bullet,
            'similarity': round(best_score, 4),
            'match_tier': match_tier,
            'action': action,
        })

    # Sort by similarity (highest first)
    alignment.sort(key=lambda x: x['similarity'], reverse=True)

    # Log summary
    high = sum(1 for a in alignment if a['match_tier'] == 'high')
    partial = sum(1 for a in alignment if a['match_tier'] == 'partial')
    none_count = sum(1 for a in alignment if a['match_tier'] == 'none')
    print(f"[rag] Alignment: {high} high, {partial} partial, {none_count} no match")

    return alignment


def build_rag_context(alignment_map):
    """Format the alignment map as a structured text block for the tailoring AI.

    This text is injected into the user message so the AI knows exactly WHERE
    to inject each keyword.
    """
    if not alignment_map:
        return ""

    sections = []
    sections.append("## RAG Semantic Alignment Map (NVIDIA Embedding-Based)")
    sections.append("These are the highest-confidence JD-to-resume matches found by semantic similarity.")
    sections.append("Use these to guide WHERE to inject each keyword. FOLLOW THESE PLACEMENTS.\n")

    # Group by tier
    high_matches = [a for a in alignment_map if a['match_tier'] == 'high']
    partial_matches = [a for a in alignment_map if a['match_tier'] == 'partial']
    no_matches = [a for a in alignment_map if a['match_tier'] == 'none']

    if high_matches:
        sections.append("### HIGH CONFIDENCE MATCHES (similarity ≥ 0.75) — INJECT THESE KEYWORDS")
        for i, match in enumerate(high_matches, 1):
            jd_text = match['jd_requirement']['text']
            bullet = match['best_bullet']
            score = match['similarity']
            action = match['action']

            if bullet:
                context = f" [{bullet['section'].title()} @ {bullet['context']}]" if bullet.get('context') else f" [{bullet['section'].title()}]"
                bullet_preview = bullet['text'][:100] + ('...' if len(bullet['text']) > 100 else '')

                if action == 'already_present':
                    sections.append(f'{i}. JD: "{jd_text}" → Resume: "{bullet_preview}"{context} (score: {score})')
                    sections.append(f'   → Already present — no action needed')
                else:
                    sections.append(f'{i}. JD: "{jd_text}" → Resume: "{bullet_preview}"{context} (score: {score})')
                    sections.append(f'   → ACTION: Inject "{jd_text}" into this bullet')
        sections.append("")

    if partial_matches:
        sections.append("### PARTIAL MATCHES (similarity 0.50-0.75) — TRANSFERABLE, USE CAREFULLY")
        for i, match in enumerate(partial_matches, len(high_matches) + 1):
            jd_text = match['jd_requirement']['text']
            bullet = match['best_bullet']
            score = match['similarity']

            if bullet:
                context = f" [{bullet['section'].title()} @ {bullet['context']}]" if bullet.get('context') else f" [{bullet['section'].title()}]"
                bullet_preview = bullet['text'][:100] + ('...' if len(bullet['text']) > 100 else '')
                sections.append(f'{i}. JD: "{jd_text}" → Resume: "{bullet_preview}"{context} (score: {score})')
                sections.append(f'   → Transferable skill — inject ONLY if contextually appropriate, mark as PARTIAL_MATCH')
        sections.append("")

    if no_matches:
        sections.append("### NO MATCH (similarity < 0.50) — DO NOT FORCE THESE")
        for i, match in enumerate(no_matches, len(high_matches) + len(partial_matches) + 1):
            jd_text = match['jd_requirement']['text']
            score = match['similarity']
            sections.append(f'{i}. JD: "{jd_text}" → No resume bullet scored above 0.50 (best: {score})')
            sections.append(f'   → ACTION: Add to keywords_skipped — no backing evidence')
        sections.append("")

    # Summary stats
    total = len(alignment_map)
    high_pct = (len(high_matches) / total * 100) if total else 0
    partial_pct = (len(partial_matches) / total * 100) if total else 0
    sections.append(f"### ALIGNMENT SUMMARY: {len(high_matches)}/{total} high ({high_pct:.0f}%), "
                    f"{len(partial_matches)}/{total} partial ({partial_pct:.0f}%), "
                    f"{len(no_matches)}/{total} no match")

    return "\n".join(sections)


def enhance_tailoring(nvidia_client, resume_text, jd_text, jd_analysis=None):
    """Top-level function: run the full RAG enhancement pipeline.

    This is called from the tailor route as step 2.5. If anything fails,
    it returns None and the existing pipeline continues unchanged.

    Args:
        nvidia_client: NvidiaClient instance
        resume_text: Raw resume text
        jd_text: Raw JD text
        jd_analysis: Optional parsed JD analysis dict

    Returns:
        str: RAG context text to inject into the tailor message, or None on failure
    """
    try:
        print("[rag] Starting RAG enhancement pipeline...")

        # Step 1: Extract resume bullets
        resume_bullets = extract_resume_bullets(resume_text)
        if not resume_bullets:
            print("[rag] No resume bullets extracted — skipping RAG")
            return None
        print(f"[rag] Extracted {len(resume_bullets)} resume bullets")

        # Step 2: Extract JD requirements
        jd_requirements = extract_jd_requirements(jd_text, jd_analysis)
        if not jd_requirements:
            print("[rag] No JD requirements extracted — skipping RAG")
            return None
        print(f"[rag] Extracted {len(jd_requirements)} JD requirements")

        # Step 3: Compute alignment map
        alignment_map = compute_alignment_map(nvidia_client, jd_requirements, resume_bullets)
        if not alignment_map:
            print("[rag] Alignment computation failed — skipping RAG")
            return None

        # Step 4: Build context text
        rag_context = build_rag_context(alignment_map)
        if not rag_context:
            print("[rag] Failed to build RAG context — skipping RAG")
            return None

        print(f"[rag] RAG enhancement complete: {len(rag_context)} chars of context generated")
        return rag_context

    except Exception as e:
        print(f"[rag] RAG enhancement failed (non-fatal): {e}")
        return None
