# middleware/auth_middleware.py
import streamlit as st
from typing import Callable, List
from functools import wraps

from core.session import session_manager
from core.exceptions import AuthenticationError, AuthorizationError

def require_auth(func: Callable):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session_manager.is_authenticated():
            st.error("يرجى تسجيل الدخول أولاً")
            st.stop()
        return func(*args, **kwargs)
    return wrapper

def require_role(*roles: List[str]):
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            session = session_manager.get_session()
            if not session:
                st.error("يرجى تسجيل الدخول أولاً")
                st.stop()
            
            if session.role not in roles:
                st.error("لا تملك الصلاحية المناسبة")
                st.stop()
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

def require_permission(permission: str):
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            username = session_manager.get_username()
            if not username:
                st.error("يرجى تسجيل الدخول أولاً")
                st.stop()
            
            from core.database import UnitOfWork
            from repositories.user_repo import UserRepository
            with UnitOfWork() as uow:
                repo = uow.get_repository(UserRepository)
                allowed = repo.has_permission(username, permission)
            
            if not allowed:
                st.error(f"لا تملك صلاحية {permission}")
                st.stop()
            
            return func(*args, **kwargs)
        return wrapper
    return decorator
