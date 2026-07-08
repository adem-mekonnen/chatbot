# app/tools/base.py
from abc import ABC, abstractmethod
from typing import List, Type
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

class BaseTool(ABC):
    @property
    @abstractmethod
    def name(self) -> str: pass

    @property
    @abstractmethod
    def required_action(self) -> str: pass

    @property
    @abstractmethod
    def description(self) -> str: pass

    @property
    @abstractmethod
    def deterministic_patterns(self) -> List[str]: pass

    @property
    @abstractmethod
    def schema(self) -> Type[BaseModel]: pass

    @abstractmethod
    async def execute(self, db: AsyncSession, user_payload: dict, parameters: BaseModel) -> str: pass