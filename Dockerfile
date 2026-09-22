FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first so the layer is cached across code changes.
COPY pyproject.toml README.md ./
COPY bot ./bot
RUN pip install --no-cache-dir .

# The bot needs no write access anywhere: it stores nothing.
RUN useradd --create-home --uid 10001 app
USER app

CMD ["python", "-m", "bot.main", "--polling"]
