# Photo Tagger API

Автоматическое тэггирование фотографий с помощью CLIP модели и FastAPI. Система позволяет анализировать изображения, определять содержимое и сохранять результаты в PostgreSQL базе данных.

## 🚀 Возможности

- **Автоматическое тэггирование** изображений с помощью CLIP модели
- **Асинхронная обработка** больших объемов фотографий
- **RESTful API** с документацией Swagger
- **PostgreSQL** для хранения результатов
- **Docker** для простого развертывания базы данных
- **Извлечение EXIF** данных из фотографий
- **Пакетная обработка** директорий

## 📋 Требования

- Python 3.8+
- Docker и Docker Compose
- CUDA (опционально, для ускорения на GPU)

## 🛠 Установка

### 1. Клонирование и установка зависимостей

```bash
git clone <your-repo>
cd photo-tagger
```

```bash
# Создаем виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows

# Устанавливаем зависимости
pip install -r requirements.txt
```

### 2. Запуск PostgreSQL

```bash
# Запускаем базу данных в Docker
docker-compose up -d

# Проверяем что контейнер запустился
docker-compose ps
```

База данных будет доступна на `localhost:5432` с параметрами:
- **База:** `photo_archive`
- **Пользователь:** `postgres`
- **Пароль:** `postgres`

### 3. Запуск API

```bash
# Простой запуск
python run.py

# Или через uvicorn напрямую
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

API будет доступно по адресу: http://localhost:8000

## 📖 Использование

### Swagger UI

Откройте http://localhost:8000/docs для интерактивной документации API.

### Основные эндпоинты

#### 1. Тэггирование одного изображения

```bash
curl -X POST "http://localhost:8000/tag/image" \
  -H "Content-Type: application/json" \
  -d '{
    "image_path": "/path/to/your/image.jpg",
    "tags": ["cat", "dog", "landscape", "city", "food", "beach", "party"],
    "top_k": 4
  }'
```

**Ответ (только топ-4 тэга):**
```json
{
  "image_path": "/path/to/your/image.jpg",
  "tags": [
    ["landscape", 0.8945],
    ["city", 0.1234],
    ["beach", 0.0876],
    ["cat", 0.0543]
  ],
  "exif_datetime": "2024:05:15 14:30:22",
  "error": null
}
```

#### 2. Тэггирование директории

```bash
curl -X POST "http://localhost:8000/tag/directory" \
  -H "Content-Type: application/json" \
  -d '{
    "directory_path": "/path/to/photos/",
    "tags": ["cat", "dog", "landscape", "party", "food", "beach", "city"],
    "file_extensions": [".jpg", ".jpeg", ".png"],
    "top_k": 4
  }'
```

**Ответ:**
```json
{
  "message": "Запущена обработка 150 изображений",
  "directory": "/path/to/photos/",
  "files_count": 150
}
```

#### 3. Проверка здоровья API

```bash
curl http://localhost:8000/health
```

### Python пример

```python
import requests

# Тэггирование одного изображения
response = requests.post(
    "http://localhost:8000/tag/image",
    json={
        "image_path": "./images/my_photo.jpg",
        "tags": ["cat", "dog", "landscape", "city", "food", "beach", "party"],
        "top_k": 4  # Получим только 4 лучших тэга
    }
)

result = response.json()
print(f"Лучший тэг: {result['tags'][0][0]} ({result['tags'][0][1]:.3f})")
print(f"Всего найдено: {len(result['tags'])} тэгов")
```

## 🎯 Параметры тэггирования

### Тэги по умолчанию

Если не указать свои тэги, используются следующие:

```python
DEFAULT_TAGS = [
    "cat", "dog", "car", "landscape", "party",
    "food", "beach", "city", "children", "sport",
    "Victory Day", "veterans", "celebration", "military"
]
```

### Параметр top_k

- **По умолчанию:** `top_k = 4` (возвращаются только 4 лучших тэга)
- **Можно изменить:** от 1 до количества переданных тэгов
- **В базе сохраняются:** только выбранные топ-K тэгов

## 🗄 База данных

### Структура таблицы `tagged_images`

| Колонка | Тип | Описание |
|---------|-----|----------|
| `id` | SERIAL | Уникальный ID |
| `image_path` | VARCHAR(1000) | Путь к изображению |
| `tags` | JSONB | Тэги с вероятностями |
| `exif_datetime` | TIMESTAMP | Дата из EXIF |
| `created_at` | TIMESTAMP | Время первой обработки |
| `updated_at` | TIMESTAMP | Время последнего обновления |

### Пример запроса к БД

```sql
-- Поиск всех фотографий с котами
SELECT image_path, tags->>0 as best_tag 
FROM tagged_images 
WHERE tags @> '[{"tag": "cat"}]'::jsonb;

