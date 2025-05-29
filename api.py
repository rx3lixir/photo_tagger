import asyncio
import os
import logging
from pathlib import Path
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel

from tagger import CLIPTagger
from image_utils import load_image, get_exif_datetime
from database import DatabaseManager

# Настройка логгирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Глобальные переменные для тэггера и БД
tagger: CLIPTagger
db_manager: DatabaseManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    global tagger, db_manager
    
    # Startup
    logger.info("Запуск Photo Tagger API...")
    
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
    
    yield  # Здесь работает приложение
    
    # Shutdown
    logger.info("Остановка Photo Tagger API...")
    await db_manager.close()


# Создаем FastAPI приложение с lifespan
app = FastAPI(
    title="Photo Tagger API", 
    description="API для автоматического тэггирования фотографий",
    version="1.0.0",
    lifespan=lifespan
)

# Список тэгов для распознавания (можно вынести в конфиг)
DEFAULT_TAGS = [
    "cat", "dog", "car", "landscape", "party",
    "food", "beach", "city", "children", "sport",
    "Victory Day", "veterans", "celebration", "military",
]


class TagImageRequest(BaseModel):
    """Модель запроса для тэггирования одного изображения"""
    image_path: str
    tags: Optional[List[str]] = None
    top_k: Optional[int] = 4


class TagDirectoryRequest(BaseModel):
    """Модель запроса для тэггирования директории"""
    directory_path: str
    tags: Optional[List[str]] = None
    file_extensions: Optional[List[str]] = [".jpg", ".jpeg", ".png", ".bmp"]
    top_k: Optional[int] = 4


class TagResult(BaseModel):
    """Модель результата тэггирования"""
    image_path: str
    tags: List[tuple]  # [(tag, confidence), ...]
    exif_datetime: Optional[str] = None
    error: Optional[str] = None


async def process_single_image(image_path: str, tags: List[str], top_k: int = 4) -> TagResult:
    """
    Асинхронная обработка одного изображения.
    
    Args:
        image_path: Путь к изображению
        tags: Список тэгов для проверки
        
    Returns:
        Результат тэггирования
    """
    try:
        # Проверяем существование файла
        if not os.path.exists(image_path):
            return TagResult(
                image_path=image_path, 
                tags=[], 
                error=f"Файл не найден: {image_path}"
            )
        
        # Загружаем изображение (синхронная операция)
        image = load_image(image_path)
        
        # Получаем EXIF данные
        exif_datetime = get_exif_datetime(image_path)
        
        # Тэггируем изображение (CPU/GPU интенсивная операция)
        # Запускаем в отдельном потоке чтобы не блокировать event loop
        loop = asyncio.get_event_loop()
        tag_results = await loop.run_in_executor(
            None, 
            tagger.tag_image, 
            image, 
            tags,
            top_k
        )
        
        logger.info(f"Успешно обработано изображение: {image_path}")
        
        return TagResult(
            image_path=image_path,
            tags=tag_results,
            exif_datetime=exif_datetime
        )
        
    except Exception as e:
        logger.error(f"Ошибка обработки {image_path}: {e}")
        return TagResult(
            image_path=image_path,
            tags=[],
            error=str(e)
        )


async def save_results_to_db(results: List[TagResult]):
    """
    Сохранение результатов в базу данных.
    
    Args:
        results: Список результатов тэггирования
    """
    try:
        for result in results:
            if not result.error:  # Сохраняем только успешные результаты
                await db_manager.save_image_tags(
                    image_path=result.image_path,
                    tags=result.tags,
                    exif_datetime=result.exif_datetime
                )
        logger.info(f"Сохранено {len(results)} результатов в БД")
        
    except Exception as e:
        logger.error(f"Ошибка сохранения в БД: {e}")


@app.post("/tag/image", response_model=TagResult)
async def tag_single_image(
    request: TagImageRequest,
    background_tasks: BackgroundTasks
):
    """
    Тэггирование одного изображения.
    
    Args:
        request: Запрос с путем к изображению и опциональными тэгами
        background_tasks: Фоновые задачи FastAPI
        
    Returns:
        Результат тэггирования
    """
    # Используем переданные тэги или дефолтные
    tags_to_use = request.tags or DEFAULT_TAGS
    top_k = request.top_k or 4
    
    logger.info(f"Запрос на тэггирование изображения: {request.image_path}, топ-{top_k} тэгов")
    
    # Обрабатываем изображение
    result = await process_single_image(request.image_path, tags_to_use, top_k)
    
    # Добавляем фоновую задачу для сохранения в БД
    background_tasks.add_task(save_results_to_db, [result])
    
    return result


@app.post("/tag/directory")
async def tag_directory(
    request: TagDirectoryRequest,
    background_tasks: BackgroundTasks
):
    """
    Тэггирование всех изображений в директории.
    
    Args:
        request: Запрос с путем к директории и параметрами
        background_tasks: Фоновые задачи FastAPI
        
    Returns:
        Статус операции
    """
    # Проверяем существование директории
    directory = Path(request.directory_path)
    if not directory.exists() or not directory.is_dir():
        raise HTTPException(
            status_code=400, 
            detail=f"Директория не найдена: {request.directory_path}"
        )
    
    # Используем переданные тэги или дефолтные
    tags_to_use = request.tags or DEFAULT_TAGS
    top_k = request.top_k or 4
    
    # Ищем все изображения в директории
    image_files: List[Path] = []
    for ext in request.file_extensions or [".jpg", ".jpeg", ".png", ".bmp"]:
        image_files.extend(directory.glob(f"*{ext.lower()}"))
        image_files.extend(directory.glob(f"*{ext.upper()}"))
    
    logger.info(f"Найдено {len(image_files)} изображений в {request.directory_path}")
    
    if not image_files:
        raise HTTPException(
            status_code=404, 
            detail="Изображения не найдены в указанной директории"
        )
    
    # Добавляем фоновую задачу для обработки всех изображений
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


async def process_directory_background(image_files: List[Path], tags: List[str], top_k: int = 4):
    """
    Фоновая обработка директории с изображениями.
    
    Args:
        image_files: Список путей к изображениям
        tags: Тэги для проверки
        top_k: Количество лучших тэгов для каждого изображения
    """
    logger.info(f"Начинаем фоновую обработку {len(image_files)} изображений, топ-{top_k} тэгов")
    
    results = []
    
    # Обрабатываем изображения пачками чтобы не перегрузить систему
    batch_size = 10  # Размер пачки
    
    for i in range(0, len(image_files), batch_size):
        batch = image_files[i:i + batch_size]
        
        # Обрабатываем пачку параллельно
        batch_tasks = [
            process_single_image(str(img_path), tags, top_k) 
            for img_path in batch
        ]
        
        batch_results = await asyncio.gather(*batch_tasks)
        results.extend(batch_results)
        
        # Сохраняем результаты пачки в БД
        await save_results_to_db(batch_results)
        
        logger.info(f"Обработано {min(i + batch_size, len(image_files))} из {len(image_files)} изображений")
        
        # Небольшая пауза между пачками чтобы не перегружать систему
        await asyncio.sleep(0.1)
    
    logger.info(f"Фоновая обработка завершена. Обработано {len(results)} изображений")


@app.get("/health")
async def health_check():
    """Проверка здоровья API"""
    return {
        "status": "ok",
        "tagger_loaded": True,
        "database_connected": True
    }
