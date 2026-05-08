# Dynamic Resume Tailoring Pipeline

Replace all hardcoded tailoring logic with a fully dynamic, AI-driven system that analyzes each JD fresh at runtime. Target: 90%+ ATS score for any JD.

## Current Hardcoded Components

| Component | File | What's Static |
|-----------|------|---------------|
| Hard Skills Bank | [ats_scorer.py](file:///Users/meetpatel/Resume_Builder_Application/app/services/ats_scorer.py) L107-160 | 160+ hardcoded tech terms (python, react, docker…) |
| Soft Skills Bank | [ats_scorer.py](file:///Users/meetpatel/Resume_Builder_Application/app/services/ats_scorer.py) L36-54 | 50+ hardcoded soft-skill words |
| Soft Skill Variants | [ats_scorer.py](file:///Users/meetpatel/Resume_Builder_Application/app/services/ats_scorer.py) L204-236 | Manually mapped verb→noun forms |
| JD Filler Words | [ats_scorer.py](file:///Users/meetpatel/Resume_Builder_Application/app/services/ats_scorer.py) L48-56 | Static set of words to ignore |
| Job Title Regex | [ats_scorer.py](file:///Users/meetpatel/Resume_Builder_Application/app/services/ats_scorer.py) L252-275 | Hardcoded role suffixes (Engineer, Developer…) |
| Keyword Frequency | [ats_scorer.py](file:///Users/meetpatel/Resume_Builder_Application/app/services/ats_scorer.py) L457-483 | Fixed top-8 unigram analysis |
| Tailor Prompt | [resume_tailor.py](file:///Users/meetpatel/Resume_Builder_Application/app/services/prompts/resume_tailor.py) L1-41 | Static optimization instructions |

## Proposed Changes

### New AI-Driven JD Analyzer

#### [NEW] [jd_analyzer.py](file:///Users/meetpatel/Resume_Builder_Application/app/services/prompts/jd_analyzer.py)

A new AI prompt that dynamically extracts **everything** from a JD in one call:
- **Exact job title(s)** — no regex guessing
- **Hard skills** — extracted from THIS JD, not a static bank
- **Soft skills** — every soft skill/trait the JD mentions
- **Top keywords by frequency** — what this employer repeats most
- **Section priority** — what this JD values most (skills vs experience vs projects)
- **Culture signals** — tone, values, what the employer cares about

Output: structured JSON that feeds directly into both the tailor prompt and the scorer.

---

### Dynamic ATS Scorer

#### [MODIFY] [ats_scorer.py](file:///Users/meetpatel/Resume_Builder_Application/app/services/ats_scorer.py)

**Hard Skills (35%)**: Replace `KNOWN_TECH_SKILLS` bank with AI-extracted skills from `jd_analyzer`. The scorer receives the exact skills list from the AI analysis instead of matching against a static bank.

**Soft Skills (10%)**: Replace `SOFT_SKILLS` set and `soft_variants` with AI-extracted soft skills. The analyzer tells us exactly which soft skills the JD contains; the scorer checks if those specific terms appear in the resume.

**Job Title (15%)**: Replace regex-based [_extract_job_titles()](file:///Users/meetpatel/Resume_Builder_Application/app/services/ats_scorer.py#243-285) with the AI-extracted job title. No more guessing with role-word suffixes.

**Keyword Frequency (10%)**: Replace static top-8 unigram counter with AI-identified top keywords. The analyzer returns the 8-10 terms the employer repeats most; the scorer checks if those appear in the resume.

Key design: [calculate_ats_score()](file:///Users/meetpatel/Resume_Builder_Application/app/services/ats_scorer.py#290-591) gains a new optional parameter `jd_analysis` (dict from the AI analyzer). When provided, the scorer uses dynamic data; when absent, it falls back to the existing static logic (backward compatibility).

---

### Enhanced Pipeline

#### [MODIFY] [tailor.py](file:///Users/meetpatel/Resume_Builder_Application/app/routes/tailor.py)

Change the 3-step pipeline to a **4-step pipeline**:

1. **Step 0 (NEW): JD Deep Analysis** — calls `jd_analyzer` prompt to extract title, skills, keywords, priorities
2. **Step 1: Brutal Critique** — unchanged
3. **Step 2: Keyword Extraction** — unchanged (complementary to step 0)
4. **Step 3: Tailor** — now receives the JD analysis as additional context, so the AI knows exactly what to target

The JD analysis dict is also passed to [calculate_ats_score()](file:///Users/meetpatel/Resume_Builder_Application/app/services/ats_scorer.py#290-591) so scoring is aligned with what the AI was actually asked to optimize for.

---

### Dynamic Tailor Prompt

#### [MODIFY] [resume_tailor.py](file:///Users/meetpatel/Resume_Builder_Application/app/services/prompts/resume_tailor.py)

[build_tailor_message()](file:///Users/meetpatel/Resume_Builder_Application/app/services/prompts/resume_tailor.py#128-224) gains a new parameter `jd_analysis` (from step 0). The prompt now includes:
- "The JD job title is: [X] — use this EXACT title in your summary"
- "The JD's top hard skills are: [list] — embed these in skills and bullets"
- "The JD's soft skills are: [list] — weave these into bullet action verbs"
- "The JD's most repeated keywords are: [list] — each must appear 3+ times"

This replaces the static instructions with dynamic, JD-specific guidance.

---

## Verification Plan

### Automated Testing
```bash
# 1. Run with an engineering JD — expect 90+ ATS score
# 2. Run with a non-tech JD (finance, healthcare) — expect 85+ ATS score
# 3. Verify backward compatibility: existing scoring without jd_analysis still works
```

### Manual Verification
- Tailor against 2 different JDs and verify all 7 ATS sub-scores ≥ 85%
- Confirm no fabrication in the output
- Check that the JD analysis step adds minimal latency (< 2s extra)

## API Cost Impact

> [!NOTE]
> This adds one extra Bedrock API call per tailoring run (~500-800 tokens). At Nova Lite pricing, this is approximately $0.001 per run — negligible.
