# Use Python 3.13 slim image
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install uv for dependency management
RUN pip install --no-cache-dir uv

# Copy dependency files (including lock file for reproducible builds)
COPY pyproject.toml uv.lock ./

# Install dependencies using uv with locked versions
RUN uv pip install --system --no-cache -r pyproject.toml

# Copy application code
COPY . .

# Create data directory for SQLite database
RUN mkdir -p data

# Run the bot
CMD ["python", "main.py"]
