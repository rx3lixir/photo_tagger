from PIL import Image
import logging

logger = logging.getLogger(__name__)

def load_image(image_path: str) -> Image.Image:
    """
    Загрузка изображения с автоматическим ресайзом для экономии памяти.
    
    Args:
        image_path: Путь к изображению
        
    Returns:
        PIL изображение
    """
    try:
        img = Image.open(image_path)
        
        # Конвертируем в RGB если нужно (для PNG с прозрачностью и т.д.)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Ресайз больших изображений для экономии памяти и ускорения
        max_size = 1024
        if img.size[0] > max_size or img.size[1] > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            logger.debug(f"Изображение {image_path} уменьшено до {img.size}")
        
        return img
        
    except Exception as e:
        logger.error(f"Ошибка загрузки изображения {image_path}: {e}")
        raise
