FROM python:3.14.6-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd --system --gid 10001 build360 \
    && useradd --system --uid 10001 --gid build360 --home-dir /app build360

WORKDIR /app
COPY pyproject.toml ./
COPY build360 ./build360
COPY modules ./modules
COPY manage.py ./
COPY ops ./ops
RUN python -m pip install --upgrade pip \
    && python -m pip install ".[dev]" \
    && mkdir -p /app/.gunicorn \
    && chown build360:build360 /app/.gunicorn

USER build360
EXPOSE 8000
CMD ["gunicorn", "--bind=0.0.0.0:8000", "--workers=2", "--threads=4", "--access-logfile=-", "--error-logfile=-", "build360.wsgi:application"]

