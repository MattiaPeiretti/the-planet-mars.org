import asyncpg
from typing import List, Optional
from src.domain.models import Post, Subscriber, PostStatus, Admin
import json

class PostRepository:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def save(self, post: Post):
        query = """
        INSERT INTO posts (id, title, slug, content, media_url, media_type, tags, status, language, views, likes, created_at, published_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        ON CONFLICT (id) DO UPDATE SET
            title = EXCLUDED.title,
            slug = EXCLUDED.slug,
            content = EXCLUDED.content,
            media_url = EXCLUDED.media_url,
            media_type = EXCLUDED.media_type,
            tags = EXCLUDED.tags,
            status = EXCLUDED.status,
            language = EXCLUDED.language,
            views = EXCLUDED.views,
            likes = EXCLUDED.likes,
            published_at = EXCLUDED.published_at
        """
        await self.pool.execute(
            query,
            post.id, post.title, post.slug, post.content, post.media_url,
            post.media_type, post.tags, post.status.value, post.language,
            post.views, post.likes, post.created_at, post.published_at
        )

    async def find_by_id(self, post_id: str) -> Optional[Post]:
        row = await self.pool.fetchrow("SELECT * FROM posts WHERE id = $1", post_id)
        if row:
            return self._to_entity(row)
        return None

    async def find_by_slug(self, slug: str) -> Optional[Post]:
        row = await self.pool.fetchrow("SELECT * FROM posts WHERE slug = $1", slug)
        if row:
            return self._to_entity(row)
        return None

    async def list_published(self, lang: str = "en", limit: int = 10, offset: int = 0) -> List[Post]:
        rows = await self.pool.fetch(
            "SELECT * FROM posts WHERE status = 'published' AND language = $1 ORDER BY published_at DESC LIMIT $2 OFFSET $3",
            lang, limit, offset
        )
        return [self._to_entity(row) for row in rows]

    async def list_all(self, limit: int = 50, offset: int = 0) -> List[Post]:
        rows = await self.pool.fetch(
            "SELECT * FROM posts ORDER BY created_at DESC LIMIT $1 OFFSET $2",
            limit, offset
        )
        return [self._to_entity(row) for row in rows]

    async def search(self, query: str, lang: str = "en") -> List[Post]:
        rows = await self.pool.fetch(
            "SELECT * FROM posts WHERE status = 'published' AND language = $1 AND (title ILIKE $2 OR content ILIKE $2) ORDER BY published_at DESC",
            lang, f"%{query}%"
        )
        return [self._to_entity(row) for row in rows]

    async def get_stats(self, lang: str = "en"):
        row = await self.pool.fetchrow("SELECT COUNT(*) as count, SUM(views) as total_views FROM posts WHERE status = 'published' AND language = $1", lang)
        return {
            "post_count": row["count"] if row else 0,
            "total_views": row["total_views"] if row and row["total_views"] else 0
        }

    def _to_entity(self, row) -> Post:
        return Post(
            id=row["id"],
            title=row["title"],
            slug=row["slug"],
            content=row["content"],
            media_url=row["media_url"],
            media_type=row["media_type"],
            tags=row["tags"],
            status=PostStatus(row["status"]),
            language=row["language"],
            views=row["views"],
            likes=row["likes"],
            created_at=row["created_at"],
            published_at=row["published_at"]
        )

class SubscriberRepository:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def save(self, subscriber: Subscriber):
        query = """
        INSERT INTO subscribers (email, subscribed_at, is_active)
        VALUES ($1, $2, $3)
        ON CONFLICT (email) DO UPDATE SET
            is_active = EXCLUDED.is_active
        """
        await self.pool.execute(query, subscriber.email, subscriber.subscribed_at, subscriber.is_active)

    async def list_active(self) -> List[Subscriber]:
        rows = await self.pool.fetch("SELECT * FROM subscribers WHERE is_active = TRUE")
        return [Subscriber(email=row["email"], subscribed_at=row["subscribed_at"], is_active=row["is_active"]) for row in rows]

class AdminRepository:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def save(self, admin: Admin):
        await self.pool.execute(
            "INSERT INTO admins (username, password_hash) VALUES ($1, $2) ON CONFLICT (username) DO UPDATE SET password_hash = EXCLUDED.password_hash",
            admin.username, admin.password_hash
        )

    async def find_by_username(self, username: str) -> Optional[Admin]:
        row = await self.pool.fetchrow("SELECT * FROM admins WHERE username = $1", username)
        if row:
            return Admin(username=row["username"], password_hash=row["password_hash"])
        return None
