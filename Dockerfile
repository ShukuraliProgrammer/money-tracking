FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY alembic.ini .
COPY migrations ./migrations
COPY app ./app

# Bot root bo'lmagan foydalanuvchi nomidan ishlaydi; SQLite fayli /app/data ichida turadi.
RUN useradd --create-home --uid 10001 bot \
    && mkdir -p /app/data \
    && chown -R bot:bot /app/data
USER bot
VOLUME ["/app/data"]

# Migratsiyalar ishga tushishda avtomatik bajariladi (app/main.py).
CMD ["python", "-m", "app.main"]
