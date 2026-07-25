# repositories/query_repo.py
from typing import List, Optional
from datetime import datetime

from repositories.base import BaseRepository
from core.models import EngineerQuery
from core.enums import QueryStatus

class QueryRepository(BaseRepository):
    def __init__(self):
        super().__init__(EngineerQuery)
    
    def get_pending(self) -> List[EngineerQuery]:
        return self.session.query(EngineerQuery).filter(
            EngineerQuery.status == QueryStatus.PENDING
        ).order_by(EngineerQuery.timestamp.desc()).all()
    
    def get_pending_by_part(self, part_number: str, category: str = None) -> List[EngineerQuery]:
        query = self.session.query(EngineerQuery).filter(
            EngineerQuery.status == QueryStatus.PENDING
        )
        
        if part_number and part_number != "PENDING":
            query = query.filter(
                (EngineerQuery.part_number.like(f"%{part_number}%")) |
                (EngineerQuery.part_category.like(f"%{part_number}%"))
            )
        elif category:
            query = query.filter(
                EngineerQuery.part_category.like(f"%{category}%")
            )
        
        return query.all()
    
    def update_status(self, query_id: int, status: str) -> bool:
        query = self.get(query_id)
        if query:
            query.status = status
            self.session.add(query)
            self.session.flush()
            return True
        return False

query_repo = QueryRepository()