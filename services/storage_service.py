# services/storage_service.py
import logging
import time
from typing import Optional

from core.config import settings

logger = logging.getLogger(__name__)

class StorageService:
    """رفع صور القطع لتخزين دائم (Supabase Storage) بدل القرص المحلي اللي بيتمسح مع أي إعادة نشر"""
    
    _instance = None
    _client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def _get_client(cls):
        if cls._client is not None:
            return cls._client
        
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            return None
        
        try:
            from supabase import create_client
            cls._client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
            return cls._client
        except Exception as e:
            logger.error(f"Supabase Storage client init error: {e}")
            return None
    
    @classmethod
    def is_available(cls) -> bool:
        return cls._get_client() is not None
    
    @classmethod
    def upload_image(cls, image_bytes: bytes, filename: str) -> Optional[str]:
        """يرفع الصورة ويرجع رابط دائم عام ليها، أو None لو فشل الرفع"""
        client = cls._get_client()
        if not client:
            logger.warning("Supabase Storage غير مهيأ - تأكد من SUPABASE_URL و SUPABASE_KEY")
            return None
        
        try:
            bucket = settings.SUPABASE_STORAGE_BUCKET
            path = f"{int(time.time())}_{filename}"
            
            client.storage.from_(bucket).upload(
                path,
                image_bytes,
                {"content-type": "image/jpeg"}
            )
            
            public_url = client.storage.from_(bucket).get_public_url(path)
            return public_url
            
        except Exception as e:
            logger.error(f"Supabase Storage upload error: {e}")
            return None

storage_service = StorageService()