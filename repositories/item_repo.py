# repositories/item_repo.py
from typing import Optional, List
from datetime import datetime

from repositories.base import BaseRepository
from core.models import InventoryItem
from core.enums import ItemStatus

class ItemRepository(BaseRepository):
    def __init__(self):
        super().__init__(InventoryItem)
    
    def get_by_part_number(self, part_number: str) -> List[InventoryItem]:
        return self.session.query(InventoryItem).filter(
            InventoryItem.part_number == part_number
        ).all()
    
    def get_available(self) -> List[InventoryItem]:
        return self.session.query(InventoryItem).filter(
            InventoryItem.status == ItemStatus.AVAILABLE
        ).all()
    
    def get_by_location(self, location: str) -> List[InventoryItem]:
        return self.session.query(InventoryItem).filter(
            InventoryItem.location == location
        ).all()
    
    def update_status(self, item_id: int, status: ItemStatus) -> bool:
        item = self.get(item_id)
        if item:
            item.status = status
            self.session.add(item)
            self.session.flush()
            return True
        return False
    
    def get_statistics(self) -> dict:
        total = self.count()
        available = self.count(status=ItemStatus.AVAILABLE)
        out = self.count(status=ItemStatus.OUT)
        return {
            "total": total,
            "available": available,
            "out": out
        }

item_repo = ItemRepository()