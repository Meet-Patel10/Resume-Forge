"""
Test Suite — Task 11
Comprehensive tests for all fixes implemented in Tasks 2-10.

Chunks:
- 11.1: Unit tests for extraction (skill validation)
- 11.2: Unit tests for validation (summary, role level)
- 11.3: Unit tests for routing
- 11.4: Integration tests
- 11.5: Edge case tests
"""

import re
import pytest


# ═══════════════════════════════════════════════════════════════════
# CHUNK 11.1: Unit Tests for Skill Validation
# ═══════════════════════════════════════════════════════════════════

class TestSkillValidation:
    """Tests for validate_skill() function"""
    
    def test_valid_skills_accepted(self):
        """Valid skills should pass validation"""
        from app.validators.skill_validator import validate_skill
        
        valid_skills = [
            "Python", "Java", "Microservices",
            "Docker", "Kubernetes", "REST APIs",
            "OOP", "Design Patterns",
            "PostgreSQL", "Redis", "MongoDB",
            "AWS", "GCP", "Azure",
            "React", "Angular", "Vue.js",
        ]
        
        for skill in valid_skills:
            is_valid, reason = validate_skill(skill)
            assert is_valid == True, f"Valid skill rejected: {skill} ({reason})"
    
    def test_bad_skills_rejected(self):
        """Nonsense skills should be rejected"""
        from app.validators.skill_validator import validate_skill
        
        bad_skills = [
            "end interfaces",
            "stack or backend",
            "product teams",
            "and implement cloud",
            "functional teams",
            "focusing on",
            "able to learn",
        ]
        
        for skill in bad_skills:
            is_valid, reason = validate_skill(skill)
            assert is_valid == False, f"Bad skill accepted: {skill}"
    
    def test_empty_skill_rejected(self):
        """Empty skills should be rejected"""
        from app.validators.skill_validator import validate_skill
        
        is_valid, _ = validate_skill("")
        assert is_valid == False
        
        is_valid, _ = validate_skill(None)
        assert is_valid == False
    
    def test_too_short_rejected(self):
        """Single character skills should be rejected"""
        from app.validators.skill_validator import validate_skill
        
        is_valid, _ = validate_skill("X")
        assert is_valid == False
    
    def test_too_long_rejected(self):
        """Very long phrases should be rejected"""
        from app.validators.skill_validator import validate_skill
        
        long_skill = "a" * 101
        is_valid, _ = validate_skill(long_skill)
        assert is_valid == False
    
    def test_non_skill_words_rejected(self):
        """Generic non-skill words should be rejected"""
        from app.validators.skill_validator import validate_skill
        
        non_skills = ["team", "ability", "experience", "strong", "excellent"]
        for word in non_skills:
            is_valid, _ = validate_skill(word)
            assert is_valid == False, f"Non-skill accepted: {word}"
    
    def test_confidence_scoring(self):
        """Confidence scoring should give higher scores to known skills"""
        from app.validators.skill_validator import calculate_skill_confidence
        
        # Known skills should score high
        python_score = calculate_skill_confidence("Python")
        assert python_score >= 0.8, f"Python scored too low: {python_score}"
        
        # Unknown single word should score medium
        unknown_score = calculate_skill_confidence("Zephyr")
        assert unknown_score >= 0.4, f"Unknown skill scored too low: {unknown_score}"


# ═══════════════════════════════════════════════════════════════════
# CHUNK 11.2: Unit Tests for Summary and Role Level Validation
# ═══════════════════════════════════════════════════════════════════

