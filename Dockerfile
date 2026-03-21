FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create a directory for the SQLite database (can be mounted as a volume)
RUN mkdir -p /data
ENV DATABASE_PATH=/data/chatbot.db

# Expose port
EXPOSE 8000

# Run with gunicorn (production WSGI server)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120", "app:app"]
