# core/session_storage.py
import json
import time
import threading
from typing import Optional, Dict
from pathlib import Path

from core.config import settings
from core.security import security_service

class SessionStorage:
    """تخزين الجلسات - يدعم Memory, Redis, Database"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_storage()
        return cls._instance
    
    def _init_storage(self):
        self._storage_type = settings.SESSION_TYPE
        self._memory_storage: Dict[str, dict] = {}
        self._redis_client = None
        
        if self._storage_type == "redis":
            self._init_redis()
        elif self._storage_type == "database":
            self._init_database()
    
    def _init_redis(self):
        if settings.REDIS_URL:
            try:
                import redis
                self._redis_client = redis.Redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True
                )
                self._redis_client.ping()
            except Exception as e:
                print(f"Redis connection failed, falling back to memory: {e}")
                self._storage_type = "memory"
    
    def _init_database(self):
        from core.database import db
        with db.get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    data TEXT,
                    created_at REAL,
                    expires_at REAL,
                    refresh_token_hash TEXT
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at)')
            conn.commit()
    
    def save_session(self, session_id: str, data: dict, refresh_token: Optional[str] = None, ttl: int = 3600) -> bool:
        now = time.time()
        expires_at = now + ttl
        
        # ملاحظة: نضم حقول المستخدم (username, role...) مباشرة في نفس القاموس
        # بدل تغليفها تحت مفتاح "data" منفصل، عشان get_session تقدر تقرأها مباشرة
        session_data = dict(data)
        session_data["created_at"] = session_data.get("created_at", now)
        session_data["expires_at"] = expires_at
        session_data["refresh_token_hash"] = security_service.hash_refresh_token(refresh_token) if refresh_token else None
        
        if self._storage_type == "redis" and self._redis_client:
            key = f"{settings.REDIS_PREFIX}{session_id}"
            self._redis_client.setex(key, ttl, json.dumps(session_data))
            return True
        
        elif self._storage_type == "database":
            from core.database import db
            with db.get_connection() as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO sessions 
                    (session_id, data, created_at, expires_at, refresh_token_hash)
                    VALUES (?, ?, ?, ?, ?)
                ''', (session_id, json.dumps(session_data), now, expires_at, 
                      session_data["refresh_token_hash"]))
                conn.commit()
            return True
        
        else:
            self._memory_storage[session_id] = session_data
            return True
    
    def get_session(self, session_id: str) -> Optional[dict]:
        if self._storage_type == "redis" and self._redis_client:
            key = f"{settings.REDIS_PREFIX}{session_id}"
            data = self._redis_client.get(key)
            if data:
                return json.loads(data)
            return None
        
        elif self._storage_type == "database":
            from core.database import db
            with db.get_connection() as conn:
                result = conn.execute(
                    "SELECT data FROM sessions WHERE session_id=? AND expires_at > ?",
                    (session_id, time.time())
                ).fetchone()
                if result:
                    return json.loads(result[0])
            return None
        
        else:
            return self._memory_storage.get(session_id)
    
    def update_activity(self, session_id: str) -> bool:
        now = time.time()
        
        if self._storage_type == "redis" and self._redis_client:
            key = f"{settings.REDIS_PREFIX}{session_id}"
            data = self._redis_client.get(key)
            if data:
                session_data = json.loads(data)
                session_data["last_activity"] = now
                ttl = int(session_data["expires_at"] - now)
                if ttl > 0:
                    self._redis_client.setex(key, ttl, json.dumps(session_data))
                return True
            return False
        
        elif self._storage_type == "database":
            from core.database import db
            with db.get_connection() as conn:
                result = conn.execute(
                    "UPDATE sessions SET data = json_set(data, '$.last_activity', ?) WHERE session_id=? AND expires_at > ?",
                    (now, session_id, now)
                )
                conn.commit()
                return result.rowcount > 0
        
        else:
            session = self._memory_storage.get(session_id)
            if session:
                session["last_activity"] = now
                return True
            return False
    
    def delete_session(self, session_id: str) -> bool:
        if self._storage_type == "redis" and self._redis_client:
            key = f"{settings.REDIS_PREFIX}{session_id}"
            self._redis_client.delete(key)
            return True
        
        elif self._storage_type == "database":
            from core.database import db
            with db.get_connection() as conn:
                conn.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))
                conn.commit()
            return True
        
        else:
            if session_id in self._memory_storage:
                del self._memory_storage[session_id]
            return True
    
    def validate_refresh_token(self, session_id: str, refresh_token: str) -> bool:
        session = self.get_session(session_id)
        if not session:
            return False
        
        token_hash = security_service.hash_refresh_token(refresh_token)
        stored_hash = session.get("refresh_token_hash")
        
        if not stored_hash:
            return False
        
        return token_hash == stored_hash
    
    def rotate_refresh_token(self, session_id: str, new_refresh_token: str) -> bool:
        session = self.get_session(session_id)
        if not session:
            return False
        
        session["refresh_token_hash"] = security_service.hash_refresh_token(new_refresh_token)
        
        if self._storage_type == "redis" and self._redis_client:
            key = f"{settings.REDIS_PREFIX}{session_id}"
            ttl = int(session["expires_at"] - time.time())
            if ttl > 0:
                self._redis_client.setex(key, ttl, json.dumps(session))
            return True
        
        elif self._storage_type == "database":
            from core.database import db
            with db.get_connection() as conn:
                conn.execute(
                    "UPDATE sessions SET refresh_token_hash=? WHERE session_id=?",
                    (session["refresh_token_hash"], session_id)
                )
                conn.commit()
            return True
        
        else:
            self._memory_storage[session_id] = session
            return True
    
    def cleanup_expired(self):
        now = time.time()
        
        if self._storage_type == "database":
            from core.database import db
            with db.get_connection() as conn:
                conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
                conn.commit()
        
        elif self._storage_type == "memory":
            expired = [
                sid for sid, data in self._memory_storage.items()
                if data.get("expires_at", 0) < now
            ]
            for sid in expired:
                del self._memory_storage[sid]

session_storage = SessionStorage()