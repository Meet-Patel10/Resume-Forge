"""
Must-Have Guarantee Engine - Main orchestrator for Phase 6.5.

Ensures that EVERY must-have and important skill extracted in Phase 0
is actually present in the final tailored resume. No exceptions.

Pipeline:
1. Audit: Which must-haves are missing?
2. Categorize: What type are they?
3. Strategic Inject: Add to best sections
4. Dedup: Remove any duplicates created
5. Verify: 100% present check
6. Report: Log all injections for debugging

Design Principles:
- NO HALLUCINATION: Only inject keywords from extracted list
- STRATEGIC PLACEMENT: Put skills in best section based on type
- DENSITY RESPECT: 8 skills per category max, 20% summary density
- EVIDENCE REQUIREMENT: Every skill must have experience bullet evidence
- DEDUPLICATION: No skill appears twice
- HONESTY ENFORCEMENT: Don't inject if no resume evidence
- GRACEFUL DEGRADATION: If can't inject due to density, skip and log
- TRACEABILITY: Log every injection decision
"""

import copy
from typing import Dict, List, Optional

from .audit_engine import AuditEngine, AuditReport
from .injection_strategies import (
    skills_injection_strategy,
    experience_injection_strategy,
    summary_injection_strategy,
    fallback_injection_strategy,
)
from .density_controller import DensityController
from .deduplication_engine import DeduplicationEngine
from .evidence_validator import EvidenceValidator
from .guarantee_verifier import GuaranteeVerifier


# Soft skills that should NEVER go in Skills section
SOFT_SKILLS = {
    'communication', 'collaboration', 'teamwork', 'leadership',
    'problem-solving', 'adaptability', 'flexibility', 'accountability',
    'mentoring', 'coaching', 'cross-functional', 'initiative',
    'critical thinking', 'analytical thinking', 'innovation',
    'customer support', 'stakeholder management', 'negotiation',
    'curiosity',
}


