"""Simulates how different ATS platforms (Greenhouse, Lever, Ashby, Workday) score resumes."""

import re
from app.services.ats_scorer import _word_match


#
# Base Simulator
#

class BaseATSSimulator:
    """Base class for all ATS platform simulators."""

    name = 'Generic ATS'
    description = ''

    def score(self, resume_text, jd_text):
        """Score resume against JD. Override in subclasses."""
        raise NotImplementedError

    def _extract_jd_keywords(self, jd_text):
        """Extract important keywords from a JD using frequency analysis."""
        text = jd_text.lower()
        # Remove common stop words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare',
            'this', 'that', 'these', 'those', 'i', 'you', 'we', 'they', 'he', 'she',
            'it', 'me', 'us', 'them', 'my', 'your', 'our', 'their', 'his', 'her',
            'its', 'who', 'whom', 'which', 'what', 'where', 'when', 'how', 'why',
            'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other', 'some',
            'such', 'no', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very',
            'just', 'about', 'above', 'after', 'again', 'also', 'am', 'as', 'back',
            'from', 'if', 'into', 'like', 'make', 'many', 'much', 'new', 'now',
            'people', 'over', 'out', 'up', 'work', 'working', 'role', 'position',
            'including', 'etc', 'able', 'well', 'within', 'across', 'using',
            'experience', 'years', 'team', 'company', 'join', 'looking', 'based',
            'required', 'preferred', 'strong', 'knowledge', 'understanding',
            'ability', 'skills', 'responsible', 'responsibilities', 'requirements',
            'qualifications', 'benefits', 'apply', 'opportunity', 'environment',
        }

        words = re.findall(r'\b[a-z][a-z+#./-]+\b', text)
        freq = {}
        for w in words:
            if w not in stop_words and len(w) > 2:
                freq[w] = freq.get(w, 0) + 1

        # Also extract multi-word tech terms (e.g., "machine learning", "ci/cd")
        bigrams = re.findall(r'\b([a-z]+(?:[-/.][a-z]+)*)\s+([a-z]+(?:[-/.][a-z]+)*)\b', text)
        for w1, w2 in bigrams:
            bigram = f'{w1} {w2}'
            if w1 not in stop_words and w2 not in stop_words:
                freq[bigram] = freq.get(bigram, 0) + 1

        # Sort by frequency, return top keywords
        sorted_kw = sorted(freq.items(), key=lambda x: (-x[1], x[0]))
        return [kw for kw, count in sorted_kw if count >= 2][:30]

    def _count_sections(self, resume_text):
        """Count standard resume sections found."""
        text_lower = resume_text.lower()
        sections = {
            'summary': ['summary', 'professional summary', 'objective', 'profile', 'about'],
            'experience': ['experience', 'professional experience', 'work experience', 'employment'],
            'education': ['education', 'academic', 'degree'],
            'skills': ['skills', 'technical skills', 'core competencies', 'technologies'],
            'projects': ['projects', 'personal projects', 'academic projects'],
        }
        found = {}
        for section, headers in sections.items():
            for header in headers:
                if header in text_lower:
                    found[section] = True
                    break
        return found

    def _count_metrics(self, resume_text):
        """Count quantifiable metrics in resume."""
        patterns = [
            r'\d+%',           # percentages
            r'\$[\d,.]+',      # dollar amounts
            r'\d+[xX]',       # multipliers
            r'\d{1,3},\d{3}',  # thousands
            r'\d+\+',         # N+ quantities
        ]
        count = 0
        for p in patterns:
            count += len(re.findall(p, resume_text))
        return count


#
# Greenhouse Simulator
#

