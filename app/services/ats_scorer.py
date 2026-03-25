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
def calculate_ats_score(resume_text, jd_text, keyword_matches=None):
    """Calculate an industry-grade ATS proxy score.

    Modeled after Jobscan, Teal HQ, and Cultivated Culture methodologies.

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
    else:
        # Extract hard skills from JD using curated tech keyword bank
        jd_skills = _extract_hard_skills(jd_text)

        # Match against resume
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
        }

    # ── 2. SOFT SKILLS MATCH (10%) ────────────────────────
    jd_soft = _extract_soft_skills_from_text(jd_text)
    resume_soft = _extract_soft_skills_from_text(resume_text)

    if jd_soft:
        soft_matched = jd_soft & resume_soft
        soft_score = (len(soft_matched) / len(jd_soft)) * 100
        soft_detail = {
            'jd_soft_skills': sorted(jd_soft),
            'matched': sorted(soft_matched),
            'missing': sorted(jd_soft - resume_soft),
        }
    else:
        soft_score = 100  # No soft skills in JD = full marks
        soft_detail = {'jd_soft_skills': [], 'matched': [], 'missing': []}

    # ── 3. JOB TITLE MATCH (15%) ──────────────────────────
    jd_titles = _extract_job_titles(jd_text)
    title_score = 0
    title_detail = {'jd_titles': jd_titles, 'match_found': False}

    if jd_titles:
        for title in jd_titles:
            title_words = set(title.split()) - STOP_WORDS
            if title_words:
                # Partial match: score based on how many words match
                resume_title_words = sum(1 for w in title_words if w in resume_lower)
                match_pct = (resume_title_words / len(title_words)) * 100
                # Boost: if majority of words match, give partial credit above 80
                if resume_title_words >= len(title_words) - 1 and len(title_words) > 1:
                    match_pct = max(match_pct, 85)  # At least 85% for near-full match
                if match_pct > title_score:
                    title_score = match_pct
                    title_detail['match_found'] = match_pct >= 60
        # Floor: always give minimum credit for having a title in the resume
        title_score = max(title_score, 20)
    else:
        # Can't extract title from patterns — try matching key JD words in resume
        jd_words = set(re.findall(r'[a-z]+', jd_lower)) - STOP_WORDS - JD_FILLER
        resume_words_set = set(re.findall(r'[a-z]+', resume_lower))
        overlap = jd_words & resume_words_set
        title_score = min((len(overlap) / max(len(jd_words), 1)) * 130, 90)  # Cap at 90
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
    # Check if important JD terms appear in the resume
    jd_words = re.findall(r'[a-z][a-z+#./\-]+', jd_lower)
    jd_word_counts = Counter(w for w in jd_words
                             if w not in STOP_WORDS and w not in JD_FILLER and len(w) >= 4)

    # Get top 8 most frequent JD terms — smaller set = higher match rate
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
