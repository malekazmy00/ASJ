# core/enums.py
from enum import Enum

class Role(str, Enum):
    ADMIN = "admin"
    ENGINEER = "engineer"
    WORKER = "worker"

class ItemStatus(str, Enum):
    AVAILABLE = "Available"
    OUT = "Out"
    RESERVED = "Reserved"
    DAMAGED = "Damaged"

class ItemCondition(str, Enum):
    NEW = "جديدة"
    USED = "مستعملة"

class QueryReason(str, Enum):
    INSPECTION = "معاينة"
    MERCHANT = "طلب شراء لتاجر"
    DEVICE = "مطلوب لجهاز معين"
    SPECS = "استفسار عن المواصفات"

class QueryStatus(str, Enum):
    PENDING = "Pending"
    FULFILLED = "Fulfilled"
    CANCELLED = "Cancelled"

class ActionType(str, Enum):
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    OUT = "OUT"
    SEARCH = "SEARCH"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    EXPORT = "EXPORT"
    IMPORT = "IMPORT"
    USER_MGMT = "USER_MGMT"
    DB_RESTORE = "DB_RESTORE"