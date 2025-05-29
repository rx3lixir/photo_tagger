# Используем Python 3.11 slim в качестве базового образа
FROM python:3.11-slim

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем только requirements.txt на первом этапе — для кэширования pip
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# Копируем остальной код приложения
COPY . .

# Создаем директорию для логов
RUN mkdir -p /app/logs

# Открываем порт для API
EXPOSE 8000

# Запускаем приложение
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
