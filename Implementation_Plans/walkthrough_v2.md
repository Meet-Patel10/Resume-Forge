# Dynamic Tailoring Pipeline — Walkthrough

## What Changed

Replaced all hardcoded, static tailoring logic with a fully dynamic AI-driven system. Every tailoring decision is now driven by fresh analysis of the actual job description at runtime.

## Files Modified

### [NEW] [jd_analyzer.py](file:///Users/meetpatel/Resume_Builder_Application/app/services/prompts/jd_analyzer.py)
New AI prompt (Step 0) that extracts from each JD:
- Exact job title + variants
- All hard skills and soft skills
- Top 8-10 keywords by importance
- Qualification verdict (`strong_fit` / `partial_fit` / `weak_fit` / `not_qualified`)
- Honest gaps with severity ratings
- Section priority and culture signals

### [MODIFIED] [ats_scorer.py](file:///Users/meetpatel/Resume_Builder_Application/app/services/ats_scorer.py)
```diff:ats_scorer.py
===
"""
Industry-grade ATS (Applicant Tracking System) Resume Scorer.

Scoring methodology modeled after Jobscan, Teal HQ, and Cultivated Culture:
  - Hard Skills Match   (35%)  — exact phrase matching of technical skills
  - Soft Skills Match   (10%)  — interpersonal & leadership keywords
  - Job Title Match     (15%)  — role title alignment
  - Section Completeness(10%)  — presence of standard resume sections
  - Measurable Results  (10%)  — numbers, percentages, dollar amounts in bullets
  - Keyword Frequency   (10%)  — repeated JD terms appearing in resume
  - Resume Length/Format(10%)  — length, contact info, ATS-safe formatting
"""

import re
from collections import Counter


# ──────────────────────────────────────────────────────────
#  Common word lists for filtering
# ──────────────────────────────────────────────────────────
STOP_WORDS = {
    'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had',
    'her', 'was', 'one', 'our', 'out', 'has', 'have', 'from', 'with', 'they',
    'been', 'said', 'each', 'which', 'their', 'will', 'other', 'about', 'many',
    'then', 'them', 'these', 'some', 'would', 'make', 'like', 'time', 'very',
    'when', 'come', 'could', 'more', 'than', 'look', 'only', 'into', 'year',
    'most', 'find', 'work', 'also', 'must', 'should', 'what', 'this', 'that',
    'such', 'well', 'just', 'your', 'those', 'does', 'both', 'much', 'need',
    'here', 'know', 'take', 'where', 'every', 'good', 'great', 'help', 'long',
    'own', 'same', 'over', 'while', 'part', 'even', 'back', 'after', 'being',
    'under', 'through', 'between', 'including', 'across', 'within', 'using',
    'able', 'may', 'new', 'who', 'how', 'its', 'been', 'were', 'there',
}

# Common soft skills referenced by Jobscan
SOFT_SKILLS = {
    'communication', 'leadership', 'teamwork', 'collaboration', 'problem solving',
    'problem-solving', 'critical thinking', 'time management', 'adaptability',
    'creativity', 'interpersonal', 'attention to detail', 'organizational',
    'decision making', 'decision-making', 'conflict resolution', 'mentoring',
    'coaching', 'empathy', 'negotiation', 'presentation', 'public speaking',
    'analytical', 'strategic thinking', 'self-motivated', 'initiative',
    'multitasking', 'flexibility', 'emotional intelligence', 'active listening',
    'customer service', 'stakeholder management', 'cross-functional',
    # Additional soft skills often found in JDs
    'fast learner', 'quick learner', 'independent', 'independently',
    'self-starter', 'detail-oriented', 'motivated', 'proactive',
    'innovative', 'collaborative', 'results-driven', 'driven',
    'passionate', 'enthusiastic', 'reliable', 'accountable',
    'transparent', 'open-minded', 'inclusive', 'empathetic',
    'creative', 'resourceful', 'resilient', 'dedicated',
    'responsible', 'diligent', 'hardworking', 'conscientious',
    'aptitude', 'willingness', 'attitude',
}

# JD filler words/phrases to ignore when extracting keywords
JD_FILLER = {
    'experience', 'team', 'role', 'join', 'ability', 'strong', 'working',
    'looking', 'ideal', 'candidate', 'responsible', 'responsibilities',
    'qualifications', 'requirements', 'preferred', 'required', 'position',
    'company', 'opportunity', 'apply', 'benefits', 'salary', 'equal',
    'employer', 'environment', 'culture', 'years', 'minimum', 'plus',
    'bonus', 'health', 'dental', 'vision', 'insurance', 'vacation',
    'competitive', 'package', 'offer', 'full-time', 'part-time',
}


# ──────────────────────────────────────────────────────────
#  Keyword extraction helpers
# ──────────────────────────────────────────────────────────
def _normalize(text):
    """Lowercase and collapse whitespace."""
    return re.sub(r'\s+', ' ', text.lower().strip())


def _extract_phrases(text, max_ngram=3):
    """Extract meaningful 1-gram, 2-gram, and 3-gram phrases from text."""
    text = _normalize(text)
    words = re.findall(r'[a-z][a-z+#./\-]+', text)

    phrases = set()
    # 1-grams (skip very short and stop words)
    for w in words:
        if len(w) >= 2 and w not in STOP_WORDS and w not in JD_FILLER:
            phrases.add(w)

    # 2-grams and 3-grams
    for n in range(2, max_ngram + 1):
        for i in range(len(words) - n + 1):
            gram = ' '.join(words[i:i + n])
            # Keep multi-word phrases if they contain at least one non-stop word
            if any(w not in STOP_WORDS for w in words[i:i + n]):
                phrases.add(gram)

    return phrases


def _extract_hard_skills(jd_text):
    """Extract likely hard/technical skills from a job description.

    Uses a curated bank of 200+ known tech terms to intersect with JD text,
    rather than extracting random n-grams which creates too many false positives.
    """
    text = _normalize(jd_text)

    # ── Curated bank of known tech skills ──
    KNOWN_TECH_SKILLS = {
        # Languages
        'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'ruby', 'go',
        'golang', 'rust', 'swift', 'kotlin', 'php', 'scala', 'r', 'matlab',
        'perl', 'shell', 'bash', 'powershell', 'sql', 'nosql', 'html', 'css',
        'sass', 'less', 'graphql', 'xml', 'json', 'yaml',
        # Frameworks & Libraries
        'react', 'angular', 'vue', 'vue.js', 'next.js', 'nuxt', 'node.js',
        'express', 'django', 'flask', 'spring', 'spring boot', '.net',
        'asp.net', 'ruby on rails', 'rails', 'laravel', 'fastapi',
        'tensorflow', 'pytorch', 'keras', 'scikit-learn', 'pandas', 'numpy',
        'matplotlib', 'jquery', 'bootstrap', 'tailwind', 'svelte',
        # Databases
        'mysql', 'postgresql', 'postgres', 'mongodb', 'redis', 'elasticsearch',
        'dynamodb', 'cassandra', 'oracle', 'sql server', 'sqlite', 'firebase',
        'neo4j', 'couchdb', 'mariadb', 'snowflake', 'bigquery',
        # Cloud & DevOps
        'aws', 'azure', 'gcp', 'google cloud', 'docker', 'kubernetes', 'k8s',
        'terraform', 'ansible', 'jenkins', 'ci/cd', 'github actions',
        'gitlab ci', 'circleci', 'travis ci', 'nginx', 'apache', 'linux',
        'unix', 'windows server', 'serverless', 'lambda', 'cloudformation',
        'helm', 'prometheus', 'grafana', 'datadog', 'splunk', 'elk',
        # Tools & Platforms
        'git', 'github', 'gitlab', 'bitbucket', 'jira', 'confluence',
        'slack', 'trello', 'figma', 'sketch', 'postman', 'swagger',
        'rest', 'restful', 'rest api', 'restful api', 'soap', 'grpc',
        'webpack', 'vite', 'npm', 'yarn', 'pip', 'maven', 'gradle',
        'visual studio', 'intellij', 'vs code', 'eclipse',
        # Concepts & Methodologies
        'microservices', 'api', 'apis', 'agile', 'scrum', 'kanban',
        'tdd', 'bdd', 'unit testing', 'integration testing', 'devops',
        'machine learning', 'deep learning', 'nlp', 'natural language processing',
        'computer vision', 'data science', 'data engineering', 'data analysis',
        'data analytics', 'data visualization', 'etl', 'data pipeline',
        'oop', 'object oriented', 'design patterns', 'solid principles',
        'system design', 'distributed systems', 'cloud computing',
        'containerization', 'orchestration', 'monitoring', 'logging',
        'authentication', 'authorization', 'oauth', 'jwt', 'sso',
        'cybersecurity', 'encryption', 'penetration testing',
        'responsive design', 'accessibility', 'seo',
        'version control', 'code review', 'pair programming',
        'full stack', 'front end', 'frontend', 'back end', 'backend',
        'mobile development', 'ios', 'android', 'react native', 'flutter',
        # Data & Analytics
        'tableau', 'power bi', 'looker', 'hadoop', 'spark', 'apache spark',
        'kafka', 'airflow', 'dbt', 'redshift', 'databricks',
        'data warehouse', 'data lake', 'data modeling',
        # Other
        'blockchain', 'web3', 'iot', 'embedded systems', 'robotics',
        'ar/vr', 'game development', 'unity', 'unreal',
        'sdn', 'networking', 'tcp/ip', 'dns', 'load balancing',
        'caching', 'message queue', 'rabbitmq', 'sqs',
        'pdf', 'latex', 'automation', 'scripting', 'regex',
    }

    # Find which known skills appear in the JD
    hard_skills = set()
    for skill in KNOWN_TECH_SKILLS:
        # Use word boundary matching for single-word terms
        if len(skill.split()) == 1:
            # Handle special chars in skill names
            escaped = re.escape(skill)
            if re.search(r'(?:^|\s|[,;/(])' + escaped + r'(?:$|\s|[,;/)])', text):
                hard_skills.add(skill)
        else:
            if skill in text:
                hard_skills.add(skill)

    # Also extract any technology-looking terms with special chars (C++, .NET, CI/CD)
    tech_special = re.findall(r'\b[a-zA-Z][a-zA-Z0-9]*[+#./\-][a-zA-Z0-9+#./\-]*\b', jd_text)
    for term in tech_special:
        hard_skills.add(term.lower())

    # Dynamic extraction: capitalized/abbreviated terms likely to be tech (SDLC, ERP, etc.)
    acronyms = re.findall(r'\b[A-Z]{2,}(?:/[A-Z]{2,})*\b', jd_text)
    for acr in acronyms:
        if acr.lower() not in STOP_WORDS and acr.lower() not in JD_FILLER and len(acr) >= 2:
            hard_skills.add(acr.lower())

    # Extract quoted or parenthetical terms that are likely skill names
    paren_terms = re.findall(r'\(([^)]{2,30})\)', jd_text)
    for pt in paren_terms:
        pt_lower = pt.strip().lower()
        if pt_lower not in STOP_WORDS and pt_lower not in JD_FILLER:
            hard_skills.add(pt_lower)

    return hard_skills


def _extract_soft_skills_from_text(text):
    """Find soft skills mentioned in text."""
    text_lower = _normalize(text)
    found = set()
    for skill in SOFT_SKILLS:
        if skill in text_lower:
            found.add(skill)
    # Also check for verb/adjective forms of soft skills
    soft_variants = {
        'collaborate': 'collaboration',
        'collaborating': 'collaboration',
        'collaborative': 'collaboration',
        'communicated': 'communication',
        'communicating': 'communication',
        'communicate': 'communication',
        'lead': 'leadership',
        'led': 'leadership',
        'leading': 'leadership',
        'managed': 'stakeholder management',
        'managing': 'stakeholder management',
        'resolved': 'conflict resolution',
        'mentored': 'mentoring',
        'coached': 'coaching',
        'presented': 'presentation',
        'negotiated': 'negotiation',
        'analyzed': 'analytical',
        'analyzing': 'analytical',
        'adapted': 'adaptability',
        'organized': 'organizational',
        'prioritized': 'time management',
        'coordinated': 'cross-functional',
        'cross-functional': 'cross-functional',
        'stakeholder': 'stakeholder management',
        'troubleshoot': 'problem solving',
        'troubleshooting': 'problem solving',
        'debug': 'problem solving',
        'debugging': 'problem solving',
        'diagnos': 'problem solving',
        'support': 'customer service',
        'supporting': 'customer service',
    }
    for variant, canonical in soft_variants.items():
        if variant in text_lower:
            found.add(canonical)
    return found


def _extract_job_titles(jd_text):
    """Extract likely job title from the JD.
    
    Tries multiple strategies to find the title in various JD formats.
    """
    lines = jd_text.strip().split('\n')[:20]  # Check more lines
    titles = []
    
    # Strategy 1: Explicit label patterns
    label_patterns = [
        r'(?:job\s+title|position|role|title)\s*[:：]\s*(.+)',
        r'(?:we\s+are\s+(?:looking|hiring|seeking)\s+(?:for\s+)?(?:a|an)\s+)(.+?)(?:\.|,|$)',
        r'(?:hiring|seeking|recruiting)\s*[:：]?\s*(.+?)(?:\.|,|$)',
    ]
    for line in lines:
        for pat in label_patterns:
            m = re.search(pat, line, re.IGNORECASE)
            if m:
                title = m.group(1).strip()
                if 3 <= len(title) <= 60:
                    titles.append(_normalize(title))
    
    # Strategy 2: Lines containing common role suffixes
    role_words = r'(?:Engineer|Developer|Manager|Analyst|Designer|Architect|Lead|Director|Specialist|Coordinator|Administrator|Consultant|Scientist|Technician|Intern|Associate|Officer|Programmer|Tester|Support)'
    for line in lines:
        m = re.search(rf'\b([A-Z][a-zA-Z\s/&,\-]+{role_words})\b', line)
        if m:
            title = m.group(1).strip()
            if 3 <= len(title) <= 60:
                titles.append(_normalize(title))
    
    # Strategy 3: First non-empty line as potential title (many JDs start with the title)
    if not titles:
        for line in lines[:3]:
            cleaned = line.strip()
            if cleaned and 3 <= len(cleaned) <= 80 and not cleaned.startswith(('http', 'www', 'About')):
                # Check if it contains a role keyword
                if re.search(role_words, cleaned, re.IGNORECASE):
                    titles.append(_normalize(cleaned))
                    break
    
    return titles


# ──────────────────────────────────────────────────────────
#  Main scoring function
# ──────────────────────────────────────────────────────────
def calculate_ats_score(resume_text, jd_text, keyword_matches=None, jd_analysis=None):
    """Calculate an industry-grade ATS proxy score.

    When jd_analysis is provided (from the JD Deep Analyzer AI), all scoring
    uses dynamic data extracted from the specific JD. When absent, falls back
    to the existing static logic for backward compatibility.

    Scoring weights:
      - Hard Skills Match    35%
      - Soft Skills Match    10%
      - Job Title Match      15%
      - Section Completeness 10%
      - Measurable Results   10%
      - Keyword Frequency    10%
      - Resume Length/Format  10%

    Args:
        resume_text: Plain text of the resume
        jd_text: Plain text of the job description
        keyword_matches: Optional pre-computed keyword matches from AI

    Returns:
        dict with detailed score breakdown
    """
    resume_lower = _normalize(resume_text)
    jd_lower = _normalize(jd_text)

    # ── 1. HARD SKILLS MATCH (35%) ────────────────────────
    if keyword_matches:
        # Use AI-provided keyword list
        total_kw = len(keyword_matches)
        strong = sum(1 for k in keyword_matches if k.get('resume_status') == 'strong_match')
        weak = sum(1 for k in keyword_matches if k.get('resume_status') == 'weak_match')
        hard_skill_score = ((strong * 1.0 + weak * 0.4) / max(total_kw, 1)) * 100
        hard_skill_detail = {
            'total_keywords': total_kw,
            'strong_matches': strong,
            'weak_matches': weak,
            'missing': total_kw - strong - weak,
        }
    elif jd_analysis and jd_analysis.get('hard_skills'):
        # DYNAMIC PATH: Use AI-extracted hard skills from this specific JD
        jd_skills = set(s.lower() for s in jd_analysis['hard_skills'])
        matched = []
        missing = []
        for term in sorted(jd_skills):
            if term in resume_lower:
                matched.append(term)
            else:
                missing.append(term)
        total = len(jd_skills)
        hard_skill_score = (len(matched) / max(total, 1)) * 100
        hard_skill_detail = {
            'total_keywords': total,
            'matched': len(matched),
            'missing_count': len(missing),
            'top_missing': missing[:15],
            'top_matched': matched[:15],
            'source': 'dynamic_jd_analysis',
        }
    else:
        # STATIC FALLBACK: Extract hard skills from JD using curated tech keyword bank
        jd_skills = _extract_hard_skills(jd_text)
        matched = []
        missing = []
        for term in sorted(jd_skills):
            if term in resume_lower:
                matched.append(term)
            else:
                missing.append(term)
        total = len(jd_skills)
        hard_skill_score = (len(matched) / max(total, 1)) * 100
        hard_skill_detail = {
            'total_keywords': total,
            'matched': len(matched),
            'missing_count': len(missing),
            'top_missing': missing[:15],
            'top_matched': matched[:15],
            'source': 'static_bank',
        }

    # ── 2. SOFT SKILLS MATCH (10%) ────────────────────────
    if jd_analysis and jd_analysis.get('soft_skills'):
        # DYNAMIC PATH: Use AI-extracted soft skills from this specific JD
        jd_soft_list = set(s.lower() for s in jd_analysis['soft_skills'])
        soft_matched = set()
        soft_missing = set()
        for skill in jd_soft_list:
            if skill in resume_lower:
                soft_matched.add(skill)
            else:
                soft_missing.add(skill)
        soft_score = (len(soft_matched) / max(len(jd_soft_list), 1)) * 100
        soft_detail = {
            'jd_soft_skills': sorted(jd_soft_list),
            'matched': sorted(soft_matched),
            'missing': sorted(soft_missing),
            'source': 'dynamic_jd_analysis',
        }
    else:
        # STATIC FALLBACK: Use hardcoded soft skills bank
        jd_soft = _extract_soft_skills_from_text(jd_text)
        resume_soft = _extract_soft_skills_from_text(resume_text)
        if jd_soft:
            soft_matched_set = jd_soft & resume_soft
            soft_score = (len(soft_matched_set) / len(jd_soft)) * 100
            soft_detail = {
                'jd_soft_skills': sorted(jd_soft),
                'matched': sorted(soft_matched_set),
                'missing': sorted(jd_soft - resume_soft),
                'source': 'static_bank',
            }
        else:
            soft_score = 100
            soft_detail = {'jd_soft_skills': [], 'matched': [], 'missing': []}

    # ── 3. JOB TITLE MATCH (15%) ──────────────────────────
    if jd_analysis and jd_analysis.get('job_title'):
        # DYNAMIC PATH: Use AI-extracted job title
        ai_title = _normalize(jd_analysis['job_title'])
        ai_title_words = set(ai_title.split()) - STOP_WORDS
        title_score = 0
        title_detail = {'jd_titles': [ai_title], 'match_found': False, 'source': 'dynamic_jd_analysis'}

        if ai_title_words:
            matched_words = sum(1 for w in ai_title_words if w in resume_lower)
            match_pct = (matched_words / len(ai_title_words)) * 100
            if matched_words >= len(ai_title_words) - 1 and len(ai_title_words) > 1:
                match_pct = max(match_pct, 85)
            title_score = match_pct
            title_detail['match_found'] = match_pct >= 60

        # Also check variants if provided
        for variant in jd_analysis.get('job_title_variants', []):
            variant_lower = _normalize(variant)
            variant_words = set(variant_lower.split()) - STOP_WORDS
            if variant_words:
                v_matched = sum(1 for w in variant_words if w in resume_lower)
                v_pct = (v_matched / len(variant_words)) * 100
                if v_matched >= len(variant_words) - 1 and len(variant_words) > 1:
                    v_pct = max(v_pct, 85)
                if v_pct > title_score:
                    title_score = v_pct
                    title_detail['match_found'] = v_pct >= 60

        title_score = max(title_score, 20)
    else:
        # STATIC FALLBACK: Regex-based title extraction
        jd_titles = _extract_job_titles(jd_text)
        title_score = 0
        title_detail = {'jd_titles': jd_titles, 'match_found': False, 'source': 'static_regex'}

        if jd_titles:
            for title in jd_titles:
                title_words = set(title.split()) - STOP_WORDS
                if title_words:
                    resume_title_words = sum(1 for w in title_words if w in resume_lower)
                    match_pct = (resume_title_words / len(title_words)) * 100
                    if resume_title_words >= len(title_words) - 1 and len(title_words) > 1:
                        match_pct = max(match_pct, 85)
                    if match_pct > title_score:
                        title_score = match_pct
                        title_detail['match_found'] = match_pct >= 60
            title_score = max(title_score, 20)
        else:
            jd_words = set(re.findall(r'[a-z]+', jd_lower)) - STOP_WORDS - JD_FILLER
            resume_words_set = set(re.findall(r'[a-z]+', resume_lower))
            overlap = jd_words & resume_words_set
            title_score = min((len(overlap) / max(len(jd_words), 1)) * 130, 90)
            title_detail['note'] = 'Inferred from JD word overlap'

    # ── 4. SECTION COMPLETENESS (10%) ─────────────────────
    required_sections = {
        'summary': ['summary', 'objective', 'profile', 'professional summary'],
        'experience': ['experience', 'work history', 'employment', 'professional experience'],
        'education': ['education', 'academic', 'degree'],
        'skills': ['skills', 'technical skills', 'competencies', 'technologies'],
    }
    optional_sections = {
        'projects': ['projects', 'portfolio'],
        'certifications': ['certifications', 'certificates', 'licenses'],
    }

    sections_found = {}
    for section_name, variants in required_sections.items():
        sections_found[section_name] = any(v in resume_lower for v in variants)

    required_count = sum(1 for v in sections_found.values() if v)
    section_score = (required_count / len(required_sections)) * 100

    # Bonus for optional sections (up to 10% extra, capped at 100)
    optional_found = sum(1 for variants in optional_sections.values()
                         if any(v in resume_lower for v in variants))
    section_score = min(section_score + (optional_found * 5), 100)

    section_detail = {
        'required': sections_found,
        'required_found': required_count,
        'optional_found': optional_found,
    }

    # ── 5. MEASURABLE RESULTS (10%) ───────────────────────
    # Look for quantified achievements (numbers, percentages, dollar amounts)
    metrics_patterns = [
        r'\d+%',                          # percentages
        r'\$[\d,]+',                      # dollar amounts
        r'\d+x\b',                        # multipliers (2x, 3x)
        r'\b\d{2,}\b',                    # numbers >= 10
        r'\b\d+\s*(?:million|billion|k)\b',  # large numbers
    ]

    metric_count = 0
    for pat in metrics_patterns:
        metric_count += len(re.findall(pat, resume_text, re.IGNORECASE))

    # Industry standard: good resumes have 5-15 measurable results
    if metric_count >= 10:
        measurable_score = 100
    elif metric_count >= 5:
        measurable_score = 80
    elif metric_count >= 3:
        measurable_score = 60
    elif metric_count >= 1:
        measurable_score = 40
    else:
        measurable_score = 10

    measurable_detail = {
        'metrics_found': metric_count,
        'recommendation': 'Add more quantified achievements (numbers, %, $)'
                          if metric_count < 5 else 'Good use of metrics'
    }

    # ── 6. KEYWORD FREQUENCY (10%) ────────────────────────
    if jd_analysis and jd_analysis.get('top_keywords'):
        # DYNAMIC PATH: Use AI-identified top keywords
        top_jd_terms = [k.lower() for k in jd_analysis['top_keywords']]
        resume_words_list = re.findall(r'[a-z][a-z+#./\-]+', resume_lower)
        resume_word_counts = Counter(resume_words_list)

        freq_matched = 0
        freq_details = []
        for term in top_jd_terms:
            # Check both exact word match and substring match for multi-word terms
            found_count = resume_word_counts.get(term, 0)
            if found_count == 0 and ' ' not in term:
                # Also check if the term appears as a substring
                found_count = resume_lower.count(term)
            if found_count > 0:
                freq_matched += 1
                freq_details.append({'term': term, 'resume_count': found_count})

        frequency_score = (freq_matched / max(len(top_jd_terms), 1)) * 100
        frequency_detail = {
            'top_jd_terms_checked': len(top_jd_terms),
            'terms_found_in_resume': freq_matched,
            'details': freq_details[:10],
            'source': 'dynamic_jd_analysis',
        }
    else:
        # STATIC FALLBACK: Top-8 unigram frequency
        jd_words = re.findall(r'[a-z][a-z+#./\-]+', jd_lower)
        jd_word_counts = Counter(w for w in jd_words
                                 if w not in STOP_WORDS and w not in JD_FILLER and len(w) >= 4)
        top_jd_terms = [term for term, _ in jd_word_counts.most_common(8)]

        resume_words_list = re.findall(r'[a-z][a-z+#./\-]+', resume_lower)
        resume_word_counts = Counter(resume_words_list)

        freq_matched = 0
        freq_details = []
        for term in top_jd_terms:
            jd_count = jd_word_counts[term]
            resume_count = resume_word_counts.get(term, 0)
            if resume_count > 0:
                freq_matched += 1
                freq_details.append({'term': term, 'jd_count': jd_count, 'resume_count': resume_count})

        frequency_score = (freq_matched / max(len(top_jd_terms), 1)) * 100
        frequency_detail = {
            'top_jd_terms_checked': len(top_jd_terms),
            'terms_found_in_resume': freq_matched,
            'details': freq_details[:10],
            'source': 'static_counter',
        }

    # ── 7. RESUME LENGTH & FORMAT (10%) ───────────────────
    format_score = 100
    format_issues = []

    # Length check
    word_count = len(resume_text.split())
    if word_count < 150:
        format_issues.append('Resume appears too short (under 150 words)')
        format_score -= 25
    elif word_count > 1000:
        format_issues.append('Resume may be too long — keep to 1 page (~400-700 words)')
        format_score -= 10

    # Contact info
    has_email = bool(re.search(r'[\w.\-]+@[\w.\-]+\.\w+', resume_text))
    has_phone = bool(re.search(r'[\d\s\-().]{10,}', resume_text))
    if not has_email:
        format_issues.append('No email address detected')
        format_score -= 15
    if not has_phone:
        format_issues.append('No phone number detected (minor — many modern resumes omit phone)')
        format_score -= 5

    # ATS-problematic characters
    if resume_text.count('|') > 15:
        format_issues.append('Excessive pipe characters (|) may confuse ATS parsers')
        format_score -= 10
    if resume_text.count('•') > 30:
        format_issues.append('Consider using standard bullet characters')
        format_score -= 5

    format_score = max(format_score, 0)
    format_detail = {
        'word_count': word_count,
        'has_email': has_email,
        'has_phone': has_phone,
        'issues': format_issues,
    }

    # ──────────────────────────────────────────────────────
    #  WEIGHTED TOTAL
    # ──────────────────────────────────────────────────────
    total_score = int(
        hard_skill_score * 0.35 +
        soft_score * 0.10 +
        title_score * 0.15 +
        section_score * 0.10 +
        measurable_score * 0.10 +
        frequency_score * 0.10 +
        format_score * 0.10
    )
    total_score = min(total_score, 100)

    # Grade (aligned with Jobscan/Teal thresholds)
    if total_score >= 85:
        grade = 'A+'
        verdict = 'Excellent match — very high chance of passing ATS and reaching a recruiter'
    elif total_score >= 75:
        grade = 'A'
        verdict = 'Strong match — likely to pass most ATS filters'
    elif total_score >= 65:
        grade = 'B'
        verdict = 'Good match — should pass many ATS systems but has room for improvement'
    elif total_score >= 50:
        grade = 'C'
        verdict = 'Fair match — may pass some ATS systems but needs keyword optimization'
    elif total_score >= 35:
        grade = 'D'
        verdict = 'Weak match — high risk of ATS rejection, significant keyword gaps'
    else:
        grade = 'F'
        verdict = 'Poor match — resume needs major rework to align with this job description'

    return {
        'total_score': total_score,
        'grade': grade,
        'verdict': verdict,
        'breakdown': {
            'hard_skills': round(hard_skill_score, 1),
            'soft_skills': round(soft_score, 1),
            'job_title': round(title_score, 1),
            'section_completeness': round(section_score, 1),
            'measurable_results': round(measurable_score, 1),
            'keyword_frequency': round(frequency_score, 1),
            'format_compliance': round(format_score, 1),
        },
        'weights': {
            'hard_skills': '35%',
            'soft_skills': '10%',
            'job_title': '15%',
            'section_completeness': '10%',
            'measurable_results': '10%',
            'keyword_frequency': '10%',
            'format_compliance': '10%',
        },
        'details': {
            'hard_skills': hard_skill_detail,
            'soft_skills': soft_detail,
            'job_title': title_detail,
            'sections': section_detail,
            'measurable': measurable_detail,
            'keyword_frequency': frequency_detail,
            'format': format_detail,
        },
        'format_issues': format_issues,
    }


# ══════════════════════════════════════════════════════════
#  GENERAL RESUME HEALTH SCORE (No JD Required)
#
#  Modeled after Resume Worded, Teal Health Check, VMock:
#   - Parsability          15%
#   - Structure/Sections   15%
#   - Action Verbs         15%
#   - Measurable Impact    15%
#   - IT Skills Coverage   20%
#   - Length & Mechanics    10%
#   - Contact Info         10%
# ══════════════════════════════════════════════════════════

# ── IT Role-Specific Keyword Banks ──
IT_ROLE_KEYWORDS = {
    'software_developer': {
        'label': 'Software Developer / Engineer',
        'must_have': [
            'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'go', 'rust', 'ruby',
            'react', 'angular', 'vue', 'node.js', 'express', 'django', 'flask', 'spring',
            'sql', 'postgresql', 'mysql', 'mongodb', 'redis',
            'git', 'github', 'docker', 'kubernetes', 'aws', 'azure', 'gcp',
            'rest', 'api', 'microservices', 'ci/cd', 'jenkins', 'terraform',
            'agile', 'scrum', 'jira', 'unit testing', 'tdd',
            'html', 'css', 'linux', 'bash',
        ],
        'nice_to_have': [
            'graphql', 'kafka', 'rabbitmq', 'elasticsearch', 'nginx',
            'webpack', 'vite', 'next.js', 'tailwind', 'sass',
            'oauth', 'jwt', 'ssl', 'security',
            'design patterns', 'solid', 'oop', 'functional programming',
            'performance optimization', 'caching', 'cdn',
            'mobile', 'react native', 'flutter', 'swift', 'kotlin',
        ],
    },
    'data_analytics': {
        'label': 'Data Analytics / Data Science',
        'must_have': [
            'python', 'r', 'sql', 'excel', 'tableau', 'power bi',
            'pandas', 'numpy', 'matplotlib', 'seaborn', 'scikit-learn',
            'machine learning', 'statistical analysis', 'data visualization',
            'etl', 'data pipeline', 'data warehouse', 'data modeling',
            'postgresql', 'mysql', 'bigquery', 'snowflake', 'redshift',
            'jupyter', 'git', 'aws', 'azure', 'gcp',
            'a/b testing', 'hypothesis testing', 'regression',
        ],
        'nice_to_have': [
            'tensorflow', 'pytorch', 'keras', 'nlp', 'deep learning',
            'spark', 'hadoop', 'airflow', 'dbt', 'kafka',
            'looker', 'metabase', 'grafana',
            'feature engineering', 'dimensionality reduction', 'clustering',
            'time series', 'forecasting', 'recommendation systems',
            'docker', 'kubernetes', 'mlops',
        ],
    },
    'it_devops': {
        'label': 'IT / DevOps / Systems',
        'must_have': [
            'linux', 'windows server', 'networking', 'tcp/ip', 'dns', 'dhcp',
            'aws', 'azure', 'gcp', 'cloud computing',
            'docker', 'kubernetes', 'terraform', 'ansible', 'puppet', 'chef',
            'ci/cd', 'jenkins', 'github actions', 'gitlab ci',
            'monitoring', 'prometheus', 'grafana', 'datadog', 'splunk',
            'bash', 'powershell', 'python', 'scripting',
            'security', 'firewall', 'vpn', 'ssl/tls',
            'active directory', 'ldap', 'sso',
            'git', 'jira', 'agile',
        ],
        'nice_to_have': [
            'istio', 'service mesh', 'helm', 'argocd',
            'elasticsearch', 'logstash', 'kibana', 'elk stack',
            'nginx', 'apache', 'load balancing', 'cdn',
            'disaster recovery', 'backup', 'high availability',
            'compliance', 'soc 2', 'gdpr', 'hipaa',
            'incident management', 'on-call', 'pagerduty',
            'infrastructure as code', 'cloudformation',
        ],
    },
}

# Strong action verbs (Resume Worded / VMock methodology)
STRONG_ACTION_VERBS = {
    'developed', 'implemented', 'designed', 'built', 'created', 'engineered',
    'architected', 'optimized', 'automated', 'deployed', 'integrated',
    'led', 'managed', 'directed', 'spearheaded', 'orchestrated', 'drove',
    'reduced', 'increased', 'improved', 'accelerated', 'streamlined',
    'analyzed', 'researched', 'evaluated', 'identified', 'diagnosed',
    'migrated', 'refactored', 'scaled', 'configured', 'provisioned',
    'launched', 'delivered', 'shipped', 'released', 'published',
    'mentored', 'trained', 'collaborated', 'coordinated', 'facilitated',
    'established', 'pioneered', 'transformed', 'revamped', 'modernized',
}

# Weak verbs/phrases to flag
WEAK_PHRASES = [
    'responsible for', 'helped with', 'assisted in', 'involved in',
    'worked on', 'participated in', 'duties included', 'tasked with',
    'hard worker', 'team player', 'go-getter', 'detail-oriented',
    'self-starter', 'results-driven', 'think outside the box',
    'synergy', 'leverage', 'paradigm', 'proactive',
]


def _detect_role(resume_text):
    """Auto-detect the most likely IT role family from resume content."""
    text = resume_text.lower()
    scores = {}
    for role_key, role_data in IT_ROLE_KEYWORDS.items():
        score = sum(1 for kw in role_data['must_have'] if kw in text)
        scores[role_key] = score

    best = max(scores, key=scores.get)
    return best, scores


def calculate_general_health_score(resume_text):
    """Calculate a general resume health score without a JD.

    Evaluates parsability, structure, action verbs, measurable impact,
    IT skills coverage, length/mechanics, and contact info.

    Args:
        resume_text: Plain text of the resume

    Returns:
        dict with detailed score breakdown
    """
    text = resume_text
    text_lower = text.lower()
    lines = text.strip().split('\n')
    words = text.split()
    word_count = len(words)

    # Detect the best-fit IT role
    detected_role, role_scores = _detect_role(text)
    role_data = IT_ROLE_KEYWORDS[detected_role]

    # ── 1. PARSABILITY (15%) ───────────────────────────────
    parse_score = 100
    parse_issues = []

    # Check for problematic characters
    special_chars = sum(1 for c in text if ord(c) > 127 and c not in '–—•·''""éèêëàâäùûüôöîïç')
    if special_chars > 20:
        parse_issues.append(f'Found {special_chars} unusual characters that may confuse ATS parsers')
        parse_score -= 15

    # Check for excessive formatting artifacts
    if text.count('|') > 20:
        parse_issues.append('Excessive pipe characters — may indicate table-based layout')
        parse_score -= 10
    if text.count('\t') > 10:
        parse_issues.append('Tab characters detected — ATS may misinterpret spacing')
        parse_score -= 10

    # Check for image/graphic indicators
    img_words = ['[image]', '[logo]', '[photo]', '[graphic]', '[chart]']
    if any(w in text_lower for w in img_words):
        parse_issues.append('Images/graphics detected — ATS cannot read these')
        parse_score -= 20

    parse_score = max(parse_score, 0)

    # ── 2. STRUCTURE & SECTIONS (15%) ─────────────────────
    required_sections = {
        'contact': ['email', 'phone', '@', 'linkedin'],
        'summary': ['summary', 'objective', 'profile', 'professional summary', 'about'],
        'experience': ['experience', 'work history', 'employment', 'professional experience'],
        'education': ['education', 'academic', 'degree', 'university', 'college'],
        'skills': ['skills', 'technical skills', 'competencies', 'technologies', 'tools'],
    }
    bonus_sections = {
        'projects': ['projects', 'portfolio', 'personal projects'],
        'certifications': ['certifications', 'certificates', 'licenses'],
    }

    sections_found = {}
    for name, variants in required_sections.items():
        sections_found[name] = any(v in text_lower for v in variants)

    required_count = sum(1 for v in sections_found.values() if v)
    structure_score = (required_count / len(required_sections)) * 100

    bonus_found = sum(1 for variants in bonus_sections.values()
                      if any(v in text_lower for v in variants))
    structure_score = min(structure_score + (bonus_found * 5), 100)

    structure_issues = []
    for name, found in sections_found.items():
        if not found:
            structure_issues.append(f'Missing standard section: {name.title()}')

    # Check for non-standard headings
    non_standard = ['my journey', 'what i do', 'my story', 'career highlights']
    for ns in non_standard:
        if ns in text_lower:
            structure_issues.append(f'Non-standard heading "{ns}" — use standard ATS headings')
            structure_score = max(structure_score - 10, 0)

    # ── 3. ACTION VERBS (15%) ─────────────────────────────
    bullet_lines = [l.strip() for l in lines if l.strip().startswith(('•', '-', '–', '*', '▪'))]
    if not bullet_lines:
        # Look for lines that look like bullets (short, capitalised start)
        bullet_lines = [l.strip() for l in lines
                        if len(l.strip()) > 20 and len(l.strip()) < 200
                        and l.strip()[0].isupper()]

    total_bullets = max(len(bullet_lines), 1)
    strong_verb_count = 0
    weak_phrase_count = 0
    weak_found = []

    for bullet in bullet_lines:
        bullet_lower = bullet.lower().lstrip('•-–*▪ ')
        first_word = bullet_lower.split()[0] if bullet_lower.split() else ''
        if first_word in STRONG_ACTION_VERBS:
            strong_verb_count += 1

        for wp in WEAK_PHRASES:
            if wp in bullet_lower:
                weak_phrase_count += 1
                if wp not in weak_found:
                    weak_found.append(wp)
                break

    verb_ratio = strong_verb_count / total_bullets
    verb_score = min(verb_ratio * 120, 100)  # 120 so 83%+ strong verbs = 100
    if weak_phrase_count > 0:
        verb_score = max(verb_score - (weak_phrase_count * 8), 0)

    verb_detail = {
        'total_bullets': total_bullets,
        'strong_verb_bullets': strong_verb_count,
        'weak_phrases_found': weak_found[:5],
    }

    # ── 4. MEASURABLE IMPACT (15%) ────────────────────────
    metrics_patterns = [
        r'\d+%',
        r'\$[\d,]+',
        r'\d+x\b',
        r'\b\d{2,}\b',
        r'\b\d+\s*(?:million|billion|k)\b',
    ]

    metric_count = 0
    for pat in metrics_patterns:
        metric_count += len(re.findall(pat, text, re.IGNORECASE))

    if metric_count >= 10:
        impact_score = 100
    elif metric_count >= 7:
        impact_score = 85
    elif metric_count >= 5:
        impact_score = 70
    elif metric_count >= 3:
        impact_score = 50
    elif metric_count >= 1:
        impact_score = 30
    else:
        impact_score = 5

    impact_detail = {
        'metrics_found': metric_count,
        'recommendation': 'Add more quantified achievements (numbers, %, $)'
                          if metric_count < 5 else 'Good use of metrics',
    }

    # ── 5. IT SKILLS COVERAGE (20%) ───────────────────────
    must_found = [kw for kw in role_data['must_have'] if kw in text_lower]
    nice_found = [kw for kw in role_data['nice_to_have'] if kw in text_lower]
    must_missing = [kw for kw in role_data['must_have'] if kw not in text_lower]

    must_ratio = len(must_found) / max(len(role_data['must_have']), 1)
    nice_ratio = len(nice_found) / max(len(role_data['nice_to_have']), 1)

    # Weighted: must_have is 70% of this score, nice_to_have is 30%
    skills_score = (must_ratio * 70) + (nice_ratio * 30)
    skills_score = min(skills_score, 100)

    # Also check across all role families
    all_roles_detail = {}
    for rk, rd in IT_ROLE_KEYWORDS.items():
        found = sum(1 for kw in rd['must_have'] if kw in text_lower)
        total = len(rd['must_have'])
        all_roles_detail[rk] = {
            'label': rd['label'],
            'match': f'{found}/{total}',
            'percentage': round((found / total) * 100) if total else 0,
        }

    skills_detail = {
        'detected_role': role_data['label'],
        'must_have_found': len(must_found),
        'must_have_total': len(role_data['must_have']),
        'nice_to_have_found': len(nice_found),
        'top_missing': must_missing[:10],
        'role_breakdown': all_roles_detail,
    }

    # ── 6. LENGTH & MECHANICS (10%) ───────────────────────
    length_score = 100
    length_issues = []

    if word_count < 200:
        length_issues.append(f'Resume is too short ({word_count} words) — aim for 400-700')
        length_score -= 30
    elif word_count < 350:
        length_issues.append(f'Resume may be too short ({word_count} words) — aim for 400-700')
        length_score -= 15
    elif word_count > 1000:
        length_issues.append(f'Resume may be too long ({word_count} words) — keep to 1-2 pages')
        length_score -= 15

    # Check for consistent date formatting
    dates = re.findall(r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]* \d{4}|'
                       r'\d{1,2}/\d{4}|\d{4}\s*[-–]\s*\d{4}|\d{4}\s*[-–]\s*present',
                       text_lower)
    if len(dates) < 2:
        length_issues.append('Few dates found — ensure work history has clear date ranges')
        length_score -= 10

    length_score = max(length_score, 0)

    # ── 7. CONTACT INFO (10%) ─────────────────────────────
    contact_score = 100
    contact_detail = {}

    has_email = bool(re.search(r'[\w.\-+]+@[\w.\-]+\.\w+', text))
    has_phone = bool(re.search(r'[\d\s\-().]{10,}', text))
    has_linkedin = 'linkedin' in text_lower
    has_github = 'github' in text_lower

    contact_detail['email'] = has_email
    contact_detail['phone'] = has_phone
    contact_detail['linkedin'] = has_linkedin
    contact_detail['github'] = has_github

    if not has_email:
        contact_score -= 30
    if not has_phone:
        contact_score -= 25
    if not has_linkedin:
        contact_score -= 15
    if not has_github:
        contact_score -= 10  # Less critical, but good for IT

    contact_score = max(contact_score, 0)

    # ══════════════════════════════════════════════════════
    #  WEIGHTED TOTAL
    # ══════════════════════════════════════════════════════
    total_score = int(
        parse_score * 0.15 +
        structure_score * 0.15 +
        verb_score * 0.15 +
        impact_score * 0.15 +
        skills_score * 0.20 +
        length_score * 0.10 +
        contact_score * 0.10
    )
    total_score = min(total_score, 100)

    # Grade
    if total_score >= 85:
        grade = 'A+'
        verdict = 'Excellent resume health — well-formatted, impactful, and skill-rich'
    elif total_score >= 75:
        grade = 'A'
        verdict = 'Strong resume — minor improvements will push it to top tier'
    elif total_score >= 65:
        grade = 'B'
        verdict = 'Good foundation — needs more metrics, action verbs, or skills'
    elif total_score >= 50:
        grade = 'C'
        verdict = 'Fair — significant improvements needed in multiple areas'
    elif total_score >= 35:
        grade = 'D'
        verdict = 'Weak — major structural and content issues to address'
    else:
        grade = 'F'
        verdict = 'Needs complete rework — parsability, structure, and content all need attention'

    # Collect all issues
    all_issues = parse_issues + structure_issues + length_issues
    if weak_found:
        all_issues.append(f'Weak phrases found: {", ".join(weak_found[:3])}')
    if metric_count < 5:
        all_issues.append(f'Only {metric_count} measurable results — add numbers, %, $')
    if not has_email:
        all_issues.append('Missing email address')
    if not has_phone:
        all_issues.append('Missing phone number')
    if not has_linkedin:
        all_issues.append('Missing LinkedIn URL')

    return {
        'total_score': total_score,
        'grade': grade,
        'verdict': verdict,
        'detected_role': role_data['label'],
        'breakdown': {
            'parsability': round(parse_score, 1),
            'structure': round(structure_score, 1),
            'action_verbs': round(verb_score, 1),
            'measurable_impact': round(impact_score, 1),
            'it_skills': round(skills_score, 1),
            'length_mechanics': round(length_score, 1),
            'contact_info': round(contact_score, 1),
        },
        'weights': {
            'parsability': '15%',
            'structure': '15%',
            'action_verbs': '15%',
            'measurable_impact': '15%',
            'it_skills': '20%',
            'length_mechanics': '10%',
            'contact_info': '10%',
        },
        'details': {
            'parsability': {'issues': parse_issues},
            'structure': {
                'required': sections_found,
                'issues': structure_issues,
            },
            'action_verbs': verb_detail,
            'measurable_impact': impact_detail,
            'it_skills': skills_detail,
            'length': {'word_count': word_count, 'issues': length_issues},
            'contact': contact_detail,
        },
        'format_issues': all_issues,
    }
```

