FROM python:3.12.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.lock ./requirements.lock
RUN pip install --no-cache-dir --requirement requirements.lock

COPY . .
RUN useradd --create-home --uid 10001 appuser \
    && mkdir --parents data \
    && chown --recursive appuser:appuser /app

USER appuser
EXPOSE 8000

CMD ["python", "app.py"]