class TestSummaryValidation:
    """Tests for summary validation functions"""
    
    def test_complete_summary_passes(self):
        """Complete summary should pass validation"""
        from app.services.prompts.resume_tailor import validate_summary_completeness
        
        good_summary = "Experienced software developer with 2.5 years of experience. Proficient in Python, Java, and Go."
        is_valid, issues = validate_summary_completeness(good_summary)
        assert is_valid == True, f"Good summary failed: {issues}"
    
    def test_truncated_summary_fails(self):
        """Truncated summary should fail validation"""
        from app.services.prompts.resume_tailor import validate_summary_completeness
        
        bad_summary = "Experienced with backend development, focusing on..."
        is_valid, issues = validate_summary_completeness(bad_summary)
        assert is_valid == False, "Truncated summary should fail"
    
    def test_fix_truncated_sentences(self):
        """Fix truncated sentences should complete them"""
        from app.services.prompts.resume_tailor import fix_truncated_sentences
        
        truncated = "Experienced with backend development, focusing on..."
        fixed = fix_truncated_sentences(truncated)
        assert "..." not in fixed, f"Still truncated: {fixed}"
        assert fixed.endswith('.'), f"Doesn't end with period: {fixed}"
    
    def test_remove_duplicates(self):
        """Duplicate phrase removal should work"""
        from app.services.prompts.resume_tailor import remove_summary_duplicates
        
        dup_text = "Proficient in Python. Proficient in Java."
        cleaned = remove_summary_duplicates(dup_text)
        assert cleaned.count("Proficient") <= 1, f"Duplicates remain: {cleaned}"
    
    def test_sentence_completeness(self):
        """Sentence completeness validator should catch issues"""
        from app.services.prompts.resume_tailor import validate_sentence_completeness
        
        # Bad - ends with ellipsis
        is_valid, issues = validate_sentence_completeness("Incomplete sentence...")
        assert is_valid == False
        
        # Bad - ends with comma
        is_valid, issues = validate_sentence_completeness("Trailing comma,")
        assert is_valid == False


class TestRoleLevelDetection:
    """Tests for role level detection"""
    
    def test_role_level_by_years(self):
        """Role level should match years of experience"""
        from app.validators.role_validator import detect_role_level_by_years
        
        assert detect_role_level_by_years(0.5) == "junior"
        assert detect_role_level_by_years(2.0) == "mid_level"
        assert detect_role_level_by_years(2.5) == "mid_level"
        assert detect_role_level_by_years(4.9) == "mid_level"
        assert detect_role_level_by_years(5.0) == "senior"
        assert detect_role_level_by_years(10.0) == "principal"
    
    def test_skill_caps_increase_with_level(self):
        """Skill caps should increase with role level"""
        from app.validators.role_validator import ROLE_SKILL_MATRIX
        
        junior_cap = ROLE_SKILL_MATRIX["junior"]["max_total_skills"]
        mid_cap = ROLE_SKILL_MATRIX["mid_level"]["max_total_skills"]
        senior_cap = ROLE_SKILL_MATRIX["senior"]["max_total_skills"]
        
        assert junior_cap < mid_cap, f"Junior ({junior_cap}) >= Mid ({mid_cap})"
        assert mid_cap < senior_cap, f"Mid ({mid_cap}) >= Senior ({senior_cap})"
    
    def test_role_level_consistency(self):
        """Role level should be consistent with years"""
        from app.validators.role_validator import validate_role_level_consistency
        
        is_valid, _ = validate_role_level_consistency(2.5, "mid_level")
        assert is_valid == True
        
        is_valid, _ = validate_role_level_consistency(2.5, "senior")
        assert is_valid == False
    
    def test_cascading_fix(self):
        """Wrong role level should no longer cause over-capping"""
        from app.validators.role_validator import detect_role_level_by_years, ROLE_SKILL_MATRIX
        
        years = 2.5
        skills_count = 46
        
        level = detect_role_level_by_years(years)
        assert level == "mid_level"
        
        max_skills = ROLE_SKILL_MATRIX[level]["max_total_skills"]
        assert max_skills == 25
        
        skills_to_remove = max(0, skills_count - max_skills)
        assert skills_to_remove == 21  # Not 26


# ═══════════════════════════════════════════════════════════════════
# CHUNK 11.3: Unit Tests for Routing
# ═══════════════════════════════════════════════════════════════════

