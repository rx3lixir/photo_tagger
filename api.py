import asyncio
import os
import logging
from pathlib import Path
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel

from tagger import CLIPTagger
from image_utils import load_image
from database import DatabaseManager

# Настройка логгирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Глобальные переменные
tagger: CLIPTagger
db_manager: DatabaseManager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    global tagger, db_manager
    
    # Startup
    logger.info("Запуск Simple Photo Tagger...")
    
    try:
        # Инициализируем тэггер
        logger.info("Загрузка CLIP модели...")
        tagger = CLIPTagger()
        
        # Инициализируем подключение к БД
        logger.info("Подключение к базе данных...")
        db_manager = DatabaseManager()
        await db_manager.init_database()
        
        logger.info("API успешно запущен!")
        
    except Exception as e:
        logger.error(f"Ошибка при запуске API: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Остановка Simple Photo Tagger...")
    await db_manager.close()

# Создаем FastAPI приложение
app = FastAPI(
    title="Simple Photo Tagger API", 
    description="Простой API для автоматического тэггирования фотографий",
    version="2.0.0",
    lifespan=lifespan
)

# Простой список тэгов
DEFAULT_TAGS = [
    "cat", "dog", "car", "landscape", "party", "food", "beach", 
    "city", "children", "sport", "nature", "building", "people"
]

class TagImageRequest(BaseModel):
    """Запрос для тэггирования одного изображения"""
    image_path: str
    tags: Optional[List[str]] = None
    top_k: Optional[int] = 3

class TagDirectoryRequest(BaseModel):
    """Запрос для тэггирования директории"""
    directory_path: str
    tags: Optional[List[str]] = None
    file_extensions: Optional[List[str]] = [".jpg", ".jpeg", ".png"]
    top_k: Optional[int] = 3

class TagResult(BaseModel):
    """Результат тэггирования"""
    image_path: str
    tags: List[tuple]  # [(tag, confidence), ...]
    error: Optional[str] = None

async def process_single_image(image_path: str, tags: List[str], top_k: int = 3) -> TagResult:
    """Обработка одного изображения"""
    try:
        # Проверяем файл
        if not os.path.exists(image_path):
            return TagResult(
                image_path=image_path, 
                tags=[], 
                error=f"Файл не найден: {image_path}"
            )
        
        # Загружаем и тэгируем
        image = load_image(image_path)
        
        # Тэггируем в отдельном потоке
        loop = asyncio.get_event_loop()
        tag_results = await loop.run_in_executor(
            None, 
            tagger.tag_image, 
            image, 
            tags,
            top_k
        )
        
        logger.info(f"Обработано: {image_path}, найдено {len(tag_results)} тэгов")
        
        return TagResult(
            image_path=image_path,
            tags=tag_results
        )
        
    except Exception as e:
        logger.error(f"Ошибка обработки {image_path}: {e}")
        return TagResult(
            image_path=image_path,
            tags=[],
            error=str(e)
        )

async def save_results_to_db(results: List[TagResult]):
    """Сохранение в базу данных"""
    try:
        for result in results:
            if not result.error:  # Только успешные результаты
                await db_manager.save_image_tags(
                    image_path=result.image_path,
                    tags=result.tags
                )
        logger.info(f"Сохранено {len(results)} результатов в БД")
        
    except Exception as e:
        logger.error(f"Ошибка сохранения в БД: {e}")

@app.post("/tag/image", response_model=TagResult)
async def tag_single_image(
    request: TagImageRequest,
    background_tasks: BackgroundTasks
):
    """Тэггирование одного изображения"""
    tags_to_use = request.tags or DEFAULT_TAGS
    top_k = request.top_k or 3
    
    logger.info(f"Тэггирование: {request.image_path}")
    
    # Обрабатываем изображение
    result = await process_single_image(request.image_path, tags_to_use, top_k)
    
    # Сохраняем в БД в фоне
    background_tasks.add_task(save_results_to_db, [result])
    
    return result

@app.post("/tag/directory")
async def tag_directory(
    request: TagDirectoryRequest,
    background_tasks: BackgroundTasks
):
    """Тэггирование директории"""
    directory = Path(request.directory_path)
    if not directory.exists() or not directory.is_dir():
        raise HTTPException(
            status_code=400, 
            detail=f"Директория не найдена: {request.directory_path}"
        )
    
    tags_to_use = request.tags or DEFAULT_TAGS
    top_k = request.top_k or 3
    
    # Ищем изображения
    image_files: List[Path] = []
    for ext in request.file_extensions or [".jpg", ".jpeg", ".png"]:
        image_files.extend(directory.glob(f"*{ext.lower()}"))
        image_files.extend(directory.glob(f"*{ext.upper()}"))
    
    logger.info(f"Найдено {len(image_files)} изображений в {request.directory_path}")
    
    if not image_files:
        raise HTTPException(
            status_code=404, 
            detail="Изображения не найдены"
        )
    
    # Запускаем обработку в фоне
    background_tasks.add_task(
        process_directory_background, 
        image_files, 
        tags_to_use,
        top_k
    )
    
    return {
        "message": f"Запущена обработка {len(image_files)} изображений",
        "directory": request.directory_path,
        "files_count": len(image_files)
    }

async def process_directory_background(image_files: List[Path], tags: List[str], top_k: int = 3):
    """Фоновая обработка директории"""
    logger.info(f"Начинаем обработку {len(image_files)} изображений")
    
    results = []
    batch_size = 10  # Обрабатываем пачками
    
    for i in range(0, len(image_files), batch_size):
        batch = image_files[i:i + batch_size]
        
        # Обрабатываем пачку параллельно
        batch_tasks = [
            process_single_image(str(img_path), tags, top_k) 
            for img_path in batch
        ]
        
        batch_results = await asyncio.gather(*batch_tasks)
        results.extend(batch_results)
        
        # Сохраняем пачку в БД
        await save_results_to_db(batch_results)
        
        logger.info(f"Обработано {min(i + batch_size, len(image_files))} из {len(image_files)} изображений")
        
        # Пауза между пачками
        await asyncio.sleep(0.1)
    
    logger.info(f"Обработка завершена! Обработано {len(results)} изображений")

@app.get("/search/{tag}")
async def search_by_tag(tag: str):
    """Поиск изображений по тэгу"""
    try:
        results = await db_manager.search_by_tag(tag)
        return {
            "tag": tag,
            "found": len(results),
            "images": results
        }
    except Exception as e:
        logger.error(f"Ошибка поиска по тэгу {tag}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats")
async def get_stats():
    """Статистика по базе данных"""
    try:
        stats = await db_manager.get_stats()
        return stats
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Проверка здоровья API"""
    return {
        "status": "ok",
        "tagger_loaded": True,
        "database_connected": True,
        "version": "2.0.0"
    }
