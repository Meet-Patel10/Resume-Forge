"""ATS resume scorer -- scores resumes against job descriptions on keyword match, sections, metrics, etc."""

import re
from collections import Counter


#
#  Word-boundary matching for accurate skill detection
#

# Skills with special characters that need exact (escaped) regex
_SPECIAL_SKILLS = {'c++', 'c#', '.net', 'ci/cd', 'node.js', 'vue.js', 'react.js',
                   'express.js', 'next.js', 'nuxt.js', 'three.js', 'd3.js',
                   'asp.net', 'ado.net', 'vb.net'}


def _word_match(term: str, text: str) -> bool:
    """Check if `term` appears in `text` as a whole word.

    Prevents false positives like:
      - 'java' matching 'javascript'
      - 'go' matching 'google'
      - 'r' matching every word containing 'r'
      - 'c' matching 'cloud'

    Special handling for terms with non-alphanumeric chars (c++, c#, .net, ci/cd).
    Also handles synonyms: 'continuous integration' matches if 'ci/cd' is present.
    """
    term = term.strip().lower()
    text = text.lower()

    if not term:
        return False

    # Check the term directly first
    if _direct_match(term, text):
        return True

    # Check synonyms — if the JD says "continuous integration" but resume says "CI/CD"
    synonyms = _SKILL_SYNONYMS.get(term)
    if synonyms:
        for alt in synonyms:
            if _direct_match(alt, text):
                return True

    return False


# Synonym map: JD term → list of equivalent terms that should also count as a match
_SKILL_SYNONYMS = {
    'continuous integration': ['ci/cd', 'ci cd', 'cicd'],
    'continuous deployment': ['ci/cd', 'ci cd', 'cicd'],
    'continuous delivery': ['ci/cd', 'ci cd', 'cicd'],
    'ci/cd': ['continuous integration', 'continuous deployment'],
    'source control': ['git', 'version control', 'github', 'gitlab', 'bitbucket'],
    'version control': ['git', 'source control', 'github', 'gitlab', 'bitbucket'],
    'nosql databases': ['nosql', 'mongodb', 'dynamodb', 'cassandra', 'redis', 'couchdb'],
    'nosql': ['mongodb', 'dynamodb', 'cassandra', 'redis'],
    'relational databases': ['sql', 'mysql', 'postgresql', 'postgres', 'oracle', 'sql server'],
    'rdbms': ['sql', 'mysql', 'postgresql', 'postgres', 'oracle'],
    'microsoft sql server': ['sql server', 'mssql', 'sql'],
    'containers': ['docker', 'containerization', 'kubernetes'],
    'containerization': ['docker', 'containers', 'kubernetes'],
    'container orchestration': ['kubernetes', 'k8s', 'docker swarm'],
    'object-oriented programming': ['oop', 'object oriented'],
    'object oriented programming': ['oop', 'object-oriented'],
    'oop': ['object-oriented', 'object oriented programming'],
    'machine learning': ['ml', 'deep learning', 'neural network'],
    'artificial intelligence': ['ai', 'machine learning', 'deep learning'],
    'data structures and algorithms': ['data structures', 'algorithms', 'dsa'],
    'data structures': ['data structures and algorithms', 'dsa'],
    'algorithms': ['data structures and algorithms', 'dsa'],
    'rest apis': ['restful apis', 'restful', 'rest api', 'apis'],
    'restful apis': ['rest apis', 'restful', 'rest api'],
    'web services': ['rest apis', 'restful apis', 'api'],
    'cloud computing': ['aws', 'azure', 'gcp', 'cloud'],
    'cloud': ['aws', 'azure', 'gcp', 'cloud computing'],
    'amazon web services': ['aws'],
    'aws': ['amazon web services'],
    'unit testing': ['junit', 'pytest', 'testing', 'test'],
    'testing': ['unit testing', 'test', 'junit', 'pytest'],
    'agile': ['agile/scrum', 'scrum', 'agile methodology', 'agile development'],
    'scrum': ['agile', 'agile/scrum', 'agile methodology'],
    'agile methodologies': ['agile', 'scrum', 'agile/scrum'],
    'etl': ['elt', 'data pipeline', 'data integration'],
    'elt': ['etl', 'data pipeline', 'data integration'],
    'data pipeline': ['etl', 'elt', 'pipeline'],
    'infrastructure as code': ['terraform', 'iac', 'cloudformation'],
    'iac': ['terraform', 'infrastructure as code'],
    'devops': ['ci/cd', 'docker', 'kubernetes', 'jenkins'],
    'linux/unix': ['linux', 'unix', 'bash'],
    'scripting': ['bash', 'python', 'shell'],
}


