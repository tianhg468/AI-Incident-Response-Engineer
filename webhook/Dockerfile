FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml .
COPY agent/ ./agent/
COPY webhook/ ./webhook/
COPY mcp_servers/ ./mcp_servers/
COPY .env .env

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Expose webhook port
EXPOSE 8080

# Run the alert webhook server
CMD ["python", "-m", "webhook.alert_webhook"]
