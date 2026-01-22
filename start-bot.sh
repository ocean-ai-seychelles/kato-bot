#!/bin/bash
# Quick start script for Kato bot using Docker

echo "Starting Kato Discord Bot..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if .env file exists
if [ ! -f "assets/.env" ]; then
    echo "Error: assets/.env not found. Please create it with your DISCORD_TOKEN."
    exit 1
fi

# Build and start
docker-compose up -d --build

echo ""
echo "Bot started! Use these commands:"
echo "  - View logs:    docker-compose logs -f"
echo "  - Stop bot:     docker-compose down"
echo "  - Restart bot:  docker-compose restart"
echo ""
