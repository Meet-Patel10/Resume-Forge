def parse_date_string(date_str):
    """Parse 'Jan 2022' to (month, year)"""
    months = {m.lower(): i for i, m in enumerate(['jan', 'feb', 'mar', 'apr', 'may', 'jun',
                                                   'jul', 'aug', 'sep', 'oct', 'nov', 'dec'], 1)}
    parts = date_str.strip().split()
    month = months.get(parts[0].lower(), 1)
    year = int(parts[1]) if len(parts) > 1 else 2024
    return month, year


def extract_gap_explanation(cover_letter_text, from_company, to_company):
    """Check if cover letter explains the gap"""
    # Look for keywords like "took time", "pursued education", "sabbatical"
    gap_keywords = ['took time', 'pursued education', 'sabbatical', 'hiatus', 'health',
                   'travel', 'startup', 'freelance', 'consulting', 'academic']

    for keyword in gap_keywords:
        if keyword in cover_letter_text.lower():
            return keyword

    return None


def analyze_employment_timeline(resume_json, cover_letter_text):
    """
    Analyze employment timeline for:
    - Gaps >6 months
    - Overlapping dates
    - Logical progression
    - Frequent job changes (red flag)
    """
    issues = []

    experiences = resume_json.get('experience', [])
    if not experiences:
        return {'status': 'NO_DATA', 'issues': [], 'timeline_coherent': True, 'total_jobs': 0, 'span_years': 0}

    # Parse dates
    parsed_exps = []
    for exp in experiences:
        dates_str = exp.get('dates', '')
        if not dates_str or ' – ' not in dates_str:
            continue

        try:
            start_str, end_str = dates_str.split(' – ')
            # Parse "Jan 2022" → (month, year)
            start_month, start_year = parse_date_string(start_str)
            end_month, end_year = parse_date_string(end_str)

            parsed_exps.append({
                'company': exp.get('company', 'Unknown'),
                'title': exp.get('title', 'Unknown'),
                'start': (start_year, start_month),
                'end': (end_year, end_month),
                'dates_str': dates_str
            })
        except Exception as e:
            print(f"[timeline] failed to parse dates: {dates_str}")
            continue

    if not parsed_exps:
        return {'status': 'UNPARSEABLE', 'issues': [], 'timeline_coherent': True, 'total_jobs': 0, 'span_years': 0}

    # Sort by start date
    parsed_exps.sort(key=lambda x: x['start'])

    # Check 1: Gaps between jobs
    for i in range(len(parsed_exps) - 1):
        current_end = parsed_exps[i]['end']
        next_start = parsed_exps[i + 1]['start']

        # Calculate months between
        months_between = (next_start[0] - current_end[0]) * 12 + (next_start[1] - current_end[1])

        if months_between > 6:
            gap_explanation = extract_gap_explanation(cover_letter_text or '',
                                                     parsed_exps[i]['company'],
                                                     parsed_exps[i + 1]['company'])

            if not gap_explanation:
                issues.append({
                    'severity': 'CRITICAL',
                    'type': 'UNEXPLAINED_GAP',
                    'gap_months': months_between,
                    'between': f"{parsed_exps[i]['company']} and {parsed_exps[i + 1]['company']}",
                    'message': f"{months_between}-month gap between jobs with no explanation in cover letter",
                    'recommendation': 'Add gap explanation to cover letter (sabbatical, education, health, etc.)'
                })
            else:
                print(f"[timeline] gap explained: {gap_explanation}")

    # Check 2: Job hopping (3+ jobs in 5 years)
    if len(parsed_exps) >= 3:
        recent_jobs = [e for e in parsed_exps if e['end'][0] >= 2021]  # Last 5 years
        if len(recent_jobs) >= 3:
            issues.append({
                'severity': 'MEDIUM',
                'type': 'JOB_HOPPING',
                'count': len(recent_jobs),
                'message': f"{len(recent_jobs)} jobs in ~5 years - recruiters might see as instability",
                'recommendation': 'Highlight growth/promotions or have explanation ready for interviews'
            })

    # Check 3: Overlapping dates
    for i in range(len(parsed_exps) - 1):
        if parsed_exps[i]['end'] > parsed_exps[i + 1]['start']:
            issues.append({
                'severity': 'HIGH',
                'type': 'OVERLAPPING_DATES',
                'jobs': [parsed_exps[i]['company'], parsed_exps[i + 1]['company']],
                'message': f"Overlapping employment dates detected",
                'recommendation': f'Fix dates: {parsed_exps[i]["dates_str"]} overlaps with {parsed_exps[i + 1]["dates_str"]}'
            })

    return {
        'status': 'PASS' if len(issues) == 0 else 'FAIL',
        'timeline_coherent': len(issues) == 0,
        'issues': issues,
        'total_jobs': len(parsed_exps),
        'span_years': parsed_exps[-1]['end'][0] - parsed_exps[0]['start'][0] if parsed_exps else 0
    }
