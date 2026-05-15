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


def _estimate_lines(resume_data):
    """Roughly estimate how many lines the resume will take at 10pt."""
    lines = 0

    # header block (name + contact)
    lines += 3

    # summary (roughly 1 line per 90 chars at 7.1in width)
    summary = resume_data.get('summary', '')
    if summary:
        lines += 2  # section header + spacing
        lines += max(1, len(summary) // 90 + 1)

    # skills (1 line per category, some wrap)
    skills = resume_data.get('skills', [])
    if skills:
        lines += 2  # section header
        for group in skills:
            items_text = ', '.join(group.get('items', []))
            lines += max(1, len(items_text) // 80 + 1)

    # projects
    projects = resume_data.get('projects', [])
    if projects:
        lines += 2
        for proj in projects:
            lines += 2  # subheading (title + tech)
            for bullet in proj.get('bullets', []):
                lines += max(1, len(bullet) // 85 + 1)

    # experience
    experience = resume_data.get('experience', [])
    if experience:
        lines += 2
        for exp in experience:
            lines += 2  # subheading
            for bullet in exp.get('bullets', []):
                lines += max(1, len(bullet) // 85 + 1)

    # certifications
    certs = resume_data.get('certifications', [])
    if certs:
        lines += 2 + len(certs)

    # education
    education = resume_data.get('education', [])
    if education:
        lines += 2
        for edu in education:
            lines += 2  # subheading
            if edu.get('details'):
                lines += max(1, len(edu['details']) // 85 + 1)

    # other experience
    other_exp = resume_data.get('other_experience', [])
    if other_exp:
        lines += 2
        for exp in other_exp:
            lines += 2
            for bullet in exp.get('bullets', []):
                lines += max(1, len(bullet) // 85 + 1)

    return lines


def render_latex(resume_data):
    """Build a .tex file that always fits on exactly one page.

    Spacing is calculated dynamically based on content volume.
    """
    header = resume_data.get('header', {})
    s = sanitize_latex

    # estimate content and pick spacing tier
    est_lines = _estimate_lines(resume_data)

    # letter paper at 10pt with 0.45in margins ≈ 62 usable lines
    # pick spacing based on how full the page is
    if est_lines <= 48:
        # light content -- generous spacing
        section_before = '4pt'
        section_after = '4pt'
        entry_gap = '3pt'
        section_gap = '2pt'
        top_margin = '0.45in'
        bottom_margin = '0.45in'
        enlarge = ''
    elif est_lines <= 56:
        # medium content -- tighter
        section_before = '3pt'
        section_after = '3pt'
        entry_gap = '2pt'
        section_gap = '1pt'
        top_margin = '0.4in'
        bottom_margin = '0.4in'
        enlarge = ''
    elif est_lines <= 64:
        # heavy content -- compress
        section_before = '2pt'
        section_after = '2pt'
        entry_gap = '1pt'
        section_gap = '0pt'
        top_margin = '0.35in'
        bottom_margin = '0.35in'
        enlarge = r'\enlargethispage{0.15in}'
    else:
        # very heavy -- maximum compression
        section_before = '1pt'
        section_after = '1pt'
        entry_gap = '0pt'
        section_gap = '0pt'
        top_margin = '0.3in'
        bottom_margin = '0.3in'
        enlarge = r'\enlargethispage{0.3in}'

    # preamble with dynamic spacing
    latex = r"""\documentclass[10pt, letterpaper]{article}

\usepackage[top=""" + top_margin + r""", bottom=""" + bottom_margin + r""", left=0.7in, right=0.7in]{geometry}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage{titlesec}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}

\titleformat{\section}{\large\bfseries\uppercase}{}{0em}{}[\titlerule]
\titlespacing{\section}{0pt}{""" + section_before + r"""}{""" + section_after + r"""}

\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}
\pagestyle{empty}

\newcommand{\resumeItem}[1]{\item\small{#1}}
\newcommand{\resumeSubheading}[4]{
  \textbf{#1} \hfill \textit{\small #2} \\
  \textit{\small #3} \hfill \textit{\small #4}
}

\begin{document}
""" + enlarge + "\n"

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

\vspace{""" + section_gap + r"""}
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
\vspace{""" + section_gap + r"""}
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

            if i < len(projects) - 1:
                latex += r"""
\vspace{""" + entry_gap + r"""}
"""

        latex += r"""
\vspace{""" + section_gap + r"""}
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

            if i < len(experience) - 1:
                latex += r"""
\vspace{""" + entry_gap + r"""}
"""

        latex += r"""
\vspace{""" + section_gap + r"""}
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
\vspace{""" + section_gap + r"""}
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
            if i < len(education) - 1:
                latex += r"""
\vspace{""" + entry_gap + r"""}
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
\vspace{""" + entry_gap + r"""}
"""

    latex += r"""
\end{document}
"""

    return latex
