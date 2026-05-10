"""Async repository for Template CRUD and counter increments."""
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from leads_bot.db.models import Template


class TemplateRepo:
    def __init__(self, session: AsyncSession):
        self._s = session

    async def active(self) -> Sequence[Template]:
        stmt = select(Template).where(Template.active.is_(True)).order_by(Template.id)
        return list((await self._s.execute(stmt)).scalars().all())

    async def all(self) -> Sequence[Template]:
        stmt = select(Template).order_by(Template.id)
        return list((await self._s.execute(stmt)).scalars().all())

    async def get(self, template_id: int) -> Template | None:
        return await self._s.get(Template, template_id)

    async def record_send(self, template_id: int) -> None:
        await self._s.execute(
            update(Template)
            .where(Template.id == template_id)
            .values(sent_count=Template.sent_count + 1)
        )
        await self._s.commit()

    async def record_reply(self, template_id: int | None) -> None:
        if template_id is None:
            return
        result = await self._s.execute(
            update(Template)
            .where(Template.id == template_id)
            .values(reply_count=Template.reply_count + 1)
        )
        if result.rowcount:
            await self._s.commit()

    async def update(
        self, template_id: int,
        *, prompt: str | None = None,
        traffic_share: int | None = None,
        active: bool | None = None,
        name: str | None = None,
    ) -> Template:
        values = {}
        if prompt is not None:
            values["prompt"] = prompt
        if traffic_share is not None:
            values["traffic_share"] = traffic_share
        if active is not None:
            values["active"] = active
        if name is not None:
            values["name"] = name
        if values:
            await self._s.execute(
                update(Template).where(Template.id == template_id).values(**values)
            )
            await self._s.commit()
        return await self.get(template_id)

    async def create(
        self, *, name: str, variant: str, prompt: str,
        traffic_share: int = 0, active: bool = True,
    ) -> Template:
        t = Template(
            name=name, variant=variant, prompt=prompt,
            traffic_share=traffic_share, active=active,
        )
        self._s.add(t)
        await self._s.commit()
        return t

    async def delete(self, template_id: int) -> None:
        t = await self.get(template_id)
        if t is None:
            return
        await self._s.delete(t)
        await self._s.commit()

    async def validate_traffic_sum(self) -> None:
        active = await self.active()
        total = sum(t.traffic_share for t in active)
        if total != 100:
            raise ValueError(
                f"Active templates' traffic_share must sum to 100, got {total}"
            )
