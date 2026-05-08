# Root Cause Analysis & Fix Plan

## Issue #1: "Master resume is not getting checked and marked properly"

### Root Cause Found

`to_resume_text()` in [master_resume.py](file:///Users/meetpatel/Resume_Builder_Application/app/models/master_resume.py#L78-111) has **critical data loss**:

1. **Projects section is invisible** — All bullets (both `experience` and `project` type) are dumped under a single `EXPERIENCE` header. Projects never appear under a `PROJECTS` heading. This means the ATS section completeness check never finds a "projects" section → score penalty.

2. **Phone/LinkedIn/GitHub are omitted** — `to_resume_text()` outputs only name, location, email. The phone, LinkedIn URL, and GitHub URL are never included. The format compliance checker then penalizes: "No phone number detected" (-5 points).

3. **Languages section missing** — `self.languages` is never output in `to_resume_text()`, so language info is invisible to the scorer.

4. **Education details are minimal** — The education section doesn't include location info.

### Fix

#### [MODIFY] [master_resume.py](file:///Users/meetpatel/Resume_Builder_Application/app/models/master_resume.py)
- Rewrite `to_resume_text()` to include ALL stored data:
  - Add phone, LinkedIn, GitHub to contact info
  - Separate `EXPERIENCE` bullets from `PROJECTS` bullets (using `section_type` field)
  - Add `PROJECTS` section header for project-type bullets
  - Include `tech_stack` for projects
  - Add `LANGUAGES` section
  - Include education location

---

## Issue #2: "Tailored resume doesn't pass its own critique/scoring"

### Root Cause Found

There's a **scoring disconnect** between the tailoring pipeline and the master resume scoring:

1. **Tailoring pipeline has AI context; master resume scoring does NOT.** When you run the tailor, it calls `calculate_ats_score()` with `jd_analysis` (AI-extracted keywords from the JD). This means hard skills matching uses the **dynamic path** (line 388-407) — AI-provided skills like "Spring Boot", "microservices", "CI/CD" are correctly matched.

   But when you re-upload the tailored resume as a master resume and do an ATS check, it calls `calculate_ats_score(resume_text, jd_text)` **without** `jd_analysis` — so it falls to the **static fallback path** (line 408-427). The static path only finds skills from the curated `KNOWN_TECH_SKILLS` bank of ~200 terms. Many JD-specific terms get missed.

2. **Static hard skill extraction misses multi-word terms.** The static `_extract_hard_skills()` uses `if skill in text` for multi-word terms (line 230) which is substring matching — but the curation bank only has generic terms. JD-specific phrases like "connected-vehicle platform", "data provisioning", "schema migrations" are never in the bank, so they're never scored.

3. **The master resume ATS check doesn't run the dynamic JD analysis.** The `/ats-check` endpoint in [master_resume.py:171-185](file:///Users/meetpatel/Resume_Builder_Application/app/routes/master_resume.py#L171-185) directly calls `calculate_ats_score(resume_text, jd_text)` without running the JD analyzer first. This means the static fallback is ALWAYS used for master resume checks.

### Fix

#### [MODIFY] [master_resume.py](file:///Users/meetpatel/Resume_Builder_Application/app/routes/master_resume.py)
- In the `ats_check()` endpoint, run the JD Deep Analyzer first (same as the tailor pipeline does), then pass the analysis to `calculate_ats_score()`:
  ```python
  jd_analysis = run_jd_analysis(jd_text, resume_text)
  score = calculate_ats_score(resume_text, jd_text, jd_analysis=jd_analysis)
  ```
  This ensures the same dynamic keyword extraction is used for both the master resume check and the tailor pipeline.

---

## Issue #3: "Won't pass actual ATS checks that top tech companies use"

### Root Causes Found

1. **Keyword matching too strict for hard skills, too loose for soft skills.**
   - Hard skills: `_word_match('spring boot', ...)` requires the exact 2-word phrase. But a resume might say "Spring Boot microservices" (with capital letters) — the `_normalize()` handles this, but `_word_match` boundary check can miss hyphenated/compound forms.
   - Soft skills: The stem-based matching (line 474-484) is too generous. `"present"` matches `"presentation"` — but it also matches the word "present" in "present the findings", giving credit for "presentation skills" the resume might not actually demonstrate.

2. **`keywords_used` self-scoring inflates scores.** When the tailor pipeline scores the tailored resume (line 321-327), it creates `keyword_matches` from the AI's self-reported `keywords_used` list. Each keyword the AI *claims* to have used is marked `strong_match` if found in the text. This bypasses the real skill-extraction logic and always produces a near-perfect hard skills score. This is why the tailored resume score looks great on the tailor page but drops when re-scored independently.

3. **Section heading detection is fragile.** The section completeness check (line 571-598) looks for exact strings like `'summary'`, `'experience'`, `'skills'` in the resume text. But the `to_resume_text()` uses `'SUMMARY'`, `'SKILLS'`, `'EXPERIENCE'` → the `_normalize()` call lowercases everything, so this works. But uploaded PDF/DOCX text may have different section headings like "Professional Summary", "Work History", "Core Competencies" — some of these variants aren't in the check.

4. **Job title matching is too forgiving.** The title match gives credit for individual word overlap (line 525-529). If the JD title is "Senior Java Full Stack Developer", each word (senior, java, full, stack, developer) is checked independently in the full resume text. The word "developer" appears in every resume → easy partial match credit even if the actual title is "QA Analyst". Real ATS systems check if the actual job title section matches.

### Fixes

#### [MODIFY] [tailor.py](file:///Users/meetpatel/Resume_Builder_Application/app/routes/tailor.py)
- **Remove self-scoring bias**: Stop using the AI's `keywords_used` as `keyword_matches` for scoring. Instead, always use the real `calculate_ats_score()` with `jd_analysis` — let the scorer independently verify whether keywords actually appear in the text.

#### [MODIFY] [ats_scorer.py](file:///Users/meetpatel/Resume_Builder_Application/app/services/ats_scorer.py)
- **Fix soft skill stem matching**: Tighten stem matching to require minimum 4-char stems and check that the stem actually appears at a word boundary, not as a substring of unrelated words.
- **Improve section heading detection**: Add more section heading variants (Professional Summary, Work History, Core Competencies, Areas of Expertise, etc.)
- **Title matching improvement**: Weight exact phrase match much higher than individual word overlap. If the full title phrase appears in the resume, give 100%. If only individual words match, cap at 60%.

---

## Summary of Changes

| File | What Changes | Impact |
|---|---|---|
| [master_resume.py](file:///Users/meetpatel/Resume_Builder_Application/app/models/master_resume.py) | Rewrite `to_resume_text()` to include all data (projects, phone, linkedin, languages) | #1: Master resume scored properly |
| [master_resume.py](file:///Users/meetpatel/Resume_Builder_Application/app/routes/master_resume.py) | Run JD analyzer in `/ats-check` endpoint | #2: Same scoring logic for both paths |
| [tailor.py](file:///Users/meetpatel/Resume_Builder_Application/app/routes/tailor.py) | Remove `keywords_used` self-scoring, use real scorer | #2: No more inflated scores |
| [ats_scorer.py](file:///Users/meetpatel/Resume_Builder_Application/app/services/ats_scorer.py) | Fix soft skill stems, better section variants, stricter title matching | #3: More realistic ATS scoring |

---

## Verification Plan

### Test 1: Master Resume Scoring
- Upload a resume → check the health score → verify projects appear as a separate section, phone/LinkedIn detected

### Test 2: Round-Trip Consistency
- Tailor a resume for a JD → note the score → re-enter the tailored text in the ATS check on the master resume page → score should be comparable (within 5-10 points)

### Test 3: Keyword Accuracy
- Use a JD with "Spring Boot", "Kubernetes", "CI/CD" → verify these are detected and matched
- Use a JD with "Customer Success" → verify it's not matched as "customer service"
