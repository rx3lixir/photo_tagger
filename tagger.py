import torch
import open_clip
from PIL import Image
from typing import List, Tuple, Any
import logging
import time

# Настройка логгера для этого модуля
logger = logging.getLogger(__name__)


class CLIPTagger:
    """
    Класс для тэггирования изображений с помощью CLIP модели.
    Использует open_clip вместо оригинального clip.
    """
    
    def __init__(self, device: str = "auto"):
        """
        Инициализация тэггера.
        
        Args:
            device: Устройство для выполнения (cuda/cpu/auto). Если auto - автоопределение
        """
        # Автоматически выбираем устройство если не указано
        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
            
        logger.info(f"Инициализация CLIPTagger на устройстве: {self.device}")
        
        # Не типизируем сложные объекты open_clip - пусть будут Any
        self.model: Any = None
        self.preprocess: Any = None
        self.tokenizer: Any = None
        
        try:
            # Загружаем модель open_clip
            logger.info("Начинаем загрузку CLIP модели...")
            logger.info("Это может занять несколько минут при первом запуске...")
            
            start_time = time.time()
            
            # create_model_and_transforms возвращает (model, preprocess_train, preprocess_val)
            logger.info("Создание модели ViT-B-32...")
            model, _, preprocess = open_clip.create_model_and_transforms(
                'ViT-B-32', 
                pretrained='openai',
                device=self.device
            )
            
            logger.info("Модель создана, загружаем на устройство...")
            self.model = model
            self.preprocess = preprocess
            
            logger.info("Загружаем токенизатор...")
            self.tokenizer = open_clip.get_tokenizer('ViT-B-32')
            
            elapsed_time = time.time() - start_time
            logger.info(f"Модель CLIP успешно загружена за {elapsed_time:.2f} секунд")
            
        except Exception as e:
            logger.error(f"Ошибка загрузки модели CLIP: {e}")
            logger.error(f"Тип ошибки: {type(e).__name__}")
            raise

    def tag_image(self, image: Image.Image, tags: List[str], top_k: int = 4) -> List[Tuple[str, float]]:
        """
        Тэггирование одного изображения.
        
        Args:
            image: PIL изображение
            tags: Список тэгов для проверки
            top_k: Количество лучших тэгов для возврата (по умолчанию 4)
            
        Returns:
            Список кортежей (тэг, вероятность) отсортированный по убыванию вероятности
        """
        try:
            # Подготавливаем изображение
            processed_image = self.preprocess(image)
            image_tensor = processed_image.unsqueeze(0).to(self.device)
            
            # Токенизируем тэги  
            text_tokens = self.tokenizer(tags).to(self.device)
            
            # Получаем эмбеддинги без градиентов (экономим память)
            with torch.no_grad():
                image_features = self.model.encode_image(image_tensor)
                text_features = self.model.encode_text(text_tokens)
                
                # Нормализуем векторы для корректного подсчета схожести
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                text_features = text_features / text_features.norm(dim=-1, keepdim=True)
                
                # Вычисляем схожесть и применяем softmax
                similarity = (100.0 * image_features @ text_features.T).softmax(dim=-1)
            
            # Сортируем результаты по убыванию вероятности и берем только топ-K
            values, indices = similarity[0].topk(min(top_k, len(tags)))
            
            # Формируем результат как список кортежей (тэг, вероятность)
            results = [(tags[idx], values[i].item()) for i, idx in enumerate(indices)]
            
            logger.debug(f"Тэггирование завершено, возвращено топ-{len(results)} тэгов")
            return results
            
        except Exception as e:
            logger.error(f"Ошибка при тэггировании изображения: {e}")
            raise