class TestSkillRouting:
    """Tests for keyword routing functions"""
    
    def test_hard_skills_route_to_skills_section(self):
        """Hard skills should route to Skills section"""
        from app.routes.tailor import route_keywords_to_sections
        
        keywords = ["Python", "Docker", "REST APIs"]
        section_targets = {"Python": ["skills", "experience"]}
        keyword_types = {"Python": "HARD_SKILL", "Docker": "HARD_SKILL", "REST APIs": "HARD_SKILL"}
        
        to_skills, to_exp, to_summary = route_keywords_to_sections(
            keywords, section_targets, keyword_types
        )
        
        assert "Python" in to_skills
        assert "Docker" in to_skills
    
    def test_soft_skills_not_in_skills_section(self):
        """Soft skills should not be in Skills section"""
        from app.routes.tailor import prevent_soft_skills_in_skills_section
        
        routed = ["Python", "Communication", "Docker", "Leadership"]
        soft_skills = ["Communication", "Leadership"]
        
        cleaned = prevent_soft_skills_in_skills_section(routed, soft_skills)
        
        assert "Communication" not in cleaned
        assert "Leadership" not in cleaned
        assert "Python" in cleaned
        assert "Docker" in cleaned
    
    def test_missing_hard_skills_force_added(self):
        """Missing hard skills should be force-added"""
        from app.routes.tailor import validate_hard_skills_in_skills_section
        
        hard_skills = ["Python", "Docker", "Java"]
        routed = ["Python"]
        
        corrected = validate_hard_skills_in_skills_section(
            hard_skills, routed, hard_skills
        )
        
        assert "Docker" in corrected
        assert "Java" in corrected


# ═══════════════════════════════════════════════════════════════════
# CHUNK 11.4: Integration Tests
# ═══════════════════════════════════════════════════════════════════

class TestQualityGates:
    """Integration tests for quality validation framework"""
    
    def test_quality_gates_pass_good_resume(self):
        """Quality gates should pass a good resume"""
        from app.validators.quality_validator import run_quality_gates
        
        good_resume = {
            'summary': 'Experienced software developer with 2.5 years building microservices. Proficient in Python and Java.',
            'skills': [
                {'category': 'Languages', 'items': ['Python', 'Java', 'Go']},
                {'category': 'Frameworks', 'items': ['Flask', 'Spring Boot']},
            ],
            'experience': [
                {'bullets': ['Developed Python microservices', 'Built Java REST APIs']},
            ],
            'projects': [],
        }
        
        result = run_quality_gates(good_resume, 'mid_level')
        assert result['overall_score'] > 50
    
    def test_quality_gates_catch_bad_skills(self):
        """Quality gates should catch nonsense skills"""
        from app.validators.quality_validator import validate_all_skills
        
        bad_resume = {
            'skills': [
                {'category': 'Languages', 'items': ['Python', 'end interfaces', 'product teams']},
            ],
        }
        
        result = validate_all_skills(bad_resume)
        assert result['is_valid'] == False
        assert len(result['invalid_skills']) >= 2


# ═══════════════════════════════════════════════════════════════════
# CHUNK 11.5: Edge Case Tests
# ═══════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Edge case tests"""
    
    def test_empty_resume(self):
        """Empty resume should not crash"""
        from app.validators.quality_validator import run_quality_gates
        
        empty_resume = {'summary': '', 'skills': [], 'experience': [], 'projects': []}
        result = run_quality_gates(empty_resume)
        assert 'overall_pass' in result
    
    def test_unicode_skills(self):
        """Unicode skills should be handled"""
        from app.validators.skill_validator import validate_skill
        
        is_valid, _ = validate_skill("C++")
        assert is_valid == True
        
        is_valid, _ = validate_skill("C#")
        assert is_valid == True
    
    def test_hyphenated_skills(self):
        """Hyphenated skills should be valid"""
        from app.validators.skill_validator import validate_skill
        
        is_valid, _ = validate_skill("CI/CD")
        assert is_valid == True
        
        is_valid, _ = validate_skill("Node.js")
        assert is_valid == True
    
    def test_limit_keywords_with_empty_section(self):
        """limit_keywords should handle empty sections"""
        from app.services.prompts.resume_tailor import limit_keywords_per_section
        
        result = limit_keywords_per_section("", ["Python", "Java"], max_per_section=3)
        assert isinstance(result, list)
    
    def test_character_budget_short_text(self):
        """Character budget should work with short text"""
        from app.services.prompts.resume_tailor import calculate_summary_character_budget
        
        budget = calculate_summary_character_budget("Short summary.")
        assert budget > 0
    
    def test_character_budget_long_text(self):
        """Character budget should return 0 for over-budget text"""
        from app.services.prompts.resume_tailor import calculate_summary_character_budget
        
        long_text = "A" * 400
        budget = calculate_summary_character_budget(long_text)
        assert budget == 0
