"""
GitHub Project Fetcher — Pulls real commit data from the Resume-Forge repo.

Fetches recent commits, parses them into meaningful development updates,
and formats them for injection into email generation prompts.

The AI uses these REAL updates to craft emails that demonstrate thought process,
dedication, and active development — not vague claims.
"""

import requests
import re
from datetime import datetime, timezone
from functools import lru_cache

# ─── Config ───

REPO_OWNER = 'Meet-Patel10'
REPO_NAME = 'Resume-Building-Application'
GITHUB_API_BASE = f'https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}'

# Local repo path (this IS the repo)
import os
_LOCAL_REPO_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Headers — supports optional GITHUB_TOKEN for private repos
def _get_headers():
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'ResumeForge-EmailGenerator/1.0',
    }
    token = os.environ.get('GITHUB_TOKEN', '')
    if token:
        headers['Authorization'] = f'token {token}'
    return headers

# Cache TTL: fetch from GitHub at most once per generation session
_cache = {}
_cache_timestamp = None
_CACHE_TTL_SECONDS = 300  # 5 minutes


# ─── Category mapping: classify commits by area ───

_CATEGORY_PATTERNS = {
    'AI/ML Pipeline': [
        r'ai', r'ml', r'model', r'prompt', r'claude', r'bedrock', r'llm',
        r'anthropic', r'nvidia', r'nim', r'embedding', r'vector', r'rag',
        r'audit', r'scoring', r'analysis', r'keyword', r'jd.?analyz',
    ],
    'Email System': [
        r'email', r'outreach', r'follow.?up', r'cold', r'leadership',
        r'sign.?off', r'subject', r'tone', r'humaniz',
    ],
    'Resume Engine': [
        r'resume', r'tailor', r'bullet', r'latex', r'pdf', r'ats',
        r'cover.?letter', r'gap.?fill', r'master.?resume',
    ],
    'Infrastructure': [
        r'docker', r'deploy', r'ci.?cd', r'railway', r'vercel', r'gunicorn',
        r'procfile', r'config', r'env', r'migration', r'database', r'postgres',
        r'sqlalchemy', r'nixpack',
    ],
    'Backend/API': [
        r'flask', r'route', r'api', r'endpoint', r'blueprint', r'auth',
        r'session', r'middleware', r'service',
    ],
    'Frontend/UI': [
        r'template', r'html', r'css', r'javascript', r'ui', r'frontend',
        r'dashboard', r'page', r'form', r'upload',
    ],
}


def _classify_commit(message, files_changed=None):
    """Classify a commit into a development category based on message + files."""
    message_lower = message.lower()
    files_str = ' '.join(files_changed or []).lower()
    combined = f"{message_lower} {files_str}"

    scores = {}
    for category, patterns in _CATEGORY_PATTERNS.items():
        score = sum(1 for p in patterns if re.search(p, combined))
        if score > 0:
            scores[category] = score

    if scores:
        return max(scores, key=scores.get)
    return 'General Development'


def _parse_commit_message(message):
    """Clean up a commit message for display."""
    # Take first line only
    first_line = message.strip().split('\n')[0].strip()
    # Remove conventional commit prefixes
    first_line = re.sub(r'^(feat|fix|refactor|chore|docs|style|test|perf|ci|build)\s*[:(]\s*', '', first_line, flags=re.IGNORECASE)
    first_line = re.sub(r'\)\s*:\s*', '', first_line)
    # Capitalize first letter
    if first_line:
        first_line = first_line[0].upper() + first_line[1:]
    return first_line


