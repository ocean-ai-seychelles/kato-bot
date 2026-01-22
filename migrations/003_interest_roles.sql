-- Interest roles system for topic-based channel access
-- Migration: 003
-- Description: Creates tables for interest definitions, member selections,
--              and persistent selector message tracking.

-- Enable foreign key constraints
PRAGMA foreign_keys = ON;

-- ============================================================================
-- INTEREST DEFINITIONS
-- ============================================================================

-- Stores available interests that members can select
CREATE TABLE IF NOT EXISTS interest_roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    interest_key TEXT NOT NULL,         -- "reinforcement_learning"
    label TEXT NOT NULL,                -- "Reinforcement Learning"
    description TEXT,                   -- "Discuss RL algorithms"
    emoji TEXT,                         -- "🤖"
    role_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (guild_id) REFERENCES guild_config(guild_id) ON DELETE CASCADE,
    UNIQUE(guild_id, interest_key)
);

-- ============================================================================
-- MEMBER SELECTIONS
-- ============================================================================

-- Tracks which interests each member has selected
CREATE TABLE IF NOT EXISTS member_interests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    interest_key TEXT NOT NULL,
    selected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (guild_id) REFERENCES guild_config(guild_id) ON DELETE CASCADE,
    UNIQUE(guild_id, user_id, interest_key)
);

-- ============================================================================
-- PERSISTENT SELECTOR MESSAGES
-- ============================================================================

-- Tracks selector messages posted by admins for persistent view handling
CREATE TABLE IF NOT EXISTS interest_selector_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (guild_id) REFERENCES guild_config(guild_id) ON DELETE CASCADE
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Index for looking up interests by guild
CREATE INDEX IF NOT EXISTS idx_interest_roles_guild
    ON interest_roles(guild_id);

-- Index for looking up interests by display order
CREATE INDEX IF NOT EXISTS idx_interest_roles_order
    ON interest_roles(guild_id, display_order);

-- Index for looking up member interests by user
CREATE INDEX IF NOT EXISTS idx_member_interests_user
    ON member_interests(guild_id, user_id);

-- Index for looking up member interests by interest key
CREATE INDEX IF NOT EXISTS idx_member_interests_key
    ON member_interests(guild_id, interest_key);

-- Index for looking up selector messages by guild
CREATE INDEX IF NOT EXISTS idx_interest_selector_messages_guild
    ON interest_selector_messages(guild_id);

-- ============================================================================
-- RECORD THIS MIGRATION
-- ============================================================================

INSERT INTO schema_migrations (version) VALUES (3);
