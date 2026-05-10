FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
COPY src/ ./src/
RUN uv pip install --system --no-cache .

COPY alembic.ini ./
COPY src/leads_bot/db/migrations ./src/leads_bot/db/migrations
COPY data/profile.example.json ./data/
COPY scripts/ ./scripts/

RUN mkdir -p /app/data /app/logs

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

CMD ["sh", "-c", "alembic upgrade head && python -m leads_bot.main"]
