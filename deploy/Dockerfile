FROM python:3.13-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend backend
CMD ["sh", "-c", "python -m backend.application.initialize && uvicorn backend.entrypoints.http:app --host 0.0.0.0 --port 8000"]