def _fetch_from_local_git(max_commits=20):
    """Fetch recent commits from the local git repository (primary source).

    This works regardless of whether the GitHub repo is public or private.
    """
    import subprocess

    try:
        # Get commits with format: hash|date|message|files
        result = subprocess.run(
            ['git', 'log', f'--max-count={max_commits}',
             '--format=%H|%aI|%s', '--name-only'],
            cwd=_LOCAL_REPO_PATH,
            capture_output=True, text=True, timeout=10,
        )

        if result.returncode != 0:
            print(f"[github-fetcher] ⚠️ Local git log failed: {result.stderr[:100]}")
            return None

        now = datetime.now(timezone.utc)
        commits = []
        current_commit = None

        for line in result.stdout.strip().split('\n'):
            line = line.strip()
            if not line:
                if current_commit:
                    current_commit['category'] = _classify_commit(
                        current_commit['message'], current_commit['files_changed']
                    )
                    commits.append(current_commit)
                    current_commit = None
                continue

            if '|' in line and len(line.split('|')) >= 3:
                # This is a commit line
                if current_commit:
                    current_commit['category'] = _classify_commit(
                        current_commit['message'], current_commit['files_changed']
                    )
                    commits.append(current_commit)

                parts = line.split('|', 2)
                sha = parts[0][:8]
                date_str = parts[1]
                message_raw = parts[2]

                try:
                    commit_date = datetime.fromisoformat(date_str)
                    if commit_date.tzinfo is None:
                        commit_date = commit_date.replace(tzinfo=timezone.utc)
                    days_ago = (now - commit_date).days
                    date_display = commit_date.strftime('%Y-%m-%d')
                except (ValueError, TypeError):
                    days_ago = 0
                    date_display = 'Unknown'

                current_commit = {
                    'sha': sha,
                    'message': _parse_commit_message(message_raw),
                    'date': date_display,
                    'days_ago': days_ago,
                    'category': 'General Development',
                    'files_changed': [],
                }
            elif current_commit:
                # This is a file path
                current_commit['files_changed'].append(line)

        # Don't forget the last commit
        if current_commit:
            current_commit['category'] = _classify_commit(
                current_commit['message'], current_commit['files_changed']
            )
            commits.append(current_commit)

        # Limit files_changed per commit
        for c in commits:
            c['files_changed'] = c['files_changed'][:5]

        print(f"[github-fetcher] ✅ Fetched {len(commits)} commits from local git")
        return commits

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        print(f"[github-fetcher] ⚠️ Local git failed: {e}")
        return None


def _fetch_from_github_api(max_commits=20):
    """Fetch recent commits from GitHub API (fallback for deployed environments)."""
    try:
        resp = requests.get(
            f'{GITHUB_API_BASE}/commits',
            headers=_get_headers(),
            params={'per_page': max_commits},
            timeout=10,
        )

        if resp.status_code == 403:
            print(f"[github-fetcher] ⚠️ GitHub rate limit hit.")
            return None
        if resp.status_code == 404:
            print(f"[github-fetcher] ⚠️ GitHub repo not found or private (set GITHUB_TOKEN env var).")
            return None
        if resp.status_code != 200:
            print(f"[github-fetcher] ⚠️ GitHub API returned {resp.status_code}")
            return None

        now = datetime.now(timezone.utc)
        commits_data = resp.json()
        parsed_commits = []

        for commit_data in commits_data:
            commit_info = commit_data.get('commit', {})
            message_raw = commit_info.get('message', '')
            date_str = commit_info.get('committer', {}).get('date', '')

            try:
                commit_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                days_ago = (now - commit_date).days
                date_display = commit_date.strftime('%Y-%m-%d')
            except (ValueError, TypeError):
                days_ago = 0
                date_display = 'Unknown'

            parsed_message = _parse_commit_message(message_raw)
            category = _classify_commit(message_raw)

            parsed_commits.append({
                'sha': commit_data.get('sha', '')[:8],
                'message': parsed_message,
                'date': date_display,
                'days_ago': days_ago,
                'category': category,
                'files_changed': [],
            })

        print(f"[github-fetcher] ✅ Fetched {len(parsed_commits)} commits from GitHub API")
        return parsed_commits

    except requests.RequestException as e:
        print(f"[github-fetcher] ❌ GitHub API error: {e}")
        return None


