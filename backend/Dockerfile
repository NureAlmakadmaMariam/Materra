# Використовуємо офіційний легкий образ Python
FROM python:3.11-slim

# Налаштування для коректного виводу логів Python у консоль Docker
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# За замовчуванням образ запускається з production-налаштуваннями (DEBUG вимкнено);
# docker-compose для локальної розробки перевизначає їх на development
ENV DJANGO_SETTINGS_MODULE=materra.settings.production

# Встановлюємо системні залежності для збирання пакетів та шрифтів (для ReportLab)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    fonts-dejavu-core \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Робоча директорія всередині контейнера, де буде жити бекенд
WORKDIR /app

# Спочатку копіюємо requirements і встановлюємо їх (це пришвидшує наступні збірки завдяки кешу Docker)
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо весь вміст папки backend в робочу директорію /app
COPY . /app/

# Відкриваємо порт для Django
EXPOSE 8000

# Команда запуску за замовчуванням
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]