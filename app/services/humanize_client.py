"""
Calls the HumanizeAI Pro API to clean up AI-generated text.
Needs HUMANIZE_API_KEY in .env -- get one at https://thehumanizeai.pro
"""

import os
import requests


API_URL = "https://thehumanizeai.pro/api/v1/humanize"


def humanize_text(text, model="humanoidx", tone="formal"):
    """Run text through the humanizer API. Returns original text if anything goes wrong."""
    api_key = os.environ.get('HUMANIZE_API_KEY', '').strip()

    if not api_key:
        print("[humanize] no API key set, skipping")
        return text

    if not text or not text.strip():
        return text

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {"text": text, "model": model}
        if model == "humanoidx" and tone:
            payload["tone"] = tone

        resp = requests.post(API_URL, headers=headers, json=payload, timeout=30)

        if resp.status_code == 200:
            data = resp.json()
            result = data.get('humanized_text', '') or data.get('output', '') or data.get('text', '') or data.get('result', '')
            if result and result.strip():
                return result.strip()

        print(f"[humanize] API returned {resp.status_code}, using original")
        return text

    except requests.exceptions.Timeout:
        print("[humanize] timed out")
        return text
    except Exception as e:
        print(f"[humanize] error: {e}")
        return text
