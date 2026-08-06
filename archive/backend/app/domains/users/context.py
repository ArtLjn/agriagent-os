"""Users 域统一鉴权上下文。"""

from dataclasses import dataclass

from app.domains.users.models import User


@dataclass(frozen=True)
class AuthContext:
    """携带当前登录用户和实际生效用户。"""

    current_user: User
    effective_user: User

    @property
    def current_user_id(self) -> str:
        """当前登录用户 ID。"""
        return self.current_user.id

    @property
    def effective_user_id(self) -> str:
        """本次业务实际生效用户 ID。"""
        return self.effective_user.id

    @property
    def is_admin(self) -> bool:
        """当前登录用户是否为管理员。"""
        return self.current_user.role == "admin"

    @property
    def is_simulated(self) -> bool:
        """本次业务是否使用管理员模拟身份。"""
        return self.current_user.id != self.effective_user.id
