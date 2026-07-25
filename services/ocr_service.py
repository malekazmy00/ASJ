# services/ocr_service.py
import logging
from typing import Tuple, Optional
from io import BytesIO
import concurrent.futures
import multiprocessing
import time
import os
from functools import partial

try:
    import pytesseract
    from PIL import Image, ImageFilter, ImageEnhance
except ImportError:
    pytesseract = None
    Image = None

from core.config import settings

logger = logging.getLogger(__name__)

def _ocr_process(image_data: bytes) -> str:
    """تنفيذ OCR في Process منفصل"""
    try:
        from PIL import Image
        from io import BytesIO
        import pytesseract
        
        image = Image.open(BytesIO(image_data))
        
        try:
            text = pytesseract.image_to_string(
                image,
                lang='ara+eng',
                config='--oem 3 --psm 6'
            )
        except:
            text = pytesseract.image_to_string(image)
        
        return text.strip()
        
    except Exception as e:
        logger.error(f"OCR process error: {e}")
        return ""

class OCRService:
    _executor = None
    _max_workers = None
    
    @classmethod
    def _get_executor(cls):
        if cls._executor is None:
            try:
                cls._max_workers = min(os.cpu_count() * 2 or 2, 4)
                cls._executor = concurrent.futures.ProcessPoolExecutor(
                    max_workers=cls._max_workers,
                    mp_context=multiprocessing.get_context('spawn')
                )
                logger.info(f"OCR ProcessPoolExecutor initialized with {cls._max_workers} workers")
            except Exception as e:
                logger.error(f"Failed to initialize ProcessPoolExecutor: {e}")
                cls._executor = None
        return cls._executor
    
    @classmethod
    def shutdown(cls):
        if cls._executor:
            cls._executor.shutdown(wait=True)
            cls._executor = None
            logger.info("OCR ProcessPoolExecutor shut down")
    
    @classmethod
    def extract_text(cls, image_bytes: bytes, timeout: int = 30) -> Tuple[str, Optional[str]]:
        if pytesseract is None or Image is None:
            return "OCR غير متاح", None
        
        try:
            processed = cls._preprocess_image(image_bytes)
            if processed is None:
                return "فشل معالجة الصورة", None
            
            img_bytes = BytesIO()
            processed.save(img_bytes, format='PNG')
            img_data = img_bytes.getvalue()
            
            executor = cls._get_executor()
            if executor is None:
                # Fallback: تنفيذ مباشر
                text = _ocr_process(img_data)
            else:
                future = executor.submit(_ocr_process, img_data)
                try:
                    text = future.result(timeout=timeout)
                except concurrent.futures.TimeoutError:
                    future.cancel()
                    logger.error("OCR timeout")
                    return "انتهى وقت معالجة OCR", None
            
            if not text:
                return "لا يوجد نص", None
            
            from services.ai_service import ai_service
            part_number = ai_service.extract_part_number(text)
            
            return text, part_number
            
        except Exception as e:
            logger.error(f"OCR error: {e}")
            return f"خطأ في OCR: {str(e)}", None
    
    @classmethod
    def _preprocess_image(cls, image_bytes: bytes) -> Optional[Image.Image]:
        try:
            from PIL import Image, ImageFilter, ImageEnhance
            from io import BytesIO
            
            Image.MAX_IMAGE_PIXELS = settings.MAX_IMAGE_PIXELS
            image = Image.open(BytesIO(image_bytes))
            
            if image.mode != 'L':
                image = image.convert('L')
            
            if image.size[0] < settings.MIN_IMAGE_DIMENSION or image.size[1] < settings.MIN_IMAGE_DIMENSION:
                ratio = max(settings.MIN_IMAGE_DIMENSION / image.size[0], 
                           settings.MIN_IMAGE_DIMENSION / image.size[1])
                new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
                image = image.resize(new_size, Image.Resampling.LANCZOS)
            
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.5)
            
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(1.5)
            
            image = image.filter(ImageFilter.MedianFilter(size=3))
            image = image.point(lambda x: 0 if x < 128 else 255, '1')
            
            return image
            
        except Exception as e:
            logger.error(f"Image preprocessing error: {e}")
            return None
    
    @classmethod
    def check_quality(cls, image_bytes: bytes) -> Tuple[bool, str]:
        if Image is None:
            return True, ""
        
        try:
            from PIL import Image, ImageFilter, ImageStat
            from io import BytesIO
            
            Image.MAX_IMAGE_PIXELS = settings.MAX_IMAGE_PIXELS
            image = Image.open(BytesIO(image_bytes))
            w, h = image.size
            
            if w < settings.MIN_IMAGE_DIMENSION or h < settings.MIN_IMAGE_DIMENSION:
                return False, "دقة الصورة منخفضة جداً"
            
            edges = image.convert("L").filter(ImageFilter.FIND_EDGES)
            variance = ImageStat.Stat(edges).var[0]
            if variance < settings.BLUR_VARIANCE_THRESHOLD:
                return False, "الصورة غير واضحة أو ضبابية"
            
            return True, ""
            
        except Exception as e:
            logger.error(f"Image quality check error: {e}")
            return True, ""

ocr_service = OCRService()