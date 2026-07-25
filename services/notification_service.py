# services/notification_service.py
from datetime import datetime
from typing import List, Optional

from core.database import UnitOfWork
from repositories.notification_repo import NotificationRepository
from repositories.query_repo import QueryRepository

class NotificationService:
    """خدمة التنبيهات والإشعارات"""
    
    @classmethod
    def add_notification(cls, message: str) -> bool:
        """إضافة تنبيه جديد"""
        try:
            with UnitOfWork() as uow:
                repo = uow.get_repository(NotificationRepository)
                repo.create(message=message)
                return True
        except Exception as e:
            print(f"Error adding notification: {e}")
            return False
    
    @classmethod
    def get_recent(cls, limit: int = 50) -> List:
        """الحصول على أحدث التنبيهات"""
        with UnitOfWork() as uow:
            repo = uow.get_repository(NotificationRepository)
            return repo.get_recent(limit)
    
    @classmethod
    def mark_all_read(cls):
        """تحديد جميع التنبيهات كمقروءة"""
        with UnitOfWork() as uow:
            repo = uow.get_repository(NotificationRepository)
            repo.mark_all_read()
    
    @classmethod
    def clear_all(cls):
        """مسح جميع التنبيهات"""
        with UnitOfWork() as uow:
            repo = uow.get_repository(NotificationRepository)
            repo.clear_all()
    
    @classmethod
    def check_and_notify_request(cls, part_number: str, category: str, location: str):
        """التحقق من طلبات القطع وإرسال تنبيه"""
        with UnitOfWork() as uow:
            query_repo_local = uow.get_repository(QueryRepository)
            
            # البحث عن طلبات معلقة
            pending = query_repo_local.get_pending_by_part(part_number, category)
            
            if pending:
                for query in pending:
                    # تحديث حالة الطلب
                    query_repo_local.update_status(query.query_id, "Fulfilled")
                    
                    # إرسال تنبيه
                    cls.add_notification(
                        f" تم توفير القطعة المطلوبة: {part_number or category} - {query.requested_by or query.username} - في الرف {location}"
                    )

notification_service = NotificationService()