def _direct_match(term: str, text: str) -> bool:
    """Check if term directly appears in text as a whole word."""
    # Special-character skills: use escaped literal match
    if term in _SPECIAL_SKILLS:
        pattern = r'(?:^|[\s,;|/\(])' + re.escape(term) + r'(?:$|[\s,;|/\)])'
        return bool(re.search(pattern, text))

    # Multi-word terms (e.g., 'machine learning'): match as exact phrase with boundaries
    if ' ' in term:
        pattern = r'\b' + re.escape(term) + r'\b'
        return bool(re.search(pattern, text))

    # Standard single-word terms: word-boundary match
    pattern = r'\b' + re.escape(term) + r'\b'
    return bool(re.search(pattern, text))


def _word_count(term: str, text: str) -> int:
    """Count how many times `term` appears in `text` as whole words."""
    term = term.strip().lower()
    text = text.lower()

    if not term:
        return 0

    if term in _SPECIAL_SKILLS:
        pattern = r'(?:^|[\s,;|/\(])' + re.escape(term) + r'(?:$|[\s,;|/\)])'
        return len(re.findall(pattern, text))

    pattern = r'\b' + re.escape(term) + r'\b'
    return len(re.findall(pattern, text))


#
#  Common word lists for filtering
#
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


#
#  Keyword extraction helpers
#
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

    # Curated bank of known tech skills
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


