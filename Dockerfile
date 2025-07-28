# Use Python 3.9 slim image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml and README.md for dependency management
COPY pyproject.toml README.md ./

# Install Python dependencies using pip
RUN pip install --upgrade pip && \
    pip install -e . && \
    pip install pytest pytest-asyncio pytest-cov httpx

# Copy application code
COPY . .

# Create non-root user
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "deal_health_service.api:app", "--host", "0.0.0.0", "--port", "8000"] 