FROM python:3.11.14-slim-bookworm
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip==26.2.2 setuptools==84.2.1 wheel==0.48.0 && pip install --no-cache-dir -r requirements.txt
COPY backend/ .
RUN chmod +x entrypoint.sh
EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
