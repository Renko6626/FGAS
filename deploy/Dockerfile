FROM python:3.13-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend backend
COPY docs/ai docs/ai
COPY alembic.ini alembic.ini
ARG FGAS_VERSION=dev
ARG FGAS_GIT_SHA=
ENV FGAS_VERSION=${FGAS_VERSION} FGAS_GIT_SHA=${FGAS_GIT_SHA}
CMD ["uvicorn", "backend.entrypoints.http:app", "--host", "0.0.0.0", "--port", "10622"]
