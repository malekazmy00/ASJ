# core/database.py
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session, scoped_session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from typing import Generator, Optional
import logging
from pathlib import Path
import time

from core.config import settings
from core.models import Base
from core.exceptions import DatabaseError

logger = logging.getLogger(__name__)

class DatabaseManager:
    """مدير قاعدة البيانات (يدعم PostgreSQL / Supabase و SQLite)"""
    
    _instance = None
    _engine = None
    _session_factory = None
    _scoped_session = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._init_engine()
            self._init_session()
            self._initialized = True
    
    def _init_engine(self):
        db_url = settings.DATABASE_URL
        
        if db_url and db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)

        if db_url:
            # الاتصال بـ Supabase (PostgreSQL)
            self._engine = create_engine(
                db_url,
                poolclass=QueuePool,
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=10,
                pool_pre_ping=True,
                echo=settings.DB_ECHO,
            )
            logger.info("Connected to remote PostgreSQL / Supabase database.")
        else:
            # الاتصال المحلي التقليدي (SQLite)
            settings.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            connect_args = {
                'timeout': settings.DB_TIMEOUT,
                'check_same_thread': False,
            }
            self._engine = create_engine(
                f'sqlite:///{settings.DB_PATH}',
                echo=settings.DB_ECHO,
                poolclass=QueuePool,
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=10,
                pool_pre_ping=True,
                connect_args=connect_args,
            )
            
            @event.listens_for(self._engine, 'connect')
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute('PRAGMA journal_mode=WAL')
                cursor.execute('PRAGMA synchronous=NORMAL')
                cursor.execute('PRAGMA foreign_keys=ON')
                cursor.execute('PRAGMA cache_size=-10000')
                cursor.execute('PRAGMA temp_store=MEMORY')
                cursor.close()
            logger.info("Connected to local SQLite database.")
    
    def _init_session(self):
        self._session_factory = sessionmaker(
            bind=self._engine,
            expire_on_commit=False,
            autoflush=False
        )
        self._scoped_session = scoped_session(self._session_factory)
    
    def init_database(self, create_fts: bool = True):
        if self._engine is None:
            self._init_engine()
        
        Base.metadata.create_all(self._engine)
        
        # FTS5 يتم إنشاؤه فقط لو كنا نستخدم SQLite محلياً
        if create_fts and not settings.DATABASE_URL:
            self._init_fts()
        
        self._init_default_users()
    
    def _init_fts(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='inventory_fts'"
            )
            if cursor.fetchone()[0] == 0:
                logger.info("Creating FTS5 virtual table...")
                cursor.execute('''
                    CREATE VIRTUAL TABLE inventory_fts USING fts5(
                        item_type, part_number, location, ocr_text,
                        content='inventory_items',
                        content_rowid='item_id'
                    )
                ''')
                cursor.execute('''
                    INSERT INTO inventory_fts(rowid, item_type, part_number, location, ocr_text)
                    SELECT item_id, item_type, part_number, location, ocr_text
                    FROM inventory_items
                ''')
                
                cursor.execute('''
                    CREATE TRIGGER inventory_fts_insert AFTER INSERT ON inventory_items
                    BEGIN
                        INSERT INTO inventory_fts(rowid, item_type, part_number, location, ocr_text)
                        VALUES (new.item_id, new.item_type, new.part_number, new.location, new.ocr_text);
                    END
                ''')
                
                cursor.execute('''
                    CREATE TRIGGER inventory_fts_update AFTER UPDATE ON inventory_items
                    BEGIN
                        INSERT INTO inventory_fts(inventory_fts, rowid, item_type, part_number, location, ocr_text)
                        VALUES ('delete', old.item_id, old.item_type, old.part_number, old.location, old.ocr_text);
                        INSERT INTO inventory_fts(rowid, item_type, part_number, location, ocr_text)
                        VALUES (new.item_id, new.item_type, new.part_number, new.location, new.ocr_text);
                    END
                ''')
                
                cursor.execute('''
                    CREATE TRIGGER inventory_fts_delete AFTER DELETE ON inventory_items
                    BEGIN
                        INSERT INTO inventory_fts(inventory_fts, rowid, item_type, part_number, location, ocr_text)
                        VALUES ('delete', old.item_id, old.item_type, old.part_number, old.location, old.ocr_text);
                    END
                ''')
                
                conn.commit()
                logger.info("FTS5 created successfully")
    
    def _init_default_users(self):
        from core.security import security_service
        from core.models import User
        
        with self.get_session() as session:
            if session.query(User).count() == 0:
                default_users = [
                    ('admin', '3333', 'admin', True, True, 'Active'),
                    ('engineer', '2222', 'engineer', True, True, 'Active'),
                    ('worker', '1111', 'worker', False, False, 'Active')
                ]
                for user, pwd, role, exp, track, status in default_users:
                    hashed = security_service.hash_password(pwd)
                    user_obj = User(
                        username=user,
                        password=hashed,
                        role=role,
                        can_export=exp,
                        can_track=track,
                        status=status
                    )
                    session.add(user_obj)
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database error: {e}")
            raise DatabaseError(str(e)) from e
        finally:
            session.close()
    
    @contextmanager
    def get_connection(self):
        conn = self._engine.raw_connection()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()
            
    def backup(self) -> Path:
        from datetime import datetime
        
        backup_dir = settings.BASE_DIR / 'backups'
        backup_dir.mkdir(exist_ok=True)
        
        backup_file = backup_dir / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        
        with self.get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(f"VACUUM INTO '{backup_file}'")
            conn.commit()
        
        logger.info(f"Backup created: {backup_file}")
        return backup_file
    
    def restore(self, backup_file: Path, checksum: Optional[str] = None):
        import shutil
        import hashlib
        
        if not backup_file.exists():
            raise DatabaseError("ملف النسخة الاحتياطية غير موجود")
        
        if checksum:
            with open(backup_file, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
            if file_hash != checksum:
                raise DatabaseError("Checksum غير متطابق")
        
        self._scoped_session.remove()
        self._engine.dispose()
        
        shutil.copy2(backup_file, settings.DB_PATH)
        
        self._init_engine()
        self._init_session()
        
        logger.info(f"Database restored from: {backup_file}")

class UnitOfWork:
    """وحدة العمل - تدير Session واحدة للعمليات المتعددة"""
    
    def __init__(self):
        self._session: Optional[Session] = None
        self._repositories: dict = {}
        self._closed = False
    
    def __enter__(self):
        self._session = db._session_factory()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()
        return False
    
    def get_repository(self, repo_class, *args, **kwargs):
        key = repo_class.__name__
        if key not in self._repositories:
            repo = repo_class(*args, **kwargs)
            repo.set_session(self._session)
            self._repositories[key] = repo
        return self._repositories[key]
    
    def commit(self):
        if self._session and not self._closed:
            try:
                self._session.commit()
            except Exception as e:
                self._session.rollback()
                raise DatabaseError(f"Commit failed: {str(e)}") from e
    
    def rollback(self):
        if self._session and not self._closed:
            self._session.rollback()
    
    def close(self):
        if self._session and not self._closed:
            self._session.close()
            self._session = None
            self._closed = True

db = DatabaseManager()