# Simple Photo Tagger Makefile - РУССКАЯ ВЕРСИЯ

.PHONY: help build up down logs clean test tag-image tag-dir check-tags

# Показать доступные команды
help:
	@echo "🚀 Simple Photo Tagger (RUS) - Доступные команды:"
	@echo ""
	@echo "Основные команды:"
	@echo "  build      - Собрать Docker образ"
	@echo "  up         - Запустить все сервисы"
	@echo "  down       - Остановить все сервисы"
	@echo "  logs       - Показать логи приложения"
	@echo "  clean      - Очистить Docker образы и данные"
	@echo ""
	@echo "Тэггирование с параметрами:"
	@echo "  tag-image  FILE=path   - Тэгировать конкретный файл"
	@echo "  tag-dir    DIR=path    - Тэгировать конкретную папку"
	@echo "  search-tag TAG=тэг     - Поиск по русскому тэгу"
	@echo ""
	@echo "Тестирование (файлы по умолчанию):"
	@echo "  tag-image-test         - Тест тэггирования test.jpg"
	@echo "  tag-dir-test           - Тест тэггирования /app/photos"
	@echo "  check-tags             - Посмотреть доступные тэги"
	@echo ""
	@echo "Безопасность БД:"
	@echo "  db-check   - Проверить подключение к БД"
	@echo "  db-stats   - Статистика по AI тэгам"
	@echo "  db-health  - Здоровье базы данных"
	@echo ""
	@echo "Примеры с параметрами:"
	@echo "  make tag-image FILE=/app/photos/dog.jpg"
	@echo "  make tag-dir DIR=/app/photos/vacation TAGS=3"
	@echo "  make search-tag TAG=собака"
	@echo "  make get-tags FILE=/app/photos/cat.jpg"

# Собрать Docker образ
build:
	@echo "🔨 Сборка Docker образа..."
	docker-compose build

# Запустить все сервисы
up:
	@echo "🚀 Запуск сервисов..."
	docker-compose up -d
	@echo ""
	@echo "✅ Сервисы запущены!"
	@echo "📡 API: http://localhost:8000"
	@echo "📖 Документация: http://localhost:8000/docs"
	@echo "🏷️  Русские тэги: http://localhost:8000/tags/available"
	@echo ""

# Остановить все сервисы
down:
	@echo "⏹️  Остановка сервисов..."
	docker-compose down

# Показать логи
logs:
	@echo "📋 Логи приложения (Ctrl+C для выхода):"
	docker-compose logs -f photo-tagger

# Логи БД
logs-db:
	@echo "📋 Логи базы данных:"
	docker-compose logs postgres

# Очистить все
clean:
	@echo "🧹 Очистка Docker..."
	docker-compose down -v
	docker system prune -f
	@echo "✅ Очистка завершена"

# Тестовые команды
test:
	@echo "🏥 Проверка здоровья API..."
	@curl -s http://localhost:8000/health | python3 -m json.tool || echo "❌ API недоступен"

# Проверить доступные тэги
check-tags:
	@echo "🏷️  Доступные русские тэги:"
	@curl -s http://localhost:8000/tags/available | python3 -c "import sys, json; data=json.load(sys.stdin); print('Всего тэгов:', data['total_tags']); print('Примеры тэгов:'); [print(f'  {k} -> {v}') for k,v in list(data['sample_mapping'].items())]" 2>/dev/null || echo "❌ API недоступен"

# Тэггирование изображения (использование: make tag-image FILE=/app/photos/dog.jpg)
tag-image:
	@if [ -z "$(FILE)" ]; then \
		echo "Использование: make tag-image FILE=/app/photos/your_image.jpg"; \
		echo "Или для теста: make tag-image-test"; \
		exit 1; \
	fi
	@echo "Тэггирование изображения: $(FILE)"
	@curl -X POST "http://localhost:8000/tag/image" \
		-H "Content-Type: application/json" \
		-d '{"image_path": "$(FILE)", "top_k": $(or $(TAGS),5)}' \
		| python3 -c "import sys, json; data=json.load(sys.stdin); print('Файл:', data.get('image_path', '')); print('Тэги:', ', '.join(data.get('russian_tags', []))); print('Коэффициенты:', [f'{s:.3f}' for s in data.get('confidence_scores', [])]); print('Ошибка:', data.get('error', 'нет'))" 2>/dev/null || echo "Ошибка запроса к API"

