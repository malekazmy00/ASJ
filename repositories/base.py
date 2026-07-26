# repositories/base.py
from typing import TypeVar, Generic, Type, Optional, List, Any
from sqlalchemy.orm import Session, Query
from sqlalchemy import text
import logging

from core.database import db
from core.exceptions import NotFoundError, DatabaseError

logger = logging.getLogger(__name__)
T = TypeVar('T')

class BaseRepository(Generic[T]):
    """Repository أساسي مع دعم كامل للـ Queries"""
    
    def __init__(self, model_class: Type[T]):
        self.model_class = model_class
        self._session: Optional[Session] = None
    
    def set_session(self, session: Session):
        self._session = session
    
    @property
    def session(self) -> Session:
        if self._session is None:
            raise DatabaseError("Repository must be used within Unit of Work")
        return self._session
    
    def get(self, id: Any) -> Optional[T]:
        return self.session.get(self.model_class, id)
    
    def get_or_raise(self, id: Any) -> T:
        obj = self.get(id)
        if not obj:
            raise NotFoundError(f"{self.model_class.__name__} not found: {id}")
        return obj
    
    def create(self, **kwargs) -> T:
        instance = self.model_class(**kwargs)
        self.session.add(instance)
        self.session.flush()
        return instance
    
    def update(self, instance: T, **kwargs) -> T:
        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        self.session.add(instance)
        self.session.flush()
        return instance
    
    def delete(self, instance: T) -> bool:
        self.session.delete(instance)
        self.session.flush()
        return True
    
    def count(self, **filters) -> int:
        query = self._build_query(**filters)
        return query.count()
    
    def _build_query(self, **filters) -> Query:
        query = self.session.query(self.model_class)
        
        for key, value in filters.items():
            if not hasattr(self.model_class, key):
                continue
            
            column = getattr(self.model_class, key)
            
            if isinstance(value, dict):
                for op, val in value.items():
                    if op == "like":
                        query = query.filter(column.like(val))
                    elif op == "ilike":
                        query = query.filter(column.ilike(val))
                    elif op == "in":
                        query = query.filter(column.in_(val))
                    elif op == "gt":
                        query = query.filter(column > val)
                    elif op == "lt":
                        query = query.filter(column < val)
                    elif op == "gte":
                        query = query.filter(column >= val)
                    elif op == "lte":
                        query = query.filter(column <= val)
                    elif op == "not":
                        query = query.filter(column != val)
            else:
                query = query.filter(column == value)
        
        return query
    
    def filter(self, **filters) -> List[T]:
        query = self._build_query(**filters)
        return query.all()
    
    def paginate(self, page: int = 1, page_size: int = 50, **filters) -> tuple:
        query = self._build_query(**filters)
        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        return items, total
    
    def search_fts(self, search_term: str, page: int = 1, page_size: int = 50) -> tuple:
        if not search_term:
            return [], 0
        
        model_name = self.model_class.__tablename__
        
        if model_name == "inventory_items":
            from core.config import settings
            
            if settings.DATABASE_URL:
                # PostgreSQL / Supabase: جدول inventory_fts (FTS5) خاص بـ SQLite بس وغير موجود هنا،
                # فبنستخدم بحث ILIKE عادي على الأعمدة المهمة بدل منه
                pattern = f"%{search_term}%"
                query = self.session.query(self.model_class).filter(
                    self.model_class.status == 'Available'
                ).filter(
                    (self.model_class.item_type.ilike(pattern)) |
                    (self.model_class.part_number.ilike(pattern)) |
                    (self.model_class.location.ilike(pattern))
                )
                total = query.count()
                items = query.offset((page - 1) * page_size).limit(page_size).all()
                return items, total
            
            fts_query = self.session.execute(
                text("""
                    SELECT rowid FROM inventory_fts 
                    WHERE inventory_fts MATCH :term 
                    ORDER BY rank
                    LIMIT :limit OFFSET :offset
                """),
                {
                    "term": search_term,
                    "limit": page_size,
                    "offset": (page - 1) * page_size
                }
            )
            rowids = [row[0] for row in fts_query]
            
            if rowids:
                items = self.session.query(self.model_class).filter(
                    self.model_class.item_id.in_(rowids)
                ).all()
                total = self.session.execute(
                    text("SELECT COUNT(*) FROM inventory_fts WHERE inventory_fts MATCH :term"),
                    {"term": search_term}
                ).scalar()
                return items, total
        
        return [], 0
