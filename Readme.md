# Simple Photo Tagger

Автоматическое тэггирование фотографий с помощью CLIP модели. Определяет содержимое изображений и сохраняет русские тэги в базу данных для удобного поиска.

## Возможности

- **Автоматическое тэггирование** изображений с помощью CLIP модели
- **Русские тэги** для удобного поиска (модель работает с английскими, в БД сохраняются русские)
- **Безопасная работа с существующей БД** - использует отдельную таблицу `ai_photo_tags`
- **Пакетная обработка** целых директорий с фотографиями
- **RESTful API** с документацией Swagger
- **Поиск по тэгам** через веб-интерфейс или API
- **Поддержка PostgreSQL, MySQL, SQLite**

## Требования

- Python 3.8+
- Docker и Docker Compose
- CUDA (опционально, для ускорения на GPU)

## Быстрый старт

### 1. Клонирование проекта

```bash
git clone https://github.com/rx3lixir/photo_tagger
cd photo-tagger
```

### 2. Настройка docker-compose.yml

Отредактируйте файл `docker-compose.yml`, указав путь к вашим фотографиям:

```yaml
services:
  photo-tagger:
    # ... другие настройки
    volumes:
      # ВАЖНО: Замените на свой путь к фотографиям
      - /home/user/Pictures:/app/photos:ro
      # Можно добавить несколько папок:
      # - /media/backup/photos:/app/backup:ro
```

**Важно**: Используйте абсолютные пути к папкам с фотографиями. Флаг `:ro` означает read-only (безопасность).

### 3. Запуск

```bash
# Собираем и запускаем
make build
make up

# Или одной командой
docker-compose up --build -d
```

### 4. Ожидание загрузки модели

После запуска контейнера **подождите 2-5 минут** - CLIP модель загружается при первом запуске:

```bash
# Смотрим логи загрузки
make logs

# Ожидаем сообщения:
# "Загрузка CLIP модели..."
# "Модель CLIP успешно загружена за X.XX секунд"
# "API успешно запущен!"
```

### 5. Проверка работоспособности

```bash
# Проверяем что API запущен
make test

# Смотрим доступные тэги
make check-tags

# Тестируем на одной фотографии
make tag-image
```

## Использование

### Веб-интерфейс

После запуска доступны:
- **API**: http://localhost:8000
- **Swagger документация**: http://localhost:8000/docs
- **Список тэгов**: http://localhost:8000/tags/available

### Тэггирование через Makefile

```bash
# Конкретный файл
make tag-image FILE=/app/photos/dog.jpg

# Конкретная папка  
make tag-dir DIR=/app/photos/vacation

# С указанием количества тэгов
make tag-image FILE=/app/photos/cat.jpg TAGS=3

# Поиск по тэгу
make search-tag TAG=собака

# Получить существующие тэги
make get-tags FILE=/app/photos/dog.jpg

# Тестовые команды (файлы по умолчанию)
make tag-image-test
make tag-dir-test
```

### Прямые API запросы

#### Тэггирование одного изображения

```bash
curl -X POST "http://localhost:8000/tag/image" \
  -H "Content-Type: application/json" \
  -d '{
    "image_path": "/app/photos/my_photo.jpg",
    "top_k": 5
  }'
```

Ответ:
```json
{
  "image_path": "/app/photos/my_photo.jpg",
  "russian_tags": ["собака", "животное", "домашнее_животное", "портрет", "город"],
  "confidence_scores": [0.8945, 0.7234, 0.6123, 0.4567, 0.3821]
}
```

#### Тэггирование директории

```bash
curl -X POST "http://localhost:8000/tag/directory" \
  -H "Content-Type: application/json" \
  -d '{
    "directory_path": "/app/photos",
    "top_k": 5
  }'
```

#### Поиск по тэгу

```bash
curl "http://localhost:8000/search/собака"
```

### Python пример

```python
import requests

# Тэггирование изображения
response = requests.post(
    "http://localhost:8000/tag/image",
    json={
        "image_path": "/app/photos/dog.jpg",
        "top_k": 5
    }
)

result = response.json()
print(f"Найдены тэги: {result['russian_tags']}")

# Поиск изображений с собаками
search = requests.get("http://localhost:8000/search/собака")
images = search.json()
print(f"Найдено {images['found']} изображений с собаками")
```

## Поддерживаемые тэги

Система поддерживает **300+ тэгов** в различных категориях:

- **Животные**: собака, кошка, птица, дикая_природа
- **Природа**: пейзаж, лес, гора, озеро, пляж
- **Люди**: дети, семья, портрет, группа
- **Транспорт**: автомобиль, автобус, поезд, самолет
- **Архитектура**: здание, город, мост, церковь
- **События**: праздник, свадьба, спорт, концерт
- **И многое другое...**