#
#  Main scoring function
#
def calculate_ats_score(resume_text, jd_text, keyword_matches=None, jd_analysis=None):
    """Score a resume against a JD. Returns breakdown dict with total_score."""
    resume_lower = _normalize(resume_text)
    jd_lower = _normalize(jd_text)

    # 1. HARD SKILLS MATCH (35%)
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
            if _word_match(term, resume_lower):
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
        print(f"[ats_scorer] hard skills: {len(matched)}/{total} matched ({hard_skill_score:.0f}%)")
        if missing:
            print(f"[ats_scorer] MISSING hard skills: {missing[:20]}")
    else:
        # STATIC FALLBACK: Extract hard skills from JD using curated tech keyword bank
        jd_skills = _extract_hard_skills(jd_text)
        matched = []
        missing = []
        for term in sorted(jd_skills):
            if _word_match(term, resume_lower):
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

    # 2. SOFT SKILLS MATCH (10%)
    if jd_analysis and jd_analysis.get('soft_skills'):
        # DYNAMIC PATH: Use AI-extracted soft skills from this specific JD
        # Uses stem-based matching to catch verb/adjective forms
        # e.g., "collaboration" matches "collaborated", "collaborative", "collaborating"
        jd_soft_list = set(s.lower().strip() for s in jd_analysis['soft_skills'])
        soft_matched = set()
        soft_missing = set()

        def _soft_skill_found(skill, text):
            """Check if a soft skill or any of its common forms appear in text."""
            # Direct match (word boundary)
            if _word_match(skill, text):
                return True
            # Stem-based matching: extract the root and check common suffixes
            # This catches: collaboration → collaborat(ed/ing/ive/ion)
            stem_map = {
                'collaboration': ['collaborat', 'collabor'],
                'communication': ['communicat', 'communic'],
                'leadership': ['leader', 'lead', 'led'],
                'teamwork': ['team', 'teamwork'],
                'problem-solving': ['problem', 'solving', 'troubleshoot'],
                'problem solving': ['problem', 'solving', 'troubleshoot'],
                'analytical': ['analyz', 'analyt', 'analysis'],
                'adaptability': ['adapt'],
                'innovation': ['innovat'],
                'creativity': ['creat', 'innovat'],
                'mentoring': ['mentor'],
                'coaching': ['coach'],
                'negotiation': ['negotiat'],
                'presentation': ['present'],
                'organizational': ['organiz'],
                'time management': ['prioritiz', 'time manage', 'deadline'],
                'cross-functional': ['cross-functional', 'cross functional', 'cross-team'],
                'detail-oriented': ['detail', 'attention to detail', 'meticulous'],
                'self-starter': ['self-starter', 'self starter', 'independently', 'proactiv'],
                'motivated': ['motivat', 'driven', 'passion'],
                'proactive': ['proactiv', 'initiative'],
                'independently': ['independen', 'autonomous', 'self-direct'],
                'willingness': ['willing', 'eager'],
                'aptitude': ['aptitude', 'proficien', 'adept'],
                'fast learner': ['fast learn', 'quick learn', 'rapid learn'],
                'results-driven': ['results-driven', 'result-driven', 'results driven'],
            }
            # Check predefined stems with word-boundary awareness
            if skill in stem_map:
                for stem in stem_map[skill]:
                    # Require the stem to appear at a word boundary, not inside unrelated words
                    if re.search(r'\b' + re.escape(stem), text):
                        return True
                return False
            # Generic stem matching: require 5+ char stems with word boundary
            words = skill.replace('-', ' ').split()
            for word in words:
                if len(word) >= 5:
                    stem = word[:min(len(word) - 1, 7)]
                    if re.search(r'\b' + re.escape(stem), text):
                        return True
                elif len(word) >= 4 and _word_match(word, text):
                    return True
            return False

        for skill in jd_soft_list:
            if _soft_skill_found(skill, resume_lower):
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

    # 3. JOB TITLE MATCH (15%)
    # Strategy: exact phrase match → high score, individual word overlap → capped lower score
    def _score_title(title_text, resume):
        """Score a title: exact phrase = 100, close match = 85, word overlap capped at 70."""
        title_norm = _normalize(title_text)
        # Check exact phrase first — this is what real ATS systems do
        if title_norm in resume:
            return 100
        # Check if all meaningful words present (close match)
        title_words = [w for w in title_norm.split() if w not in STOP_WORDS and len(w) >= 2]
        if not title_words:
            return 0
        matched_words = sum(1 for w in title_words if _word_match(w, resume))
        if matched_words == len(title_words):
            return 90  # All words present but not as exact phrase
        if matched_words >= len(title_words) - 1 and len(title_words) > 2:
            return 75  # Off by one word in a multi-word title
        # Partial word match — cap at 70 to prevent "developer" in any resume from inflating
        return min((matched_words / len(title_words)) * 100, 70)

    if jd_analysis and jd_analysis.get('job_title'):
        ai_title = jd_analysis['job_title']
        title_score = _score_title(ai_title, resume_lower)
        title_detail = {'jd_titles': [ai_title], 'match_found': title_score >= 60, 'source': 'dynamic_jd_analysis'}

        # Also check variants if provided
        for variant in jd_analysis.get('job_title_variants', []):
            v_score = _score_title(variant, resume_lower)
            if v_score > title_score:
                title_score = v_score
                title_detail['match_found'] = v_score >= 60

        title_score = max(title_score, 15)  # Minimum floor
    else:
        # STATIC FALLBACK
        jd_titles = _extract_job_titles(jd_text)
        title_score = 0
        title_detail = {'jd_titles': jd_titles, 'match_found': False, 'source': 'static_regex'}

        if jd_titles:
            for title in jd_titles:
                t_score = _score_title(title, resume_lower)
                if t_score > title_score:
                    title_score = t_score
                    title_detail['match_found'] = t_score >= 60
            title_score = max(title_score, 15)
        else:
            jd_words = set(re.findall(r'[a-z]+', jd_lower)) - STOP_WORDS - JD_FILLER
            resume_words_set = set(re.findall(r'[a-z]+', resume_lower))
            overlap = jd_words & resume_words_set
            title_score = min((len(overlap) / max(len(jd_words), 1)) * 100, 70)
            title_detail['note'] = 'Inferred from JD word overlap'

    # 4. SECTION COMPLETENESS (10%)
    required_sections = {
        'summary': ['summary', 'objective', 'profile', 'professional summary',
                     'career summary', 'career objective', 'about me',
                     'personal statement', 'career profile', 'executive summary'],
        'experience': ['experience', 'work history', 'employment',
                       'professional experience', 'work experience',
                       'career history', 'relevant experience', 'employment history'],
        'education': ['education', 'academic', 'degree', 'university',
                      'academic background', 'academic qualifications'],
        'skills': ['skills', 'technical skills', 'competencies', 'technologies',
                   'core competencies', 'areas of expertise', 'proficiencies',
                   'technical proficiencies', 'technical competencies', 'tools'],
    }
    optional_sections = {
        'projects': ['projects', 'portfolio', 'personal projects',
                     'academic projects', 'side projects', 'key projects'],
        'certifications': ['certifications', 'certificates', 'licenses',
                           'professional certifications', 'training',
                           'professional development'],
        'languages': ['languages', 'language proficiency'],
    }

    sections_found = {}
    for section_name, variants in required_sections.items():
        sections_found[section_name] = any(v in resume_lower for v in variants)

    required_count = sum(1 for v in sections_found.values() if v)
    section_score = (required_count / len(required_sections)) * 100

    # Bonus for optional sections (up to 15% extra, capped at 100)
    optional_found = sum(1 for variants in optional_sections.values()
                         if any(v in resume_lower for v in variants))
    section_score = min(section_score + (optional_found * 5), 100)

    section_detail = {
        'required': sections_found,
        'required_found': required_count,
        'optional_found': optional_found,
    }

    # 5. MEASURABLE RESULTS (10%)
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

    # 6. KEYWORD FREQUENCY (10%)
    if jd_analysis and jd_analysis.get('top_keywords'):
        # DYNAMIC PATH: Use AI-identified top keywords
        # Use full-text substring matching for both single and multi-word terms
        top_jd_terms = [k.lower().strip() for k in jd_analysis['top_keywords']]

        freq_matched = 0
        freq_details = []
        for term in top_jd_terms:
            # Primary: full word-boundary match in resume text
            found_count = _word_count(term, resume_lower)
            # Secondary: for multi-word terms, check if all words appear
            if found_count == 0 and ' ' in term:
                term_words = term.split()
                if all(_word_match(w, resume_lower) for w in term_words if len(w) >= 3):
                    found_count = 1  # credit for having all component words
            # Tertiary: for hyphenated or slash terms, check variants
            if found_count == 0:
                variants = [term.replace('-', ' '), term.replace('/', ' '), term.replace('.', '')]
                for v in variants:
                    if v != term and _word_match(v, resume_lower):
                        found_count = 1
                        break
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

    # 7. RESUME LENGTH & FORMAT (10%)
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

    #
    #  WEIGHTED TOTAL
    #
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
        verdict = 'Excellent match — resume strongly aligns with the job description'
    elif total_score >= 75:
        grade = 'A'
        verdict = 'Strong match — resume aligns well with most job requirements'
    elif total_score >= 65:
        grade = 'B'
        verdict = 'Good match — resume covers many requirements but has room for improvement'
    elif total_score >= 50:
        grade = 'C'
        verdict = 'Fair match — resume needs keyword optimization to better align'
    elif total_score >= 35:
        grade = 'D'
        verdict = 'Weak match — significant keyword gaps between resume and job description'
    else:
        grade = 'F'
        verdict = 'Poor match — resume needs major rework to align with this job description'

    return {
        'total_score': total_score,
        'grade': grade,
        'verdict': verdict,
        'disclaimer': 'This Resume Match Score estimates keyword alignment between your resume and the job description. It is not a simulation of any specific ATS platform. For actual ATS compatibility testing, cross-check with tools like Jobscan.',
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

# IT Role-Specific Keyword Banks
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
    'product_manager': {
        'label': 'Product Management',
        'must_have': [
            'product management', 'roadmap', 'product strategy', 'user stories',
            'agile', 'scrum', 'kanban', 'jira', 'confluence',
            'stakeholder management', 'requirements', 'prioritization',
            'a/b testing', 'analytics', 'kpi', 'okr',
            'user research', 'customer discovery', 'market analysis',
            'wireframe', 'prototype', 'figma', 'miro',
            'cross-functional', 'go-to-market', 'mvp',
        ],
        'nice_to_have': [
            'sql', 'python', 'data analysis', 'tableau', 'amplitude',
            'mixpanel', 'segment', 'product-led growth', 'saas',
            'api', 'technical product management', 'platform',
            'pricing', 'monetization', 'competitive analysis',
        ],
    },
    'marketing': {
        'label': 'Marketing / Digital Marketing',
        'must_have': [
            'marketing strategy', 'digital marketing', 'content marketing',
            'seo', 'sem', 'ppc', 'google ads', 'facebook ads',
            'social media', 'email marketing', 'campaign management',
            'analytics', 'google analytics', 'kpi', 'roi',
            'brand management', 'content creation', 'copywriting',
            'crm', 'hubspot', 'salesforce', 'mailchimp',
            'a/b testing', 'conversion optimization',
        ],
        'nice_to_have': [
            'marketing automation', 'lead generation', 'funnel',
            'influencer marketing', 'pr', 'video marketing',
            'adobe creative suite', 'canva', 'figma',
            'sql', 'python', 'tableau', 'data visualization',
        ],
    },
    'finance_analyst': {
        'label': 'Finance / Financial Analysis',
        'must_have': [
            'financial analysis', 'financial modeling', 'excel',
            'sql', 'python', 'tableau', 'power bi',
            'budgeting', 'forecasting', 'variance analysis',
            'accounting', 'gaap', 'ifrs', 'financial reporting',
            'valuation', 'dcf', 'cash flow', 'p&l',
            'risk management', 'compliance', 'audit',
            'erp', 'sap', 'oracle',
        ],
        'nice_to_have': [
            'cfa', 'cpa', 'fpa', 'treasury',
            'bloomberg', 'capital iq', 'factset',
            'mergers', 'acquisitions', 'due diligence',
            'derivatives', 'fixed income', 'portfolio management',
        ],
    },
    'cybersecurity': {
        'label': 'Cybersecurity / Information Security',
        'must_have': [
            'security', 'cybersecurity', 'information security',
            'vulnerability assessment', 'penetration testing', 'incident response',
            'siem', 'splunk', 'ids', 'ips', 'firewall',
            'encryption', 'ssl/tls', 'pki', 'authentication',
            'compliance', 'soc 2', 'iso 27001', 'nist', 'gdpr',
            'network security', 'endpoint security', 'cloud security',
            'linux', 'windows', 'tcp/ip', 'dns',
            'python', 'bash', 'scripting', 'automation',
        ],
        'nice_to_have': [
            'oscp', 'cissp', 'ceh', 'security+',
            'threat intelligence', 'malware analysis', 'forensics',
            'devsecops', 'container security', 'zero trust',
            'aws security', 'azure security', 'gcp security',
            'owasp', 'burp suite', 'nmap', 'wireshark',
        ],
    },
}

