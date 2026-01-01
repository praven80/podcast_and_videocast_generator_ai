FROM --platform=linux/amd64 python:3.11.4-slim

RUN apt-get update && apt-get install -y curl

# Install system dependencies (including ffmpeg)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /tmp/doctalk && \
    chmod 777 /tmp/doctalk

WORKDIR /app

# Copy requirements first (for better caching)
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY app.py .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]