-- Статистика по тэгам
SELECT 
  jsonb_array_elements(tags)->>'tag' as tag,
  COUNT(*) as count
FROM tagged_images 
GROUP BY tag 
ORDER BY count DESC;
```

## ⚙️ Конфигурация

### Параметры базы данных

Измените в `database.py`:

```python
self.db_config = {
    'host': 'localhost',      # Хост PostgreSQL
    'port': 5432,            # Порт
    'user': 'postgres',      # Пользователь
    'password': 'postgres',  # Пароль
    'database': 'photo_archive'  # Имя базы
}
```

### Настройка модели CLIP

В `tagger.py` можно изменить модель:

```python
# Доступные модели: ViT-B-32, ViT-B-16, ViT-L-14
model, _, preprocess = open_clip.create_model_and_transforms(
    'ViT-L-14',  # Более точная, но медленная модель
    pretrained='openai',
    device=self.device
)
```

### Размер пакета обработки

В `api.py` настройте размер пакета:

```python
batch_size = 10  # Уменьшите для слабых машин, увеличьте для мощных
```

## 🔧 Troubleshooting

### Проблема: "CUDA out of memory"

```python
# В tagger.py измените на CPU
tagger = CLIPTagger(device="cpu")
```

### Проблема: Медленная обработка

1. **Используйте GPU:** Установите CUDA и PyTorch с GPU поддержкой
2. **Увеличьте batch_size:** В `api.py` увеличьте до 20-50
3. **Используйте меньшую модель:** ViT-B-32 вместо ViT-L-14

### Проблема: "Connection refused" к PostgreSQL

```bash
# Проверьте статус контейнера
docker-compose ps

# Перезапустите базу данных
docker-compose down
docker-compose up -d

# Проверьте логи
docker-compose logs postgres
```

### Проблема: Большие изображения

Добавьте ресайз в `image_utils.py`:

```python
def load_image(image_path: str) -> Image.Image:
    img = Image.open(image_path)
    # Ресайз больших изображений
    if img.size[0] > 2048 or img.size[1] > 2048:
        img.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
    return img
```

## 📊 Производительность

### Тестовые результаты

| Конфигурация | Изображений/сек | Примечание |
|--------------|-----------------|------------|
| CPU (Intel i7) | ~2-3 | Медленно |
| GPU (RTX 3060) | ~15-20 | Рекомендуется |
| GPU (RTX 4090) | ~40-50 | Быстро |

### Оптимизация

1. **GPU обязательно** для больших объемов
2. **Batch обработка** - не отправляйте изображения по одному
3. **SSD диск** для быстрого чтения изображений
4. **Достаточно RAM** - модель занимает ~2-4 ГБ

## 🏗 Архитектура

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   FastAPI       │    │   CLIPTagger     │    │   PostgreSQL    │
│                 │    │                  │    │                 │
│ • HTTP Routes   │───▶│ • Image Loading  │    │ • Tagged Images │
│ • Async Tasks   │    │ • CLIP Model     │    │ • EXIF Data     │
│ • Background    │    │ • Tag Inference  │    │ • Search Index  │
│   Processing    │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                        ▲
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                  │
                            ┌─────▼──────┐
                            │ File System│
                            │   Images   │
                            └────────────┘
```

## 📝 TODO / Roadmap

- [ ] **Web интерфейс** для загрузки изображений
- [ ] **Поиск по тэгам** через API
- [ ] **Статистика и аналитика** 
- [ ] **Дедупликация** похожих изображений
- [ ] **Пользовательские модели** CLIP
- [ ] **Кэширование** результатов
- [ ] **Мониторинг** производительности

## 📄 Лицензия

MIT License - используйте как хотите!

## 🤝 Поддержка

Если что-то не работает:

1. Проверьте логи: `docker-compose logs` и логи API
2. Убедитесь что все зависимости установлены
3. Проверьте свободное место на диске (база данных растет)
4. Для GPU проблем - проверьте CUDA drivers

---

**Готово к продакшену?** Добавьте переменные окружения, HTTPS, мониторинг и бэкапы! 🚀
