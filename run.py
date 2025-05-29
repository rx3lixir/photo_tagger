import uvicorn
import os
from pathlib import Path

# Загружаем .env файл если он есть
def load_env():
    env_file = Path('.env')
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key] = value

if __name__ == "__main__":
    # Загружаем переменные окружения
    load_env()
    
    # Запускаем сервер с базовыми настройками
    uvicorn.run(
        "api:app",  # модуль:приложение
        host="0.0.0.0",  # доступно извне
        port=8000,  # порт
        reload=True,  # автоперезагрузка при изменении кода
        log_level="info"  # уровень логгирования
    )
