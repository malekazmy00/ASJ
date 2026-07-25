# core/exceptions.py

class AppException(Exception):
    """استثناء أساسي للتطبيق"""
    pass

class DatabaseError(AppException):
    """أخطاء قاعدة البيانات"""
    pass

class AuthenticationError(AppException):
    """أخطاء المصادقة"""
    pass

class AuthorizationError(AppException):
    """أخطاء الصلاحيات"""
    pass

class ValidationError(AppException):
    """أخطاء التحقق من البيانات"""
    pass

class RateLimitError(AppException):
    """تجاوز حد الطلبات"""
    pass

class ImageError(AppException):
    """أخطاء الصور"""
    pass

class AIServiceError(AppException):
    """أخطاء الذكاء الاصطناعي"""
    pass

class SecurityError(AppException):
    """أخطاء الأمان"""
    pass

class NotFoundError(AppException):
    """العنصر غير موجود"""
    pass