# Тэггирование папки (использование: make tag-dir DIR=/app/photos/vacation)
tag-dir:
	@if [ -z "$(DIR)" ]; then \
		echo "Использование: make tag-dir DIR=/app/photos/your_folder"; \
		echo "Или для теста: make tag-dir-test"; \
		exit 1; \
	fi
	@echo "Тэггирование папки: $(DIR)"
	@curl -X POST "http://localhost:8000/tag/directory" \
		-H "Content-Type: application/json" \
		-d '{"directory_path": "$(DIR)", "top_k": $(or $(TAGS),5)}' \
		| python3 -c "import sys, json; data=json.load(sys.stdin); print('Запущена обработка:', data.get('message', '')); print('Папка:', data.get('directory', '')); print('Файлов найдено:', data.get('files_count', 0))" 2>/dev/null || echo "Ошибка запроса к API"

# Тестовые команды (используют файлы по умолчанию)
tag-image-test:
	@echo "Тестирование тэггирования изображения..."
	@echo "Проверяем наличие тестовых файлов в /app/photos"
	@curl -X POST "http://localhost:8000/tag/image" \
		-H "Content-Type: application/json" \
		-d '{"image_path": "/app/photos/test.jpg", "top_k": 5}' \
		| python3 -c "import sys, json; data=json.load(sys.stdin); print('Файл:', data.get('image_path', '')); print('Тэги:', ', '.join(data.get('russian_tags', []))); print('Ошибка:', data.get('error', 'нет'))" 2>/dev/null || echo "Ошибка: убедитесь что API запущен и файл /app/photos/test.jpg существует"

tag-dir-test:
	@echo "Тестирование тэггирования папки..."
	@curl -X POST "http://localhost:8000/tag/directory" \
		-H "Content-Type: application/json" \
		-d '{"directory_path": "/app/photos", "top_k": 5}' \
		| python3 -c "import sys, json; data=json.load(sys.stdin); print('Результат:', data.get('message', '')); print('Файлов:', data.get('files_count', 0))" 2>/dev/null || echo "Ошибка: убедитесь что API запущен и папка /app/photos доступна"

# Поиск по тэгу (использование: make search-tag TAG=собака)
search-tag:
	@if [ -z "$(TAG)" ]; then \
		echo "Использование: make search-tag TAG=ваш_тэг"; \
		echo "Примеры: make search-tag TAG=собака"; \
		echo "         make search-tag TAG=пейзаж"; \
		exit 1; \
	fi
	@echo "Поиск изображений по тэгу: $(TAG)"
	@curl -s "http://localhost:8000/search/$(TAG)" \
		| python3 -c "import sys, json; data=json.load(sys.stdin); print(f'Найдено: {data[\"found\"]} изображений'); [print(f'  {img[\"image_path\"]}') for img in data[\"images\"][:10]]" 2>/dev/null || echo "Тэг не найден или API недоступен"
get-tags:
	@if [ -z "$(FILE)" ]; then \
		echo "Использование: make get-tags FILE=/app/photos/your_image.jpg"; \
		exit 1; \
	fi
	@echo "Получение тэгов для: $(FILE)"
	@curl -s "http://localhost:8000/image/$(FILE)/tags" \
		| python3 -c "import sys, json; data=json.load(sys.stdin); print('Файл:', data.get('image_path', '')); print('Найдено:', 'да' if data.get('found') else 'нет'); print('Тэги:', ', '.join(data.get('russian_tags', [])) if data.get('found') else 'отсутствуют')" 2>/dev/null || echo "Ошибка запроса к API"

# Список файлов в примонтированной папке
list-photos:
	@echo "Содержимое папки /app/photos:"
	@docker exec simple_photo_tagger find /app/photos -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.webp" \) | head -20 2>/dev/null || echo "Контейнер не запущен или папка недоступна"
	@echo ""
	@echo "Для тэггирования используйте:"
	@echo "  make tag-image FILE=/app/photos/filename.jpg"

