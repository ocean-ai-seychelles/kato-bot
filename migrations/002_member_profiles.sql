-- Member profiles table for KYC onboarding
-- Migration: 002
-- Description: Creates table for storing member KYC data after verification.

-- Enable foreign key constraints
PRAGMA foreign_keys = ON;

-- ============================================================================
-- MEMBER PROFILES (KYC)
-- ============================================================================

-- Store KYC information submitted by members during onboarding
CREATE TABLE IF NOT EXISTS member_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    discord_username TEXT NOT NULL,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL,
    country TEXT NOT NULL,
    address TEXT NOT NULL,
    id_number TEXT NOT NULL,
    verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (guild_id) REFERENCES guild_config(guild_id) ON DELETE CASCADE,
    UNIQUE(guild_id, user_id)
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Index for looking up member profiles by user
CREATE INDEX IF NOT EXISTS idx_member_profiles_user
    ON member_profiles(guild_id, user_id);

-- Index for looking up member profiles by email
CREATE INDEX IF NOT EXISTS idx_member_profiles_email
    ON member_profiles(email);

-- ============================================================================
-- RECORD THIS MIGRATION
-- ============================================================================

INSERT INTO schema_migrations (version) VALUES (2);