class GreenhouseSimulator(BaseATSSimulator):
    """Greenhouse -- keyword-heavy, structured parsing, very common in tech."""

    name = 'Greenhouse'
    description = 'Most popular ATS for tech companies. Keyword-dense, structured parsing.'

    def score(self, resume_text, jd_text):
        resume_lower = resume_text.lower()
        jd_keywords = self._extract_jd_keywords(jd_text)
        sections = self._count_sections(resume_text)
        metrics_count = self._count_metrics(resume_text)

        # 1. Keyword Match (40%) — Greenhouse heavily weights keywords
        matched = sum(1 for kw in jd_keywords[:20] if _word_match(kw, resume_lower))
        keyword_score = min((matched / max(len(jd_keywords[:20]), 1)) * 100, 100)

        # 2. Section Structure (20%) — Standard sections expected
        expected = ['summary', 'experience', 'education', 'skills']
        section_count = sum(1 for s in expected if s in sections)
        section_score = (section_count / len(expected)) * 100

        # 3. Contact Completeness (10%)
        contact_score = 0
        if re.search(r'[\w.-]+@[\w.-]+', resume_text): contact_score += 25
        if re.search(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', resume_text): contact_score += 25
        if 'linkedin' in resume_lower: contact_score += 25
        if re.search(r'[a-z]+,\s*[a-z]+', resume_lower): contact_score += 25  # City, State

        # 4. Quantifiable Achievements (15%)
        metrics_score = min(metrics_count * 12, 100)  # ~8+ metrics = 100

        # 5. Format Compliance (15%) — Clean formatting
        format_score = 100
        issues = []
        if len(resume_text) < 300:
            format_score -= 30
            issues.append('Resume is too short — Greenhouse parsers need substance')
        if len(resume_text) > 8000:
            format_score -= 15
            issues.append('Resume may be too long — keep to 1-2 pages')
        if not re.search(r'\b(20\d{2})\b', resume_text):
            format_score -= 20
            issues.append('No dates found — Greenhouse relies on date parsing')
        if '|' in resume_text[:200]:  # Contact line formatting
            format_score += 0  # Pipe-separated is fine

        total = (keyword_score * 0.40 + section_score * 0.20 +
                 contact_score * 0.10 + metrics_score * 0.15 +
                 max(format_score, 0) * 0.15)

        return {
            'platform': self.name,
            'total_score': round(total),
            'breakdown': {
                'keyword_match': round(keyword_score),
                'section_structure': round(section_score),
                'contact_info': round(contact_score),
                'quantifiable_results': round(metrics_score),
                'format_compliance': round(max(format_score, 0)),
            },
            'keywords_matched': matched,
            'keywords_total': len(jd_keywords[:20]),
            'issues': issues,
            'tips': self._get_tips(keyword_score, section_score, metrics_score),
        }

    def _get_tips(self, kw, sect, metrics):
        tips = []
        if kw < 60: tips.append('Add more JD keywords verbatim — Greenhouse matches exact terms')
        if sect < 75: tips.append('Use standard section headings: Summary, Experience, Education, Skills')
        if metrics < 50: tips.append('Add percentages and numbers to 5+ bullet points')
        return tips


#
# Lever Simulator
#

class LeverSimulator(BaseATSSimulator):
    """Lever -- skills-first matching, more flexible on format."""

    name = 'Lever'
    description = 'Skills-first ATS used by mid-to-large tech cos. More flexible parsing.'

    def score(self, resume_text, jd_text):
        resume_lower = resume_text.lower()
        jd_keywords = self._extract_jd_keywords(jd_text)
        sections = self._count_sections(resume_text)
        metrics_count = self._count_metrics(resume_text)

        # 1. Skills Alignment (35%) — Lever emphasizes skill tags
        tech_keywords = [kw for kw in jd_keywords[:25] if len(kw) > 2]
        matched = sum(1 for kw in tech_keywords if _word_match(kw, resume_lower))
        skills_score = min((matched / max(len(tech_keywords), 1)) * 110, 100)

        # 2. Experience Relevance (25%) — Lever looks at role-JD alignment
        exp_score = 0
        # Check if job titles in resume intersect with JD
        jd_title_words = set(re.findall(r'\b[a-z]+\b', jd_text.lower().split('\n')[0]))
        jd_title_words -= {'the', 'a', 'and', 'or', 'at', 'in', 'for', 'we', 'are', 'our', 'is'}
        resume_words = set(re.findall(r'\b[a-z]+\b', resume_lower))
        title_overlap = len(jd_title_words & resume_words) / max(len(jd_title_words), 1)
        exp_score = min(title_overlap * 100, 100)
        # Boost if years match
        jd_years = re.findall(r'(\d+)\+?\s*(?:years|yrs)', jd_text.lower())
        if jd_years:
            resume_years = re.findall(r'(\d+)\+?\s*(?:years|yrs)', resume_lower)
            if resume_years:
                exp_score = min(exp_score + 15, 100)

        # 3. Summary/Headline Quality (15%) — Lever values good summaries
        summary_score = 0
        if 'summary' in sections or 'profile' in resume_lower[:500].lower():
            summary_score += 50
            # Check if summary mentions key JD terms
            summary_text = resume_text[:500].lower()
            summary_kw_hits = sum(1 for kw in jd_keywords[:10] if kw in summary_text)
            summary_score += min(summary_kw_hits * 10, 50)

        # 4. Impact Metrics (15%)
        metrics_score = min(metrics_count * 15, 100)

        # 5. Completeness (10%)
        completeness = 0
        if 'education' in sections: completeness += 30
        if 'experience' in sections: completeness += 30
        if 'skills' in sections: completeness += 20
        if re.search(r'[\w.-]+@[\w.-]+', resume_text): completeness += 20

        issues = []
        if skills_score < 50:
            issues.append('Low skills alignment — Lever tags skills from your resume and matches against JD')
        if summary_score < 30:
            issues.append('Missing or weak summary — Lever uses your summary for candidate preview')

        total = (skills_score * 0.35 + exp_score * 0.25 +
                 summary_score * 0.15 + metrics_score * 0.15 +
                 completeness * 0.10)

        return {
            'platform': self.name,
            'total_score': round(total),
            'breakdown': {
                'skills_alignment': round(skills_score),
                'experience_relevance': round(exp_score),
                'summary_quality': round(summary_score),
                'impact_metrics': round(metrics_score),
                'completeness': round(completeness),
            },
            'keywords_matched': matched,
            'keywords_total': len(tech_keywords),
            'issues': issues,
            'tips': self._get_tips(skills_score, summary_score),
        }

    def _get_tips(self, skills, summary):
        tips = []
        if skills < 60: tips.append('List more technical skills from the JD in your Skills section')
        if summary < 50: tips.append('Add a strong summary with JD keywords in the first 2-3 lines')
        return tips


#
# Ashby Simulator
#

class AshbySimulator(BaseATSSimulator):
    """Ashby -- modern, AI-based matching, popular with startups."""

    name = 'Ashby'
    description = 'Modern ATS for high-growth companies. AI-assisted, content-quality focused.'

    def score(self, resume_text, jd_text):
        resume_lower = resume_text.lower()
        jd_keywords = self._extract_jd_keywords(jd_text)
        sections = self._count_sections(resume_text)
        metrics_count = self._count_metrics(resume_text)

        # 1. Content Relevance (35%) — Ashby uses AI matching
        matched = sum(1 for kw in jd_keywords[:25] if _word_match(kw, resume_lower))
        relevance_score = min((matched / max(len(jd_keywords[:25]), 1)) * 105, 100)

        # 2. Technical Depth (25%) — Quality of experience descriptions
        tech_depth = 0
        bullet_lines = [l.strip() for l in resume_text.split('\n')
                       if l.strip() and len(l.strip()) > 20 and len(l.strip()) < 250]
        if bullet_lines:
            # Check for technical specificity
            tech_patterns = [
                r'\b(?:api|sdk|rest|graphql|microservice|pipeline|deploy)\b',
                r'\b(?:aws|gcp|azure|docker|kubernetes|k8s|terraform)\b',
                r'\b(?:python|java|javascript|typescript|go|rust|c\+\+)\b',
                r'\b(?:sql|nosql|postgres|mongodb|redis|kafka)\b',
                r'\b(?:react|angular|vue|node|django|flask|spring)\b',
            ]
            tech_hits = sum(1 for p in tech_patterns
                          if re.search(p, resume_lower, re.IGNORECASE))
            tech_depth = min(tech_hits * 20, 100)

        # 3. Achievement Orientation (20%) — Metrics and impact
        achievement_score = min(metrics_count * 14, 100)

        # 4. Career Progression (10%)
        progression_score = 0
        dates = re.findall(r'20\d{2}', resume_text)
        if len(dates) >= 4:
            progression_score += 50  # Shows history
        roles = re.findall(r'\b(?:senior|lead|principal|staff|manager|director|intern|junior)\b',
                          resume_lower)
        if len(set(roles)) >= 2:
            progression_score = min(progression_score + 50, 100)

        # 5. Presentation (10%)
        presentation = 80  # Default — Ashby is lenient
        issues = []
        if not sections.get('skills'):
            presentation -= 20
            issues.append('Missing Skills section — Ashby extracts skills for matching')
        if len(resume_text) < 400:
            presentation -= 30
            issues.append('Resume too thin — add more detail for better AI matching')

        total = (relevance_score * 0.35 + tech_depth * 0.25 +
                 achievement_score * 0.20 + progression_score * 0.10 +
                 max(presentation, 0) * 0.10)

        return {
            'platform': self.name,
            'total_score': round(total),
            'breakdown': {
                'content_relevance': round(relevance_score),
                'technical_depth': round(tech_depth),
                'achievement_orientation': round(achievement_score),
                'career_progression': round(progression_score),
                'presentation': round(max(presentation, 0)),
            },
            'keywords_matched': matched,
            'keywords_total': len(jd_keywords[:25]),
            'issues': issues,
            'tips': self._get_tips(relevance_score, tech_depth, achievement_score),
        }

    def _get_tips(self, relevance, depth, achievements):
        tips = []
        if relevance < 60: tips.append('Ashby uses AI matching — mirror JD language naturally')
        if depth < 50: tips.append('Add specific technologies and tools to your bullet points')
        if achievements < 50: tips.append('Quantify impact — Ashby ranks candidates by measurable results')
        return tips


#
# Workday Simulator
#

class WorkdaySimulator(BaseATSSimulator):
    """Workday -- very strict formatting, exact keyword match, enterprise/Fortune 500."""

    name = 'Workday'
    description = 'Enterprise ATS (Fortune 500). Strict formatting, exact keyword matching.'

    def score(self, resume_text, jd_text):
        resume_lower = resume_text.lower()
        jd_keywords = self._extract_jd_keywords(jd_text)
        sections = self._count_sections(resume_text)
        metrics_count = self._count_metrics(resume_text)

        # 1. Exact Keyword Match (45%) — Workday is very literal
        matched = sum(1 for kw in jd_keywords[:20] if _word_match(kw, resume_lower))
        keyword_score = min((matched / max(len(jd_keywords[:20]), 1)) * 100, 100)

        # 2. Format Strictness (20%) — Workday DEMANDS standard structure
        format_score = 0
        issues = []
        # Required sections
        if sections.get('experience'):
            format_score += 25
        else:
            issues.append('CRITICAL: Missing "Experience" section heading — Workday cannot parse')
        if sections.get('education'):
            format_score += 25
        else:
            issues.append('CRITICAL: Missing "Education" section — Workday requires it')
        if sections.get('skills'):
            format_score += 25
        else:
            issues.append('Missing "Skills" section — Workday needs explicit skill listing')

        # Date formatting
        if re.search(r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+20\d{2}', resume_text):
            format_score += 15
        elif re.search(r'20\d{2}', resume_text):
            format_score += 10
        else:
            issues.append('No dates found — Workday requires explicit dates for experience')

        # Contact info
        if re.search(r'[\w.-]+@[\w.-]+', resume_text):
            format_score += 10

        # 3. Minimum Qualifications Check (15%)
        # Extract years-of-experience requirements
        min_qual = 0
        jd_years = re.findall(r'(\d+)\+?\s*(?:years|yrs)', jd_text.lower())
        if jd_years:
            max_req = max(int(y) for y in jd_years)
            resume_years = re.findall(r'20(\d{2})', resume_text)
            if resume_years:
                span = max(int(y) for y in resume_years) - min(int(y) for y in resume_years)
                if span >= max_req:
                    min_qual = 100
                else:
                    min_qual = min((span / max_req) * 100, 100)
        else:
            min_qual = 70  # No explicit year req — default pass

        # 4. Content Density (10%)
        word_count = len(resume_text.split())
        density_score = 100 if 300 <= word_count <= 1200 else max(70, 100 - abs(word_count - 750) // 10)

        # 5. Measurable Results (10%)
        results_score = min(metrics_count * 15, 100)

        total = (keyword_score * 0.45 + format_score * 0.20 +
                 min_qual * 0.15 + density_score * 0.10 +
                 results_score * 0.10)

        return {
            'platform': self.name,
            'total_score': round(total),
            'breakdown': {
                'exact_keyword_match': round(keyword_score),
                'format_compliance': round(format_score),
                'minimum_qualifications': round(min_qual),
                'content_density': round(density_score),
                'measurable_results': round(results_score),
            },
            'keywords_matched': matched,
            'keywords_total': len(jd_keywords[:20]),
            'issues': issues,
            'tips': self._get_tips(keyword_score, format_score),
        }

    def _get_tips(self, kw, fmt):
        tips = []
        if kw < 60: tips.append('Workday matches EXACT keywords — mirror the JD phrasing precisely')
        if fmt < 75: tips.append('Use standard headings: "Experience", "Education", "Skills" — Workday is rigid')
        tips.append('Workday strips formatting — avoid tables, columns, headers/footers')
        return tips


#
# Simulator Registry
#

ALL_SIMULATORS = {
    'greenhouse': GreenhouseSimulator(),
    'lever': LeverSimulator(),
    'ashby': AshbySimulator(),
    'workday': WorkdaySimulator(),
}


def run_all_simulators(resume_text, jd_text):
    """Run all simulators, return combined results with average score."""
    results = {}
    for key, sim in ALL_SIMULATORS.items():
        results[key] = sim.score(resume_text, jd_text)

    scores = [r['total_score'] for r in results.values()]
    avg = round(sum(scores) / len(scores)) if scores else 0
    worst = min(results.items(), key=lambda x: x[1]['total_score']) if results else None

    return {
        'platforms': results,
        'average_score': avg,
        'weakest_platform': worst[0] if worst else None,
        'weakest_score': worst[1]['total_score'] if worst else 0,
        'disclaimer': 'These scores approximate each platform\'s known behavior. '
                      'Actual ATS algorithms are proprietary and may differ.',
    }
