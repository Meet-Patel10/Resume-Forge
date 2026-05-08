import re


def sanitize_latex(text):
    """Escape chars that break LaTeX (& % $ # _ { } ~ ^)."""
    if not text:
        return ''

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
    """Build a .tex file from structured resume JSON.

    Layout matches Meet_Patel_Resume.pdf exactly:
    - cmss (Computer Modern Sans Serif) throughout
    - 9pt body, 17pt name, 12pt section headers
    - All black, no color accents
    - Two-line experience blocks: Title...Dates / Company...Location
    """
    header = resume_data.get('header', {})
    s = sanitize_latex

    # Preamble -- cmss fonts, tight margins
    latex = r"""\documentclass[9pt,a4paper]{article}

\usepackage[utf8]{inputenc}
\usepackage[english]{babel}
\usepackage{geometry}
\usepackage{hyperref}
\usepackage{enumitem}
\usepackage{titlesec}

% use sans-serif font to match the template
\renewcommand{\familydefault}{\sfdefault}

\geometry{left=0.5in, top=0.4in, right=0.5in, bottom=0.4in}

\pagestyle{empty}
\urlstyle{same}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}

% section headers: bold uppercase with rule, all black
\titleformat{\section}{\normalsize\bfseries\uppercase}{}{0pt}{}[\titlerule]
\titlespacing{\section}{0pt}{8pt}{4pt}

\setlist[itemize]{noitemsep, topsep=2pt, leftmargin=1.2em, label=\textbullet, parsep=0pt, partopsep=0pt}

\hypersetup{
    colorlinks=true,
    linkcolor=black,
    urlcolor=black,
}

\begin{document}
"""

    # Header
    name = s(header.get('name', 'Name'))
    location = header.get('location', '')
    phone = header.get('phone', '')
    email = header.get('email', '')
    linkedin = header.get('linkedin', '')
    github = header.get('github', '')

    contact_parts = []
    if location:
        contact_parts.append(s(location))
    if phone:
        contact_parts.append(s(phone))
    if email:
        contact_parts.append(r'\href{mailto:' + s(email) + '}{' + s(email) + '}')
    if linkedin:
        linkedin_display = linkedin.replace('https://', '').replace('http://', '')
        contact_parts.append(r'\href{' + s(linkedin) + '}{' + s(linkedin_display) + '}')
    if github:
        github_display = github.replace('https://', '').replace('http://', '')
        contact_parts.append(r'\href{' + s(github) + '}{' + s(github_display) + '}')

    contact_line = r' $|$ '.join(contact_parts)

    latex += r"""
\begin{center}
    {\fontsize{17.28pt}{20pt}\selectfont \textbf{""" + name + r"""}} \\[4pt]
    \small """ + contact_line + r"""
\end{center}
"""

    # Summary
    summary = resume_data.get('summary', '')
    if summary:
        latex += r"""
\section*{SUMMARY}
""" + s(summary) + "\n"

    # Skills
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

    # Projects
    projects = resume_data.get('projects', [])
    if projects:
        latex += r"""
\section*{PROJECTS}
"""
        for proj in projects:
            proj_name = s(proj.get('name', ''))
            tech = s(proj.get('tech_stack', ''))
            dates = s(proj.get('dates', ''))

            latex += rf"""
\textbf{{{proj_name}}} \hfill \textit{{{dates}}}
"""
            if tech:
                latex += rf"""\textit{{{tech}}}
"""
            latex += r"""\begin{itemize}
"""
            for bullet in proj.get('bullets', []):
                latex += f"\\item {s(bullet)}\n"
            latex += r"\end{itemize}" + "\n"

    # Experience
    experience = resume_data.get('experience', [])
    if experience:
        latex += r"""
\section*{EXPERIENCE}
"""
        for exp in experience:
            title = s(exp.get('title', ''))
            company = s(exp.get('company', ''))
            exp_location = s(exp.get('location', ''))
            dates = s(exp.get('dates', ''))

            latex += rf"""
\textbf{{{title}}} \hfill \textit{{{dates}}}
"""
            latex += rf"""\textit{{{company}}} \hfill \textit{{{exp_location}}}
"""
            latex += r"""\begin{itemize}
"""
            for bullet in exp.get('bullets', []):
                latex += f"\\item {s(bullet)}\n"
            latex += r"\end{itemize}" + "\n"

    # Certifications
    certifications = resume_data.get('certifications', [])
    if certifications:
        latex += r"""
\section*{CERTIFICATIONS}
"""
        for cert in certifications:
            if isinstance(cert, dict):
                cert_name = s(cert.get('name', ''))
                cert_dates = s(cert.get('dates', ''))
                latex += rf"""\textbf{{{cert_name}}} \hfill \textit{{{cert_dates}}}
"""
            elif isinstance(cert, str):
                latex += rf"""\textbf{{{s(cert)}}}
"""

    # Education
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

            latex += rf"""
\textbf{{{degree}}} \hfill \textit{{{dates}}}
"""
            latex += rf"""\textit{{{school}}} \hfill \textit{{{edu_location}}}
"""
            if details:
                latex += r"""\begin{itemize}
"""
                latex += f"\\item {s(details)}\n"
                latex += r"\end{itemize}" + "\n"

    # Other experience (if any)
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
\textbf{{{title}}} \hfill \textit{{{dates}}}
"""
            latex += rf"""\textit{{{company}}} \hfill \textit{{{exp_location}}}
"""
            latex += r"""\begin{itemize}
"""
            for bullet in exp.get('bullets', []):
                latex += f"\\item {s(bullet)}\n"
            latex += r"\end{itemize}" + "\n"

    # Languages
    other = resume_data.get('other', {})
    languages = ''
    if other and other.get('languages'):
        languages = s(other['languages'])
    elif resume_data.get('languages'):
        languages = s(resume_data['languages'])

    if languages:
        latex += r"""
\section*{LANGUAGES}
""" + languages + "\n"

    # Additional info
    if other and other.get('additional'):
        latex += r"""
\section*{ADDITIONAL}
""" + s(other['additional']) + "\n"

    latex += r"""
\end{document}
"""

    return latex
