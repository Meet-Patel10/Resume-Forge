import re


def sanitize_latex(text):
    """Escape chars that break LaTeX (& % $ # _ { } ~ ^).

    Also normalizes unicode dashes to LaTeX -- and fixes abbreviation spacing.
    """
    if not text:
        return ''

    # Normalize unicode dashes to LaTeX double-hyphen BEFORE escaping
    text = text.replace('\u2013', '--')  # en-dash → --
    text = text.replace('\u2014', '---')  # em-dash → ---

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

    # Fix abbreviation spacing for LaTeX
    # "St." before a capital letter → "St.\ " (proper LaTeX inter-word space)
    # "Jr." before a space → "Jr.\ "
    text = re.sub(r'\b(St|Jr|Dr|Mr|Mrs|Ms|Prof|Inc|Corp|Ltd)\.\s+', r'\1.\\ ', text)

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
    """Build a .tex file that matches Meet_Patel_Resume_v4.tex template EXACTLY.

    Spacing is calculated dynamically based on content volume to ensure
    the resume always fits on exactly one page.
    """
    header = resume_data.get('header', {})
    s = sanitize_latex

    # estimate content and pick spacing tier
    est_lines = _estimate_lines(resume_data)

    # letter paper at 10pt with 0.45in margins ≈ 62 usable lines
    if est_lines <= 52:
        # light content -- generous spacing
        section_before = '2pt'
        section_after = '2pt'
        proj_entry_gap = '-1pt'
        exp_entry_gap = '3pt'
        edu_entry_gap = '3pt'
        section_gap = '1pt'
        top_margin = '0.45in'
        bottom_margin = '0.45in'
        enlarge = ''
    elif est_lines <= 60:
        # medium content -- tighter
        section_before = '2pt'
        section_after = '2pt'
        proj_entry_gap = '-1pt'
        exp_entry_gap = '2pt'
        edu_entry_gap = '2pt'
        section_gap = '1pt'
        top_margin = '0.45in'
        bottom_margin = '0.45in'
        enlarge = ''
    elif est_lines <= 68:
        # heavy content -- compress
        section_before = '2pt'
        section_after = '2pt'
        proj_entry_gap = '-1pt'
        exp_entry_gap = '2pt'
        edu_entry_gap = '2pt'
        section_gap = '1pt'
        top_margin = '0.4in'
        bottom_margin = '0.4in'
        enlarge = r'\enlargethispage{0.15in}'
    else:
        # very heavy -- maximum compression
        section_before = '2pt'
        section_after = '2pt'
        proj_entry_gap = '-2pt'
        exp_entry_gap = '1pt'
        edu_entry_gap = '1pt'
        section_gap = '0pt'
        top_margin = '0.35in'
        bottom_margin = '0.35in'
        enlarge = r'\enlargethispage{0.3in}'

    # ---- PREAMBLE (matches Meet_Patel_Resume_v4.tex exactly) ----
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
"""
    if enlarge:
        latex += enlarge + "\n"

    # ---- HEADER (matches template: \\[0pt] + \vspace{-7pt}) ----
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
        linkedin_url = linkedin if linkedin.startswith('http') else 'https://' + linkedin
        linkedin_display = linkedin.replace('https://', '').replace('http://', '')
        contact_parts.append(r'\href{' + s(linkedin_url) + '}{' + s(linkedin_display) + '}')

    contact_line = r' $\vert$ '.join(contact_parts)

    latex += "\n%---------- HEADER ----------\n"
    latex += "\\begin{center}\n"
    latex += "  {\\LARGE \\textbf{" + name + "}} \\\\[0pt]\n"
    latex += "  \\small\n"
    latex += "  " + contact_line + "\n"
    latex += "\\end{center}\n"
    latex += "\\vspace{-7pt}\n"

    # ---- SUMMARY (matches template: \small + blank line + text) ----
    summary = resume_data.get('summary', '')
    if summary:
        latex += "\n\n%---------- SUMMARY ----------\n"
        latex += "\\section{Summary}\n"
        latex += "\\small\n"
        latex += "\n"
        latex += s(summary) + "\n"
        latex += "\n\\vspace{" + section_gap + "}\n"

    # ---- EDUCATION (matches template: GPA in heading, coursework in bullet) ----
    education = resume_data.get('education', [])
    if education:
        latex += "\n%---------- EDUCATION ----------\n"
        latex += "\\section{Education}\n"
        for i, edu in enumerate(education):
            degree_raw = edu.get('degree', '')
            school = s(edu.get('school', ''))
            edu_location = s(edu.get('location', ''))
            dates = s(edu.get('dates', ''))
            details = edu.get('details', '') or ''

            # Extract GPA from details and put it in the degree heading
            # Template: "Master of Applied Computer Science $|$ GPA: 3.9/4.0 (88\%)"
            gpa_text = ''
            coursework_text = ''

            if details:
                # Try to extract GPA/CGPA pattern from details
                gpa_match = re.search(
                    r'((?:C?GPA|Grade)[\s:]*[\d.]+\s*/\s*[\d.]+(?:\s*\([\d.]+%?\))?)',
                    details, re.IGNORECASE
                )
                if gpa_match:
                    gpa_text = gpa_match.group(1).strip()

                # Extract coursework — everything after "Coursework:", "Focus:", etc.
                cw_match = re.search(
                    r'(?:Relevant\s+)?(?:Coursework|Focus|Specialization)\s*[:\-]\s*(.*)',
                    details, re.IGNORECASE
                )
                if cw_match:
                    coursework_text = cw_match.group(0).strip()
                    # Ensure it starts with "Relevant Coursework:"
                    if not coursework_text.lower().startswith('relevant'):
                        coursework_text = 'Relevant Coursework: ' + cw_match.group(1).strip()
                elif not gpa_match:
                    # No GPA and no coursework pattern — use details as-is
                    coursework_text = details

            # Build degree with GPA in heading (template style)
            degree_display = s(degree_raw)
            if gpa_text and '$|$' not in degree_raw and 'GPA' not in degree_raw.upper():
                degree_display = s(degree_raw) + r' $|$ ' + s(gpa_text)

            latex += "\n\\resumeSubheading{" + degree_display + "}{" + dates + "}{" + school + "}{" + edu_location + "}\n"
            if coursework_text:
                latex += "\\begin{itemize}[leftmargin=1.5em, itemsep=0pt, topsep=2pt]\n"
                latex += "  \\resumeItem{" + s(coursework_text) + "}\n"
                latex += "\\end{itemize}\n"

            if i < len(education) - 1:
                latex += "\n\\vspace{" + edu_entry_gap + "}\n"

        latex += "\n\\vspace{" + section_gap + "}\n"

    # ---- PROJECTS (matches template: -1pt between entries) ----
    projects = resume_data.get('projects', [])
    if projects:
        latex += "\n%---------- PROJECTS ----------\n"
        latex += "\\section{Projects}\n"
        for i, proj in enumerate(projects):
            proj_name = s(proj.get('name', ''))
            tech = s(proj.get('tech_stack', ''))
            dates = s(proj.get('dates', ''))

            latex += "\n\\resumeSubheading{" + proj_name + "}{" + dates + "}{" + tech + "}{}\n"
            latex += "\\begin{itemize}[leftmargin=1.5em, itemsep=0pt, topsep=2pt]\n"
            for bullet in proj.get('bullets', []):
                latex += "  \\resumeItem{" + s(bullet) + "}\n"
            latex += "\\end{itemize}\n"

            if i < len(projects) - 1:
                latex += "\n\\vspace{" + proj_entry_gap + "}\n"

        latex += "\n\\vspace{" + section_gap + "}\n"

    # ---- EXPERIENCE (matches template: 3pt between entries) ----
    experience = resume_data.get('experience', [])
    if experience:
        latex += "\n%---------- EXPERIENCE ----------\n"
        latex += "\\section{Experience}\n"
        for i, exp in enumerate(experience):
            title = s(exp.get('title', ''))
            company = s(exp.get('company', ''))
            exp_location = s(exp.get('location', ''))
            dates = s(exp.get('dates', ''))

            latex += "\n\\resumeSubheading{" + title + "}{" + dates + "}{" + company + "}{" + exp_location + "}\n"
            latex += "\\begin{itemize}[leftmargin=1.5em, itemsep=0pt, topsep=2pt]\n"
            for bullet in exp.get('bullets', []):
                latex += "  \\resumeItem{" + s(bullet) + "}\n"
            latex += "\\end{itemize}\n"

            if i < len(experience) - 1:
                latex += "\n\\vspace{" + exp_entry_gap + "}\n"

        latex += "\n\\vspace{" + section_gap + "}\n"

    # ---- TECHNICAL SKILLS ----
    skills = resume_data.get('skills', [])
    if skills:
        latex += "\n%---------- TECHNICAL SKILLS ----------\n"
        latex += "\\section{Technical Skills}\n"
        latex += "\\small\n"
        skill_lines = []
        for group in skills:
            category = s(group.get('category', ''))
            items = ', '.join([s(item) for item in group.get('items', [])])
            skill_lines.append(rf"\textbf{{{category}:}} {items}")
        latex += ' \\\\\n'.join(skill_lines) + "\n"
        latex += "\n\\vspace{" + section_gap + "}\n"

    # ---- CERTIFICATIONS ----
    certifications = resume_data.get('certifications', [])
    if certifications:
        latex += "\n%---------- CERTIFICATIONS ----------\n"
        latex += "\\section{Certifications}\n"
        latex += "\\small\n"
        for cert in certifications:
            if isinstance(cert, dict):
                cert_name = s(cert.get('name', ''))
                cert_dates = s(cert.get('dates', ''))
                latex += "\\textbf{" + cert_name + "} \\hfill \\textit{" + cert_dates + "}\n"
            elif isinstance(cert, str):
                latex += "\\textbf{" + s(cert) + "}\n"
        latex += "\n\\vspace{" + section_gap + "}\n"

    # ---- OTHER EXPERIENCE ----
    other_experience = resume_data.get('other_experience', [])
    if other_experience:
        latex += "\n%---------- OTHER EXPERIENCE ----------\n"
        latex += "\\section{Other Experience}\n"
        for i, exp in enumerate(other_experience):
            title = s(exp.get('title', ''))
            company = s(exp.get('company', ''))
            exp_location = s(exp.get('location', ''))
            dates = s(exp.get('dates', ''))

            latex += "\n\\resumeSubheading{" + title + "}{" + dates + "}{" + company + "}{" + exp_location + "}\n"
            latex += "\\begin{itemize}[leftmargin=1.5em, itemsep=0pt, topsep=2pt]\n"
            for bullet in exp.get('bullets', []):
                latex += "  \\resumeItem{" + s(bullet) + "}\n"
            latex += "\\end{itemize}\n"

            if i < len(other_experience) - 1:
                latex += "\n\\vspace{" + exp_entry_gap + "}\n"

    latex += "\n\\end{document}\n"

    return latex
