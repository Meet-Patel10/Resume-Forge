import re


def sanitize_latex(text):
    """Escape special LaTeX characters to prevent compilation errors.

    This is CRITICAL — raw text from the AI will contain characters
    that break LaTeX compilation (& % $ # _ { } ~ ^).
    """
    if not text:
        return ''

    # Order matters — backslash must be first
    replacements = [
        ('\\', r'\textbackslash{}'),
        ('&', r'\&'),
        ('%', r'\%'),
        ('$', r'\$'),
        ('#', r'\#'),
        ('_', r'\_'),
        ('{', r'\{'),
        ('}', r'\}'),
        ('~', r'\textasciitilde{}'),
        ('^', r'\textasciicircum{}'),
    ]

    for char, replacement in replacements:
        text = text.replace(char, replacement)

    return text


def render_latex(resume_data):
    """Convert a structured resume JSON object into a complete LaTeX document.

    Matches the ATS_Resume_Jordan_Carter.docx format exactly:
    - Centered header with large bold name + bullet-separated contact
    - Blue uppercase section headers with horizontal rule
    - Experience: Title | Company | Location • Dates
    - Skills: Bold Category: items
    - Education: Degree — University

    Args:
        resume_data: dict matching the TailoredResume schema from resume_tailor.py

    Returns:
        Complete .tex file content as a string
    """
    header = resume_data.get('header', {})
    s = sanitize_latex  # shorthand

    # ── PREAMBLE ──
    latex = r"""\documentclass[11pt,a4paper]{article}

% --- Packages ---
\usepackage[utf8]{inputenc}
\usepackage[english]{babel}
\usepackage{geometry}
\usepackage{hyperref}
\usepackage{enumitem}
\usepackage{titlesec}
\usepackage{xcolor}

% --- Margin Setup ---
\geometry{left=0.6in, top=0.5in, right=0.6in, bottom=0.5in}

% --- Color Definitions ---
\definecolor{sectionblue}{RGB}{47, 84, 117}

% --- Custom Styles ---
\pagestyle{empty}
\urlstyle{same}
\setlength{\parindent}{0pt}
\setlength{\parskip}{2pt}

% Section formatting: blue, uppercase, with rule
\titleformat{\section}{\large\bfseries\color{sectionblue}\uppercase}{}{0pt}{}[\color{sectionblue}\titlerule]
\titlespacing{\section}{0pt}{12pt}{6pt}

% Bullet point styling
\setlist[itemize]{noitemsep, topsep=3pt, leftmargin=1.5em, label=\textbullet}

% Link colors
\hypersetup{
    colorlinks=true,
    linkcolor=sectionblue,
    urlcolor=sectionblue,
}

\begin{document}
"""

    # ── HEADER ──
    name = s(header.get('name', 'Name'))
    location = header.get('location', '')
    phone = header.get('phone', '')
    email = header.get('email', '')
    linkedin = header.get('linkedin', '')
    github = header.get('github', '')
    tagline = header.get('tagline', '')

    # Build contact info line with bullet separators (matching sample)
    contact_parts = []
    if phone:
        contact_parts.append(s(phone))
    if email:
        contact_parts.append(r'\href{mailto:' + s(email) + '}{' + s(email) + '}')
    if linkedin:
        linkedin_clean = linkedin.replace('https://', '').replace('http://', '')
        contact_parts.append(r'\href{' + s(linkedin) + '}{' + s(linkedin_clean) + '}')
    if github:
        github_clean = github.replace('https://', '').replace('http://', '')
        contact_parts.append(r'\href{' + s(github) + '}{' + s(github_clean) + '}')
    if location:
        contact_parts.append(s(location))

    contact_line = r'  \textbullet\hspace{4pt}  '.join(contact_parts)

    latex += r"""
% --- Header ---
\begin{center}
    {\fontsize{22pt}{26pt}\selectfont \textbf{""" + name + r"""}} \\[6pt]
    \small """ + contact_line + r"""
\end{center}
"""

    # Add tagline if present (italic, centered, below header)
    if tagline:
        latex += r"""\begin{center}
\small\textit{""" + s(tagline) + r"""}
\end{center}
"""

    # ── PROFESSIONAL SUMMARY ──
    summary = resume_data.get('summary', '')
    if summary:
        latex += r"""
\section*{PROFESSIONAL SUMMARY}
""" + s(summary) + "\n"

    # ── TECHNICAL SKILLS ──
    skills = resume_data.get('skills', [])
    if skills:
        latex += r"""
\section*{TECHNICAL SKILLS}
"""
        skill_lines = []
        for group in skills:
            category = s(group.get('category', ''))
            items = ', '.join([s(item) for item in group.get('items', [])])
            skill_lines.append(rf"\textbf{{{category}:}} {items}")
        latex += ' \\\\\n'.join(skill_lines) + "\n"

    # ── ACADEMIC PROJECTS ──
    projects = resume_data.get('projects', [])
    if projects:
        latex += r"""
\section*{PROJECTS}
"""
        for proj in projects:
            proj_name = s(proj.get('name', ''))
            tech = s(proj.get('tech_stack', ''))
            # Match sample: Bold title | tech_stack on right
            latex += rf"""
\textbf{{{proj_name}}} \hfill \textit{{{tech}}}
\begin{{itemize}}
"""
            for bullet in proj.get('bullets', []):
                latex += f"\\item {s(bullet)}\n"
            latex += r"\end{itemize}" + "\n"

    # ── PROFESSIONAL EXPERIENCE ──
    experience = resume_data.get('experience', [])
    if experience:
        latex += r"""
\section*{PROFESSIONAL EXPERIENCE}
"""
        for exp in experience:
            title = s(exp.get('title', ''))
            company = s(exp.get('company', ''))
            exp_location = s(exp.get('location', ''))
            dates = s(exp.get('dates', ''))
            # Match sample format: Bold Title | Bold Company (blue) | Location • Dates
            latex += rf"""
\textbf{{{title}}} \hspace{{3pt}}$|$\hspace{{3pt}} \textbf{{\textcolor{{sectionblue}}{{{company}}}}} \hspace{{3pt}}$|$\hspace{{3pt}} {exp_location} \textbullet\hspace{{4pt}} {dates}
\begin{{itemize}}
"""
            for bullet in exp.get('bullets', []):
                latex += f"\\item {s(bullet)}\n"
            latex += r"\end{itemize}" + "\n"

    # ── EDUCATION ──
    education = resume_data.get('education', [])
    if education:
        latex += r"""
\section*{EDUCATION}
"""
        for edu in education:
            degree = s(edu.get('degree', ''))
            school = s(edu.get('school', ''))
            edu_location = s(edu.get('location', ''))
            dates = s(edu.get('dates', ''))
            details = edu.get('details', '')

            # Match sample: Bold Degree — Bold University (blue)
            latex += rf"""
\textbf{{{degree}}} \hspace{{3pt}}---\hspace{{3pt}} \textbf{{\textcolor{{sectionblue}}{{{school}}}}}"""
            if edu_location:
                latex += rf", {edu_location}"
            if dates:
                latex += rf" \hfill {dates}"
            latex += "\n"
            if details:
                latex += f"\\\\\n{s(details)}\n"

    # ── OTHER EXPERIENCE ──
    other = resume_data.get('other', {})
    other_experience = resume_data.get('other_experience', [])

    if other_experience:
        latex += r"""
\section*{OTHER EXPERIENCE}
"""
        for exp in other_experience:
            title = s(exp.get('title', ''))
            company = s(exp.get('company', ''))
            exp_location = s(exp.get('location', ''))
            dates = s(exp.get('dates', ''))
            latex += rf"""
\textbf{{{title}}} \hspace{{3pt}}$|$\hspace{{3pt}} \textbf{{\textcolor{{sectionblue}}{{{company}}}}} \hspace{{3pt}}$|$\hspace{{3pt}} {exp_location} \textbullet\hspace{{4pt}} {dates}
\begin{{itemize}}
"""
            for bullet in exp.get('bullets', []):
                latex += f"\\item {s(bullet)}\n"
            latex += r"\end{itemize}" + "\n"

    # ── LANGUAGES ──
    languages = ''
    if other and other.get('languages'):
        languages = s(other['languages'])
    elif resume_data.get('languages'):
        languages = s(resume_data['languages'])

    if languages:
        latex += r"""
\section*{LANGUAGES}
""" + languages + "\n"

    # ── OTHER / ADDITIONAL ──
    if other and other.get('additional'):
        latex += r"""
\section*{ADDITIONAL}
""" + s(other['additional']) + "\n"

    latex += r"""
\end{document}
"""

    return latex
