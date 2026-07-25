# services/auth_service.py
import logging
from typing import Tuple, Optional

from core.session import session_manager
from core.security import security_service
from core.exceptions import AuthenticationError, RateLimitError
from core.database import UnitOfWork
from repositories.user_repo import user_repo, UserRepository
from core.enums import Role
from core.config import settings

logger = logging.getLogger(__name__)

class AuthService:
    @classmethod
    def login(cls, username: str, password: str, user_agent: str = "Unknown",
              device_fingerprint: str = "") -> Tuple[bool, Optional[str], Optional[str]]:
        
        if not session_manager.check_rate_limit(f"login_{username}", 
                                                 limit=settings.RATE_LIMIT_LOGIN, 
                                                 window=settings.RATE_LIMIT_WINDOW):
            logger.warning(f"Rate limit exceeded for user: {username}")
            return False, None, "اسم المستخدم أو كلمة المرور غير صحيحة"
        
        try:
            with UnitOfWork() as uow:
                repo = uow.get_repository(UserRepository)
                
                user = repo.get_by_username(username)
                if not user:
                    return False, None, "اسم المستخدم أو كلمة المرور غير صحيحة"
                
                if user.status == "Banned":
                    return False, None, "الحساب غير نشط"
                
                if not security_service.verify_password(user.password, password):
                    logger.warning(f"Failed login attempt for user: {username}")
                    return False, None, "اسم المستخدم أو كلمة المرور غير صحيحة"
                
                if security_service.check_needs_rehash(user.password):
                    new_hash = security_service.hash_password(password)
                    repo.update_password(username, new_hash)
                
                repo.update_last_login(username, "", user_agent)
                uow.commit()
                
                access_token, refresh_token = session_manager.create_session(
                    username=username,
                    role=user.role,
                    user_agent=user_agent,
                    device_fingerprint=device_fingerprint
                )
                
                logger.info(f"User logged in: {username}")
                return True, user.role, None
                
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False, None, "حدث خطأ أثناء تسجيل الدخول"
    
    @classmethod
    def logout(cls, username: str):
        logger.info(f"User logged out: {username}")
        session_manager.clear_session()
    
    @classmethod
    def change_password(cls, username: str, old_password: str, new_password: str) -> bool:
        try:
            with UnitOfWork() as uow:
                repo = uow.get_repository(UserRepository)
                user = repo.get_by_username(username)
                if not user:
                    return False
                
                if not security_service.verify_password(user.password, old_password):
                    return False
                
                new_hash = security_service.hash_password(new_password)
                repo.update_password(username, new_hash)
                logger.info(f"Password changed for user: {username}")
                return True
        except Exception as e:
            logger.error(f"Password change error: {e}")
            return False

auth_service = AuthService()
