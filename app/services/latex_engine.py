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
    r"""Estimate how many lines the resume will take at 10pt.

    Uses conservative chars-per-line values calibrated to Computer Modern
    at 10pt with 7.1in text width (~75 cpl for body, ~78 for \small,
    ~70 for bold+items skill lines).  Accounts for itemize environment
    overhead (topsep / begin-end spacing).
    """
    lines = 0

    # header block (name + contact)
    lines += 3

    # summary (\small text at 7.1in width ≈ 78 chars/line)
    summary = resume_data.get('summary', '')
    if summary:
        lines += 2  # section header + spacing
        lines += max(1, len(summary) // 78 + 1)

    # skills — include bold category prefix in width calculation
    skills = resume_data.get('skills', [])
    if skills:
        lines += 2  # section header
        for group in skills:
            category = group.get('category', '')
            items_text = ', '.join(group.get('items', []))
            # "Category: item1, item2, ..." — bold prefix is ~20% wider
            full_width = int(len(category) * 1.2) + 2 + len(items_text)
            lines += max(1, full_width // 70 + 1)

    # projects — each has a subheading + itemize environment
    projects = resume_data.get('projects', [])
    if projects:
        lines += 2  # section header
        for proj in projects:
            lines += 2  # subheading (title + tech)
            for bullet in proj.get('bullets', []):
                lines += max(1, len(bullet) // 75 + 1)

    # experience — each has a subheading + itemize environment
    experience = resume_data.get('experience', [])
    if experience:
        lines += 2  # section header
        for exp in experience:
            lines += 2  # subheading
            for bullet in exp.get('bullets', []):
                lines += max(1, len(bullet) // 75 + 1)

    # certifications
    certs = resume_data.get('certifications', [])
    if certs:
        lines += 2 + len(certs)

    # education
    education = resume_data.get('education', [])
    if education:
        lines += 2  # section header
        for edu in education:
            lines += 2  # subheading
            if edu.get('details'):
                lines += max(1, len(edu['details']) // 75 + 1)

    # other experience
    other_exp = resume_data.get('other_experience', [])
    if other_exp:
        lines += 2
        for exp in other_exp:
            lines += 2
            for bullet in exp.get('bullets', []):
                lines += max(1, len(bullet) // 75 + 1)

    return lines


def _trim_bullets_to_fit(resume_data, max_chars=155):
    """Trim overlong bullets to enforce single-page output.

    Cuts at the last natural break point (comma, semicolon, or ' and ')
    before max_chars to preserve grammatical completeness.
    """
    trimmed_count = 0
    for section_key in ('experience', 'projects', 'other_experience'):
        entries = resume_data.get(section_key, [])
        for entry in entries:
            bullets = entry.get('bullets', [])
            new_bullets = []
            for bullet in bullets:
                if len(bullet) > max_chars:
                    cut = bullet[:max_chars]
                    # Find the last natural break point
                    last_comma = cut.rfind(',')
                    last_semi = cut.rfind(';')
                    last_and = cut.rfind(' and ')
                    break_at = max(last_comma, last_semi, last_and)
                    if break_at > max_chars * 0.6:
                        bullet = bullet[:break_at].rstrip(' ,;')
                    else:
                        last_space = cut.rfind(' ')
                        if last_space > max_chars * 0.6:
                            bullet = bullet[:last_space].rstrip()
                        else:
                            bullet = cut.rstrip()
                    trimmed_count += 1
                new_bullets.append(bullet)
            entry['bullets'] = new_bullets
    if trimmed_count:
        print(f"[latex] trimmed {trimmed_count} bullets to max {max_chars} chars")


def _cap_skills_per_category(resume_data, max_per_cat=8):
    """Cap the number of skills per category to prevent line overflow."""
    skills = resume_data.get('skills', [])
    for group in skills:
        items = group.get('items', [])
        if len(items) > max_per_cat:
            group['items'] = items[:max_per_cat]
            print(f"[latex] capped skills '{group.get('category','')[:20]}': {len(items)} → {max_per_cat}")


def render_latex(resume_data):
    """Build a .tex file that matches Meet_Patel_Resume_v4.tex template EXACTLY.

    Spacing is calculated dynamically based on content volume to ensure
    the resume always fits on exactly one page.
    """
    header = resume_data.get('header', {})
    s = sanitize_latex

    # estimate content and pick spacing tier
    est_lines = _estimate_lines(resume_data)
    use_small_font = False
    left_margin = '0.7in'
    right_margin = '0.7in'

    # Progressive content reduction for strict 1-page enforcement
    if est_lines > 62:
        import copy
        resume_data = copy.deepcopy(resume_data)

        # Pass 1: cap skills + trim bullets to 155 chars
        _cap_skills_per_category(resume_data, max_per_cat=8)
        _trim_bullets_to_fit(resume_data, max_chars=155)
        est_lines = _estimate_lines(resume_data)
        print(f"[latex] 1-page pass 1: est={est_lines}")

        # Pass 2: still heavy — trim harder
        if est_lines > 68:
            _trim_bullets_to_fit(resume_data, max_chars=140)
            est_lines = _estimate_lines(resume_data)
            print(f"[latex] 1-page pass 2: est={est_lines}")

    # Tier thresholds calibrated to actual LaTeX rendering capacity:
    #   light/medium: ~60 usable lines (0.45in margins, no enlarge)
    #   heavy:        ~62 lines (0.4in margins + 0.15in enlarge)
    #   extreme:      ~66 lines (0.3in margins + 0.4in enlarge + 0.55in sides)
    #   nuclear:      ~75 lines (0.25in margins + 0.5in enlarge + 0.5in sides + \small)
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
    elif est_lines <= 58:
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
    elif est_lines <= 63:
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
    elif est_lines <= 68:
        # extreme content -- aggressive compression + tighter side margins
        section_before = '1pt'
        section_after = '1pt'
        proj_entry_gap = '-2pt'
        exp_entry_gap = '0pt'
        edu_entry_gap = '0pt'
        section_gap = '0pt'
        top_margin = '0.3in'
        bottom_margin = '0.3in'
        left_margin = '0.55in'
        right_margin = '0.55in'
        enlarge = r'\enlargethispage{0.4in}'
    else:
        # nuclear -- maximum single-page compression + font reduction
        section_before = '1pt'
        section_after = '1pt'
        proj_entry_gap = '-3pt'
        exp_entry_gap = '0pt'
        edu_entry_gap = '0pt'
        section_gap = '0pt'
        top_margin = '0.25in'
        bottom_margin = '0.25in'
        left_margin = '0.5in'
        right_margin = '0.5in'
        enlarge = r'\enlargethispage{0.5in}'
        use_small_font = True

    # ---- PREAMBLE (matches Meet_Patel_Resume_v4.tex exactly) ----
    print(f"[latex] est_lines={est_lines}, tier={'light' if est_lines<=52 else 'medium' if est_lines<=60 else 'heavy' if est_lines<=68 else 'extreme' if est_lines<=76 else 'nuclear'}, margins=({top_margin},{bottom_margin},{left_margin},{right_margin})")

    latex = r"""\documentclass[10pt, letterpaper]{article}

\usepackage[top=""" + top_margin + r""", bottom=""" + bottom_margin + r""", left=""" + left_margin + r""", right=""" + right_margin + r"""]{geometry}
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
    if use_small_font:
        latex += "\\small\n"

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
