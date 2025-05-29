import json
import logging
import os
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime

# Импорты драйверов остаются те же...
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
            raise ImportError("Не найден ни один поддерживаемый драйвер БД")

logger = logging.getLogger(__name__)

class SafeDatabaseManager:
    """
    БЕЗОПАСНЫЙ менеджер БД для работы с существующими базами данных.
    Использует отдельную таблицу для AI тэгов и не трогает существующие данные.
    """
    
    def __init__(self, table_name: str = "ai_photo_tags"):
        """
        Инициализация с ОТДЕЛЬНОЙ таблицей для AI тэгов
        
        Args:
            table_name: имя таблицы для AI тэгов (НЕ ТРОГАЕТ существующие таблицы!)
        """
        self.pool = None
        self.connection = None
        self.db_type = db_type
        self.table_name = table_name  # Используем отдельную таблицу!
        
        # Параметры подключения из переменных окружения
        self.db_config = self._get_db_config()
        
        logger.info(f"🔒 БЕЗОПАСНЫЙ режим: используется отдельная таблица '{self.table_name}'")
        logger.info(f"Тип БД: {self.db_type}")
    
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
                'db': os.getenv('DB_NAME', 'photo_archive')
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
            
            # Проверяем существующие таблицы БЕЗОПАСНО
            await self._check_existing_tables()
            
            # Создаем ТОЛЬКО нашу таблицу для AI тэгов
            await self._create_ai_tags_table()
            
        except Exception as e:
            logger.error(f"Ошибка подключения к БД: {e}")
            raise
    
    async def _check_existing_tables(self):
        """БЕЗОПАСНАЯ проверка существующих таблиц (не меняет их!)"""
        try:
            if self.db_type == "postgresql":
                query = """
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                """
            elif self.db_type == "mysql":
                query = """
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = DATABASE()
                """
            else:  # SQLite
                query = """
                SELECT name FROM sqlite_master WHERE type='table'
                """
            
            existing_tables = await self._fetch_query(query)
            table_names = [row[0] for row in existing_tables] if existing_tables else []
            
            logger.info(f"📋 Найдено существующих таблиц: {len(table_names)}")
            logger.info(f"🔍 Таблицы: {', '.join(table_names[:5])}{'...' if len(table_names) > 5 else ''}")
            
            if self.table_name in table_names:
                logger.info(f"✅ Таблица AI тэгов '{self.table_name}' уже существует")
            else:
                logger.info(f"🆕 Таблица AI тэгов '{self.table_name}' будет создана")
                
        except Exception as e:
            logger.warning(f"Не удалось проверить существующие таблицы: {e}")
    
    async def _create_ai_tags_table(self):
        """Создание ПРОСТОЙ таблицы для AI тэгов: только путь + тэги"""
        
        if self.db_type == "postgresql":
            create_table_query = f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id SERIAL PRIMARY KEY,
                image_path VARCHAR(1000) NOT NULL UNIQUE,
                ai_tags JSONB NOT NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_{self.table_name}_path ON {self.table_name}(image_path);
            CREATE INDEX IF NOT EXISTS idx_{self.table_name}_tags ON {self.table_name} USING GIN(ai_tags);
            
            -- Добавляем комментарий для ясности
            COMMENT ON TABLE {self.table_name} IS 'AI-generated Russian tags from CLIP model';
            """
            
        elif self.db_type == "mysql":
            create_table_query = f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id INT AUTO_INCREMENT PRIMARY KEY,
                image_path VARCHAR(1000) NOT NULL UNIQUE,
                ai_tags JSON NOT NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_{self.table_name}_path ON {self.table_name}(image_path);
            """
            
        else:  # SQLite
            create_table_query = f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_path TEXT NOT NULL UNIQUE,
                ai_tags TEXT NOT NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_{self.table_name}_path ON {self.table_name}(image_path);
            """
        
        await self._execute_query(create_table_query)
        logger.info(f"✅ Простая таблица AI тэгов '{self.table_name}' создана/проверена")
    
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
    
    async def _fetch_query(self, query: str, *args):
        """Универсальное выполнение SELECT запросов"""
        if self.db_type == "postgresql":
            async with self.pool.acquire() as connection:
                return await connection.fetch(query, *args)
                
        elif self.db_type == "mysql":
            async with self.pool.acquire() as connection:
                async with connection.cursor() as cursor:
                    await cursor.execute(query, args)
                    return await cursor.fetchall()
                    
        else:  # SQLite
            cursor = await self.connection.execute(query, args)
            return await cursor.fetchall()
    
    async def save_image_tags(self, image_path: str, russian_tags: List[str]):
        """
        Сохранение русских AI тэгов изображения - ТОЛЬКО путь + тэги
        
        Args:
            image_path: путь к изображению
            russian_tags: список русских тэгов
        """
        try:
            # Подготавливаем данные - только тэги
            tags_json = json.dumps(russian_tags, ensure_ascii=False)
            
            if self.db_type == "postgresql":
                query = f"""
                INSERT INTO {self.table_name} (image_path, ai_tags)
                VALUES ($1, $2)
                ON CONFLICT (image_path) 
                DO UPDATE SET ai_tags = EXCLUDED.ai_tags
                """
                await self._execute_query(query, image_path, tags_json)
                
            elif self.db_type == "mysql":
                query = f"""
                INSERT INTO {self.table_name} (image_path, ai_tags)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE ai_tags = VALUES(ai_tags)
                """
                await self._execute_query(query, image_path, tags_json)
                
            else:  # SQLite
                query = f"""
                INSERT OR REPLACE INTO {self.table_name} (image_path, ai_tags)
                VALUES (?, ?)
                """
                await self._execute_query(query, image_path, tags_json)
            
            logger.debug(f"💾 Сохранены AI тэги для {image_path}: {russian_tags}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения тэгов для {image_path}: {e}")
            raise
    
    async def get_image_tags(self, image_path: str) -> Optional[List[str]]:
        """Получение AI тэгов для изображения"""
        try:
            query = f"""
            SELECT ai_tags
            FROM {self.table_name} 
            WHERE image_path = {'$1' if self.db_type == 'postgresql' else '?' if self.db_type == 'sqlite' else '%s'}
            """
            
            result = await self._fetch_query(query, image_path)
            
            if result:
                return json.loads(result[0][0])
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения тэгов для {image_path}: {e}")
            return None
    
    async def search_by_tag(self, russian_tag: str) -> List[Dict]:
        """Поиск изображений по русскому тэгу"""
        try:
            if self.db_type == "postgresql":
                query = f"""
                SELECT image_path, ai_tags 
                FROM {self.table_name} 
                WHERE ai_tags @> $1::jsonb
                """
                tag_json = json.dumps([russian_tag], ensure_ascii=False)
                
            elif self.db_type == "mysql":
                query = f"""
                SELECT image_path, ai_tags 
                FROM {self.table_name} 
                WHERE JSON_CONTAINS(ai_tags, %s)
                """
                tag_json = json.dumps([russian_tag], ensure_ascii=False)
                
            else:  # SQLite
                query = f"""
                SELECT image_path, ai_tags 
                FROM {self.table_name} 
                WHERE ai_tags LIKE ?
                """
                tag_json = f'%"{russian_tag}"%'
            
            results = await self._fetch_query(query, tag_json)
            
            return [
                {
                    'image_path': row[0],
                    'tags': json.loads(row[1])
                }
                for row in results
            ]
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска по тэгу {russian_tag}: {e}")
            return []
    
    async def get_stats(self) -> Dict:
        """Статистика по AI тэгам"""
        try:
            count_query = f"SELECT COUNT(*) FROM {self.table_name}"
            count_result = await self._fetch_query(count_query)
            total_images = count_result[0][0] if count_result else 0
            
            return {
                'total_tagged_images': total_images,
                'table_name': self.table_name
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики: {e}")
            return {'error': str(e)}
    
    async def check_database_health(self) -> Dict:
        """Проверка здоровья подключения к БД"""
        try:
            # Простой запрос для проверки
            test_query = f"SELECT COUNT(*) FROM {self.table_name}"
            result = await self._fetch_query(test_query)
            
            return {
                'status': 'healthy',
                'connection_type': self.db_type,
                'table_exists': True,
                'total_records': result[0][0] if result else 0
            }
            
        except Exception as e:
            logger.error(f"❌ Проблемы с БД: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'connection_type': self.db_type
            }
    
    async def close(self):
        """Закрытие подключения"""
        try:
            if self.db_type in ["postgresql", "mysql"] and self.pool:
                self.pool.close()
                await self.pool.wait_closed()
            elif self.db_type == "sqlite" and self.connection:
                await self.connection.close()
                
            logger.info("🔌 Подключение к БД закрыто")
        except Exception as e:
            logger.error(f"❌ Ошибка закрытия подключения: {e}")

# Для обратной совместимости
DatabaseManager = SafeDatabaseManager
