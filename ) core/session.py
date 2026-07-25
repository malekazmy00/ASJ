# core/session.py
import streamlit as st
import secrets
import time
import threading
from typing import Optional, Tuple
from dataclasses import dataclass, field

from core.config import settings
from core.session_storage import session_storage
from core.security import security_service
from core.exceptions import AuthenticationError

@dataclass
class SessionData:
    username: str
    role: str
    user_agent: str
    session_id: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    refresh_token: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    device_fingerprint: str = ""
    
    def is_expired(self) -> bool:
        return time.time() - self.last_activity > settings.SESSION_TIMEOUT
    
    def refresh(self):
        self.last_activity = time.time()

class SessionManager:
    """مدير الجلسات مع تخزين مركزي"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance
    
    def _init(self):
        self._storage = session_storage
    
    def create_session(self, username: str, role: str, user_agent: str = "Unknown", 
                       device_fingerprint: str = "") -> Tuple[str, str]:
        with self._lock:
            refresh_token = secrets.token_urlsafe(32)
            
            session = SessionData(
                username=username,
                role=role,
                user_agent=user_agent,
                refresh_token=refresh_token,
                device_fingerprint=device_fingerprint
            )
            
            access_token = security_service.generate_jwt(
                username, role, session.session_id, device_fingerprint
            )
            
            self._storage.save_session(
                session_id=session.session_id,
                data={
                    "username": username,
                    "role": role,
                    "user_agent": user_agent,
                    "created_at": session.created_at,
                    "last_activity": session.last_activity,
                    "device_fingerprint": device_fingerprint
                },
                refresh_token=refresh_token,
                ttl=settings.SESSION_TIMEOUT
            )
            
            st.session_state.session_id = session.session_id
            st.session_state.access_token = access_token
            st.session_state.refresh_token = refresh_token
            
            return access_token, refresh_token
    
    def get_session(self) -> Optional[SessionData]:
        session_id = st.session_state.get('session_id')
        access_token = st.session_state.get('access_token')
        refresh_token = st.session_state.get('refresh_token')
        
        if not session_id or not access_token:
            return None
        
        session_data = self._storage.get_session(session_id)
        if not session_data:
            self.clear_session()
            return None
        
        last_activity = session_data.get("last_activity", 0)
        if time.time() - last_activity > settings.SESSION_TIMEOUT:
            self.clear_session()
            return None
        
        valid, payload = security_service.validate_jwt(access_token)
        if not valid:
            if refresh_token and self._storage.validate_refresh_token(session_id, refresh_token):
                return self._refresh_session(session_id, refresh_token)
            self.clear_session()
            return None
        
        self._storage.update_activity(session_id)
        
        return SessionData(
            username=session_data["username"],
            role=session_data["role"],
            user_agent=session_data.get("user_agent", ""),
            session_id=session_id,
            created_at=session_data.get("created_at", time.time()),
            last_activity=session_data.get("last_activity", time.time()),
            refresh_token=refresh_token,
            device_fingerprint=session_data.get("device_fingerprint", "")
        )
    
    def _refresh_session(self, session_id: str, refresh_token: str) -> Optional[SessionData]:
        session_data = self._storage.get_session(session_id)
        if not session_data:
            return None
        
        new_refresh_token = secrets.token_urlsafe(32)
        
        new_jwt = security_service.generate_jwt(
            session_data["username"],
            session_data["role"],
            session_id,
            session_data.get("device_fingerprint", "")
        )
        
        session_data["last_activity"] = time.time()
        
        self._storage.rotate_refresh_token(session_id, new_refresh_token)
        self._storage.save_session(
            session_id=session_id,
            data=session_data,
            refresh_token=new_refresh_token,
            ttl=settings.SESSION_TIMEOUT
        )
        
        st.session_state.access_token = new_jwt
        st.session_state.refresh_token = new_refresh_token
        
        return SessionData(
            username=session_data["username"],
            role=session_data["role"],
            user_agent=session_data.get("user_agent", ""),
            session_id=session_id,
            created_at=session_data.get("created_at", time.time()),
            last_activity=session_data.get("last_activity", time.time()),
            refresh_token=new_refresh_token,
            device_fingerprint=session_data.get("device_fingerprint", "")
        )
    
    def clear_session(self):
        session_id = st.session_state.get('session_id')
        if session_id:
            self._storage.delete_session(session_id)
        
        st.session_state.pop('session_id', None)
        st.session_state.pop('access_token', None)
        st.session_state.pop('refresh_token', None)
    
    def get_username(self) -> Optional[str]:
        session = self.get_session()
        return session.username if session else None
    
    def get_role(self) -> Optional[str]:
        session = self.get_session()
        return session.role if session else None
    
    def is_authenticated(self) -> bool:
        return self.get_session() is not None
    
    def check_rate_limit(self, key: str, limit: int = 5, window: int = 60) -> bool:
        return self._storage.check_rate_limit(key, limit, window)

session_manager = SessionManager()