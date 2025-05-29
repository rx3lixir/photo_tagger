# api.py - ОБНОВЛЕННАЯ ВЕРСИЯ с поддержкой русских тэгов
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
from database import SafeDatabaseManager
from tag_translation import TAG_TRANSLATION_MAP, get_russian_tags, ENGLISH_TAGS

# Настройка логгирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Глобальные переменные
tagger: CLIPTagger
db_manager: SafeDatabaseManager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    global tagger, db_manager
    
    # Startup
    logger.info("🚀 Запуск Simple Photo Tagger с русскими тэгами...")
    
    try:
        # Инициализируем тэггер
        logger.info("🤖 Загрузка CLIP модели...")
        tagger = CLIPTagger()
        
        # Инициализируем БЕЗОПАСНОЕ подключение к БД
        logger.info("🔒 Безопасное подключение к базе данных...")
        db_manager = SafeDatabaseManager(table_name="ai_photo_tags")
        await db_manager.init_database()
        
        logger.info("✅ API успешно запущен!")
        logger.info(f"📝 Поддерживается {len(ENGLISH_TAGS)} тэгов (англ -> рус)")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске API: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("⏹️  Остановка Simple Photo Tagger...")
    await db_manager.close()

# Создаем FastAPI приложение
app = FastAPI(
    title="Simple Photo Tagger API (RUS)", 
    description="Простой API для автоматического тэггирования фотографий с русскими тэгами",
    version="2.1.0-RUS",
    lifespan=lifespan
)

class TagImageRequest(BaseModel):
    """Запрос для тэггирования одного изображения"""
    image_path: str
    use_all_tags: Optional[bool] = True  # Использовать все доступные тэги
    custom_tags: Optional[List[str]] = None  # Кастомные английские тэги
    top_k: Optional[int] = 5

class TagDirectoryRequest(BaseModel):
    """Запрос для тэггирования директории"""
    directory_path: str
    use_all_tags: Optional[bool] = True
    custom_tags: Optional[List[str]] = None
    file_extensions: Optional[List[str]] = [".jpg", ".jpeg", ".png", ".webp"]
    top_k: Optional[int] = 5

class TagResult(BaseModel):
    """Результат тэггирования с русскими тэгами"""
    image_path: str
    russian_tags: List[str]  # Только русские тэги
    confidence_scores: List[float]  # Для отображения (не сохраняется в БД)
    error: Optional[str] = None

