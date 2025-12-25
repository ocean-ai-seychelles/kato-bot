.PHONY: help install test lint format clean run docker-build docker-up docker-down docker-logs pre-commit-install

help:
	@echo "Available commands:"
	@echo "  make install           - Install dependencies"
	@echo "  make test              - Run tests with coverage"
	@echo "  make lint              - Run linter checks"
	@echo "  make format            - Format code with ruff"
	@echo "  make clean             - Remove generated files and caches"
	@echo "  make run               - Run the bot locally"
	@echo "  make docker-build      - Build Docker image"
	@echo "  make docker-up         - Start bot with Docker Compose"
	@echo "  make docker-down       - Stop Docker containers"
	@echo "  make docker-logs       - View Docker logs"
	@echo "  make pre-commit-install - Install pre-commit hooks"

install:
	uv pip install -r pyproject.toml

test:
	rm -f data/dory.db
	uv run pytest tests/ -v --cov=bot --cov-report=term-missing

lint:
	uv run ruff check .

format:
	uv run ruff format .

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -f data/dory.db
	rm -f bot.log
	rm -f bot.pid

run:
	uv run python main.py

docker-build:
	docker-compose build

docker-up:
	./start-bot.sh

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

pre-commit-install:
	pre-commit install
