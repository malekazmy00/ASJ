# repositories/notification_repo.py
from typing import List, Optional
from datetime import datetime

from repositories.base import BaseRepository
from core.models import Notification

class NotificationRepository(BaseRepository):
    def __init__(self):
        super().__init__(Notification)
    
    def get_recent(self, limit: int = 50) -> List[Notification]:
        return self.session.query(Notification).order_by(
            Notification.timestamp.desc()
        ).limit(limit).all()
    
    def get_unread(self) -> List[Notification]:
        return self.session.query(Notification).filter(
            Notification.is_read == False
        ).order_by(Notification.timestamp.desc()).all()
    
    def mark_all_read(self):
        self.session.query(Notification).update({"is_read": True})
        self.session.flush()
    
    def clear_all(self):
        self.session.query(Notification).delete()
        self.session.flush()

notification_repo = NotificationRepository()