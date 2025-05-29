# Simple Photo Tagger Makefile

.PHONY: help build up down logs clean test tag-image tag-dir

# Показать доступные команды
help:
	@echo "🚀 Simple Photo Tagger - Доступные команды:"
	@echo ""
	@echo "Основные команды:"
	@echo "  build      - Собрать Docker образ"
	@echo "  up         - Запустить все сервисы"
	@echo "  down       - Остановить все сервисы"
	@echo "  logs       - Показать логи приложения"
	@echo "  clean      - Очистить Docker образы и данные"
	@echo ""
	@echo "Тестирование тэггера:"
	@echo "  test       - Проверить здоровье API"
	@echo "  tag-image  - Тест тэггирования одной фотки"
	@echo "  tag-dir    - Тест тэггирования папки"
	@echo ""
	@echo "Примеры:"
	@echo "  make up           # Запустить тэггер"
	@echo "  make tag-image    # Протестировать тэггирование"
	@echo "  make logs         # Посмотреть что происходит"

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

# Тест тэггирования изображения (нужно создать тестовую фотку)
tag-image:
	@echo "🏷️  Тестируем тэггирование изображения..."
	@echo "Убедись что у тебя есть фотка в примонтированной папке!"
	@echo ""
	curl -X POST "http://localhost:8000/tag/image" \
		-H "Content-Type: application/json" \
		-d '{"image_path": "/app/photos/test.jpg", "top_k": 3}' \
		| python3 -m json.tool

# Тест тэггирования папки
tag-dir:
	@echo "📁 Тестируем тэггирование папки..."
	curl -X POST "http://localhost:8000/tag/directory" \
		-H "Content-Type: application/json" \
		-d '{"directory_path": "/app/photos", "top_k": 3}' \
		| python3 -m json.tool



# Зайти в контейнер (для отладки)
shell:
	@echo "🐚 Заходим в контейнер..."
	docker exec -it simple_photo_tagger /bin/bash

# Проверить примонтированные папки
check-mounts:
	@echo "📂 Проверяем примонтированные папки..."
	@echo "Папки в контейнере:"
	docker exec simple_photo_tagger ls -la /app/
	@echo ""
	@echo "Содержимое /app/photos:"
	docker exec simple_photo_tagger ls -la /app/photos/ || echo "❌ Папка /app/photos недоступна"

# Перезапуск только приложения (без БД)
restart-app:
	@echo "🔄 Перезапуск приложения..."
	docker-compose restart photo-tagger
	@sleep 5
	@make test

# Быстрая установка (первый запуск)
install:
	@echo "Быстрая установка Simple Photo Tagger..."
	@echo ""
	@echo "1. Отредактируйте docker-compose.yml - добавь пути к своим фоткам!"
	@echo "2. Затем выполните: make build && make up"
	@echo ""
	@echo "Пример в docker-compose.yml:"
	@echo "volumes:"
	@echo "  - /home/user/Pictures:/app/photos:ro"
	@echo "  - /media/photos:/app/backup:ro"
