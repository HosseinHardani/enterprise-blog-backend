import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.custom import AlreadyExistsError, NotFoundError
from app.models.category import Category
from app.repositories.category import CategoryRepository
from app.utils.slug import generate_slug


class CategoryService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.categories = CategoryRepository(db)

    async def create(self, name: str, description: str | None) -> Category:
        if await self.categories.get_by_name(name):
            raise AlreadyExistsError("A category with this name already exists")
        slug = generate_slug(name)
        if await self.categories.get_by_slug(slug):
            raise AlreadyExistsError("A category with a similar name already exists")
        category = await self.categories.create(name=name, slug=slug, description=description)
        await self.db.commit()
        return category

    async def get_by_id_or_404(self, category_id: uuid.UUID) -> Category:
        category = await self.categories.get_by_id(category_id)
        if category is None:
            raise NotFoundError("Category not found")
        return category

    async def list_all(self, offset: int, limit: int):
        items = await self.categories.list_all(offset=offset, limit=limit)
        total = await self.categories.count()
        return items, total

    async def update(self, category_id: uuid.UUID, name: str | None, description: str | None) -> Category:
        category = await self.get_by_id_or_404(category_id)
        update_kwargs: dict = {}
        if name is not None and name != category.name:
            if await self.categories.get_by_name(name):
                raise AlreadyExistsError("A category with this name already exists")
            update_kwargs["name"] = name
            update_kwargs["slug"] = generate_slug(name)
        if description is not None:
            update_kwargs["description"] = description
        updated = await self.categories.update(category, **update_kwargs)
        await self.db.commit()
        return updated

    async def delete(self, category_id: uuid.UUID) -> None:
        category = await self.get_by_id_or_404(category_id)
        await self.categories.delete(category)
        await self.db.commit()
