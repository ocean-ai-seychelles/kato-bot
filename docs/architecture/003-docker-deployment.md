# Docker Deployment Strategy

**Date**: 2025-01 (Post Phase 3)
**Status**: Active
**Context**: Need the bot to run 24/7 without keeping developer laptop running.

## Problem

**Initial situation**: Bot only runs when `uv run main.py` is active on laptop

**Requirements**:
- 24/7 uptime
- Auto-restart on crashes
- Easy updates from git
- Simple deployment to VPS (Linode)
- Database persistence across restarts

## Options Considered

### 1. tmux/screen on Laptop
**Pros**: Simple, no new tools
**Cons**:
- Laptop must stay on 24/7
- Not portable to VPS
- No auto-restart on crashes

**Verdict**: ❌ Not suitable for production

### 2. systemd Service on VPS
**Pros**: Native Linux service, auto-restart, logging
**Cons**:
- Manual setup on each server
- System-level permissions required
- Harder to replicate locally

**Verdict**: ⚠️ Good option, but more ops overhead

### 3. PM2 (Process Manager)
**Pros**: Auto-restart, logging, monitoring
**Cons**:
- Node.js dependency for Python project
- Extra tooling to learn
- Not as isolated as containers

**Verdict**: ⚠️ Viable but not ideal

### 4. Docker + Docker Compose ✅
**Pros**:
- Isolated environment
- Same setup local and production
- Auto-restart built-in
- Easy rollbacks
- Volume mounts for persistence

**Cons**:
- Learning curve for Docker
- Extra layer of abstraction

**Verdict**: ✅ **Chosen** - Best balance of simplicity and production-readiness

## Solution: Docker with Docker Compose

### Dockerfile

```dockerfile
FROM python:3.13-slim
WORKDIR /app

# Install uv package manager
RUN pip install --no-cache-dir uv

# Install dependencies
COPY pyproject.toml ./
RUN uv pip install --system --no-cache -r pyproject.toml

# Copy application code
COPY . .

# Create data directory for database
RUN mkdir -p data

CMD ["python", "main.py"]
```

**Design choices**:
- `python:3.13-slim`: Minimal image, matches dev environment
- `--no-cache`: Smaller image size
- `uv pip install --system`: Install to system Python (no venv in container)
- `mkdir -p data`: Ensure database directory exists

### docker-compose.yml

```yaml
services:
  kato-bot:
    build: .
    container_name: kato-bot
    restart: unless-stopped
    volumes:
      - ./data:/app/data          # Database persistence
      - ./assets:/app/assets:ro   # Config files (read-only)
    environment:
      - PYTHONUNBUFFERED=1        # Real-time logging
```

**Key features**:
- `restart: unless-stopped`: Auto-restart on crashes
- Volume mounts: Data persists across container restarts
- `PYTHONUNBUFFERED=1`: See logs immediately

### .dockerignore

Exclude unnecessary files from Docker image:
```
__pycache__/
.venv/
.git/
tests/
*.md
data/*.db
```

**Benefits**: Faster builds, smaller images

## Deployment Workflow

### Initial Setup on VPS

```bash
# 1. Clone repo
git clone https://github.com/your-org/kato-bot.git
cd kato-bot

# 2. Add Discord token
echo "DISCORD_TOKEN=your_token_here" > assets/.env

# 3. Start bot
docker-compose up -d --build
```

### Updates

```bash
# 1. Pull latest code
git pull

# 2. Rebuild and restart
docker-compose up -d --build
```

**Zero-downtime updates** (future):
- Use blue-green deployment
- Or health checks + rolling updates

### Monitoring

```bash
# View logs
docker-compose logs -f

# Check status
docker-compose ps

# Restart bot
docker-compose restart
```

## File Structure

```
.
├── Dockerfile              # Container image definition
├── docker-compose.yml      # Orchestration config
├── .dockerignore          # Build exclusions
├── start-bot.sh           # Convenience script
└── DEPLOYMENT.md          # Detailed deployment guide
```

## Consequences

### Positive
- ✅ Consistent environment (dev = prod)
- ✅ Auto-restart on crashes
- ✅ Database persists across restarts
- ✅ Easy to replicate (works on any VPS)
- ✅ Simple updates (`git pull && docker-compose up -d --build`)
- ✅ Isolated from host system

### Negative
- ⚠️ Extra complexity (Docker layer)
- ⚠️ Slightly slower startup (container overhead)
- ⚠️ Need Docker installed on VPS

### Trade-offs Accepted
- Chose portability over simplicity (Docker vs systemd)
- Chose isolation over performance (container overhead acceptable)
- Chose standardization over customization (Docker standard practices)

## Deployment Options Matrix

| Method | 24/7 Uptime | Auto-restart | Easy Updates | Portability | Complexity |
|--------|-------------|--------------|--------------|-------------|------------|
| tmux   | ❌ (laptop) | ❌           | ❌           | ❌          | ⭐         |
| systemd| ✅          | ✅           | ⚠️           | ⚠️          | ⭐⭐       |
| PM2    | ✅          | ✅           | ✅           | ✅          | ⭐⭐       |
| Docker | ✅          | ✅           | ✅           | ✅          | ⭐⭐⭐     |

## Related Documents

- [Decision 001: Why Docker](../decisions/001-why-docker.md)

## Future Enhancements

### Considered for Later:
- **Health checks**: Container restarts if bot becomes unresponsive
- **Multi-stage builds**: Separate build and runtime stages (smaller image)
- **Docker secrets**: More secure token management
- **GitHub Actions + self-hosted runner**: Auto-deploy on push to main
- **Kubernetes**: If scaling to multiple instances needed