# Strong action verbs (Resume Worded / VMock methodology)
# Expanded set: includes past tense, present tense, and gerund forms
STRONG_ACTION_VERBS = {
    # Core development
    'developed', 'develop', 'developing', 'implemented', 'implement', 'implementing',
    'designed', 'design', 'designing', 'built', 'build', 'building',
    'created', 'create', 'creating', 'engineered', 'engineer', 'engineering',
    'architected', 'architect', 'architecting',
    # Optimization
    'optimized', 'optimize', 'optimizing', 'automated', 'automate', 'automating',
    'deployed', 'deploy', 'deploying', 'integrated', 'integrate', 'integrating',
    # Leadership
    'led', 'lead', 'leading', 'managed', 'manage', 'managing',
    'directed', 'direct', 'directing', 'spearheaded', 'spearhead', 'spearheading',
    'orchestrated', 'orchestrate', 'orchestrating', 'drove', 'drive', 'driving',
    # Impact
    'reduced', 'reduce', 'reducing', 'increased', 'increase', 'increasing',
    'improved', 'improve', 'improving', 'accelerated', 'accelerate', 'accelerating',
    'streamlined', 'streamline', 'streamlining',
    # Analysis
    'analyzed', 'analyze', 'analyzing', 'researched', 'research', 'researching',
    'evaluated', 'evaluate', 'evaluating', 'identified', 'identify', 'identifying',
    'diagnosed', 'diagnose', 'diagnosing',
    # Infrastructure
    'migrated', 'migrate', 'migrating', 'refactored', 'refactor', 'refactoring',
    'scaled', 'scale', 'scaling', 'configured', 'configure', 'configuring',
    'provisioned', 'provision', 'provisioning',
    # Delivery
    'launched', 'launch', 'launching', 'delivered', 'deliver', 'delivering',
    'shipped', 'ship', 'shipping', 'released', 'release', 'releasing',
    'published', 'publish', 'publishing',
    # Collaboration
    'mentored', 'mentor', 'mentoring', 'trained', 'train', 'training',
    'collaborated', 'collaborate', 'collaborating',
    'coordinated', 'coordinate', 'coordinating',
    'facilitated', 'facilitate', 'facilitating',
    # Transformation
    'established', 'establish', 'establishing',
    'pioneered', 'pioneer', 'pioneering',
    'transformed', 'transform', 'transforming',
    'revamped', 'revamp', 'revamping',
    'modernized', 'modernize', 'modernizing',
    # Additional strong verbs commonly used in resumes
    'achieved', 'achieve', 'achieving', 'executed', 'execute', 'executing',
    'resolved', 'resolve', 'resolving', 'eliminated', 'eliminate', 'eliminating',
    'generated', 'generate', 'generating', 'consolidated', 'consolidate',
    'negotiated', 'negotiate', 'negotiating', 'secured', 'secure', 'securing',
    'constructed', 'construct', 'constructing', 'devised', 'devise', 'devising',
    'formulated', 'formulate', 'formulating', 'initiated', 'initiate', 'initiating',
    'maintained', 'maintain', 'maintaining', 'translated', 'translate',
    'communicated', 'communicate', 'communicating',
    'presented', 'present', 'presenting',
    'programmed', 'program', 'programming',
    'tested', 'test', 'testing', 'debugged', 'debug', 'debugging',
    'documented', 'document', 'documenting',
    'monitored', 'monitor', 'monitoring',
    'authored', 'author', 'authoring',
    'overhauled', 'overhaul', 'overhauling',
    'standardized', 'standardize', 'standardizing',
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
    """Auto-detect the most likely IT role family from resume content.

    Uses word-boundary matching (_word_match) to prevent false positives
    like 'react' matching 'reactive' or 'go' matching 'google'.
    """
    text_lower = resume_text.lower()
    scores = {}
    for role_key, role_data in IT_ROLE_KEYWORDS.items():
        score = sum(1 for kw in role_data['must_have'] if _word_match(kw, text_lower))
        scores[role_key] = score

    best = max(scores, key=scores.get)
    return best, scores


def calculate_general_health_score(resume_text):
    """Score a resume without a JD -- checks structure, verbs, metrics, skills, etc."""
    text = resume_text
    text_lower = text.lower()
    lines = text.strip().split('\n')
    words = text.split()
    word_count = len(words)

    # Detect the best-fit IT role
    detected_role, role_scores = _detect_role(text)
    role_data = IT_ROLE_KEYWORDS[detected_role]

    # 1. PARSABILITY (15%)
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

    # 1b. DATE FORMAT CONSISTENCY
    # Detect mixed date formats and flag as issue
    date_formats = {
        'month_year_long': len(re.findall(r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b', text)),
        'month_year_short': len(re.findall(r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}\b', text)),
        'mm_slash_yyyy': len(re.findall(r'\b\d{1,2}/\d{4}\b', text)),
        'yyyy_mm_dash': len(re.findall(r'\b\d{4}-\d{2}\b', text)),
        'mm_dash_yyyy': len(re.findall(r'\b\d{2}-\d{4}\b', text)),
    }
    formats_used = {k: v for k, v in date_formats.items() if v > 0}

    if len(formats_used) > 1:
        format_names = {
            'month_year_long': 'January 2024',
            'month_year_short': 'Jan 2024',
            'mm_slash_yyyy': '01/2024',
            'yyyy_mm_dash': '2024-01',
            'mm_dash_yyyy': '01-2024',
        }
        examples = [f'{format_names[k]} (×{v})' for k, v in formats_used.items()]
        parse_issues.append(f'Mixed date formats detected: {", ".join(examples)} — use one consistent format')
        parse_score = max(parse_score - 10, 0)

    # 1c. CHRONOLOGICAL ORDER CHECK
    # Extract date ranges associated with experience entries and check for reverse-chronological order
    month_map = {
        'jan': 1, 'january': 1, 'feb': 2, 'february': 2, 'mar': 3, 'march': 3,
        'apr': 4, 'april': 4, 'may': 5, 'jun': 6, 'june': 6,
        'jul': 7, 'july': 7, 'aug': 8, 'august': 8, 'sep': 9, 'september': 9,
        'oct': 10, 'october': 10, 'nov': 11, 'november': 11, 'dec': 12, 'december': 12,
    }
    # Match patterns like "Jan 2023", "January 2023", "01/2023"
    date_entries = re.findall(
        r'(?:(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{4}))',
        text
    )
    # Also capture "MM/YYYY" format
    date_entries_numeric = re.findall(r'\b(\d{1,2})/(\d{4})\b', text)

    # Build a list of years from experience dates (approximate check)
    experience_years = [int(y) for y in date_entries]
    experience_years.extend([int(y) for _, y in date_entries_numeric])

    if len(experience_years) >= 4:
        # Check pairs: in reverse-chronological, years should generally decrease
        # We check start dates of entries (every other date is typically a start date)
        start_years = experience_years[::2]  # Approximate: even indices
        if len(start_years) >= 2:
            inversions = sum(1 for i in range(len(start_years) - 1)
                             if start_years[i] < start_years[i + 1])
            if inversions > 0:
                parse_issues.append(
                    'Experience entries may not be in reverse-chronological order — '
                    'most recent role should appear first'
                )
                parse_score = max(parse_score - 10, 0)


    # 2. STRUCTURE & SECTIONS (15%)
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

    # 3. ACTION VERBS (15%)
    # Detect bullet lines: explicit markers, indented lines, or short capitalized lines
    bullet_lines = [l.strip() for l in lines if l.strip().startswith(('•', '-', '–', '*', '▪'))]
    # Also catch indented lines (common in parsed resumes: "  Built REST APIs...")
    for l in lines:
        stripped = l.strip()
        cleaned = stripped.lstrip('•-–*▪ \t')
        if (stripped not in bullet_lines
                and len(cleaned) > 20 and len(cleaned) < 250
                and cleaned and cleaned[0].isupper()
                and (l.startswith('  ') or l.startswith('\t'))):
            bullet_lines.append(stripped)
    # Fallback: lines that look like accomplishment bullets (20-200 chars, start upper)
    if not bullet_lines:
        bullet_lines = [l.strip() for l in lines
                        if len(l.strip()) > 20 and len(l.strip()) < 200
                        and l.strip()[0].isupper()]

    total_bullets = max(len(bullet_lines), 1)
    strong_verb_count = 0
    weak_phrase_count = 0
    weak_found = []

    for bullet in bullet_lines:
        bullet_lower = bullet.lower().lstrip('•-–*▪ \t')
        words = bullet_lower.split()
        if not words:
            continue
        # Check the first word AND the second word (handles "Successfully deployed...")
        found_strong = False
        for word in words[:2]:
            # Strip trailing punctuation/commas
            clean_word = word.rstrip('.,;:')
            if clean_word in STRONG_ACTION_VERBS:
                found_strong = True
                break
        if found_strong:
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

    # 4. MEASURABLE IMPACT (15%)
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

    # 5. IT SKILLS COVERAGE (20%)
    must_found = [kw for kw in role_data['must_have'] if _word_match(kw, text_lower)]
    nice_found = [kw for kw in role_data['nice_to_have'] if _word_match(kw, text_lower)]
    must_missing = [kw for kw in role_data['must_have'] if not _word_match(kw, text_lower)]

    must_ratio = len(must_found) / max(len(role_data['must_have']), 1)
    nice_ratio = len(nice_found) / max(len(role_data['nice_to_have']), 1)

    # Weighted: must_have is 70% of this score, nice_to_have is 30%
    skills_score = (must_ratio * 70) + (nice_ratio * 30)
    skills_score = min(skills_score, 100)

    # Also check across all role families
    all_roles_detail = {}
    for rk, rd in IT_ROLE_KEYWORDS.items():
        found = sum(1 for kw in rd['must_have'] if _word_match(kw, text_lower))
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

    # 6. LENGTH & MECHANICS (10%)
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

    # 7. CONTACT INFO (10%)
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

    disclaimer = 'This Health Score evaluates general resume quality for IT roles. It does not simulate any specific ATS platform.'

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
        'disclaimer': disclaimer,
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
