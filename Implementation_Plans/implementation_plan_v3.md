# Dynamic Resume Tailoring Pipeline

Replace all hardcoded tailoring logic with a fully dynamic, AI-driven system that analyzes each JD fresh at runtime. Target: 90%+ ATS score for any JD.

> [!CAUTION]
> **BRUTAL HONESTY IS A HARD REQUIREMENT — NOT A PREFERENCE.**
> Every stage of this pipeline — JD analysis, keyword gap analysis, bullet rewrites, qualification assessment, and the final tailored resume — must enforce zero-tolerance honesty:
> - If a skill is missing → state it as **missing**. Do not hedge.
> - If a bullet is weak → rewrite it as strong or **flag it explicitly**. Do not soften.
> - If the candidate is underqualified → **say so directly**. Do not sugarcoat.
> - The final resume must reflect only what is **honest, specific, and verifiable**.
> - **Banned language**: "Developed a foundational understanding", "Applied robust methodologies", "Gained exposure to", "Leveraged synergies", or any vague filler.
> - Every claim in the output resume must be traceable to concrete evidence in the master resume.

## Current Hardcoded Components

| Component | File | What's Static |
|-----------|------|---------------|
| Hard Skills Bank | [ats_scorer.py](file:///Users/meetpatel/Resume_Builder_Application/app/services/ats_scorer.py) L107-160 | 160+ hardcoded tech terms |
| Soft Skills Bank | [ats_scorer.py](file:///Users/meetpatel/Resume_Builder_Application/app/services/ats_scorer.py) L36-54 | 50+ hardcoded soft-skill words |
| Soft Skill Variants | [ats_scorer.py](file:///Users/meetpatel/Resume_Builder_Application/app/services/ats_scorer.py) L204-236 | Manually mapped verb→noun forms |
| JD Filler Words | [ats_scorer.py](file:///Users/meetpatel/Resume_Builder_Application/app/services/ats_scorer.py) L48-56 | Static set of words to ignore |
| Job Title Regex | [ats_scorer.py](file:///Users/meetpatel/Resume_Builder_Application/app/services/ats_scorer.py) L252-275 | Hardcoded role suffixes |
| Keyword Frequency | [ats_scorer.py](file:///Users/meetpatel/Resume_Builder_Application/app/services/ats_scorer.py) L457-483 | Fixed top-8 unigram analysis |
| Tailor Prompt | [resume_tailor.py](file:///Users/meetpatel/Resume_Builder_Application/app/services/prompts/resume_tailor.py) L1-41 | Static optimization instructions |

---

## Proposed Changes

### 1. New AI-Driven JD Analyzer

#### [NEW] [jd_analyzer.py](file:///Users/meetpatel/Resume_Builder_Application/app/services/prompts/jd_analyzer.py)

A new AI prompt that dynamically extracts **everything** from a JD in one call:

| Output Field | Description | Replaces |
|---|---|---|
| [job_title](file:///Users/meetpatel/Resume_Builder_Application/app/services/ats_scorer.py#243-285) | Exact role title(s) from the JD | Regex-based [_extract_job_titles()](file:///Users/meetpatel/Resume_Builder_Application/app/services/ats_scorer.py#243-285) |
| [hard_skills](file:///Users/meetpatel/Resume_Builder_Application/app/services/ats_scorer.py#98-194) | Every technical skill/tool the JD mentions | Static `KNOWN_TECH_SKILLS` bank |
| [soft_skills](file:///Users/meetpatel/Resume_Builder_Application/app/services/ats_scorer.py#196-241) | Every interpersonal/behavioral trait | Static `SOFT_SKILLS` set |
| `top_keywords` | 8-10 most-repeated domain terms | Static top-8 unigram counter |
| `section_priority` | What the JD values most | Static section ordering |
| `qualification_verdict` | Honest assessment: is the candidate qualified? | Nothing (new) |

**Honesty enforcement in JD Analyzer:**
- `qualification_verdict` must be one of: `"strong_fit"`, `"partial_fit"`, `"weak_fit"`, `"not_qualified"`
- `honest_gaps` field lists skills/experience the candidate genuinely lacks — no euphemisms
- If a JD requires 5 years React and the candidate has 1 year → say "Candidate has 1 year React, JD requires 5. This is a significant gap."

---

### 2. Dynamic ATS Scorer

#### [MODIFY] [ats_scorer.py](file:///Users/meetpatel/Resume_Builder_Application/app/services/ats_scorer.py)

[calculate_ats_score()](file:///Users/meetpatel/Resume_Builder_Application/app/services/ats_scorer.py#290-591) gains a new optional parameter `jd_analysis` (dict from the JD Analyzer). When provided, all scoring uses dynamic data:

| Scoring Section | Current (Static) | New (Dynamic) |
|---|---|---|
| Hard Skills (35%) | Match against 160+ hardcoded terms | Match against AI-extracted [hard_skills](file:///Users/meetpatel/Resume_Builder_Application/app/services/ats_scorer.py#98-194) from this specific JD |
| Soft Skills (10%) | Match against hardcoded `SOFT_SKILLS` set | Match against AI-extracted [soft_skills](file:///Users/meetpatel/Resume_Builder_Application/app/services/ats_scorer.py#196-241) |
| Job Title (15%) | Regex with role suffixes | Direct match against AI-extracted [job_title](file:///Users/meetpatel/Resume_Builder_Application/app/services/ats_scorer.py#243-285) |
| Keyword Freq (10%) | Top-8 unigram frequency count | Match against AI-identified `top_keywords` |

When `jd_analysis` is `None`, the scorer falls back to the existing static logic — preserving full backward compatibility.

**Honesty enforcement in scorer:** The scorer must never inflate scores. If the AI-extracted skills list has 10 items and the resume matches 5, the score is 50% — no boosting, no rounding up, no "bonus points."

---

### 3. Enhanced 4-Step Pipeline

#### [MODIFY] [tailor.py](file:///Users/meetpatel/Resume_Builder_Application/app/routes/tailor.py)

| Step | Name | Purpose | Honesty Rule |
|---|---|---|---|
| **0 (NEW)** | JD Deep Analysis | Extract title, skills, keywords, qualification verdict | Must report honest gaps |
| **1** | Brutal Critique | Identify resume weaknesses vs this JD | No softening. "Reject" means reject. |
| **2** | Keyword Extraction | Map JD keywords to resume evidence | "not_applicable" = genuinely missing. No faking. |
| **3** | Tailor | Modify resume with JD-specific context | Only embed keywords the candidate can truthfully claim |

Step 0's output (`jd_analysis` dict) is passed to:
- Step 3 (tailor prompt) — so the AI knows exactly what to target
- [calculate_ats_score()](file:///Users/meetpatel/Resume_Builder_Application/app/services/ats_scorer.py#290-591) — so scoring aligns with what was optimized

---

### 4. Dynamic Tailor Prompt

#### [MODIFY] [resume_tailor.py](file:///Users/meetpatel/Resume_Builder_Application/app/services/prompts/resume_tailor.py)

[build_tailor_message()](file:///Users/meetpatel/Resume_Builder_Application/app/services/prompts/resume_tailor.py#128-224) gains a `jd_analysis` parameter. The prompt now includes JD-specific context instead of static instructions:

```
The JD job title is: "{jd_analysis.job_title}" — use this EXACT title in your summary.
The JD's hard skills are: {jd_analysis.hard_skills} — embed these in skills and bullets.
The JD's soft skills are: {jd_analysis.soft_skills} — weave these into bullet action verbs.
The JD's top keywords are: {jd_analysis.top_keywords} — each must appear 3+ times.
Candidate qualification: {jd_analysis.qualification_verdict}
Honest gaps: {jd_analysis.honest_gaps}
```

**Honesty enforcement in tailor prompt:**
- "If the candidate CANNOT truthfully claim a keyword → **leave it out** and add it to `keywords_skipped` with a direct explanation."
- "Every bullet must contain a **specific, verifiable claim**. If you cannot make it specific, flag it in `tailoring_notes` as 'WEAK — needs real evidence'."
- "DO NOT use: 'Developed a foundational understanding', 'Gained exposure to', 'Applied robust methodologies', 'Leveraged synergies', or similar empty filler. These will cause immediate rejection."

---

## Verification Plan

### Automated Tests
1. Tailor against an engineering JD → expect 90+ ATS, all sub-scores ≥ 85%
2. Tailor against a non-tech JD → scorer must use dynamic skills, not the static bank
3. Backward compat: call [calculate_ats_score()](file:///Users/meetpatel/Resume_Builder_Application/app/services/ats_scorer.py#290-591) without `jd_analysis` → static logic still works
4. Honesty audit: `keywords_skipped` must list genuinely missing skills, not be empty

### Manual Verification
- Review 2 tailored resumes for any sugarcoated/vague language
- Confirm `qualification_verdict` is honest (not always "strong_fit")
- Verify the JD analysis step adds < 2s latency

## API Cost Impact

> [!NOTE]
> Adds one extra Bedrock API call per tailoring run (~500-800 tokens). At Nova Lite pricing ≈ $0.001/run — negligible.
