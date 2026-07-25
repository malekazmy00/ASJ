# repositories/knowledge_repo.py
from typing import Optional
from datetime import datetime

from repositories.base import BaseRepository
from core.models import KnowledgeBase

class KnowledgeRepository(BaseRepository):
    def __init__(self):
        super().__init__(KnowledgeBase)
    
    def get_by_part_number(self, part_number: str) -> Optional[KnowledgeBase]:
        return self.session.query(KnowledgeBase).filter(
            KnowledgeBase.Part_Number == part_number
        ).first()
    
    def create_or_update(self, part_number: str, **kwargs) -> KnowledgeBase:
        existing = self.get_by_part_number(part_number)
        if existing:
            for key, value in kwargs.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            existing.last_updated = datetime.now()
            self.session.add(existing)
            self.session.flush()
            return existing
        else:
            return self.create(Part_Number=part_number, **kwargs)

knowledge_repo = KnowledgeRepository()