class MustHaveGuaranteeEngine:
    """
    Main orchestrator for the Must-Have Guarantee Engine (Phase 6.5).
    
    Runs AFTER AI tailoring (Phase 6) and BEFORE validation checkpoints (Phase 7).
    """
    
    def __init__(self):
        self.audit_engine = AuditEngine()
        self.density_controller = DensityController()
        self.dedup_engine = DeduplicationEngine()
        self.evidence_validator = EvidenceValidator()
        self.verifier = GuaranteeVerifier()
        
        # Tracking
        self.injection_log = []
        self.skipped_log = []
    
    def guarantee_injection(
        self,
        resume_json: Dict,
        critical_keywords: List[str],
        keyword_metadata: Dict,
        must_haves: List[str],
        important_keywords: List[str],
    ) -> Dict:
        """
        Main method: Guarantee all must-haves and important keywords are in resume.
        
        Args:
            resume_json: Tailored resume from Phase 6
            critical_keywords: All keywords to guarantee
            keyword_metadata: ExtractedKeyword objects keyed by text
            must_haves: List of must-have keyword texts
            important_keywords: List of important keyword texts
            
        Returns: 
            Guaranteed resume JSON with all must-haves injected
        """
        # Deep copy to avoid mutating original
        guaranteed = copy.deepcopy(resume_json)
        
        # Step 1: AUDIT — What's missing?
        print("[guarantee] Step 1: Auditing resume for missing keywords...")
        audit_report = self.audit_engine.audit(
            guaranteed, must_haves, important_keywords
        )
        
        print(f"[guarantee] Audit: {audit_report.coverage_percentage:.1f}% coverage")
        print(f"[guarantee]   Missing must-haves: {audit_report.missing_must_haves}")
        print(f"[guarantee]   Missing important: {audit_report.missing_important}")
        
        if audit_report.audit_status == "COMPLETE":
            print("[guarantee] ✓ All keywords already present — no injection needed")
            return guaranteed
        
        # Step 2: INJECT missing keywords
        all_missing = audit_report.missing_must_haves + audit_report.missing_important
        
        for keyword in all_missing:
            self._inject_keyword(guaranteed, keyword, keyword_metadata)
        
        # Step 3: DEDUPLICATE
        print("[guarantee] Step 3: Deduplicating skills...")
        guaranteed, dedup_count = self.dedup_engine.deduplicate_skills(guaranteed)
        if dedup_count > 0:
            print(f"[guarantee]   Removed {dedup_count} duplicates")
        
        # Step 4: VERIFY
        print("[guarantee] Step 4: Final verification...")
        verification = self.verifier.verify_guarantee(
            guaranteed, must_haves, important_keywords
        )
        
        # Update verification with injection counts
        verification['injections_count'] = len(self.injection_log)
        if self.injection_log:
            confidences = [log.get('confidence', 0) for log in self.injection_log]
            verification['confidence_average'] = sum(confidences) / len(confidences)
        
        # Step 5: EMERGENCY — If still missing, try fallback
        if verification['still_missing']:
            print(f"[guarantee] ⚠ {len(verification['still_missing'])} still missing — trying emergency injection")
            for keyword in verification['still_missing']:
                success, reason = fallback_injection_strategy(guaranteed, keyword)
                if success:
                    self.injection_log.append({
                        'keyword': keyword,
                        'strategy': 'emergency_fallback',
                        'reason': reason,
                        'confidence': 0.7,
                    })
                    print(f"[guarantee]   Emergency: {reason}")
                else:
                    self.skipped_log.append({
                        'keyword': keyword,
                        'reason': f"All strategies failed: {reason}",
                    })
                    print(f"[guarantee]   ✗ Cannot inject '{keyword}': {reason}")
        
        # Step 6: REPORT
        print(f"[guarantee] Step 6: Report")
        print(f"[guarantee]   Injections attempted: {len(self.injection_log) + len(self.skipped_log)}")
        print(f"[guarantee]   Injections successful: {len(self.injection_log)}")
        print(f"[guarantee]   Injections skipped: {len(self.skipped_log)}")
        
        return guaranteed
    
    def _inject_keyword(self, resume_json: Dict, keyword: str, keyword_metadata: Dict):
        """
        Inject a single missing keyword using the decision tree.
        
        Decision tree:
        1. Is it in extracted_keywords list? → YES
        2. Does it have resume evidence? → Check
        3. Can we inject without violating density? → Check
        4. Already exists? → Dedup check
        5. Is soft skill going to Skills? → Redirect
        6. INJECT
        """
        keyword_lower = keyword.lower()
        
        # Decision 1: Is soft skill?
        is_soft = keyword_lower in SOFT_SKILLS
        
        # Decision 2: Evidence check
        evidence = self.evidence_validator.check_evidence(keyword, resume_json)
        
        if not evidence.should_inject:
            self.skipped_log.append({
                'keyword': keyword,
                'reason': f"No evidence in resume (confidence={evidence.confidence})",
            })
            print(f"[guarantee]   ✗ Skipping '{keyword}' — no resume evidence")
            return
        
        # Decision 3: Dedup check
        if self.dedup_engine.is_duplicate(keyword, resume_json):
            self.skipped_log.append({
                'keyword': keyword,
                'reason': "Already present (duplicate detected)",
            })
            print(f"[guarantee]   ✗ Skipping '{keyword}' — already present (dedup)")
            return
        
        # Decision 4: Choose injection strategy
        if is_soft:
            # Soft skills → Experience (NEVER Skills section)
            success, reason = experience_injection_strategy(resume_json, keyword)
        else:
            # Hard skills / Tools → Skills section first
            # Check density
            can_inject, density_reason = self.density_controller.check_can_inject(
                resume_json, keyword, 'skills'
            )
            
            if can_inject:
                success, reason = skills_injection_strategy(resume_json, keyword)
            else:
                # Try experience as fallback
                success, reason = experience_injection_strategy(resume_json, keyword)
        
        # Decision 5: If primary failed, try fallback
        if not success:
            success, reason = fallback_injection_strategy(resume_json, keyword)
        
        # Log result
        if success:
            self.injection_log.append({
                'keyword': keyword,
                'strategy': 'skills' if not is_soft else 'experience',
                'reason': reason,
                'confidence': evidence.confidence,
            })
            print(f"[guarantee]   ✓ {reason}")
        else:
            self.skipped_log.append({
                'keyword': keyword,
                'reason': f"Injection failed: {reason}",
            })
            print(f"[guarantee]   ✗ Failed to inject '{keyword}': {reason}")

    # ═══════════════════════════════════════════════════════════════
    # FIX #7: Guarantee Engine 2.0 — uses protected_keywords_registry
    # ═══════════════════════════════════════════════════════════════
    def guarantee_injection_v2(self, resume_json, protected_keywords_registry,
                               confidence_threshold=0.75):
        """
        FIX #7: Guarantee injection of protected keywords only.

        CRITICAL CHANGE: Only work with protected_keywords_registry.
        Do NOT accept raw keyword lists (prevents hallucination).

        Args:
            resume_json: Tailored resume from AI
            protected_keywords_registry: Dict of {normalized_key: {original_text, tier, ...}}
            confidence_threshold: Min confidence to inject (default 0.75)

        Returns:
            {
                'resume_json': guaranteed_resume,
                'metadata': {
                    'must_have_coverage': float,
                    'important_coverage': float,
                    'injections_made': int,
                    'all_protected_found': bool,
                    'still_missing': list,
                    'audit_details': dict,
                    'injection_log': list,
                    'skipped_log': list,
                    'placement_check': dict,
                }
            }

        TASK 9 fix: this path (the one tailor.py actually calls whenever
        protected_keywords_registry is available — see "FIX #7 preferred")
        used to be a single pass with three real gaps, found by comparing
        it against GuaranteeVerifier/AuditEngine — the more thorough,
        already-tested modules `guarantee_injection` (v1, below) already
        uses but this v2 path bypassed:
          1. Presence checks used a bare `json.dumps(resume).lower()`
             substring match instead of the existing fuzzy word-match
             checker (self.verifier._keyword_present). A keyword present
             as a known variant (e.g. "REST APIs" vs. resume text
             "RESTful APIs") was scored MISSING, triggering a pointless
             duplicate-injection attempt and an inaccurate coverage number.
          2. Deduplication ran, but nothing retried keywords that failed
             injection *before* dedup — even though dedup can free up the
             exact density room ("category full") that caused the failure.
             That's the real "fallback only tries once" gap (not literally
             the guide's generic 6-step class hierarchy, which doesn't
             match this codebase's actual guarantee-engine architecture).
          3. Per-keyword success/failure reasons were tracked in
             self.injection_log/self.skipped_log by _inject_keyword() (the
             v1 code path) but v2 never touched those logs, so the caller
             (tailor.py) only ever saw aggregate counts — no audit trail,
             no failure-reason breakdown.
        Fixed by reusing self.verifier's existing matcher/placement-check
        methods instead of a second, weaker inline implementation, and by
        recording + returning the full injection/skip log plus a genuine
        post-dedup retry.
        """
        guaranteed = copy.deepcopy(resume_json)

        print("[guarantee] Step 1: Auditing resume...")

        resume_text = self.verifier._build_searchable_text(guaranteed)

        audit = {
            'found': [],
            'missing': [],
        }

        # ONLY check protected keywords
        for protected_key, protected_info in protected_keywords_registry.items():
            original_text = protected_info['original_text']
            confidence = protected_info['confidence']
            tier = protected_info['tier']

            # Skip low-confidence keywords (they may be wrongly extracted)
            if confidence < confidence_threshold:
                audit['missing'].append({
                    'keyword': original_text,
                    'reason': f'Low confidence ({confidence:.1%})',
                    'action': 'SKIP'
                })
                continue

            # Check if in resume (fuzzy match — same matcher used by the
            # final verification below, so "found" here can't drift from
            # "found" at the end)
            if self.verifier._keyword_present(original_text, resume_text, guaranteed):
                audit['found'].append(original_text)
            else:
                audit['missing'].append({
                    'keyword': original_text,
                    'reason': 'Not found in resume',
                    'action': 'INJECT' if confidence >= confidence_threshold else 'SKIP',
                    'tier': tier,
                })

        print(f"[guarantee]   Found: {len(audit['found'])}")
        print(f"[guarantee]   Missing: {len(audit['missing'])}")

        # Inject missing (high-confidence only)
        injections_made = 0
        pending_retry = []  # keywords whose primary + fallback strategy both failed pre-dedup
        for item in audit['missing']:
            if item['action'] == 'INJECT':
                keyword = item['keyword']
                keyword_lower = keyword.lower()

                # ═══════════════════════════════════════════════════════
                # CHUNK 9.1: Validate keyword before injection
                # CHUNK 9.2: Only inject from protected_keywords_registry
                # CHUNK 9.3: Skip invalid keywords with logging
                # ═══════════════════════════════════════════════════════
                from app.validators.skill_validator import validate_skill
                is_valid_keyword, reject_reason = validate_skill(keyword)
                if not is_valid_keyword:
                    print(f"[guarantee]   ✗ SKIPPED invalid keyword: '{keyword}' ({reject_reason})")
                    self.skipped_log.append({'keyword': keyword, 'reason': f'Invalid: {reject_reason}'})
                    continue

                # Use existing injection strategies
                is_soft = keyword_lower in SOFT_SKILLS

                if is_soft:
                    success, reason = experience_injection_strategy(guaranteed, keyword)
                else:
                    success, reason = skills_injection_strategy(guaranteed, keyword)

                if not success:
                    success, reason = fallback_injection_strategy(guaranteed, keyword)

                if success:
                    injections_made += 1
                    self.injection_log.append({
                        'keyword': keyword,
                        'strategy': 'experience' if is_soft else 'skills',
                        'reason': reason,
                    })
                    print(f"[guarantee]   ✓ Injected: {keyword}")
                else:
                    pending_retry.append(keyword)
                    print(f"[guarantee]   ✗ Failed to inject: {keyword} ({reason})")

        # Deduplicate after injection
        guaranteed, dedup_count = self.dedup_engine.deduplicate_skills(guaranteed)
        if dedup_count > 0:
            print(f"[guarantee]   Deduplicated: removed {dedup_count} duplicates")

        # TASK 9: genuine emergency retry — dedup can free the exact
        # density room that made the first attempt fail, so retry keywords
        # that failed pre-dedup instead of dropping them silently.
        if pending_retry:
            print(f"[guarantee]   Retrying {len(pending_retry)} keyword(s) post-dedup...")
        for keyword in pending_retry:
            success, reason = fallback_injection_strategy(guaranteed, keyword)
            if success:
                injections_made += 1
                self.injection_log.append({
                    'keyword': keyword,
                    'strategy': 'emergency_retry_post_dedup',
                    'reason': reason,
                })
                print(f"[guarantee]   ✓ Emergency retry succeeded: {keyword}")
            else:
                self.skipped_log.append({
                    'keyword': keyword,
                    'reason': f'All strategies failed (incl. post-dedup retry): {reason}',
                })
                print(f"[guarantee]   ✗ Emergency retry also failed: {keyword} ({reason})")

        # Final verification
        print("[guarantee] Step 2: Final verification...")
        all_found = True
        still_missing = []
        resume_text_final = self.verifier._build_searchable_text(guaranteed)

        for protected_key, protected_info in protected_keywords_registry.items():
            if protected_info['confidence'] >= confidence_threshold:
                original_text = protected_info['original_text']
                if not self.verifier._keyword_present(original_text, resume_text_final, guaranteed):
                    print(f"[guarantee]   ✗ Still missing: {original_text}")
                    all_found = False
                    still_missing.append(original_text)

        # Calculate coverage
        must_have_coverage = self._calc_tier_coverage(
            guaranteed, protected_keywords_registry, 'must_have', confidence_threshold
        )
        important_coverage = self._calc_tier_coverage(
            guaranteed, protected_keywords_registry, 'important', confidence_threshold
        )

        # QA: placement check (e.g. soft skills leaking into Skills section)
        placement_check = self.verifier._verify_placement(guaranteed)

        return {
            'resume_json': guaranteed,
            'metadata': {
                'must_have_coverage': must_have_coverage,
                'important_coverage': important_coverage,
                'injections_made': injections_made,
                'all_protected_found': all_found,
                'still_missing': still_missing,
                'audit_details': audit,
                'injection_log': list(self.injection_log),
                'skipped_log': list(self.skipped_log),
                'placement_check': placement_check,
            }
        }

    def _calc_tier_coverage(self, resume_json, registry, tier_value, threshold):
        """Calculate coverage for a specific tier.

        TASK 9 fix: reuse the same fuzzy matcher as guarantee_injection_v2's
        audit/verification steps instead of a third, separate naive
        json.dumps() substring check — otherwise this could report a
        different coverage number than the 'all_protected_found' flag
        computed moments earlier from the same resume.
        """
        resume_text = self.verifier._build_searchable_text(resume_json)

        tier_keywords = {k: v for k, v in registry.items()
                         if v['tier'] == tier_value and v['confidence'] >= threshold}

        if not tier_keywords:
            return 1.0  # No keywords of this tier = 100% coverage

        found = 0
        for key, info in tier_keywords.items():
            if self.verifier._keyword_present(info['original_text'], resume_text, resume_json):
                found += 1

        return found / len(tier_keywords)

