# Deployment Guide

This guide covers different ways to deploy the Dory bot for 24/7 uptime.

## Option 1: Docker (Recommended)

### Prerequisites
- Docker and Docker Compose installed
- Discord bot token in `assets/.env`

### Local Testing
```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Deploy to VPS/Cloud
1. Copy project to your server
2. Ensure `assets/.env` contains your `DISCORD_TOKEN`
3. Run:
   ```bash
   docker-compose up -d
   ```

The bot will:
- Auto-restart on crashes (`restart: unless-stopped`)
- Persist database in `./data/` directory
- Auto-start on server reboot (if Docker is configured to start on boot)

### Useful Commands
```bash
# Rebuild after code changes
docker-compose up -d --build

# View logs
docker-compose logs -f dory-bot

# Restart bot
docker-compose restart

# Stop bot
docker-compose down

# Check status
docker-compose ps
```

## Option 2: GitHub Actions (Self-Hosted Runner)

**Note:** GitHub-hosted runners have time limits. You need a self-hosted runner on a server.

### Setup Self-Hosted Runner
1. Go to your GitHub repo → Settings → Actions → Runners
2. Click "New self-hosted runner"
3. Follow instructions to install runner on your server
4. Add your `DISCORD_TOKEN` as a repository secret

### Deploy
- Push to `main` branch automatically deploys
- Or manually trigger from Actions tab

## Option 3: systemd (Linux VPS)

Create `/etc/systemd/system/dory-bot.service`:

```ini
[Unit]
Description=Dory Discord Bot
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/path/to/dory-bot
Environment="PATH=/path/to/dory-bot/.venv/bin:/usr/bin"
ExecStart=/path/to/dory-bot/.venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable dory-bot
sudo systemctl start dory-bot
sudo systemctl status dory-bot
```

## Option 4: Cloud Platforms

### Railway.app
1. Connect GitHub repo
2. Add `DISCORD_TOKEN` environment variable
3. Deploy automatically on push

### Render.com
1. New → Background Worker
2. Connect GitHub repo
3. Build command: `uv pip install -r pyproject.toml`
4. Start command: `python main.py`
5. Add `DISCORD_TOKEN` environment variable

### Fly.io
```bash
fly launch
fly secrets set DISCORD_TOKEN=your_token_here
fly deploy
```

## Monitoring

### Check if bot is online
- Look at Discord server - bot should show as online
- Check logs for any errors

### Docker logs
```bash
docker-compose logs -f --tail=100
```

### systemd logs
```bash
sudo journalctl -u dory-bot -f
```

## Updating the Bot

### Docker
```bash
git pull
docker-compose up -d --build
```

### systemd
```bash
git pull
sudo systemctl restart dory-bot
```

## Troubleshooting

### Bot not connecting
- Check `DISCORD_TOKEN` is set correctly
- Verify internet connection
- Check logs for error messages

### Database locked errors
- Ensure only one instance is running
- Check file permissions on `data/dory.db`

### Permission errors
- Verify bot has required Discord permissions
- Check role hierarchy in Discord server
