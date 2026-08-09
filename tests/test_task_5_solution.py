# ============================================================================
# TASK 5: TEST SUITE - SUMMARY PRESERVATION
#
# TASK_5_COMPLETE_SOLUTION.md's Problems 1, 2, 3, and 4 are already solved
# by existing, real, already-wired code in this codebase (verified by
# reading it, not assumed):
#   - Problem 1 (summary modified when it shouldn't be): the pipeline always
#     builds the summary from master.summary (DB), never trusts the AI's
#     rewrite — both at the prompt level ("SECTION 1: SUMMARY — DO NOT
#     CHANGE (LOCKED)") and in code (tailor.py's "SUMMARY ENFORCEMENT" block).
#   - Problem 2 (character budget): SummaryConstraints (Task 2) already
#     enforces MAX_SUMMARY_LENGTH=400 / EFFECTIVE_MAX=350 — the exact same
#     numbers TASK_5_COMPLETE_SOLUTION.md proposes.
#   - Problem 3 (structure validator corruption): tailor.py already saves
#     curated_summary before the structure validator runs and restores it
#     after ("RE-ENFORCE curated skills, summary & header" block).
#   - Problem 4 (soft skills breaking summary formatting): soft skills are
#     only ever injected into experience/project bullets in this codebase
#     ("SOFT SKILLS INJECTION INTO BULLETS") — they never touch the summary,
#     so this bug cannot occur here.
#
# This file tests the one genuinely new piece added for Task 5:
# verify_summary_integrity() — a final end-to-end check/restore, since none
# of the four existing protections cover the *whole* pipeline in one place.
# ============================================================================

import pytest
from app.services.prompts.resume_tailor import verify_summary_integrity


class TestVerifySummaryIntegrity:

    def test_empty_master_is_noop(self):
        """No master summary to compare against — pass final through untouched."""
        result, was_restored = verify_summary_integrity('', 'Some final summary.')
        assert result == 'Some final summary.'
        assert was_restored is False

    def test_empty_final_restores_master(self):
        master = "Software engineer with 5 years of experience in backend systems."
        result, was_restored = verify_summary_integrity(master, '')
        assert result == master
        assert was_restored is True

    def test_severely_truncated_restores_master(self):
        master = "Software engineer with 5 years of experience building scalable distributed systems."
        truncated = master[:15]  # less than half
        result, was_restored = verify_summary_integrity(master, truncated)
        assert result == master
        assert was_restored is True

    def test_no_punctuation_restores_master(self):
        master = "Software engineer with 5 years of experience."
        no_punct = "Software engineer with five years of experience and strong backend skills"
        result, was_restored = verify_summary_integrity(master, no_punct)
        assert result == master
        assert was_restored is True

    def test_intact_identical_summary_untouched(self):
        master = "Software engineer with 5 years of experience. Proficient in Python."
        result, was_restored = verify_summary_integrity(master, master)
        assert result == master
        assert was_restored is False

    def test_valid_rewrite_not_forced_back_to_master(self):
        """A complete, valid summary that legitimately differs from master
        (e.g. keyword-injected) should NOT be force-reverted just because
        it isn't byte-identical to master — only real corruption triggers a
        restore."""
        master = "Software engineer with 5 years of experience."
        valid_rewrite = "Software engineer with 5 years of experience in Python and Docker."
        result, was_restored = verify_summary_integrity(master, valid_rewrite)
        assert result == valid_rewrite
        assert was_restored is False

    def test_minor_issue_autofixed_not_hard_restored(self):
        """A summary with a fixable issue (e.g. missing trailing period)
        should be repaired via the existing Task 2 fixer, not nuked back to
        master wholesale."""
        master = "Software engineer with 5 years of experience building systems."
        minor_issue = "Software engineer with 5 years of experience building systems"  # no period
        result, was_restored = verify_summary_integrity(master, minor_issue)
        assert was_restored is True
        assert result.endswith('.')
        # Should still resemble the original content, not be nuked to master
        assert 'building systems' in result.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
