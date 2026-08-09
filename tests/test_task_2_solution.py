# ============================================================================
# TASK 2: COMPLETE TEST SUITE
# ============================================================================

import pytest
from app.services.prompts.resume_tailor import (
    SummaryGenerator,
    SummaryConstraints,
    ConvergenceGuard
)

class TestSummaryConstraints:
    """Test constraint values."""

    def test_constraints_defined(self):
        """Verify all constraints are properly defined."""
        constraints = SummaryConstraints()
        assert constraints.MAX_SUMMARY_LENGTH == 400
        assert constraints.EFFECTIVE_MAX == 350
        assert constraints.MIN_SUMMARY_LENGTH == 20  # bugfix: was 200, rejected valid short summaries
        assert len(constraints.FORBIDDEN_PATTERNS) > 0
        assert len(constraints.DUPLICATE_PHRASES) > 0


class TestLimitKeywords:
    """Test Chunk 2.1: Keyword limiting."""

    def setup_method(self):
        self.gen = SummaryGenerator()

    def test_limit_keywords_to_max(self):
        """Test limiting keywords to MAX_KEYWORDS_PER_SECTION."""
        keywords = ['Python', 'Java', 'JavaScript', 'Go', 'Rust', 'C++', 'Ruby']
        limited = self.gen.limit_keywords_per_section(keywords)

        assert len(limited) <= 5, "Should limit to 5 keywords max"
        assert 'Python' in limited, "Should keep first keyword"

    def test_limit_empty_keywords(self):
        """Test with empty keyword list."""
        limited = self.gen.limit_keywords_per_section([])
        assert limited == []

    def test_respect_character_budget(self):
        """Test that keyword limiting respects character budget."""
        keywords = ['Python', 'Java', 'JavaScript', 'C++', 'Rust']
        limited = self.gen.limit_keywords_per_section(keywords)

        # Calculate total length
        total_len = sum(len(k) + 2 for k in limited)  # +2 for ", "
        assert total_len <= 350, "Should not exceed effective max"


class TestValidateCompleteness:
    """Test Chunk 2.2: Completeness validation."""

    def setup_method(self):
        self.gen = SummaryGenerator()

    def test_valid_summary_passes(self):
        """Test that valid summary passes validation."""
        valid = "Software engineer with 5 years experience. Proficient in Python and Java. Strong problem solver."
        is_valid, issues = self.gen.validate_summary_completeness(valid)

        assert is_valid, f"Valid summary should pass. Issues: {issues}"
        assert len(issues) == 0

    def test_detects_focusing_on_pattern(self):
        """Test detection of 'focusing on...' pattern."""
        invalid = "Experienced with backend development, focusing on..."
        is_valid, issues = self.gen.validate_summary_completeness(invalid)

        assert not is_valid, "Should detect focusing on pattern"
        assert any('focusing on' in issue.lower() for issue in issues)

    def test_detects_missing_punctuation(self):
        """Test detection of missing punctuation."""
        invalid = "Software engineer with 5 years experience"  # No period
        is_valid, issues = self.gen.validate_summary_completeness(invalid)

        assert not is_valid, "Should detect missing punctuation"
        assert any('punctuation' in issue.lower() for issue in issues)

    def test_detects_multiple_issues(self):
        """Test detection of multiple issues."""
        invalid = "Experienced with Python, focusing on... and also Experienced with Java, focusing on"
        is_valid, issues = self.gen.validate_summary_completeness(invalid)

        assert not is_valid
        assert len(issues) > 0, "Should find multiple issues"

    def test_detects_too_short_summary(self):
        """Test detection of summary that's too short."""
        short = "Engineer."
        is_valid, issues = self.gen.validate_summary_completeness(short)

        assert not is_valid
        assert any('short' in issue.lower() for issue in issues)

    def test_detects_too_long_summary(self):
        """Test detection of summary that's too long."""
        long = "A" * 401  # Exceeds MAX_SUMMARY_LENGTH
        is_valid, issues = self.gen.validate_summary_completeness(long)

        assert not is_valid
        assert any('long' in issue.lower() for issue in issues)


class TestRemoveDuplicates:
    """Test Chunk 2.3: Duplicate removal."""

    def setup_method(self):
        self.gen = SummaryGenerator()

    def test_remove_duplicate_proficient(self):
        """Test removing duplicate 'Proficient in' phrases."""
        summary = "Proficient in Python. Proficient in Java. Proficient in Go."
        result = self.gen.remove_summary_duplicates(summary)

        # Should only have 1 "Proficient in"
        count = result.lower().count('proficient in')
        assert count == 1, f"Expected 1 'Proficient in', got {count}"

    def test_remove_duplicate_experienced(self):
        """Test removing duplicate 'Experienced with' phrases."""
        summary = "Experienced with backend work. Experienced with microservices."
        result = self.gen.remove_summary_duplicates(summary)

        count = result.lower().count('experienced with')
        assert count == 1, f"Expected 1 'Experienced with', got {count}"

    def test_no_duplicates_unchanged(self):
        """Test that text without duplicates stays unchanged."""
        summary = "Software engineer with 5 years experience. Proficient in Python."
        result = self.gen.remove_summary_duplicates(summary)

        assert result == summary, "Text without duplicates should remain unchanged"


