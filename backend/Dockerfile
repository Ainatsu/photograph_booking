FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    AUTO_RUN_MIGRATIONS=false

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
COPY backend/requirements-vision.txt /app/backend/requirements-vision.txt
ARG INSTALL_VISION_EMBEDDING=false
ARG INSTALL_LOCAL_EMBEDDING=true
RUN pip install --upgrade pip \
    && pip install -r /app/backend/requirements.txt \
    && if [ "$INSTALL_VISION_EMBEDDING" = "true" ] || [ "$INSTALL_LOCAL_EMBEDDING" = "true" ]; then pip install -r /app/backend/requirements-vision.txt; fi

COPY alembic.ini /app/alembic.ini
COPY backend /app/backend

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"]
