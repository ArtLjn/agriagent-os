from typing import TypeVar, Generic

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """通用分页响应包装。"""

    items: list[T]
    total: int
