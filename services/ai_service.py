# services/ai_service.py
import json
import logging
import time
import base64
import re
from typing import Optional, Tuple
from io import BytesIO
from datetime import datetime, timedelta

import streamlit as st
from PIL import Image

from core.config import settings
from core.security import security_service

logger = logging.getLogger(__name__)

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, timeout_seconds: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"
    
    def is_open(self) -> bool:
        if self.state == "OPEN":
            if datetime.now() - self.last_failure_time > timedelta(seconds=self.timeout_seconds):
                self.state = "HALF_OPEN"
                return False
            return True
        return False
    
    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
    
    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"

class AIService:
    _instance = None
    _model_cache = {}
    _response_cache = {}
    _circuit_breaker = CircuitBreaker()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def _get_api_key(cls) -> Optional[str]:
        return settings.GEMINI_API_KEY or st.secrets.get("GEMINI_API_KEY")
    
    @classmethod
    def _get_model(cls, model_name: str):
        import google.generativeai as genai
        
        api_key = cls._get_api_key()
        if not api_key:
            return None
        
        cache_key = f"{api_key}_{model_name}"
        if cache_key not in cls._model_cache:
            genai.configure(api_key=api_key)
            cls._model_cache[cache_key] = genai.GenerativeModel(model_name)
        
        return cls._model_cache[cache_key]
    
    @classmethod
    def analyze_part(cls, part_number: str, image_base64: Optional[str] = None,
                     max_retries: int = 3) -> Tuple[str, str, str, str, str, str, str]:
        
        if cls._circuit_breaker.is_open():
            logger.warning("Circuit breaker is open, skipping AI call")
            return "ERROR", "ERROR", part_number, "", "", "", "الخدمة غير متاحة حالياً"
        
        image_hash = None
        if image_base64:
            image_bytes = base64.b64decode(image_base64)
            image_hash = security_service.hash_file(image_bytes)
        
        cache_key = f"{part_number}_{image_hash or 'no_image'}"
        if cache_key in cls._response_cache:
            cached_time, cached_data = cls._response_cache[cache_key]
            if datetime.now() - cached_time < timedelta(hours=1):
                return cached_data
        
        try:
            result = cls._call_gemini_with_retry(part_number, image_base64, max_retries)
            
            if result and not result[6].startswith(('خطأ', 'Pending', 'تحذير')):
                cls._response_cache[cache_key] = (datetime.now(), result)
                if len(cls._response_cache) > 1000:
                    cls._clean_cache()
            
            cls._circuit_breaker.record_success()
            return result
            
        except Exception as e:
            cls._circuit_breaker.record_failure()
            logger.error(f"AI service error: {e}")
            return "ERROR", "ERROR", part_number, "", "", "", f"خطأ: {str(e)}"
    
    @classmethod
    def _call_gemini_with_retry(cls, part_number: str, image_base64: Optional[str] = None,
                                max_retries: int = 3) -> Tuple[str, str, str, str, str, str, str]:
        
        import google.generativeai as genai
        
        if not cls._get_api_key():
            return "UNKNOWN", "UNKNOWN", part_number, "", "", "", "مفتاح API غير متاح"
        
        # ترتيب تصاعدي: الأرخص/الأسرع أولاً، والانتقال للنموذج الأقوى فقط عند الحاجة
        # (استنفاذ الباقة أو مشكلة في التحليل)، وليس بإعادة محاولة نفس النموذج
        model_chain = [settings.LITE_AI_MODEL, settings.FAST_AI_MODEL, settings.STRONG_AI_MODEL]
        last_error = "فشل بعد تجربة كل النماذج المتاحة"
        
        generation_config = {
            "temperature": 0.1,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 1024,
        }
        
        prompt = f"""Analyze this medical equipment part.
        Part Number or Description: '{part_number}'
        
        Return a JSON object with exactly these keys:
        - "Brand": string
        - "Category": string
        - "Part_Number": string
        - "Compatible_Model": string
        - "Additional_Compatibility": string
        - "Market_Value": string
        - "Gemini_Insights": string (in Arabic)
        
        Respond ONLY with valid JSON."""
        
        for tier_index, model_name in enumerate(model_chain):
            is_last_tier = (tier_index == len(model_chain) - 1)
            
            try:
                model = cls._get_model(model_name)
                if not model:
                    last_error = "تعذر تحميل النموذج"
                    continue
                
                if image_base64:
                    image_data = base64.b64decode(image_base64)
                    image = Image.open(BytesIO(image_data))
                    response = model.generate_content([prompt, image], generation_config=generation_config)
                else:
                    response = model.generate_content(prompt, generation_config=generation_config)
                
                text_resp = response.text
                text_resp = re.sub(r'```json\s*', '', text_resp)
                text_resp = re.sub(r'```\s*', '', text_resp)
                text_resp = text_resp.strip()
                
                data = json.loads(text_resp)
                
                return (
                    data.get("Brand", "Unknown"),
                    data.get("Category", "Unknown"),
                    data.get("Part_Number", part_number),
                    data.get("Compatible_Model", ""),
                    data.get("Additional_Compatibility", ""),
                    data.get("Market_Value", ""),
                    data.get("Gemini_Insights", "تم الفحص بنجاح")
                )
                
            except json.JSONDecodeError as e:
                logger.warning(f"JSON decode error on {model_name}: {e}")
                last_error = "خطأ في تنسيق الاستجابة"
                continue  # جرب النموذج الأقوى التالي
                    
            except Exception as e:
                logger.error(f"Gemini error on {model_name}: {e}")
                
                error_str = str(e).lower()
                if any(x in error_str for x in ["429", "exhausted", "quota", "rate limit"]):
                    if is_last_tier:
                        return "PENDING", "PENDING", part_number, "", "", "", "Pending_AI_Quota"
                    continue  # باقة هذا النموذج انتهت، جرب النموذج الأقوى التالي
                
                last_error = f"خطأ: {str(e)}"
                if is_last_tier:
                    return "ERROR", "ERROR", part_number, "", "", "", last_error
                continue  # مشكلة في التحليل، جرب النموذج الأقوى التالي
        
        return "ERROR", "ERROR", part_number, "", "", "", last_error
    
    @classmethod
    def _clean_cache(cls):
        now = datetime.now()
        keys_to_delete = []
        for key, (timestamp, _) in cls._response_cache.items():
            if now - timestamp > timedelta(hours=24):
                keys_to_delete.append(key)
        for key in keys_to_delete:
            del cls._response_cache[key]
    
    @classmethod
    def extract_part_number(cls, text: str) -> Optional[str]:
        if not text:
            return None
        
        patterns = [
            r'(?:PN|P/N|Part|PART)[:\s]*([A-Z0-9\-/]+)',
            r'[A-Z]{2,4}[- ]?\d{4,8}',
            r'\d{5,10}',
            r'[A-Z]{2,4}\d{4,8}',
            r'[A-Z]{2,4}[-\s]?\d{4,8}[-\s]?[A-Z]?\d*',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1) if '(' in pattern else match.group().strip()
        
        return None

ai_service = AIService()
