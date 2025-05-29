import json
import logging
import os
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime

# Пробуем импортировать разные драйверы
db_driver = None
db_type = None

try:
    import asyncpg
    db_driver = asyncpg
    db_type = "postgresql"
    logger = logging.getLogger(__name__)
    logger.info("Используется PostgreSQL драйвер")
except ImportError:
    try:
        import aiomysql
        db_driver = aiomysql
        db_type = "mysql"
        logger = logging.getLogger(__name__)
        logger.info("Используется MySQL/MariaDB драйвер")
    except ImportError:
        try:
            import aiosqlite
            db_driver = aiosqlite
            db_type = "sqlite"
            logger = logging.getLogger(__name__)
            logger.info("Используется SQLite драйвер")
        except ImportError:
            raise ImportError("Не найден ни один поддерживаемый драйвер БД. Установите asyncpg, aiomysql или aiosqlite")

logger = logging.getLogger(__name__)

class DatabaseManager:
    """
    Универсальный менеджер для работы с разными типами баз данных.
    Поддерживает PostgreSQL, MySQL/MariaDB и SQLite.
    """
    
    def __init__(self):
        """Инициализация менеджера БД"""
        self.pool = None
        self.connection = None  # Для SQLite
        self.db_type = db_type
        
        # Параметры подключения из переменных окружения
        self.db_config = self._get_db_config()
        
        logger.info(f"Тип БД: {self.db_type}")
        logger.info(f"Подключение: {self.db_config.get('host', 'localhost')}:{self.db_config.get('port', 'N/A')}")
    
    def _get_db_config(self) -> Dict[str, Any]:
        """Получение конфигурации БД из переменных окружения"""
        db_type_env = os.getenv('DB_TYPE', 'postgresql').lower()
        
        if db_type_env in ['postgres', 'postgresql'] and self.db_type == "postgresql":
            return {
                'host': os.getenv('DB_HOST', 'localhost'),
                'port': int(os.getenv('DB_PORT', '5432')),
                'user': os.getenv('DB_USER', 'postgres'),
                'password': os.getenv('DB_PASSWORD', 'postgres'),
                'database': os.getenv('DB_NAME', 'photo_archive')
            }
        elif db_type_env in ['mysql', 'mariadb'] and self.db_type == "mysql":
            return {
                'host': os.getenv('DB_HOST', 'localhost'),
                'port': int(os.getenv('DB_PORT', '3306')),
                'user': os.getenv('DB_USER', 'root'),
                'password': os.getenv('DB_PASSWORD', 'password'),
                'db': os.getenv('DB_NAME', 'photo_archive')  # MySQL использует 'db' вместо 'database'
            }
        else:  # SQLite
            return {
                'database': os.getenv('DB_PATH', './photo_archive.db')
            }
    
    async def init_database(self):
        """Инициализация подключения к БД"""
        try:
            if self.db_type == "postgresql":
                self.pool = await asyncpg.create_pool(**self.db_config, min_size=1, max_size=10)
                logger.info("PostgreSQL подключение установлено")
                
            elif self.db_type == "mysql":
                self.pool = await aiomysql.create_pool(**self.db_config, minsize=1, maxsize=10)
                logger.info("MySQL/MariaDB подключение установлено")
                
            elif self.db_type == "sqlite":
                self.connection = await aiosqlite.connect(self.db_config['database'])
                logger.info(f"SQLite подключение установлено: {self.db_config['database']}")
            
            # Создаем таблицы
            await self._create_tables()
            
        except Exception as e:
            logger.error(f"Ошибка подключения к БД: {e}")
            raise
    
    async def _create_tables(self):
        """Создание таблиц с учетом типа БД"""
        
        if self.db_type == "postgresql":
            create_table_query = """
            CREATE TABLE IF NOT EXISTS tagged_images (
                id SERIAL PRIMARY KEY,
                image_path VARCHAR(1000) NOT NULL UNIQUE,
                tags JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_image_path ON tagged_images(image_path);
            CREATE INDEX IF NOT EXISTS idx_tags ON tagged_images USING GIN(tags);
            """
            
        elif self.db_type == "mysql":
            create_table_query = """
            CREATE TABLE IF NOT EXISTS tagged_images (
                id INT AUTO_INCREMENT PRIMARY KEY,
                image_path VARCHAR(1000) NOT NULL UNIQUE,
                tags JSON NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_image_path ON tagged_images(image_path);
            """
            
        else:  # SQLite
            create_table_query = """
            CREATE TABLE IF NOT EXISTS tagged_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_path TEXT NOT NULL UNIQUE,
                tags TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_image_path ON tagged_images(image_path);
            """
        
        await self._execute_query(create_table_query)
        logger.info("Таблицы созданы/проверены")
    
    async def _execute_query(self, query: str, *args):
        """Универсальное выполнение запросов"""
        if self.db_type == "postgresql":
            async with self.pool.acquire() as connection:
                return await connection.execute(query, *args)
                
        elif self.db_type == "mysql":
            async with self.pool.acquire() as connection:
                async with connection.cursor() as cursor:
                    await cursor.execute(query, args)
                    await connection.commit()
                    
        else:  # SQLite
            await self.connection.execute(query, args)
            await self.connection.commit()
    
    async def save_image_tags(self, image_path: str, tags: List[Tuple[str, float]]):
        """Сохранение тэгов изображения"""
        try:
            # Преобразуем тэги в простой список строк
            tag_names = [tag for tag, _ in tags]
            tags_json = json.dumps(tag_names)
            
            if self.db_type == "postgresql":
                query = """
                INSERT INTO tagged_images (image_path, tags, updated_at)
                VALUES ($1, $2, CURRENT_TIMESTAMP)
                ON CONFLICT (image_path) 
                DO UPDATE SET 
                    tags = EXCLUDED.tags,
                    updated_at = CURRENT_TIMESTAMP
                """
                await self._execute_query(query, image_path, tags_json)
                
            elif self.db_type == "mysql":
                query = """
                INSERT INTO tagged_images (image_path, tags)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE 
                    tags = VALUES(tags),
                    updated_at = CURRENT_TIMESTAMP
                """
                await self._execute_query(query, image_path, tags_json)
                
            else:  # SQLite
                query = """
                INSERT OR REPLACE INTO tagged_images (image_path, tags, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                """
                await self._execute_query(query, image_path, tags_json)
                await self.connection.commit()
            
            logger.debug(f"Сохранены тэги для {image_path}: {tag_names}")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения тэгов для {image_path}: {e}")
            raise
    

    
    async def close(self):
        """Закрытие подключения"""
        try:
            if self.db_type in ["postgresql", "mysql"] and self.pool:
                self.pool.close()
                await self.pool.wait_closed()
            elif self.db_type == "sqlite" and self.connection:
                await self.connection.close()
                
            logger.info("Подключение к БД закрыто")
        except Exception as e:
            logger.error(f"Ошибка закрытия подключения: {e}")
