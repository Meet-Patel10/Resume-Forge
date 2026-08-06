-- Database Migration: Add convergence tracking columns to resume_versions table
-- This migration adds columns needed for the Guided Convergence Engine

ALTER TABLE resume_versions ADD COLUMN IF NOT EXISTS ats_score_before_convergence INTEGER;
ALTER TABLE resume_versions ADD COLUMN IF NOT EXISTS ats_score_after_convergence INTEGER;
ALTER TABLE resume_versions ADD COLUMN IF NOT EXISTS convergence_iterations INTEGER;
ALTER TABLE resume_versions ADD COLUMN IF NOT EXISTS convergence_applied BOOLEAN DEFAULT FALSE;

-- Add comments for clarity
COMMENT ON COLUMN resume_versions.ats_score_before_convergence IS 'ATS score before convergence iterations';
COMMENT ON COLUMN resume_versions.ats_score_after_convergence IS 'ATS score after convergence iterations';
COMMENT ON COLUMN resume_versions.convergence_iterations IS 'Number of convergence iterations applied';
COMMENT ON COLUMN resume_versions.convergence_applied IS 'Whether convergence was applied to this version';
