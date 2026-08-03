FROM python:3.11-slim

# Prevent Python from writing .pyc files to disk
ENV PYTHONDONTWRITEBYTECODE=1

# Force stdin, stdout, and stderr to be totally unbuffered
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy only the files needed for installation and execution
COPY requirements.txt rank.py ./

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Define the default command to run the script
CMD ["python", "rank.py", "--candidates", "candidates.jsonl.gz"]
