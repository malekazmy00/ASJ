# repositories/user_repo.py
from typing import Optional
from datetime import datetime

from repositories.base import BaseRepository
from core.models import User
from core.enums import Role
from core.security import security_service
from core.exceptions import NotFoundError

class UserRepository(BaseRepository):
    def __init__(self):
        super().__init__(User)
    
    def get_by_username(self, username: str) -> Optional[User]:
        return self.session.query(User).filter(User.username == username).first()
    
    def get_by_username_or_raise(self, username: str) -> User:
        user = self.get_by_username(username)
        if not user:
            raise NotFoundError(f"User not found: {username}")
        return user
    
    def has_permission(self, username: str, permission: str) -> bool:
        user = self.get_by_username(username)
        if not user:
            return False
        
        if user.role == Role.ADMIN:
            return True
        
        if permission == "export":
            return user.can_export
        elif permission == "track":
            return user.can_track
        
        return False
    
    def update_last_login(self, username: str, ip: str, user_agent: str):
        user = self.get_by_username(username)
        if user:
            user.last_login = datetime.now()
            user.last_ip = ip
            user.last_user_agent = user_agent
            self.session.add(user)
            self.session.flush()
    
    def update_password(self, username: str, new_hash: str):
        user = self.get_by_username(username)
        if user:
            user.password = new_hash
            self.session.add(user)
            self.session.flush()
    
    def create_user(self, username: str, password: str, role: str = Role.WORKER,
                   can_export: bool = False, can_track: bool = False, status: str = "Active") -> User:
        hashed = security_service.hash_password(password)
        user = User(
            username=username,
            password=hashed,
            role=role,
            can_export=can_export,
            can_track=can_track,
            status=status
        )
        self.session.add(user)
        self.session.flush()
        return user

user_repo = UserRepository()