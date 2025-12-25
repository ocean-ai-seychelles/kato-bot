-- Initial database schema for Dory Discord moderation bot
-- Migration: 001
-- Description: Creates core tables for guild configuration, moderation,
--              logging, and auto-moderation features.

-- Enable foreign key constraints
PRAGMA foreign_keys = ON;

-- ============================================================================
-- GUILD CONFIGURATION
-- ============================================================================

-- Stores server-specific configuration that can be updated at runtime
CREATE TABLE IF NOT EXISTS guild_config (
    guild_id INTEGER PRIMARY KEY,
    welcome_channel_id INTEGER,
    mod_log_channel_id INTEGER,
    reaction_role_message_id INTEGER,
    reaction_role_channel_id INTEGER,
    initial_role_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- MODERATION DATA
-- ============================================================================

-- User warnings with severity levels for escalation
CREATE TABLE IF NOT EXISTS warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    moderator_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    severity INTEGER DEFAULT 1 CHECK(severity IN (1, 2, 3)),  -- 1=low, 2=medium, 3=high
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (guild_id) REFERENCES guild_config(guild_id) ON DELETE CASCADE
);

-- Audit log of all moderation actions
CREATE TABLE IF NOT EXISTS mod_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    action_type TEXT NOT NULL CHECK(action_type IN ('kick', 'ban', 'timeout', 'warn', 'unmute', 'unban')),
    target_user_id INTEGER NOT NULL,
    moderator_id INTEGER NOT NULL,
    reason TEXT,
    duration_seconds INTEGER,  -- For timeouts
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (guild_id) REFERENCES guild_config(guild_id) ON DELETE CASCADE
);

-- ============================================================================
-- MESSAGE LOGGING
-- ============================================================================

-- Audit trail for message events (edits, deletions)
CREATE TABLE IF NOT EXISTS message_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    author_id INTEGER NOT NULL,
    content TEXT,
    event_type TEXT NOT NULL CHECK(event_type IN ('created', 'edited', 'deleted')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (guild_id) REFERENCES guild_config(guild_id) ON DELETE CASCADE
);

-- ============================================================================
-- AUTO-MODERATION
-- ============================================================================

-- Auto-moderation violation tracking
CREATE TABLE IF NOT EXISTS automod_violations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    violation_type TEXT NOT NULL CHECK(violation_type IN ('spam', 'caps', 'mentions', 'banned_word')),
    message_content TEXT,
    action_taken TEXT CHECK(action_taken IN ('deleted', 'timeout', 'warned', 'none')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (guild_id) REFERENCES guild_config(guild_id) ON DELETE CASCADE
);

-- Banned words list with regex support
CREATE TABLE IF NOT EXISTS banned_words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    word TEXT NOT NULL,
    is_regex BOOLEAN DEFAULT 0 CHECK(is_regex IN (0, 1)),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (guild_id) REFERENCES guild_config(guild_id) ON DELETE CASCADE,
    UNIQUE(guild_id, word)
);

-- Rate limiting cache for spam detection
CREATE TABLE IF NOT EXISTS rate_limit_cache (
    user_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    message_count INTEGER DEFAULT 1,
    window_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, channel_id)
);

-- ============================================================================
-- REACTION ROLES
-- ============================================================================

-- Reaction-to-role mappings for role assignment
CREATE TABLE IF NOT EXISTS reaction_roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    emoji TEXT NOT NULL,
    role_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (guild_id) REFERENCES guild_config(guild_id) ON DELETE CASCADE,
    UNIQUE(message_id, emoji)
);

-- ============================================================================
-- MIGRATION TRACKING
-- ============================================================================

-- Track which migrations have been applied
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Index for looking up warnings by user
CREATE INDEX IF NOT EXISTS idx_warnings_user
    ON warnings(guild_id, user_id);

-- Index for looking up warnings by time (for cleanup)
CREATE INDEX IF NOT EXISTS idx_warnings_created
    ON warnings(created_at);

-- Index for looking up moderation actions by user
CREATE INDEX IF NOT EXISTS idx_mod_actions_user
    ON mod_actions(guild_id, target_user_id);

-- Index for looking up moderation actions by type
CREATE INDEX IF NOT EXISTS idx_mod_actions_type
    ON mod_actions(guild_id, action_type);

-- Index for looking up message logs by message ID
CREATE INDEX IF NOT EXISTS idx_message_logs_message
    ON message_logs(message_id);

-- Index for looking up message logs by author
CREATE INDEX IF NOT EXISTS idx_message_logs_author
    ON message_logs(guild_id, author_id);

-- Index for looking up automod violations by user
CREATE INDEX IF NOT EXISTS idx_automod_user
    ON automod_violations(guild_id, user_id);

-- Index for looking up automod violations by type
CREATE INDEX IF NOT EXISTS idx_automod_type
    ON automod_violations(guild_id, violation_type);

-- Index for looking up banned words
CREATE INDEX IF NOT EXISTS idx_banned_words_guild
    ON banned_words(guild_id);

-- Index for looking up reaction roles by message
CREATE INDEX IF NOT EXISTS idx_reaction_roles_message
    ON reaction_roles(message_id);

-- ============================================================================
-- RECORD THIS MIGRATION
-- ============================================================================

INSERT INTO schema_migrations (version) VALUES (1);
