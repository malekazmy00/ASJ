# core/security.py
import secrets
import hashlib
import hmac
from typing import Optional, Tuple
from PIL import Image
from io import BytesIO

import argon2
from jose import JWTError, jwt

from core.config import settings
from core.exceptions import SecurityError

# Argon2 Hasher
hasher = argon2.PasswordHasher(
    time_cost=2,
    memory_cost=102400,
    parallelism=8,
    hash_len=32,
    salt_len=16
)

class SecurityService:
    """خدمة الأمان"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        return hasher.hash(password)
    
    @staticmethod
    def verify_password(stored_hash: str, provided_password: str) -> bool:
        try:
            return hasher.verify(stored_hash, provided_password)
        except argon2.exceptions.VerificationError:
            return False
        except Exception:
            return False
    
    @staticmethod
    def check_needs_rehash(stored_hash: str) -> bool:
        try:
            return hasher.check_needs_rehash(stored_hash)
        except:
            return False
    
    @staticmethod
    def hash_refresh_token(token: str, secret_key: str = None) -> str:
        """تشفير Refresh Token باستخدام HMAC"""
        key = secret_key or settings.SECRET_KEY
        return hmac.new(
            key.encode('utf-8'),
            token.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    @staticmethod
    def generate_jwt(username: str, role: str, session_id: str, device_fingerprint: str = "") -> str:
        import time
        payload = {
            "sub": username,
            "role": role,
            "sid": session_id,
            "dfp": device_fingerprint[:16] if device_fingerprint else "",
            "iat": int(time.time()),
            "exp": int(time.time() + settings.SESSION_TIMEOUT),
            "jti": secrets.token_urlsafe(12)
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    
    @staticmethod
    def validate_jwt(token: str) -> Tuple[bool, Optional[dict]]:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            return True, payload
        except JWTError:
            return False, None
    
    @staticmethod
    def generate_secure_password(length: int = 12) -> str:
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()"
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    @staticmethod
    def hash_file(file_bytes: bytes) -> str:
        return hashlib.sha256(file_bytes).hexdigest()
    
    @staticmethod
    def validate_image(file_bytes: bytes) -> Tuple[bool, str]:
        try:
            if len(file_bytes) > settings.MAX_IMAGE_MB * 1024 * 1024:
                return False, f"حجم الصورة يتجاوز {settings.MAX_IMAGE_MB}MB"
            
            Image.MAX_IMAGE_PIXELS = settings.MAX_IMAGE_PIXELS
            image = Image.open(BytesIO(file_bytes))
            
            if image.width * image.height > settings.MAX_IMAGE_PIXELS:
                return False, "أبعاد الصورة كبيرة جداً"
            
            return True, ""
        except Exception as e:
            return False, f"ملف غير صحيح: {str(e)}"

security_service = SecurityService()