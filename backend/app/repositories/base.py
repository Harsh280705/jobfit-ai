"""Generic async repository helpers (keeps DB logic out of routes/NLP)."""
from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class BaseRepository:
    model = None

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, id: str):
        return await self.session.get(self.model, id)

    async def list(self, limit: int = 50):
        rows = await self.session.execute(select(self.model).limit(limit))
        return rows.scalars().all()
