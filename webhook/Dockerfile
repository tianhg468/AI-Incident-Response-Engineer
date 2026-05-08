FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (cached layer)
RUN apt-get update && apt-get install -y \
    git \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install kubectl (cached layer - only rebuilds if kubectl version changes)
RUN ARCH=$(uname -m) && if [ "$ARCH" = "x86_64" ]; then ARCH="amd64"; elif [ "$ARCH" = "aarch64" ]; then ARCH="arm64"; fi \
    && curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/${ARCH}/kubectl" \
    && chmod +x kubectl \
    && mv kubectl /usr/local/bin/

# Install AWS CLI (cached layer - only rebuilds if AWS CLI version changes)
RUN AWSARCH=$(uname -m) && curl "https://awscli.amazonaws.com/awscli-exe-linux-${AWSARCH}.zip" -o "awscliv2.zip" \
    && unzip awscliv2.zip \
    && ./aws/install \
    && rm -rf aws awscliv2.zip

# Copy only dependency files first (for better layer caching)
COPY pyproject.toml .

# Install Python dependencies from pyproject.toml BEFORE copying code
# This layer only rebuilds when dependencies change, not when code changes
RUN pip install --no-cache-dir \
    flask \
    python-dotenv \
    requests \
    langgraph \
    langgraph-checkpoint-sqlite \
    langchain \
    langchain-anthropic \
    pyyaml

# NOW copy the application code (this changes frequently)
# Code changes won't trigger dependency reinstallation
COPY agent/ ./agent/
COPY webhook/ ./webhook/
COPY mcp_servers/ ./mcp_servers/
COPY .env .env

# Expose webhook port
EXPOSE 8080

# Run the unified webhook server (alerts + Slack)
CMD ["python", "-m", "webhook.unified_webhook"]
