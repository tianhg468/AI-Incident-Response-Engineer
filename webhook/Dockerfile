FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including kubectl and AWS CLI
RUN apt-get update && apt-get install -y \
    git \
    curl \
    unzip \
    && ARCH=$(uname -m) && if [ "$ARCH" = "x86_64" ]; then ARCH="amd64"; elif [ "$ARCH" = "aarch64" ]; then ARCH="arm64"; fi \
    && curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/${ARCH}/kubectl" \
    && chmod +x kubectl \
    && mv kubectl /usr/local/bin/ \
    && AWSARCH=$(uname -m) && curl "https://awscli.amazonaws.com/awscli-exe-linux-${AWSARCH}.zip" -o "awscliv2.zip" \
    && unzip awscliv2.zip \
    && ./aws/install \
    && rm -rf aws awscliv2.zip \
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
