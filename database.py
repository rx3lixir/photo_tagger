import asyncpg
import json
import logging
import os
from typing import List, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Менеджер для работы с PostgreSQL базой данных.
    Управляет подключением и операциями с тэгированными изображениями.
    """
    
    def __init__(self):
        """Инициализация менеджера БД"""
        self.pool: Optional[asyncpg.Pool] = None
        
        # Параметры подключения из переменных окружения
        # Fallback значения совпадают с docker-compose.yml
        self.db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', '5434')),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', 'postgres'),
            'database': os.getenv('DB_NAME', 'photo_archive')
        }
        
        logger.info(f"Подключение к БД: {self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}")
    
    async def init_database(self):
        """
        Инициализация подключения к БД и создание таблиц.
        """
        try:
            # Создаем пул подключений для эффективной работы
            self.pool = await asyncpg.create_pool(
                **self.db_config,
                min_size=1,
                max_size=10
            )
            
            logger.info("Подключение к PostgreSQL установлено")
            
            # Создаем таблицы если их нет
            await self._create_tables()
            
        except Exception as e:
            logger.error(f"Ошибка подключения к БД: {e}")
            raise
    
    async def _create_tables(self):
        """Создание необходимых таблиц в БД"""
        
        if not self.pool:
            raise RuntimeError("Пул подключений не инициализирован")
        
        create_table_query = """
        CREATE TABLE IF NOT EXISTS tagged_images (
            id SERIAL PRIMARY KEY,
            image_path VARCHAR(1000) NOT NULL UNIQUE,
            tags JSONB NOT NULL,
            exif_datetime TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Индекс для быстрого поиска по пути изображения
        CREATE INDEX IF NOT EXISTS idx_image_path ON tagged_images(image_path);
        
        -- Индекс для поиска по тэгам (GIN индекс для JSONB)
        CREATE INDEX IF NOT EXISTS idx_tags ON tagged_images USING GIN(tags);
        
        -- Индекс по дате создания фото
        CREATE INDEX IF NOT EXISTS idx_exif_datetime ON tagged_images(exif_datetime);
        """
        
        async with self.pool.acquire() as connection:
            await connection.execute(create_table_query)
            
        logger.info("Таблицы базы данных созданы/проверены")
    
    async def save_image_tags(
        self, 
        image_path: str, 
        tags: List[Tuple[str, float]], 
        exif_datetime: Optional[str] = None
    ):
        """
        Сохранение тэгов изображения в БД.
        
        Args:
            image_path: Путь к изображению
            tags: Список кортежей (тэг, вероятность)
            exif_datetime: EXIF дата из изображения
        """
        if not self.pool:
            raise RuntimeError("Пул подключений не инициализирован")
            
        try:
            # Извлекаем только названия тэгов без confidence
            tag_names = [tag for tag, _ in tags]
            tags_json = json.dumps(tag_names)
            
            # Парсим EXIF дату если она есть
            parsed_datetime = None
            if exif_datetime:
                try:
                    # EXIF формат обычно "YYYY:MM:DD HH:MM:SS"
                    parsed_datetime = datetime.strptime(exif_datetime, "%Y:%m:%d %H:%M:%S")
                except ValueError:
                    logger.warning(f"Не удалось распарсить EXIF дату: {exif_datetime}")
            
            # Используем UPSERT (INSERT ... ON CONFLICT) для обновления существующих записей
            upsert_query = """
            INSERT INTO tagged_images (image_path, tags, exif_datetime, updated_at)
            VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
            ON CONFLICT (image_path) 
            DO UPDATE SET 
                tags = EXCLUDED.tags,
                exif_datetime = EXCLUDED.exif_datetime,
                updated_at = CURRENT_TIMESTAMP
            """
            
            async with self.pool.acquire() as connection:
                await connection.execute(
                    upsert_query, 
                    image_path, 
                    tags_json, 
                    parsed_datetime
                )
            
            logger.debug(f"Сохранены тэги для {image_path}: {tag_names}")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения тэгов для {image_path}: {e}")
            raise
    
    async def get_image_tags(self, image_path: str) -> Optional[dict]:
        """
        Получение тэгов изображения из БД.
        
        Args:
            image_path: Путь к изображению
            
        Returns:
            Dict с информацией об изображении или None если не найдено
        """
        if not self.pool:
            raise RuntimeError("Пул подключений не инициализирован")
            
        try:
            select_query = """
            SELECT image_path, tags, exif_datetime, created_at, updated_at
            FROM tagged_images 
            WHERE image_path = $1
            """
            
            async with self.pool.acquire() as connection:
                row = await connection.fetchrow(select_query, image_path)
                
                if row:
                    return {
                        'image_path': row['image_path'],
                        'tags': json.loads(row['tags']),  # Теперь это просто список строк
                        'exif_datetime': row['exif_datetime'],
                        'created_at': row['created_at'],
                        'updated_at': row['updated_at']
                    }
                
                return None
                
        except Exception as e:
            logger.error(f"Ошибка получения тэгов для {image_path}: {e}")
            raise
    
    async def search_by_tag(self, tag: str) -> List[dict]:
        """
        Поиск изображений по тэгу.
        
        Args:
            tag: Тэг для поиска
            
        Returns:
            Список изображений с данным тэгом
        """
        if not self.pool:
            raise RuntimeError("Пул подключений не инициализирован")
            
        try:
            # Используем JSONB операторы PostgreSQL для поиска
            search_query = """
            SELECT image_path, tags, exif_datetime, created_at
            FROM tagged_images
            WHERE tags @> $1::jsonb
            ORDER BY created_at DESC
            """
            
            # Формируем условие поиска - теперь это просто строка в массиве
            search_condition = json.dumps([tag])
            
            async with self.pool.acquire() as connection:
                rows = await connection.fetch(search_query, search_condition)
                
                results = []
                for row in rows:
                    tags = json.loads(row['tags'])  # Список строк
                    
                    # Проверяем что тэг действительно есть в списке
                    if tag in tags:
                        results.append({
                            'image_path': row['image_path'],
                            'tags': tags,
                            'exif_datetime': row['exif_datetime'],
                            'created_at': row['created_at']
                        })
                
                return results
                
        except Exception as e:
            logger.error(f"Ошибка поиска по тэгу {tag}: {e}")
            raise
    
    async def get_stats(self) -> dict:
        """
        Получение статистики по базе данных.
        
        Returns:
            Dict со статистикой
        """
        if not self.pool:
            raise RuntimeError("Пул подключений не инициализирован")
            
        try:
            stats_query = """
            SELECT 
                COUNT(*) as total_images,
                COUNT(exif_datetime) as images_with_exif,
                MIN(created_at) as first_processed,
                MAX(updated_at) as last_processed
            FROM tagged_images
            """
            
            async with self.pool.acquire() as connection:
                row = await connection.fetchrow(stats_query)
                
                return {
                    'total_images': row['total_images'],
                    'images_with_exif': row['images_with_exif'],
                    'first_processed': row['first_processed'],
                    'last_processed': row['last_processed']
                }
                
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            raise
    
    async def close(self):
        """Закрытие подключения к БД"""
        if self.pool:
            await self.pool.close()
            logger.info("Подключение к БД закрыто")
