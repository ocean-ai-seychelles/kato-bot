# Dory Bot Documentation

This directory contains architectural decisions, pitfalls encountered, and solutions implemented during the development of Dory Bot.

## Purpose

This documentation serves as a knowledge base to:
- **Enable Bayesian reasoning**: Each decision builds on previous learnings
- **Avoid repeating mistakes**: Document pitfalls and their solutions
- **Onboard contributors**: Understand why things are the way they are
- **Support data-driven decisions**: Make informed choices based on past experiences

## Structure

### `/architecture`
High-level architectural decisions and design patterns used in the bot.

### `/decisions`
Specific technology and implementation choices, following the ADR (Architecture Decision Records) pattern.

### `/pitfalls`
Problems encountered during development, root causes, and solutions.

## Document Format

Each document follows this structure:

```markdown
# Title

**Date**: YYYY-MM-DD
**Status**: Active | Superseded | Deprecated
**Context**: Brief background

## Problem / Decision / Issue
Description of what we're addressing

## Options Considered (for decisions)
- Option A: pros/cons
- Option B: pros/cons

## Solution / Outcome
What we chose and why

## Consequences
- Positive impacts
- Negative impacts
- Trade-offs

## Related Documents
Links to related decisions/pitfalls
```

## Index

### Architecture
- [001 - Database Design](architecture/001-database-design.md)
- [002 - Discord.py Cogs Pattern](architecture/002-cog-architecture.md)
- [003 - Docker Deployment Strategy](architecture/003-docker-deployment.md)

### Decisions
- [001 - Why Docker for Deployment](decisions/001-why-docker.md)
- [002 - Why Ruff for Linting](decisions/002-why-ruff.md)
- [003 - Test Isolation with Fixtures](decisions/003-test-isolation-fixture.md)

### Pitfalls
- [001 - Database Locking in Tests](pitfalls/001-database-locking.md)
- [002 - Foreign Key Constraint Failures](pitfalls/002-foreign-key-constraints.md)
- [003 - Test Pollution and Monkeypatching](pitfalls/003-test-pollution.md)

## Contributing to Documentation

When you encounter a new architectural decision or pitfall:

1. Create a new numbered document in the appropriate directory
2. Follow the document format above
3. Update this README's index
4. Link related documents together

## Principles

- **Be honest about failures**: Document what didn't work
- **Show your work**: Explain the reasoning process
- **Update beliefs**: When new information changes a decision, document it
- **Cross-reference**: Link related decisions and pitfalls