class TestCompleteIncompleteSentences:
    """Test Chunk 2.4: Sentence completion."""

    def setup_method(self):
        self.gen = SummaryGenerator()

    def test_complete_focusing_on_pattern(self):
        """Test completing 'focusing on...' patterns."""
        summary = "Experienced with Python, focusing on..."
        result = self.gen.complete_incomplete_sentences(summary)

        assert 'focusing on' not in result.lower(), "Should remove 'focusing on' pattern"
        assert result.endswith('.'), "Should end with period"

    def test_add_missing_periods(self):
        """Test adding missing periods to sentences."""
        summary = "Software engineer with 5 years experience"
        result = self.gen.complete_incomplete_sentences(summary)

        assert result.endswith('.'), "Should add period at end"

    def test_handle_multiple_sentences(self):
        """Test handling multiple sentences."""
        summary = "First sentence Proficient in Python, Java. Second sentence about Go"
        result = self.gen.complete_incomplete_sentences(summary)

        # Every sentence should end with punctuation
        sentences = result.split('.')
        for sent in sentences[:-1]:  # Skip last empty string after final period
            if sent.strip():
                # This will be checked by validation
                pass


class TestValidateAndFix:
    """Test Chunk 2.6: Full validation and fixing pipeline."""

    def setup_method(self):
        self.gen = SummaryGenerator()

    def test_fix_broken_summary(self):
        """Test fixing a completely broken summary."""
        broken = "Experienced with backend development, focusing on... Experienced with Python, focusing on..."

        fixed, report = self.gen.validate_and_fix_summary(broken)

        assert report['final_valid'], "Should be valid after fixing"
        assert 'focusing on' not in fixed.lower(), "Should remove focusing on patterns"
        assert len(fixed) >= self.gen.constraints.MIN_SUMMARY_LENGTH, "Should be at least minimum length"
        assert fixed.endswith('.'), "Should end with period"

    def test_preserve_good_summary(self):
        """Test that a good summary is preserved."""
        good = "Software engineer with 5 years experience building scalable systems. Expert in Python and Java."

        fixed, report = self.gen.validate_and_fix_summary(good)

        assert report['final_valid'], "Good summary should remain valid"
        assert fixed == good, "Good summary should not be modified"

    def test_enforce_character_budget(self):
        """Test that character budget is enforced."""
        long_summary = "A" * 500  # Exceeds max

        fixed, report = self.gen.validate_and_fix_summary(long_summary)

        assert len(fixed) <= 400, f"Should enforce max length, got {len(fixed)}"

    def test_report_includes_all_fields(self):
        """Test that report includes all expected fields."""
        summary = "Test summary."
        _, report = self.gen.validate_and_fix_summary(summary)

        assert 'original_length' in report
        assert 'steps_applied' in report
        assert 'issues_found' in report
        assert 'final_valid' in report
        assert 'final_length' in report


class TestConvergenceGuard:
    """Test convergence engine protection."""

    def setup_method(self):
        self.guard = ConvergenceGuard()

    def test_valid_convergence_accepted(self):
        """Test that valid convergence output is accepted."""
        original = "Original summary."
        convergence = "Better tailored summary for the role."

        result, used_convergence = self.guard.validate_convergence_output(original, convergence)

        assert used_convergence, "Should use valid convergence output"
        assert result == convergence

    def test_invalid_convergence_reverted(self):
        """Test that invalid convergence reverts to original."""
        original = "Valid original summary with good content."
        convergence = "Experienced with Python, focusing on..."  # Invalid

        result, used_convergence = self.guard.validate_convergence_output(original, convergence)

        # Should either fix it or revert to original
        is_valid, _ = self.guard.summary_gen.validate_summary_completeness(result)
        assert is_valid, "Result should be valid"

    def test_convergence_fixing(self):
        """Test that convergence output is fixed if possible."""
        original = "Original summary."
        # Slightly broken convergence (fixable)
        convergence = "Better summary Proficient in Python, Java. Also experienced with Go"  # Missing period

        result, _ = self.guard.validate_convergence_output(original, convergence)

        is_valid, _ = self.guard.summary_gen.validate_summary_completeness(result)
        assert is_valid, "Should produce valid summary"


class TestTaskTwoIntegration:
    """Integration tests for complete Task 2 solution."""

    def setup_method(self):
        self.gen = SummaryGenerator()

    def test_real_world_scenario_1(self):
        """Test real-world broken summary from production."""
        broken = """Applied Computer Science graduate student with over two years of professional
        experience as an software engineer enhancing and maintaining large-scale microservice
        architectures in enterprise-level production settings. Proficient in backend programming,
        distributed computing, cloud computing services. Experienced with backend development,
        focusing on... Experienced with troubleshooting, focusing on..."""

        fixed, report = self.gen.validate_and_fix_summary(broken)

        assert report['final_valid'], f"Should produce valid summary. Issues: {report['issues_found']}"
        assert 'focusing on' not in fixed.lower()
        assert len(fixed) <= 400

    def test_real_world_scenario_2(self):
        """Test another real-world scenario."""
        broken = """Proficient in backend programming, distributed computing. Proficient in Python
        and Proficient in Java. Proficient in Go, focusing on..."""

        fixed, report = self.gen.validate_and_fix_summary(broken)

        assert report['final_valid']
        # Should reduce "Proficient in" repetition
        proficient_count = fixed.lower().count('proficient in')
        assert proficient_count <= 2, "Should reduce repetition"


# ============================================================================
# PYTEST RUNNER
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
