FROM python:3.11-slim

# Prevent Python from writing .pyc files to disk
ENV PYTHONDONTWRITEBYTECODE=1

# Force stdin, stdout, and stderr to be totally unbuffered
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy requirements files
COPY requirements.txt requirements-prod.txt ./

# Install python dependencies (default to full requirements)
# Note: If deploying to a memory-constrained container, you can change this to requirements-prod.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Expose port (7860 is default for Hugging Face Spaces)
EXPOSE 7860

# Start FastAPI server using uvicorn, reading from $PORT environment variable if defined, falling back to 7860
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
