FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system meetinghq && adduser --system --ingroup meetinghq meetinghq

COPY apps/api/pyproject.toml /app/pyproject.toml
COPY apps/api/src /app/src
RUN pip install --upgrade pip && pip install .

COPY apps/api/alembic.ini /app/alembic.ini
COPY apps/api/alembic /app/alembic
COPY apps/api/scripts /app/scripts
COPY infrastructure/api/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && chown -R meetinghq:meetinghq /app

USER meetinghq
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "meetinghq_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
