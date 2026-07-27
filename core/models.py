# core/models.py
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

from core.enums import Role, ItemStatus, ItemCondition, QueryReason, QueryStatus, ActionType

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    username = Column(String(50), primary_key=True)
    password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default='worker')
    can_export = Column(Boolean, default=False)
    can_track = Column(Boolean, default=False)
    can_edit = Column(Boolean, default=False)
    status = Column(String(20), default='Active')
    created_at = Column(DateTime, default=func.now())
    last_login = Column(DateTime)
    last_ip = Column(String(45))
    last_user_agent = Column(String(255))

class InventoryItem(Base):
    __tablename__ = 'inventory_items'
    
    item_id = Column(Integer, primary_key=True, autoincrement=True)
    item_type = Column(String(100), default='بوردة')
    part_number = Column(String(100), default='PENDING')
    location = Column(String(100))
    condition = Column(String(50))
    image_path = Column(String(500))
    ocr_text = Column(Text)
    status = Column(String(20), default='Available')
    sync_status = Column(String(20), default='Offline_Queue')
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_inventory_status', 'status'),
        Index('idx_inventory_part', 'part_number'),
        Index('idx_inventory_item_type', 'item_type'),
    )

class KnowledgeBase(Base):
    __tablename__ = 'specs_knowledge_base'
    
    Part_Number = Column(String(100), primary_key=True)
    Brand = Column(Text)
    Category = Column(Text)
    Compatible_Model = Column(Text)
    Additional_Compatibility = Column(Text)
    market_value = Column(Text)
    Gemini_Insights = Column(Text)
    last_updated = Column(DateTime, default=func.now(), onupdate=func.now())

class TransactionLog(Base):
    __tablename__ = 'transactions_log'
    
    log_id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(Integer)
    action_type = Column(String(50), nullable=False)
    username = Column(String(50))
    details = Column(Text)
    ip_address = Column(String(45), default='0.0.0.0')
    user_agent = Column(String(255))
    timestamp = Column(DateTime, default=func.now())
    
    __table_args__ = (
        Index('idx_logs_timestamp', 'timestamp'),
        Index('idx_logs_username', 'username'),
        Index('idx_logs_action', 'action_type'),
    )

class EngineerQuery(Base):
    __tablename__ = 'engineer_queries'
    
    query_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50))
    part_number = Column(String(100))
    part_category = Column(String(100))
    part_description = Column(Text)
    query_reason = Column(String(100))
    requested_by = Column(String(100))
    target_device = Column(String(255))
    merchant_name = Column(String(100))
    merchant_phone = Column(String(50))
    comments = Column(Text)
    status = Column(String(20), default='Pending')
    timestamp = Column(DateTime, default=func.now())
    
    __table_args__ = (
        Index('idx_queries_part', 'part_number'),
        Index('idx_queries_status', 'status'),
        Index('idx_queries_timestamp', 'timestamp'),
    )

class Notification(Base):
    __tablename__ = 'admin_notifications'
    
    notif_id = Column(Integer, primary_key=True, autoincrement=True)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=func.now())
