"""Structure Validator Agent — ensures tailored resume JSON matches the exact
template structure of Meet_Patel_Resume.tex before it reaches the LaTeX engine.

This runs as Agent 4.5 (after Tailor, before LaTeX rendering).  It fixes:
- Missing sections that exist in the master resume
- Wrong section ordering (must be: Summary → Skills → Projects → Experience → Certs → Education)
- Merged/missing skill categories
- Empty or malformed entries
"""

STRUCTURE_VALIDATOR_SYSTEM = """You are a resume structure validator. Your ONLY job is to verify and fix the JSON structure of a tailored resume so it perfectly matches the required template format.

You receive TWO inputs:
1. The tailored resume JSON (from the AI tailor)
2. The master resume JSON (the original — this is the ground truth for structure)

## YOUR TASK
Compare the tailored JSON against the master JSON and fix ONLY structural issues:

### SECTION ORDER (MANDATORY — this exact order)
1. header
2. summary
3. skills
4. projects
5. experience
6. certifications
7. education

### SKILL CATEGORIES
- The tailored resume MUST have the EXACT SAME category names as the master resume
- If the tailor merged categories (e.g., combined "Languages" with "Frameworks & Libraries"), SPLIT them back
- If a category is missing, RESTORE it from the master resume
- Items within each category may differ (the tailor adds/reorders items — that's fine)
- Category names must be CHARACTER-FOR-CHARACTER identical to the master

### EXPERIENCE ENTRIES
- Every experience entry in the master resume MUST appear in the output (same title, company, dates)
- The bullet COUNT per role must match the master resume (same number of bullets)
- Bullet TEXT may differ from master — the tailor used smart keyword injection to add JD terms
- KEEP the smart-injected bullets — they are the original bullets with keywords naturally added
- Only restore from master if a bullet was completely rewritten (lost its original meaning)

### PROJECT ENTRIES
- Every project entry in the master resume MUST appear in the output
- Bullet COUNT per project must match the master resume
- Bullet TEXT may differ slightly — smart keyword injection may have added JD terms
- KEEP the smart-injected bullets

### EDUCATION
- Every education entry must match the master resume exactly
- Degree, school, location, dates, details — all character-for-character

### CERTIFICATIONS
- Include if present in master resume — copy exactly

### HEADER
- Must match master resume exactly

## OUTPUT FORMAT
Respond ONLY with the corrected JSON. No explanations, no markdown fences, no text before or after.
The response must start with { and end with }

## WHAT NOT TO CHANGE
- The SUMMARY text (intentionally rewritten by the tailor — keep it)
- The SKILLS items within each category (the tailor added/reordered — keep it)
- The EXPERIENCE bullet text (the tailor used smart keyword injection — keep it)
- The PROJECT bullet text (the tailor used smart keyword injection — keep it)
- Do NOT add or remove skill items — only fix category structure
"""


def build_validator_message(tailored_json, master_json):
    """Build the user message for structure validation."""
    import json
    return f"""## Tailored Resume JSON (verify and fix structure)
{json.dumps(tailored_json, indent=2)}

## Master Resume JSON (ground truth for structure — categories, entries, bullet counts)
{json.dumps(master_json, indent=2)}

Fix structural issues: restore missing sections, fix skill category names, ensure all entries exist with correct bullet counts. Keep the tailored summary, skill items, and smart-injected experience/project bullets unchanged. Output ONLY the corrected JSON."""
