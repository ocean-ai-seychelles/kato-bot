# ADR 001: Why Docker for Deployment

**Date**: 2025-01
**Status**: Accepted
**Deciders**: Development team
**Context**: Need to deploy bot to VPS for 24/7 operation

## Decision

Use Docker and Docker Compose for deploying the bot to production.

## Context and Problem Statement

The bot was initially developed to run locally via `uv run main.py`. For production use, we need:
- 24/7 uptime without keeping development laptop running
- Automatic restart on crashes
- Easy deployment to VPS (Linode)
- Simple update process when pushing new features
- Database persistence across restarts

## Decision Drivers

- **Simplicity**: Must be easy to deploy and maintain
- **Reliability**: Must auto-restart on failures
- **Portability**: Should work on any VPS provider
- **Developer experience**: Same environment locally and in production
- **Cost**: Should not require expensive infrastructure

## Options Considered

### Option 1: tmux/screen Session

Run bot in a persistent terminal session on laptop.

**Pros**:
- Zero learning curve
- No new tools needed

**Cons**:
- Laptop must stay on 24/7
- No auto-restart on crashes
- Not portable to VPS
- Not a production solution

**Verdict**: Rejected

### Option 2: systemd Service

Create a systemd unit file to run bot as a Linux service.

**Pros**:
- Native Linux integration
- Auto-restart built-in
- System-level logging
- No container overhead

**Cons**:
- Manual setup on each server
- System-level permissions required
- Different environment dev vs prod
- Harder to replicate exactly

**Verdict**: Good option, but more operational overhead

### Option 3: PM2 Process Manager

Use PM2 to manage the Python process.

**Pros**:
- Auto-restart on crashes
- Built-in monitoring
- Log management
- Easy to use

**Cons**:
- Requires Node.js for Python project
- Extra dependency to manage
- Less isolation than containers
- Overkill for single process

**Verdict**: Viable but not ideal for this use case

### Option 4: Docker + Docker Compose (CHOSEN)

Package bot as Docker container, orchestrate with Docker Compose.

**Pros**:
- Consistent environment (dev = prod)
- Auto-restart via `restart: unless-stopped`
- Volume mounts for data persistence
- Easy rollbacks (just rebuild previous version)
- Works on any VPS provider
- Industry standard tooling
- Isolated from host system

**Cons**:
- Learning curve for Docker
- Extra layer of abstraction
- Slightly slower startup
- Requires Docker on VPS

**Verdict**: Best balance of simplicity and production-readiness

## Decision Outcome

**Chosen option**: Docker + Docker Compose

### Implementation

```yaml
# docker-compose.yml
services:
  kato-bot:
    build: .
    restart: unless-stopped
    volumes:
      - ./data:/app/data
      - ./assets:/app/assets:ro
```

### Deployment Flow

1. Clone repo on VPS
2. Add `.env` file with Discord token
3. Run `docker-compose up -d --build`
4. Bot runs 24/7 with auto-restart

### Update Flow

1. `git pull` latest changes
2. `docker-compose up -d --build`
3. Docker rebuilds and restarts automatically

## Consequences

### Positive

- ✅ **Portability**: Works on Linode, DigitalOcean, AWS, anywhere Docker runs
- ✅ **Consistency**: Same Python version, dependencies, environment locally and prod
- ✅ **Reliability**: Auto-restart on crashes via restart policy
- ✅ **Simplicity**: Single `docker-compose up` command
- ✅ **Rollback**: Easy to revert to previous version
- ✅ **Documentation**: Docker is well-documented

### Negative

- ⚠️ **Complexity**: Team needs to understand Docker basics
- ⚠️ **Overhead**: Small memory/CPU overhead from container
- ⚠️ **Setup**: VPS must have Docker installed

### Neutral

- 📝 **Logging**: Need to use `docker-compose logs` instead of system logs
- 📝 **Debugging**: Need to exec into container for live debugging

## Compliance

- No compliance considerations for this project

## Validation

Success criteria:
- ✅ Bot runs 24/7 on VPS
- ✅ Survives bot crashes (auto-restarts)
- ✅ Survives server reboots (auto-starts)
- ✅ Database persists across restarts
- ✅ Updates deployed with single command

All criteria met in testing.

## Related Decisions

- [Architecture 003: Docker Deployment Strategy](../architecture/003-docker-deployment.md)

## Notes

### Why not Kubernetes?
- Overkill for single-instance bot
- Too complex for the benefit
- Consider if we need to scale to 1000+ guilds

### Why Docker Compose instead of plain Docker?
- Easier to manage environment variables
- Simpler volume mount syntax
- Can add services later (Redis cache, etc.)
- Standard practice for single-server deployments

### Future Considerations

If the bot scales:
- **Multi-instance**: Deploy to multiple servers with load balancer
- **Kubernetes**: For auto-scaling and advanced orchestration
- **Cloud-native**: AWS ECS, Google Cloud Run, etc.

For now, Docker Compose on a single VPS is the right level of complexity.
