FROM python:3.12-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir .

# Create data directory
RUN mkdir -p /app/data

# Expose port (for future HTTP transport)
EXPOSE 8080

# Run AgentEvolution
CMD ["agentevolution"]
