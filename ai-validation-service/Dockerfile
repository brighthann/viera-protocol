FROM python:3.12.6-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    clamav \
    clamav-daemon \
    clamav-freshclam \
    nodejs \
    npm \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install ESLint globally
RUN npm install -g eslint eslint-plugin-security

# Update ClamAV virus database
RUN freshclam

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Start ClamAV daemon and FastAPI
CMD ["sh", "-c", "clamd & uvicorn app.main:app --host 0.0.0.0 --port 8000"]