Полный список доступен по адресу: http://localhost:8000/tags/available

## База данных

### Автоматическая настройка

При первом запуске автоматически создается таблица `ai_photo_tags`:

```sql
CREATE TABLE ai_photo_tags (
    id SERIAL PRIMARY KEY,
    image_path VARCHAR(1000) NOT NULL UNIQUE,
    ai_tags JSONB NOT NULL
);
```

### Безопасность

- **Отдельная таблица** - не влияет на существующие данные
- **Только добавление тэгов** - никакие данные не удаляются
- **Проверка существующих таблиц** при запуске

### Поддерживаемые БД

- **PostgreSQL** (по умолчанию)
- **MySQL/MariaDB**
- **SQLite**

Настройки в `.env` файле или переменных окружения.

## Конфигурация

### Переменные окружения

```bash
# Тип базы данных
DB_TYPE=postgresql

# PostgreSQL (по умолчанию)
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=photo_archive

# Для MySQL измените DB_TYPE=mysql
# Для SQLite измените DB_TYPE=sqlite и укажите DB_PATH
```

### Настройка производительности

В файле `api.py` можно изменить:

```python
batch_size = 5  # Размер пакета для обработки
top_k = 5       # Количество тэгов по умолчанию
```

Для слабых машин уменьшите `batch_size` до 1-2.
Для мощных машин можно увеличить до 10-20.

## Производительность

### Скорость обработки

| Конфигурация | Изображений/сек | Время загрузки модели |
|--------------|-----------------|----------------------|
| CPU (Intel i7) | 2-3 | 3-5 минут |
| GPU (RTX 3060) | 15-20 | 1-2 минуты |
| GPU (RTX 4090) | 40-50 | 30-60 секунд |

### Использование ресурсов

- **RAM**: ~2-4 ГБ для модели + изображения
- **Диск**: ~500 МБ для модели
- **VRAM**: ~1-2 ГБ на GPU

## Troubleshooting

### API недоступен

```bash
# Проверьте логи
make logs

# Убедитесь что модель загрузилась
# Ищите сообщение: "API успешно запущен!"
```

### Медленная работа

1. **Используйте GPU** - установите CUDA драйверы
2. **Уменьшите batch_size** в `api.py`
3. **Освободите RAM** - закройте другие приложения

### Ошибка "CUDA out of memory"

Отредактируйте `tagger.py`:
```python
# Принудительно используем CPU
tagger = CLIPTagger(device="cpu")
```

### Проблемы с базой данных

```bash
# Проверьте статус БД
make db-check

# Перезапустите БД
make down && make up

# Посмотрите логи БД
make logs-db
```

### Изображения не найдены

1. Проверьте пути в `docker-compose.yml`
2. Убедитесь что используете абсолютные пути
3. Проверьте права доступа к папкам

```bash
# Проверьте примонтированные папки
make check-mounts
```

## Полезные команды

```bash
# Основные
make up           # Запустить сервисы
make down         # Остановить сервисы
make logs         # Посмотреть логи
make test         # Проверить здоровье

# Тэггирование с параметрами
make tag-image FILE=/app/photos/dog.jpg         # Конкретный файл
make tag-dir DIR=/app/photos/vacation TAGS=3    # Конкретная папка
make get-tags FILE=/app/photos/cat.jpg          # Получить тэги

# Тестовые команды
make tag-image-test    # Тест на test.jpg
make tag-dir-test      # Тест на /app/photos
make check-tags        # Список тэгов

# Поиск и статистика
make search-tag TAG=собака  # Поиск по тэгу
make list-photos           # Файлы в папке
make stats-tags            # Статистика

# База данных
make db-check     # Проверить БД
make db-stats     # Статистика
make db-health    # Полная проверка

# Обслуживание
make clean        # Очистить Docker
make restart-app  # Перезапустить только API
make shell        # Зайти в контейнер
```

## Архитектура

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   FastAPI       │    │   CLIP Model     │    │   PostgreSQL    │
│                 │    │                  │    │                 │
│ • HTTP Routes   │───▶│ • English Tags   │    │ • Russian Tags  │
│ • Async Tasks   │    │ • Image Analysis │    │ • Search Index  │
│ • Tag Translation│   │ • GPU/CPU        │    │ • Safe Storage  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                        │
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                  │
                            ┌─────▼──────┐
                            │   Photos   │
                            │ (mounted)  │
                            └────────────┘
```

## Поддержка

При возникновении проблем:

1. Проверьте логи: `make logs`
2. Убедитесь что модель загрузилась полностью
3. Проверьте пути к фотографиям в `docker-compose.yml`
4. Проверьте свободное место на диске (модель занимает ~500 МБ)

Для отладки используйте команду `make shell` чтобы зайти внутрь контейнера.
