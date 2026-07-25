# repositories/log_repo.py
from datetime import datetime, timedelta
from typing import List, Optional

from repositories.base import BaseRepository
from core.models import TransactionLog
from core.enums import ActionType

class LogRepository(BaseRepository):
    def __init__(self):
        super().__init__(TransactionLog)
    
    def get_by_item(self, item_id: int) -> List[TransactionLog]:
        return self.session.query(TransactionLog).filter(
            TransactionLog.item_id == item_id
        ).order_by(TransactionLog.timestamp.desc()).all()
    
    def get_by_user(self, username: str) -> List[TransactionLog]:
        return self.session.query(TransactionLog).filter(
            TransactionLog.username == username
        ).order_by(TransactionLog.timestamp.desc()).all()
    
    def get_recent(self, days: int = 7) -> List[TransactionLog]:
        since = datetime.now() - timedelta(days=days)
        return self.session.query(TransactionLog).filter(
            TransactionLog.timestamp >= since
        ).order_by(TransactionLog.timestamp.desc()).all()
    
    def log_action(self, item_id: Optional[int], action_type: ActionType, 
                   username: str, details: str, ip: str = "", user_agent: str = "") -> TransactionLog:
        log = TransactionLog(
            item_id=item_id,
            action_type=action_type,
            username=username,
            details=details,
            ip_address=ip,
            user_agent=user_agent
        )
        self.session.add(log)
        self.session.flush()
        return log

log_repo = LogRepository()