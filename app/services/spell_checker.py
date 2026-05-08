"""Spell/grammar checker using the free LanguageTool API."""

import requests


LANGUAGETOOL_URL = 'https://api.languagetool.org/v2/check'


def check_spelling_grammar(text: str, language: str = 'en-US') -> dict:
    """Run text through LanguageTool and return any errors found."""
    if not text or len(text.strip()) < 10:
        return {'errors': [], 'error_count': 0, 'summary': 'No text to check.'}

    try:
        response = requests.post(
            LANGUAGETOOL_URL,
            data={
                'text': text,
                'language': language,
                'disabledCategories': 'CASING',  # Resumes often have unconventional casing
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        return {
            'errors': [],
            'error_count': 0,
            'summary': f'LanguageTool API unavailable: {str(e)}',
            'api_error': True,
        }

    matches = data.get('matches', [])
    errors = []
    for m in matches:
        replacements = [r.get('value', '') for r in m.get('replacements', [])[:3]]
        errors.append({
            'message': m.get('message', ''),
            'short_message': m.get('shortMessage', ''),
            'offset': m.get('offset', 0),
            'length': m.get('length', 0),
            'context': m.get('context', {}).get('text', ''),
            'context_offset': m.get('context', {}).get('offset', 0),
            'replacements': replacements,
            'rule_id': m.get('rule', {}).get('id', ''),
            'rule_category': m.get('rule', {}).get('category', {}).get('name', ''),
            'type': 'spelling' if 'SPELL' in m.get('rule', {}).get('id', '') else 'grammar',
        })

    spelling_count = sum(1 for e in errors if e['type'] == 'spelling')
    grammar_count = sum(1 for e in errors if e['type'] == 'grammar')

    if not errors:
        summary = '✅ No spelling or grammar errors found!'
    else:
        parts = []
        if spelling_count:
            parts.append(f'{spelling_count} spelling error{"s" if spelling_count != 1 else ""}')
        if grammar_count:
            parts.append(f'{grammar_count} grammar issue{"s" if grammar_count != 1 else ""}')
        summary = f'Found {" and ".join(parts)}.'

    return {
        'errors': errors,
        'error_count': len(errors),
        'spelling_errors': spelling_count,
        'grammar_errors': grammar_count,
        'summary': summary,
    }
