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
                    'audit_details': dict,
                }
            }
        """
        import json
        
        guaranteed = copy.deepcopy(resume_json)
        
        print("[guarantee] Step 1: Auditing resume...")
        
        resume_text = json.dumps(guaranteed).lower()
        
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
            
            # Check if in resume
            if protected_key in resume_text or original_text.lower() in resume_text:
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
                    print(f"[guarantee]   ✓ Injected: {keyword}")
                else:
                    print(f"[guarantee]   ✗ Failed to inject: {keyword} ({reason})")
        
        # Deduplicate after injection
        guaranteed, dedup_count = self.dedup_engine.deduplicate_skills(guaranteed)
        if dedup_count > 0:
            print(f"[guarantee]   Deduplicated: removed {dedup_count} duplicates")
        
        # Final verification
        print("[guarantee] Step 2: Final verification...")
        all_found = True
        resume_text_final = json.dumps(guaranteed).lower()
        
        for protected_key, protected_info in protected_keywords_registry.items():
            if protected_info['confidence'] >= confidence_threshold:
                original_text = protected_info['original_text']
                if original_text.lower() not in resume_text_final:
                    print(f"[guarantee]   ✗ Still missing: {original_text}")
                    all_found = False
        
        # Calculate coverage
        must_have_coverage = self._calc_tier_coverage(
            guaranteed, protected_keywords_registry, 'must_have', confidence_threshold
        )
        important_coverage = self._calc_tier_coverage(
            guaranteed, protected_keywords_registry, 'important', confidence_threshold
        )
        
        return {
            'resume_json': guaranteed,
            'metadata': {
                'must_have_coverage': must_have_coverage,
                'important_coverage': important_coverage,
                'injections_made': injections_made,
                'all_protected_found': all_found,
                'audit_details': audit,
            }
        }
    
    def _calc_tier_coverage(self, resume_json, registry, tier_value, threshold):
        """Calculate coverage for a specific tier."""
        import json
        resume_text = json.dumps(resume_json).lower()
        
        tier_keywords = {k: v for k, v in registry.items()
                         if v['tier'] == tier_value and v['confidence'] >= threshold}
        
        if not tier_keywords:
            return 1.0  # No keywords of this tier = 100% coverage
        
        found = 0
        for key, info in tier_keywords.items():
            if key in resume_text or info['original_text'].lower() in resume_text:
                found += 1
        
        return found / len(tier_keywords)