async def process_single_image(image_path: str, english_tags: List[str], top_k: int = 5) -> TagResult:
    """Обработка одного изображения"""
    try:
        # Проверяем файл
        if not os.path.exists(image_path):
            return TagResult(
                image_path=image_path, 
                russian_tags=[], 
                confidence_scores=[],
                error=f"Файл не найден: {image_path}"
            )
        
        # Загружаем и тэгируем
        image = load_image(image_path)
        
        # Тэггируем в отдельном потоке (английские тэги для модели)
        loop = asyncio.get_event_loop()
        english_results = await loop.run_in_executor(
            None, 
            tagger.tag_image, 
            image, 
            english_tags,
            top_k
        )
        
        # Преобразуем в русские тэги
        english_tags_only = [tag for tag, _ in english_results]
        confidence_scores = [conf for _, conf in english_results]
        russian_tags = get_russian_tags(english_tags_only)
        
        logger.info(f"✅ Обработано: {image_path}, найдено {len(russian_tags)} тэгов")
        logger.debug(f"🏷️  Тэги: {russian_tags}")
        
        return TagResult(
            image_path=image_path,
            russian_tags=russian_tags,
            confidence_scores=confidence_scores
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки {image_path}: {e}")
        return TagResult(
            image_path=image_path,
            russian_tags=[],
            confidence_scores=[],
            error=str(e)
        )

async def save_results_to_db(results: List[TagResult]):
    """Сохранение русских тэгов в базу данных - ТОЛЬКО путь + тэги"""
    try:
        for result in results:
            if not result.error and result.russian_tags:  # Только успешные результаты
                await db_manager.save_image_tags(
                    image_path=result.image_path,
                    russian_tags=result.russian_tags
                    # Коэффициенты НЕ сохраняем
                )
        
        successful_saves = len([r for r in results if not r.error and r.russian_tags])
        logger.info(f"💾 Сохранено {successful_saves} результатов в БД")
        
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения в БД: {e}")

@app.post("/tag/image", response_model=TagResult)
async def tag_single_image(
    request: TagImageRequest,
    background_tasks: BackgroundTasks
):
    """Тэггирование одного изображения с русскими тэгами"""
    
    # Определяем какие английские тэги использовать
    if request.use_all_tags:
        english_tags_to_use = ENGLISH_TAGS  # Все доступные тэги
    elif request.custom_tags:
        english_tags_to_use = request.custom_tags
    else:
        english_tags_to_use = ENGLISH_TAGS[:50]  # Топ-50 по умолчанию
    
    top_k = min(request.top_k or 5, len(english_tags_to_use))
    
    logger.info(f"🏷️  Тэггирование: {request.image_path}")
    logger.info(f"📊 Используется {len(english_tags_to_use)} тэгов, top_k={top_k}")
    
    # Обрабатываем изображение
    result = await process_single_image(request.image_path, english_tags_to_use, top_k)
    
    # Сохраняем в БД в фоне
    background_tasks.add_task(save_results_to_db, [result])
    
    return result

@app.post("/tag/directory")
async def tag_directory(
    request: TagDirectoryRequest,
    background_tasks: BackgroundTasks
):
    """Тэггирование директории с русскими тэгами"""
    directory = Path(request.directory_path)
    if not directory.exists() or not directory.is_dir():
        raise HTTPException(
            status_code=400, 
            detail=f"Директория не найдена: {request.directory_path}"
        )
    
    # Определяем английские тэги
    if request.use_all_tags:
        english_tags_to_use = ENGLISH_TAGS
    elif request.custom_tags:
        english_tags_to_use = request.custom_tags
    else:
        english_tags_to_use = ENGLISH_TAGS[:50]
    
    top_k = min(request.top_k or 5, len(english_tags_to_use))
    
    # Ищем изображения
    image_files: List[Path] = []
    for ext in request.file_extensions or [".jpg", ".jpeg", ".png", ".webp"]:
        image_files.extend(directory.glob(f"*{ext.lower()}"))
        image_files.extend(directory.glob(f"*{ext.upper()}"))
    
    logger.info(f"📁 Найдено {len(image_files)} изображений в {request.directory_path}")
    
    if not image_files:
        raise HTTPException(
            status_code=404, 
            detail="Изображения не найдены"
        )
    
    # Запускаем обработку в фоне
    background_tasks.add_task(
        process_directory_background, 
        image_files, 
        english_tags_to_use,
        top_k
    )
    
    return {
        "message": f"🚀 Запущена обработка {len(image_files)} изображений",
        "directory": request.directory_path,
        "files_count": len(image_files),
        "tags_count": len(english_tags_to_use),
        "top_k": top_k
    }

async def process_directory_background(image_files: List[Path], english_tags: List[str], top_k: int = 5):
    """Фоновая обработка директории"""
    logger.info(f"🔄 Начинаем обработку {len(image_files)} изображений")
    
    results = []
    batch_size = 5  # Уменьшаем размер пачки для стабильности
    
    for i in range(0, len(image_files), batch_size):
        batch = image_files[i:i + batch_size]
        
        # Обрабатываем пачку параллельно
        batch_tasks = [
            process_single_image(str(img_path), english_tags, top_k) 
            for img_path in batch
        ]
        
        batch_results = await asyncio.gather(*batch_tasks)
        results.extend(batch_results)
        
        # Сохраняем пачку в БД
        await save_results_to_db(batch_results)
        
        processed_count = min(i + batch_size, len(image_files))
        logger.info(f"📊 Обработано {processed_count} из {len(image_files)} изображений")
        
        # Пауза между пачками для снижения нагрузки
        await asyncio.sleep(0.5)
    
    successful_results = len([r for r in results if not r.error])
    logger.info(f"🎉 Обработка завершена! Успешно: {successful_results}/{len(results)}")

@app.get("/search/{russian_tag}")
async def search_by_russian_tag(russian_tag: str):
    """Поиск изображений по русскому тэгу"""
    try:
        results = await db_manager.search_by_tag(russian_tag)
        return {
            "tag": russian_tag,
            "found": len(results),
            "images": results
        }
    except Exception as e:
        logger.error(f"❌ Ошибка поиска по тэгу {russian_tag}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tags/available")
async def get_available_tags():
    """Получить все доступные тэги"""
    russian_tags = list(TAG_TRANSLATION_MAP.values())
    return {
        "total_tags": len(TAG_TRANSLATION_MAP),
        "russian_tags": russian_tags[:20],  # Первые 20 для примера
        "all_russian_tags": russian_tags,
        "sample_mapping": dict(list(TAG_TRANSLATION_MAP.items())[:10])
    }

@app.get("/image/{image_path:path}/tags")
async def get_image_existing_tags(image_path: str):
    """Получить существующие тэги для изображения"""
    try:
        tags = await db_manager.get_image_tags(image_path)
        if tags:
            return {
                "image_path": image_path,
                "found": True,
                "russian_tags": tags
            }
        else:
            return {
                "image_path": image_path,
                "found": False,
                "message": "Тэги не найдены"
            }
    except Exception as e:
        logger.error(f"❌ Ошибка получения тэгов для {image_path}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats")
async def get_stats():
    """Статистика по русским тэгам"""
    try:
        stats = await db_manager.get_stats()
        return {
            **stats,
            "supported_languages": ["Russian", "English (for model)"],
            "total_available_tags": len(TAG_TRANSLATION_MAP)
        }
    except Exception as e:
        logger.error(f"❌ Ошибка получения статистики: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Проверка здоровья API"""
    try:
        db_health = await db_manager.check_database_health()
        return {
            "status": "ok",
            "tagger_loaded": True,
            "database": db_health,
            "version": "2.1.0-RUS",
            "features": ["russian_tags", "safe_database", "separate_table"],
            "total_tags": len(TAG_TRANSLATION_MAP)
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "version": "2.1.0-RUS"
        }
