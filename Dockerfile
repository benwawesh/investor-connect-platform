# Use Python 3.12 slim image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=investor_platform.settings

# Set work directory
WORKDIR /app

# Install system dependencies (as root)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        build-essential \
        libpq-dev \
        git \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . /app/

# Create static directory
RUN mkdir -p /app/static

# Create media directory for uploads
RUN mkdir -p /app/media

# Collect static files
RUN python manage.py collectstatic --noinput || true

# Create non-root user for security (MOVE THIS TO THE END)
RUN adduser --disabled-password --gecos '' appuser \
    && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8080

# Default command
CMD ["uvicorn", "investor_platform.asgi:application", "--host", "0.0.0.0", "--port", "8080"]