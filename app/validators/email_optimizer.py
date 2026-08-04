import re


def optimize_email_subject_line(role_title, company_name, recipient_name, proof_points):
    """
    Generate optimized subject line that:
    - Is <50 characters (optimal for email)
    - Has compelling hook (specific, not generic)
    - Avoids spam trigger words
    - Matches recipient's interests
    """
    # Spam trigger words to avoid
    spam_triggers = ['free', 'limited time', 'act now', 'urgent', 'guaranteed',
                     'risk free', 'no obligation', 'call now', 'click here', 'amazing']

    # Compelling hooks (specific to situation)
    hooks = []

    if proof_points and len(proof_points) > 0:
        # Use specific achievement
        for proof in proof_points[:3]:
            if 'improved' in proof.lower() or 'reduced' in proof.lower():
                # Extract the metric
                metric_match = re.search(r'(\d+%|\d+x)', proof)
                if metric_match:
                    metric = metric_match.group(1)
                    hooks.append(f"I improved similar system by {metric}")

    if 'data' in role_title.lower():
        hooks.append("Your data pipeline problem – I've solved this")
    elif 'ml' in role_title.lower() or 'machine learning' in role_title.lower():
        hooks.append("ML optimization that cut inference time in half")
    elif 'backend' in role_title.lower():
        hooks.append("Scaled backend to 10M+ requests/day")
    elif 'frontend' in role_title.lower():
        hooks.append("React performance optimization for your platform")

    # Generic hooks
    hooks.extend([
        f"Quick question about {role_title} at {company_name}",
        f"Interested in {company_name}'s {role_title} role",
        f"Let's discuss {role_title} opportunity",
    ])

    # Remove duplicates and sort by specificity (specific first)
    hooks = list(set(hooks))
    specific_hooks = [h for h in hooks if not any(g in h for g in ['quick question', 'interested', 'discuss'])]
    generic_hooks = [h for h in hooks if any(g in h for g in ['quick question', 'interested', 'discuss'])]

    subject = specific_hooks[0] if specific_hooks else generic_hooks[0]

    # Validate
    issues = []

    # Check 1: Length
    if len(subject) > 50:
        # Truncate while keeping meaning
        subject = subject[:47] + "..."
        issues.append('Truncated to <50 chars')

    # Check 2: Spam words
    subject_lower = subject.lower()
    found_spam = [s for s in spam_triggers if s in subject_lower]
    if found_spam:
        issues.append(f'Contains spam trigger words: {found_spam}')
        # Try to replace
        for spam in found_spam:
            subject = subject.replace(spam, '')

    # Check 3: Professionalism
    if subject.startswith('quick') or 'check this out' in subject:
        issues.append('Might be too casual')

    return {
        'subject': subject,
        'length': len(subject),
        'issues': issues,
        'quality_score': 100 - (len(issues) * 20),
        'recommendation': 'Add company research or specific achievement for better response' if len(specific_hooks) == 0 else 'Good - specific and compelling'
    }
