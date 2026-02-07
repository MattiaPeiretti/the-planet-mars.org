from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from enum import Enum
import uuid

class PostStatus(Enum):
    DRAFT = "draft"
    PUBLISHED = "published"

@dataclass
class Post:
    id: str
    title: str
    slug: str
    content: str
    media_url: Optional[str]
    media_type: Optional[str]  # "image" or "video"
    tags: List[str]
    status: PostStatus
    views: int = 0
    likes: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    published_at: Optional[datetime] = None

    @classmethod
    def create(cls, title: str, slug: str, content: str, media_url: Optional[str], media_type: Optional[str], tags: List[str]):
        return cls(
            id=str(uuid.uuid4()),
            title=title,
            slug=slug,
            content=content,
            media_url=media_url,
            media_type=media_type,
            tags=tags,
            status=PostStatus.DRAFT
        )

    def publish(self):
        if not self.title:
            raise ValueError("Post must have a title to be published")
        self.status = PostStatus.PUBLISHED
        self.published_at = datetime.utcnow()
        return self

    def increment_views(self):
        self.views += 1

    def increment_likes(self):
        self.likes += 1

@dataclass
class Subscriber:
    email: str
    subscribed_at: datetime = field(default_factory=datetime.utcnow)
    is_active: bool = True

    @classmethod
    def create(cls, email: str):
        return cls(email=email)

@dataclass
class Admin:
    username: str
    password_hash: str

    @classmethod
    def create(cls, username: str, password_hash: str):
        return cls(username=username, password_hash=password_hash)
