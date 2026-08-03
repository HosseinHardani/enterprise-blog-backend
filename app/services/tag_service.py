import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.custom import AlreadyExistsError, NotFoundError
from app.models.tag import Tag
from app.repositories.tag import TagRepository
from app.utils.slug import generate_slug


class TagService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.tags = TagRepository(db)

    async def create(self, name: str) -> Tag:
        if await self.tags.get_by_name(name):
            raise AlreadyExistsError("This tag already exists")
        slug = generate_slug(name)
        if await self.tags.get_by_slug(slug):
            raise AlreadyExistsError("A tag with a similar name already exists")
        tag = await self.tags.create(name=name, slug=slug)
        await self.db.commit()
        return tag

    async def get_or_create_many(self, names: list[str]) -> list[Tag]:
        """Used internally by post creation for a convenience 'free text tags' flow."""
        tags = []
        for name in names:
            existing = await self.tags.get_by_name(name)
            if existing is None:
                existing = await self.tags.create(name=name, slug=generate_slug(name))
            tags.append(existing)
        return tags

    async def get_by_id_or_404(self, tag_id: uuid.UUID) -> Tag:
        tag = await self.tags.get_by_id(tag_id)
        if tag is None:
            raise NotFoundError("Tag not found")
        return tag

    async def list_all(self, offset: int, limit: int):
        items = await self.tags.list_all(offset=offset, limit=limit)
        total = await self.tags.count()
        return items, total

    async def delete(self, tag_id: uuid.UUID) -> None:
        tag = await self.get_by_id_or_404(tag_id)
        await self.tags.delete(tag)
        await self.db.commit()