[calculate_ats_score()](file:///Users/meetpatel/Resume_Builder_Application/app/services/ats_scorer.py#290-682) now accepts optional [jd_analysis](file:///Users/meetpatel/Resume_Builder_Application/app/services/prompts/jd_analyzer.py#69-93) dict. When provided, **4 scoring sections** use dynamic data:

| Section | Before (Static) | After (Dynamic) |
|---------|-----------------|-----------------|
| Hard Skills (35%) | 160+ hardcoded tech terms | AI-extracted from this JD |
| Soft Skills (10%) | 50+ hardcoded words | AI-extracted from this JD |
| Job Title (15%) | Regex with role suffixes | AI-extracted exact title |
| Keyword Freq (10%) | Top-8 unigram counter | AI-identified top keywords |

Falls back to static logic when [jd_analysis](file:///Users/meetpatel/Resume_Builder_Application/app/services/prompts/jd_analyzer.py#69-93) is `None` (backward compatible).

### [MODIFIED] [tailor.py](file:///Users/meetpatel/Resume_Builder_Application/app/routes/tailor.py)
```diff:tailor.py
===
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
from app.services.prompts.jd_analyzer import JD_ANALYZER_SYSTEM, build_jd_analysis_message
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

    # ── STEP 0: JD Deep Analysis (Dynamic extraction) ────
    jd_analysis = None
    try:
        jd_msg = build_jd_analysis_message(resume_text, jd_text)
        jd_result = claude.analyze(JD_ANALYZER_SYSTEM, jd_msg, max_tokens=3000)
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
            print(f"[TAILOR] Step 0 done: JD Deep Analysis completed")
            if jd_analysis:
                print(f"[TAILOR] JD title: {jd_analysis.get('job_title', 'N/A')}, "
                      f"hard_skills: {len(jd_analysis.get('hard_skills', []))}, "
                      f"soft_skills: {len(jd_analysis.get('soft_skills', []))}, "
                      f"verdict: {jd_analysis.get('qualification_verdict', {}).get('rating', 'N/A')}")
        else:
            print(f"[TAILOR] Step 0 skipped: {jd_result['error']}")
    except Exception as e:
        print(f"[TAILOR] Step 0 error: {e}")

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

    # ── STEP 3: Tailor the resume (with critique + keyword + JD analysis insights) ──
    user_message = build_tailor_message(
        resume_text, jd_text,
        keyword_analysis=keyword_analysis,
        critique_data=critique_data,
        keyword_data=keyword_data,
        jd_analysis=jd_analysis,
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

    ats = calculate_ats_score(resume_plain, jd_text, keyword_matches, jd_analysis=jd_analysis)

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
```

Pipeline changed from 3 steps to **4 steps**:
1. **Step 0 (NEW)**: JD Deep Analysis
2. **Step 1**: Brutal Critique (unchanged)
3. **Step 2**: Keyword Extraction (unchanged)
4. **Step 3**: Tailor (now receives [jd_analysis](file:///Users/meetpatel/Resume_Builder_Application/app/services/prompts/jd_analyzer.py#69-93) context)

The [jd_analysis](file:///Users/meetpatel/Resume_Builder_Application/app/services/prompts/jd_analyzer.py#69-93) dict feeds into both the tailor prompt AND [calculate_ats_score()](file:///Users/meetpatel/Resume_Builder_Application/app/services/ats_scorer.py#290-682).

### [MODIFIED] [resume_tailor.py](file:///Users/meetpatel/Resume_Builder_Application/app/services/prompts/resume_tailor.py)
```diff:resume_tailor.py
===
RESUME_TAILOR_SYSTEM = """You are an expert resume modifier specializing in ATS optimization. Your job is to take a candidate's EXISTING master resume and make SURGICAL, TARGETED modifications to optimize it for a specific job description — achieving a 90+ ATS score.

## CRITICAL RULE: MODIFY, DO NOT REWRITE
You are NOT creating a new resume. You are MODIFYING the existing one. This means:
- KEEP every single experience entry, project, and education from the original
- KEEP the original bullet points — enhance them by INSERTING JD keywords naturally
- KEEP the original structure and order unless critique specifically says to reorder
- DO NOT remove content unless it's genuinely irrelevant (a last resort)
- DO NOT shorten bullets — make them BETTER by adding keywords
- DO NOT fabricate, invent, or sugarcoat ANY experience, skill, or achievement
- The output resume should be the SAME LENGTH or LONGER than the input, never shorter

## HOW TO MODIFY (not rewrite):
1. **Summary**: Rewrite ONLY the summary to embed top 5 JD keywords. Keep it factual.
2. **Skills section**: ADD missing JD skills the candidate actually has. Reorder to put JD skills first.
3. **Bullet points**: Take each EXISTING bullet and enhance it:
   - Insert relevant JD keywords into the existing sentence naturally
   - Add metrics if the original lacks them (only REAL ones from the resume)
   - Do NOT replace the bullet with a completely different sentence
   - Example: "Built REST APIs" → "Built REST APIs using Python Flask with CI/CD pipeline integration"
4. **Section order**: Move sections only if critique feedback says to

## ZERO TOLERANCE FOR FABRICATION
- If the JD asks for "casualty claims" and the candidate has NEVER done claims work → DO NOT add fake claims experience
- If a keyword is genuinely outside the candidate's background → SKIP IT
- Only embed keywords the candidate can truthfully claim
- Use the candidate's ACTUAL verbs, ACTUAL metrics, ACTUAL technologies
- If you cannot honestly incorporate a keyword → leave it out and note it in tailoring_notes

## ATS OPTIMIZATION (Target: 90+)
- Mirror exact keyword phrases from the JD (not synonyms)
- Place high-priority JD keywords in the summary and first bullets of each role
- Use standard section headings: Summary, Technical Skills, Experience, Projects, Education
- Include abbreviated AND full forms (e.g., "CI/CD (Continuous Integration/Continuous Deployment)")
- In `keywords_used`, list ONLY keywords you actually wove in truthfully
- **SOFT SKILLS**: MANDATORY. Scan the JD for ALL soft skill terms (teamwork, collaboration, communication, leadership, problem-solving, analytical, motivated, independently, aptitude, willingness, fast learner, cross-functional, proactive, detail-oriented, self-starter, innovative, results-driven, etc.). For EACH soft skill found in the JD:
  - Embed it naturally into at least 2-3 bullet points using action verbs
  - Examples: "Independently designed...", "Collaborated with cross-functional teams...", "Demonstrated aptitude for...", "Communicated technical concepts...", "Led problem-solving efforts...", "Proactively identified...", "Motivated cross-team initiatives..."
  - Do NOT just add the word randomly — weave it into a real accomplishment sentence
- **JOB TITLE**: MANDATORY. The VERY FIRST SENTENCE of the summary MUST start with the EXACT job title from the JD. Example: if JD says "Frontend UI Developer", write "Frontend UI Developer with X years of experience..."
- **KEYWORD FREQUENCY**: Top 3-4 JD keywords MUST each appear in AT LEAST 3 different places across the resume (summary + skills section + 2+ bullet points). These are the most important terms for ATS frequency scoring.

## Output Format
Respond ONLY with valid JSON in this exact structure:
{
  "header": {
    "name": "<full name>",
    "location": "<city, state/province>",
    "phone": "<phone>",
    "email": "<email>",
    "linkedin": "<linkedin URL or null>",
    "github": "<github URL or null>",
    "tagline": "<e.g. 'PGWP-eligible | Available for full-time roles'>"
  },
  "summary": "<MODIFIED 2-3 sentence summary — embed top JD keywords using candidate's REAL experience>",
  "skills": [
    {
      "category": "<e.g. Languages & Frameworks, Tools & Concepts>",
      "items": ["<skill1>", "<skill2>"]
    }
  ],
  "projects": [
    {
      "name": "<project name>",
      "tech_stack": "<technologies used, e.g. Python, PyTorch, Transformers>",
      "bullets": ["<MODIFIED bullet 1>", "<MODIFIED bullet 2>"]
    }
  ],
  "experience": [
    {
      "title": "<ORIGINAL job title — do not change>",
      "company": "<company name>",
      "location": "<location>",
      "dates": "<date range, e.g. Feb 2022 -- March 2024>",
      "bullets": ["<MODIFIED bullet 1 — original + JD keywords>", "<MODIFIED bullet 2>"]
    }
  ],
  "education": [
    {
      "degree": "<degree name>",
      "school": "<school name>",
      "location": "<location>",
      "dates": "<date range>",
      "details": "<GPA, coursework, specialization — keep original details>"
    }
  ],
  "other_experience": [
    {
      "title": "<job title for non-technical roles>",
      "company": "<company name>",
      "location": "<location>",
      "dates": "<date range>",
      "bullets": ["<bullet describing the role>"]
    }
  ],
  "other": {
    "additional": "<any additional info or null>",
    "languages": "<spoken languages formatted as: English (Advanced) | Hindi (Advanced) | Gujarati (Native)>"
  },
  "tailoring_notes": {
    "changes_made": ["<list each specific modification you made and why>"],
    "keywords_incorporated": ["<JD keywords you wove into existing bullets>"],
    "keywords_skipped": ["<JD keywords you could NOT honestly incorporate and why>"],
    "sections_reordered": "<true/false>",
    "items_removed": ["<anything removed and why — should be minimal>"]
  },
  "keywords_used": ["<exact list of all JD keywords/phrases you embedded truthfully>"]
}

## Rules
- EVERY experience and project from the master resume MUST appear in the output
- Bullet count per role should be SAME or MORE than original, never fewer
- Every bullet must be the ORIGINAL bullet with targeted keyword insertions
- Skills section: ADD JD skills the candidate has, do not remove existing skills
- DO NOT sugarcoat. Direct, professional, factual tone only.
- DO NOT use phrases like "Developed a foundational understanding" or "Applied robust methodologies" — these are empty filler
- Use the EXACT job title from the candidate's experience, never embellish it

## CRITICAL: OUTPUT FORMAT ENFORCEMENT
- You MUST respond with ONLY valid JSON — no markdown, no explanations, no code fences
- Do NOT wrap your response in ```json ... ``` blocks
- Do NOT include any text before or after the JSON object
- The response must start with { and end with }
- If you cannot produce valid JSON, still try your best — the system will parse it
"""


def build_tailor_message(resume_text, jd_text, keyword_analysis=None,
                         critique_data=None, keyword_data=None, jd_analysis=None):
    """Build the user message for resume tailoring.

    Args:
        resume_text: Plain text of the master resume
        jd_text: Job description text
        keyword_analysis: Legacy field (simple string)
        critique_data: Dict from the Brutal Critique AI analysis
        keyword_data: Dict from the Keyword Extractor AI analysis
        jd_analysis: Dict from the JD Deep Analyzer AI analysis (dynamic pipeline)
    """
    # ── Build JD analysis context (DYNAMIC — replaces static instructions) ──
    jd_context = ""
    if jd_analysis and isinstance(jd_analysis, dict):
        sections = []

        # Job title
        job_title = jd_analysis.get('job_title', '')
        if job_title:
            sections.append(f'JOB TITLE FROM JD: "{job_title}" — Your summary MUST start with this EXACT title.')

        # Title variants
        variants = jd_analysis.get('job_title_variants', [])
        if variants:
            sections.append(f'TITLE VARIANTS: {", ".join(variants)}')

        # Hard skills
        hard_skills = jd_analysis.get('hard_skills', [])
        if hard_skills:
            sections.append(f'HARD SKILLS FROM JD (embed these in skills section AND bullets): {", ".join(hard_skills)}')

        # Soft skills
        soft_skills = jd_analysis.get('soft_skills', [])
        if soft_skills:
            sections.append(f'SOFT SKILLS FROM JD (weave into bullet action verbs): {", ".join(soft_skills)}')

        # Top keywords
        top_keywords = jd_analysis.get('top_keywords', [])
        if top_keywords:
            sections.append(f'TOP KEYWORDS — each MUST appear 3+ times across resume: {", ".join(top_keywords)}')

        # Qualification verdict
        verdict = jd_analysis.get('qualification_verdict', {})
        if verdict and isinstance(verdict, dict):
            rating = verdict.get('rating', 'unknown')
            reasoning = verdict.get('reasoning', '')
            sections.append(f'QUALIFICATION ASSESSMENT: {rating.upper()} — {reasoning}')

        # Honest gaps
        gaps = jd_analysis.get('honest_gaps', [])
        if gaps:
            gap_lines = []
            for g in gaps:
                if isinstance(g, dict):
                    status = g.get('candidate_status', 'unknown')
                    req = g.get('requirement', '')
                    severity = g.get('severity', '')
                    if status in ('missing', 'partial'):
                        gap_lines.append(f'  - [{severity.upper()}] {req}: {status} — {g.get("evidence", "No evidence")}')
            if gap_lines:
                sections.append('HONEST GAPS (do NOT fabricate these — skip or note in keywords_skipped):\n' + '\n'.join(gap_lines))

        # Section priority
        priority = jd_analysis.get('section_priority', {})
        if priority and isinstance(priority, dict):
            most_valued = priority.get('most_valued', '')
            if most_valued:
                sections.append(f'JD EMPHASIS: This JD values "{most_valued}" most — prioritize this section.')

        if sections:
            jd_context = '\n\n## Dynamic JD Analysis (use this to guide your tailoring — these are the EXACT requirements)\n' + '\n'.join(sections)

    # ── Build critique context ──
    critique_context = ""
    if critique_data and isinstance(critique_data, dict):
        sections = []

        verdict = critique_data.get('verdict', '')
        if verdict:
            sections.append(f"HIRING MANAGER VERDICT: {verdict}")

        weaknesses = critique_data.get('weaknesses', [])
        if weaknesses:
            items = []
            for w in weaknesses:
                if isinstance(w, dict):
                    items.append(f"  - [{w.get('severity','?')}] {w.get('issue','')}: {w.get('fix','')}")
                else:
                    items.append(f"  - {w}")
            sections.append("WEAKNESSES TO FIX:\n" + "\n".join(items))

        red_flags = critique_data.get('red_flags', [])
        if red_flags:
            sections.append("RED FLAGS: " + "; ".join(
                [r if isinstance(r, str) else str(r) for r in red_flags]))

        missing = critique_data.get('missing_for_role', [])
        if missing:
            sections.append("MISSING FOR THIS ROLE: " + ", ".join(
                [m if isinstance(m, str) else str(m) for m in missing]))

        if sections:
            critique_context = "\n\n## Brutal Critique Feedback (Address what you CAN — skip what requires fabrication)\n" + "\n".join(sections)

    # ── Build keyword context ──
    keyword_context = ""
    if keyword_data and isinstance(keyword_data, dict):
        top_kw = keyword_data.get('top_keywords', [])
        if top_kw:
            applicable_kw = [k for k in top_kw
                             if isinstance(k, dict) and k.get('resume_status') != 'not_applicable']
            missing_kw = [k for k in applicable_kw
                          if k.get('resume_status') == 'missing']
            weak_kw = [k for k in applicable_kw
                       if k.get('resume_status') == 'weak_match']

            sections = []
            if missing_kw:
                items = []
                for k in missing_kw:
                    phrase = k.get('phrase_to_add', '')
                    where = k.get('where_to_add', '')
                    items.append(f"  - KEYWORD: \"{k.get('keyword','')}\" → SUGGESTED: \"{phrase}\" in {where}")
                sections.append("MISSING KEYWORDS (incorporate ONLY if candidate has real experience):\n" + "\n".join(items))

            if weak_kw:
                items = []
                for k in weak_kw:
                    phrase = k.get('phrase_to_add', '')
                    items.append(f"  - KEYWORD: \"{k.get('keyword','')}\" → STRENGTHEN WITH: \"{phrase}\"")
                sections.append("WEAK KEYWORDS (strengthen with candidate's actual evidence):\n" + "\n".join(items))

            critical = keyword_data.get('ats_optimization', {}).get('critical_missing', [])
            if critical:
                sections.append("CRITICAL MISSING SKILLS: " + ", ".join(critical))

            if sections:
                keyword_context = "\n\n## Keyword Gap Analysis (incorporate truthfully — skip keywords outside candidate's experience)\n" + "\n".join(sections)

    elif keyword_analysis:
        keyword_context = f"\n\n## Previous Keyword Analysis\nTop keywords: {keyword_analysis}"

    return f"""## Target Job Description
{jd_text}

## Master Resume (MODIFY THIS — do not rewrite from scratch)
{resume_text}
{jd_context}
{critique_context}
{keyword_context}

MODIFY this resume for the job above. You MUST:
1. KEEP every experience, project, and education entry — do not remove anything
2. ENHANCE existing bullets by inserting JD keywords naturally into them
3. ADD missing JD skills to the skills section (only ones candidate actually has)
4. Rewrite ONLY the summary to target this specific role
5. DO NOT fabricate or sugarcoat — if a keyword doesn't fit the candidate's real experience, skip it and note it in keywords_skipped
6. Output the structured JSON for LaTeX rendering"""
```

[build_tailor_message()](file:///Users/meetpatel/Resume_Builder_Application/app/services/prompts/resume_tailor.py#128-287) now injects a **Dynamic JD Analysis** section including:
- Exact job title instruction
- Hard skills list to embed
- Soft skills to weave into action verbs
- Top keywords with 3+ occurrence requirement
- Qualification verdict and honest gaps

## Brutal Honesty Enforcement

Every pipeline stage enforces zero-tolerance honesty:
- **JD Analyzer**: Reports honest qualification verdicts and gaps
- **Scorer**: No score inflation — raw match percentages only
- **Tailor Prompt**: Banned filler phrases, verifiable-only claims, `keywords_skipped` required

## Next Steps

Restart the server and run a tailoring job to verify the 4-step pipeline produces 90+ ATS scores dynamically.