# Статистика по тэгам (топ популярных)
stats-tags:
	@echo "Статистика по популярным тэгам:"
	@curl -s "http://localhost:8000/stats" \
		| python3 -c "import sys, json; data=json.load(sys.stdin); print(f'Помеченных изображений: {data.get(\"total_tagged_images\", 0)}'); print(f'Всего доступно тэгов: {data.get(\"total_available_tags\", 0)}')" 2>/dev/null || echo "API недоступен"

# Тэггирование с кастомными тэгами (использование: make tag-custom FILE=/app/photos/dog.jpg CUSTOM_TAGS='["dog","cat","car"]')
tag-custom:
	@if [ -z "$(FILE)" ] || [ -z "$(CUSTOM_TAGS)" ]; then \
		echo "Использование: make tag-custom FILE=/app/photos/file.jpg CUSTOM_TAGS='[\"dog\",\"cat\",\"car\"]'"; \
		echo "Доступные английские тэги смотрите в документации"; \
		exit 1; \
	fi
	@echo "Тэггирование $(FILE) с кастомными тэгами: $(CUSTOM_TAGS)"
	@curl -X POST "http://localhost:8000/tag/image" \
		-H "Content-Type: application/json" \
		-d "{\"image_path\": \"$(FILE)\", \"use_all_tags\": false, \"custom_tags\": $(CUSTOM_TAGS), \"top_k\": $(or $(TAGS),5)}" \
		| python3 -c "import sys, json; data=json.load(sys.stdin); print('Результат:', ', '.join(data.get('russian_tags', [])))" 2>/dev/null || echo "Ошибка запроса"

# НОВЫЕ команды для работы с БД
db-check:
	@echo "🔗 Проверка подключения к БД..."
	@curl -s http://localhost:8000/health | python3 -c "import sys, json; data=json.load(sys.stdin); db=data['database']; print(f'Статус: {db[\"status\"]}'); print(f'Тип БД: {db[\"connection_type\"]}'); print(f'Записей: {db.get(\"total_records\", 0)}')" 2>/dev/null || echo "❌ API недоступен"

db-stats:
	@echo "📊 Статистика по AI тэгам..."
	@curl -s http://localhost:8000/stats | python3 -c "import sys, json; data=json.load(sys.stdin); print(f'Помеченных изображений: {data.get(\"total_tagged_images\", 0)}'); print(f'Таблица: {data.get(\"table_name\", \"N/A\")}'); print(f'Всего тэгов: {data.get(\"total_available_tags\", 0)}')" 2>/dev/null || echo "❌ API недоступен"

db-health:
	@echo "💊 Полная проверка здоровья..."
	@curl -s http://localhost:8000/health | python3 -m json.tool

# Зайти в контейнер (для отладки)
shell:
	@echo "🐚 Заходим в контейнер..."
	docker exec -it simple_photo_tagger /bin/bash

# Проверить примонтированные папки
check-mounts:
	@echo "📂 Проверяем примонтированные папки..."
	@echo "Папки в контейнере:"
	docker exec simple_photo_tagger ls -la /app/ 2>/dev/null || echo "❌ Контейнер не запущен"
	@echo ""
	@echo "Содержимое /app/photos:"
	docker exec simple_photo_tagger ls -la /app/photos/ 2>/dev/null || echo "❌ Папка /app/photos недоступна"

# Перезапуск только приложения (без БД)
restart-app:
	@echo "🔄 Перезапуск приложения..."
	docker-compose restart photo-tagger
	@sleep 5
	@make test

# Быстрая установка (первый запуск)
install:
	@echo "🚀 Быстрая установка Simple Photo Tagger с русскими тэгами..."
	@echo ""
	@echo "1. Отредактируйте docker-compose.yml - добавь пути к своим фоткам!"
	@echo "2. Затем выполните: make build && make up"
	@echo "3. Проверьте: make test && make check-tags"
	@echo ""
	@echo "Пример в docker-compose.yml:"
	@echo "volumes:"
	@echo "  - /home/user/Pictures:/app/photos:ro"
	@echo "  - /media/photos:/app/backup:ro"
	@echo ""
	@echo "🏷️ Особенности русской версии:"
	@echo "  ✅ Модель работает с английскими тэгами (лучше обучена)"
	@echo "  ✅ В БД сохраняются русские тэги"
	@echo "  ✅ Отдельная таблица ai_photo_tags (не мешает существующим данным)"
	@echo "  ✅ Поиск работает по русским тэгам"
