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
    """Build a .tex file that matches Meet_Patel_Resume.tex format exactly."""
    header = resume_data.get('header', {})
    s = sanitize_latex

    # preamble -- matches the template exactly
    latex = r"""\documentclass[10pt, letterpaper]{article}

\usepackage[top=0.45in, bottom=0.45in, left=0.7in, right=0.7in]{geometry}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage{titlesec}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}

\titleformat{\section}{\large\bfseries\uppercase}{}{0em}{}[\titlerule]
\titlespacing{\section}{0pt}{3pt}{3pt}

\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}
\pagestyle{empty}

\newcommand{\resumeItem}[1]{\item\small{#1}}
\newcommand{\resumeSubheading}[4]{
  \textbf{#1} \hfill \textit{\small #2} \\
  \textit{\small #3} \hfill \textit{\small #4}
}

\begin{document}
"""

    # header
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
    if github:
        github_url = github if github.startswith('http') else 'https://' + github
        github_display = github.replace('https://', '').replace('http://', '')
        contact_parts.append(r'\href{' + s(github_url) + '}{' + s(github_display) + '}')
    if linkedin:
        linkedin_url = linkedin if linkedin.startswith('http') else 'https://' + linkedin
        linkedin_display = linkedin.replace('https://', '').replace('http://', '')
        contact_parts.append(r'\href{' + s(linkedin_url) + '}{' + s(linkedin_display) + '}')

    contact_line = r' $\vert$ '.join(contact_parts)

    latex += r"""
%---------- HEADER ----------
\begin{center}
  {\LARGE \textbf{""" + name + r"""}} \\[3pt]
  \small
  """ + contact_line + r"""
\end{center}
"""

    # summary
    summary = resume_data.get('summary', '')
    if summary:
        latex += r"""
%---------- SUMMARY ----------
\section{Summary}
\small

""" + s(summary) + r"""

\vspace{1pt}
"""

    # skills
    skills = resume_data.get('skills', [])
    if skills:
        latex += r"""
%---------- TECHNICAL SKILLS ----------
\section{Technical Skills}
\small
"""
        skill_lines = []
        for group in skills:
            category = s(group.get('category', ''))
            items = ', '.join([s(item) for item in group.get('items', [])])
            skill_lines.append(rf"\textbf{{{category}:}} {items}")
        latex += ' \\\\\n'.join(skill_lines) + "\n"
        latex += r"""
\vspace{1pt}
"""

    # projects
    projects = resume_data.get('projects', [])
    if projects:
        latex += r"""
%---------- PROJECTS ----------
\section{Projects}
"""
        for i, proj in enumerate(projects):
            proj_name = s(proj.get('name', ''))
            tech = s(proj.get('tech_stack', ''))
            dates = s(proj.get('dates', ''))

            latex += r"""
\resumeSubheading{""" + proj_name + r"""}{""" + dates + r"""}{""" + tech + r"""}{}
\begin{itemize}[leftmargin=1.5em, itemsep=0pt, topsep=2pt]
"""
            for bullet in proj.get('bullets', []):
                latex += r"  \resumeItem{" + s(bullet) + "}\n"
            latex += r"\end{itemize}" + "\n"

            # spacing between entries
            if i < len(projects) - 1:
                latex += r"""
\vspace{3pt}
"""

        latex += r"""
\vspace{1pt}
"""

    # experience
    experience = resume_data.get('experience', [])
    if experience:
        latex += r"""
%---------- EXPERIENCE ----------
\section{Experience}
"""
        for i, exp in enumerate(experience):
            title = s(exp.get('title', ''))
            company = s(exp.get('company', ''))
            exp_location = s(exp.get('location', ''))
            dates = s(exp.get('dates', ''))

            latex += r"""
\resumeSubheading{""" + title + r"""}{""" + dates + r"""}{""" + company + r"""}{""" + exp_location + r"""}
\begin{itemize}[leftmargin=1.5em, itemsep=0pt, topsep=2pt]
"""
            for bullet in exp.get('bullets', []):
                latex += r"  \resumeItem{" + s(bullet) + "}\n"
            latex += r"\end{itemize}" + "\n"

            # spacing between entries
            if i < len(experience) - 1:
                latex += r"""
\vspace{3pt}
"""

        latex += r"""
\vspace{1pt}
"""

    # certifications
    certifications = resume_data.get('certifications', [])
    if certifications:
        latex += r"""
%---------- CERTIFICATIONS ----------
\section{Certifications}
\small
"""
        for cert in certifications:
            if isinstance(cert, dict):
                cert_name = s(cert.get('name', ''))
                cert_dates = s(cert.get('dates', ''))
                latex += rf"\textbf{{{cert_name}}} \hfill \textit{{{cert_dates}}}" + "\n"
            elif isinstance(cert, str):
                latex += rf"\textbf{{{s(cert)}}}" + "\n"

        latex += r"""
\vspace{1pt}
"""

    # education
    education = resume_data.get('education', [])
    if education:
        latex += r"""
%---------- EDUCATION ----------
\section{Education}
"""
        for i, edu in enumerate(education):
            degree = s(edu.get('degree', ''))
            school = s(edu.get('school', ''))
            edu_location = s(edu.get('location', ''))
            dates = s(edu.get('dates', ''))
            details = edu.get('details', '')

            latex += r"""
\resumeSubheading{""" + degree + r"""}{""" + dates + r"""}{""" + school + r"""}{""" + edu_location + r"""}
"""
            if details:
                latex += r"""\begin{itemize}[leftmargin=1.5em, itemsep=0pt, topsep=2pt]
  \resumeItem{""" + s(details) + r"""}
\end{itemize}
"""
            # spacing between entries
            if i < len(education) - 1:
                latex += r"""
\vspace{3pt}
"""

    # other experience
    other_experience = resume_data.get('other_experience', [])
    if other_experience:
        latex += r"""
%---------- OTHER EXPERIENCE ----------
\section{Other Experience}
"""
        for i, exp in enumerate(other_experience):
            title = s(exp.get('title', ''))
            company = s(exp.get('company', ''))
            exp_location = s(exp.get('location', ''))
            dates = s(exp.get('dates', ''))

            latex += r"""
\resumeSubheading{""" + title + r"""}{""" + dates + r"""}{""" + company + r"""}{""" + exp_location + r"""}
\begin{itemize}[leftmargin=1.5em, itemsep=0pt, topsep=2pt]
"""
            for bullet in exp.get('bullets', []):
                latex += r"  \resumeItem{" + s(bullet) + "}\n"
            latex += r"\end{itemize}" + "\n"

            if i < len(other_experience) - 1:
                latex += r"""
\vspace{3pt}
"""

    # languages
    other = resume_data.get('other', {})
    languages = ''
    if other and other.get('languages'):
        languages = s(other['languages'])
    elif resume_data.get('languages'):
        languages = s(resume_data['languages'])

    if languages:
        latex += r"""
\section{Languages}
\small
""" + languages + "\n"

    latex += r"""
\end{document}
"""

    return latex