def fetch_recent_commits(max_commits=20):
    """Fetch recent commits — tries local git first, then GitHub API.

    Returns a list of commit dicts or empty list.
    """
    global _cache, _cache_timestamp

    # Check cache
    now = datetime.now(timezone.utc)
    if _cache_timestamp and (now - _cache_timestamp).total_seconds() < _CACHE_TTL_SECONDS:
        if 'commits' in _cache:
            print(f"[github-fetcher] Using cached commits ({len(_cache['commits'])} commits)")
            return _cache['commits']

    print(f"[github-fetcher] Fetching commits from {REPO_OWNER}/{REPO_NAME}...")

    # Strategy 1: Local git (always works, even for private repos)
    commits = _fetch_from_local_git(max_commits)

    # Strategy 2: GitHub API (fallback for deployed environments without local git)
    if commits is None:
        commits = _fetch_from_github_api(max_commits)

    # Final fallback: empty
    if commits is None:
        commits = []

    # Cache results
    _cache['commits'] = commits
    _cache_timestamp = now

    return commits


def build_project_updates_summary(max_commits=20):
    """Build a formatted summary of recent project updates for email prompts.

    Returns a string ready for injection into prompts, or empty string if
    GitHub is unreachable.
    """
    commits = fetch_recent_commits(max_commits)
    if not commits:
        return ''

    # Group commits by category
    by_category = {}
    for c in commits:
        cat = c['category']
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(c)

    # Build the summary
    lines = []
    lines.append("## RECENT RESUMEFORGE DEVELOPMENT UPDATES (from live GitHub repo)")
    lines.append("These are REAL commits from the candidate's active project. Use these to demonstrate")
    lines.append("active development, thought process, and dedication. Pick 1-2 most relevant to the JD.")
    lines.append("")

    # Determine time range
    if commits:
        newest = min(c['days_ago'] for c in commits)
        oldest = max(c['days_ago'] for c in commits)
        if newest == 0:
            lines.append(f"**Activity span:** Last {oldest} days (most recent: today)")
        else:
            lines.append(f"**Activity span:** {newest}-{oldest} days ago")
        lines.append(f"**Total commits:** {len(commits)}")
        lines.append("")

    # Sort categories by relevance (AI/ML first, then Backend, etc.)
    category_priority = [
        'AI/ML Pipeline', 'Email System', 'Resume Engine',
        'Backend/API', 'Infrastructure', 'Frontend/UI', 'General Development',
    ]
    sorted_cats = sorted(by_category.keys(), key=lambda c: category_priority.index(c) if c in category_priority else 99)

    for cat in sorted_cats:
        cat_commits = by_category[cat]
        lines.append(f"### {cat} ({len(cat_commits)} commits)")
        # Show top 3-4 per category
        for c in cat_commits[:4]:
            age = f"{c['days_ago']}d ago" if c['days_ago'] > 0 else "today"
            lines.append(f"- {c['message']} ({age})")
        if len(cat_commits) > 4:
            lines.append(f"  ...and {len(cat_commits) - 4} more")
        lines.append("")

    lines.append("### HOW TO USE THESE UPDATES IN THE EMAIL:")
    lines.append("- Pick the 1-2 updates MOST relevant to the JD's tech stack or role requirements")
    lines.append("- Frame as: \"I recently [built/shipped/implemented] [specific feature] in ResumeForge\"")
    lines.append("- Shows ACTIVE development and problem-solving — not a stale side project")
    lines.append("- DO NOT list all updates — pick the most impressive/relevant ones")
    lines.append("- DO NOT fabricate details beyond what the commit messages say")

    return '\n'.join(lines)


def get_project_updates_for_prompt():
    """High-level function for route handlers. Returns formatted project updates
    or empty string if unavailable.

    Call this ONCE per generation batch, not per recipient.
    """
    try:
        summary = build_project_updates_summary()
        if summary:
            print(f"[github-fetcher] Project updates ready ({len(summary)} chars)")
        else:
            print(f"[github-fetcher] No project updates available (GitHub unreachable or empty)")
        return summary
    except Exception as e:
        print(f"[github-fetcher] ⚠️ Failed to fetch updates: {e}")
        return ''
