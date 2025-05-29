# Photo Tagger Makefile

.PHONY: help build up down logs clean test

# Показать доступные команды
help:
	@echo "Доступные команды:"
	@echo "  build   - Собрать Docker образ"
	@echo "  up      - Запустить все сервисы"
	@echo "  down    - Остановить все сервисы"
	@echo "  logs    - Показать логи приложения"
	@echo "  clean   - Очистить Docker образы и volumes"
	@echo "  test    - Тестовый запрос к API"

# Собрать Docker образ
build:
	docker-compose build

# Запустить все сервисы
up:
	docker-compose up -d
	@echo "Сервисы запущены!"
	@echo "API: http://localhost:8000"
	@echo "Swagger: http://localhost:8000/docs"

# Остановить все сервисы
down:
	docker-compose down

# Показать логи
logs:
	docker-compose logs -f photo-tagger

# Очистить все
clean:
	docker-compose down -v
	docker system prune -f

# Тестовый запрос
test:
	@echo "Тестируем health check..."
	curl -s http://localhost:8000/health | python -m json.tool
