import os
from contextlib import asynccontextmanager
import asyncpg
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from src.persistence.repositories import PostRepository, SubscriberRepository, AdminRepository
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse, JSONResponse
import bcrypt
from typing import List, Optional
from src.domain.models import Post, Subscriber, PostStatus, Admin
from src.seed_data import SEED_VIDEOS
from slugify import slugify
from fastapi.responses import Response, JSONResponse
from src.storage.service import StorageService
import uuid

SUPPORTED_LANGS = ["en", "it"]

# Database connection pool
pool = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    pool = await asyncpg.create_pool(
        os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/mars_blog")
    )
    # Initialize schema if exists
    if os.path.exists("schema.sql"):
        with open("schema.sql", "r") as f:
            await pool.execute(f.read())

    # Create default admin if not exists (for demo)
    async with pool.acquire() as conn:
        admin_repo = AdminRepository(conn)
        if not await admin_repo.find_by_username("admin"):
            hashed = bcrypt.hashpw("mars2026".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            await admin_repo.save(Admin("admin", hashed))
    yield
    await pool.close()


app = FastAPI(lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "super-secret-mars-key"))

# Templates and Static files
app.mount("/static", StaticFiles(directory="src/static"), name="static")
templates = Jinja2Templates(directory="src/templates")


# Dependency Injection
async def get_post_repo():
    async with pool.acquire() as conn:
        yield PostRepository(conn)


async def get_subscriber_repo():
    async with pool.acquire() as conn:
        yield SubscriberRepository(conn)


async def get_admin_repo():
    async with pool.acquire() as conn:
        yield AdminRepository(conn)


async def get_storage_service():
    return StorageService()


# Auth helper
def get_current_admin(request: Request):
    user = request.session.get("user")
    if not user:
        return None
    return user


# --- ADMIN ROUTES ---

@app.get("/admin/login")
async def admin_login_get(request: Request):
    return templates.TemplateResponse("admin_login.html", {"request": request})


@app.post("/admin/login")
async def admin_login_post(request: Request, repo: AdminRepository = Depends(get_admin_repo)):
    form = await request.form()
    username = form.get("username")
    password = form.get("password")
    admin = await repo.find_by_username(username)
    if admin and bcrypt.checkpw(password.encode('utf-8'), admin.password_hash.encode('utf-8')):
        request.session["user"] = username
        return RedirectResponse("/admin", status_code=303)
    return templates.TemplateResponse("admin_login.html", {"request": request, "error": "Invalid credentials"})


@app.get("/admin")
async def admin_dash(request: Request, repo: PostRepository = Depends(get_post_repo)):
    if not get_current_admin(request):
        return RedirectResponse("/admin/login")
    posts = await repo.list_all()
    return templates.TemplateResponse("admin_dash.html", {"request": request, "posts": posts})


@app.get("/admin/post/new")
async def admin_post_new_get(request: Request):
    if not get_current_admin(request):
        return RedirectResponse("/admin/login")
    return templates.TemplateResponse("admin_editor.html", {"request": request, "post": None})


@app.post("/admin/post/new")
async def admin_post_new_post(request: Request, repo: PostRepository = Depends(get_post_repo)):
    if not get_current_admin(request):
        return RedirectResponse("/admin/login")
    form = await request.form()
    # author_tags = [t.strip() for t in form.get("tags", "").split(",") if t.strip()]
    slug = slugify(form.get("title"))

    post = Post.create(
        title=form.get("title"),
        title_it=form.get("title_it"),
        slug=slug,
        content=form.get("content"),
        content_it=form.get("content_it"),
        media_url=form.get("media_url"),
        media_type=form.get("media_type"),
        tags=[t.strip() for t in form.get("tags", "").split(",") if t.strip()]
    )
    if form.get("status") == "published":
        post.publish()
    await repo.save(post)
    return RedirectResponse("/admin", status_code=303)


@app.get("/admin/post/edit/{post_id}")
async def admin_post_edit_get(post_id: str, request: Request, repo: PostRepository = Depends(get_post_repo)):
    if not get_current_admin(request):
        return RedirectResponse("/admin/login")
    post = await repo.find_by_id(post_id)
    return templates.TemplateResponse("admin_editor.html", {"request": request, "post": post})


@app.post("/admin/post/edit/{post_id}")
async def admin_post_edit_post(post_id: str, request: Request, repo: PostRepository = Depends(get_post_repo)):
    if not get_current_admin(request):
        return RedirectResponse("/admin/login")
    post = await repo.find_by_id(post_id)
    form = await request.form()
    post.title = form.get("title")
    post.title_it = form.get("title_it")
    post.slug = slugify(post.title)
    post.content = form.get("content")
    post.content_it = form.get("content_it")
    post.media_url = form.get("media_url")
    post.media_type = form.get("media_type")
    post.tags = [t.strip() for t in form.get("tags", "").split(",") if t.strip()]
    if form.get("status") == "published" and post.status != PostStatus.PUBLISHED:
        post.publish()
    elif form.get("status") == "draft":
        post.status = PostStatus.DRAFT
    await repo.save(post)
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/post/delete/{post_id}")
async def admin_post_delete(post_id: str, request: Request, repo: PostRepository = Depends(get_post_repo)):
    if not get_current_admin(request):
        return RedirectResponse("/admin/login")
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM posts WHERE id = $1", post_id)
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/api/signed-url")
async def admin_signed_url(request: Request, storage: StorageService = Depends(get_storage_service)):
    if not get_current_admin(request):
        raise HTTPException(status_code=401)

    json_data = await request.json()
    filename = json_data.get("filename")
    content_type = json_data.get("content_type")

    if not filename or not content_type:
        raise HTTPException(status_code=400, detail="Missing filename or content_type")

    # Generate a random UUID for the filename to prevent collisions and keep it clean
    ext = os.path.splitext(filename)[1]
    unique_filename = f"{uuid.uuid4()}{ext}"

    result = storage.generate_presigned_url(unique_filename, content_type)
    if not result:
        raise HTTPException(status_code=500, detail="Storage service not configured")

    return JSONResponse(result)


@app.get("/admin/subscribers")
async def admin_subscribers(request: Request, repo: SubscriberRepository = Depends(get_subscriber_repo)):
    if not get_current_admin(request):
        return RedirectResponse("/admin/login")
    subs = await repo.list_active()
    return templates.TemplateResponse("admin_subscribers.html", {"request": request, "subscribers": subs})


@app.post("/admin/seed")
async def admin_seed(request: Request, repo: PostRepository = Depends(get_post_repo)):
    if not get_current_admin(request):
        return RedirectResponse("/admin/login")

    import random
    for item in SEED_VIDEOS:
        post = Post.create(
            title=item["title"],
            slug=slugify(item["title"]),
            content=item["description"],
            media_url=item["sources"][0],
            media_type="video",
            tags=[random.choice(["geology", "atmosphere", "water", "exploration", "mission-log"])]
        )
        post.publish()
        await repo.save(post)

    return RedirectResponse("/admin", status_code=303)


# --- PUBLIC ROUTES ---

@app.get("/")
async def root_redirect():
    return RedirectResponse("/en")


@app.get("/{lang}")
async def home(lang: str, request: Request, repo: PostRepository = Depends(get_post_repo)):
    if lang not in SUPPORTED_LANGS:
        raise HTTPException(status_code=404)
    posts = await repo.list_published(lang=lang, limit=5)
    stats = await repo.get_stats(lang=lang)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "posts": posts,
        "stats": stats,
        "lang": lang
    })


@app.get("/{lang}/post/{slug}")
async def post_detail(lang: str, slug: str, request: Request, repo: PostRepository = Depends(get_post_repo)):
    if lang not in SUPPORTED_LANGS:
        raise HTTPException(status_code=404)
    post = await repo.find_by_slug(slug)
    if not post:
        return templates.TemplateResponse("404.html", {"request": request, "lang": lang}, status_code=404)
    post.increment_views()
    await repo.save(post)
    return templates.TemplateResponse("post.html", {"request": request, "post": post, "lang": lang})


@app.get("/{lang}/archive")
async def archive(lang: str, request: Request, repo: PostRepository = Depends(get_post_repo)):
    if lang not in SUPPORTED_LANGS:
        raise HTTPException(status_code=404)
    posts = await repo.list_published(lang=lang, limit=100)
    return templates.TemplateResponse("archive.html", {"request": request, "posts": posts, "lang": lang})


@app.post("/{lang}/subscribe")
async def subscribe(lang: str, request: Request, repo: SubscriberRepository = Depends(get_subscriber_repo)):
    if lang not in SUPPORTED_LANGS:
        raise HTTPException(status_code=404)
    form = await request.form()
    # ... (no change to subscription logic itself)
    form = await request.form()
    email = form.get("email")
    if email:
        sub = Subscriber.create(email)
        await repo.save(sub)

    if request.headers.get("accept") == "application/json":
        return {"success": True, "message": "Subscription established."}
    return RedirectResponse(f"/{lang}", status_code=303)


@app.get("/{lang}/api/posts")
async def api_list_posts(lang: str, offset: int = 0, limit: int = 5, repo: PostRepository = Depends(get_post_repo)):
    if lang not in SUPPORTED_LANGS:
        raise HTTPException(status_code=404)
    posts = await repo.list_published(lang=lang, limit=limit, offset=offset)
    return [
        {
            "id": p.id,
            "title": p.title,
            "title_it": p.title_it,
            "slug": p.slug,
            "content": p.content,
            "content_it": p.content_it,
            "media_url": p.media_url,
            "media_type": p.media_type,
            "tags": p.tags,
            "published_at": p.published_at.isoformat() if p.published_at else None,
            "views": p.views,
            "likes": p.likes
        } for p in posts
    ]


@app.post("/{lang}/post/{slug}/like")
async def post_like(lang: str, slug: str, request: Request, repo: PostRepository = Depends(get_post_repo)):
    if lang not in SUPPORTED_LANGS:
        raise HTTPException(status_code=404)
    liked_posts = request.cookies.get("liked_posts", "")
    liked_list = liked_posts.split(",") if liked_posts else []

    if slug in liked_list:
        if request.headers.get("accept") == "application/json":
            return {"success": False, "message": "Already acknowledged."}
        return RedirectResponse(f"/{lang}/post/{slug}", status_code=303)

    post = await repo.find_by_slug(slug)
    if post:
        post.likes += 1
        await repo.save(post)

    liked_list.append(slug)
    new_cookie_val = ",".join(liked_list)

    response = None
    if request.headers.get("accept") == "application/json":
        response = JSONResponse({"success": True, "likes": post.likes if post else 0})
    else:
        response = RedirectResponse(f"/{lang}/post/{slug}", status_code=303)

    response.set_cookie(key="liked_posts", value=new_cookie_val, max_age=31536000)  # 1 year
    return response


@app.get("/{lang}/search")
async def search(lang: str, q: str, request: Request, repo: PostRepository = Depends(get_post_repo)):
    if lang not in SUPPORTED_LANGS:
        raise HTTPException(status_code=404)
    posts = await repo.search(q, lang=lang)
    return templates.TemplateResponse("search.html", {"request": request, "posts": posts, "query": q, "lang": lang})


@app.get("/{lang}/rss")
async def rss_feed(lang: str, repo: PostRepository = Depends(get_post_repo)):
    if lang not in SUPPORTED_LANGS:
        raise HTTPException(status_code=404)
    posts = await repo.list_published(lang=lang)
    rss = f"""<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0">
      <channel>
        <title>the-planet-mars.org ({lang})</title>
        <link>https://the-planet-mars.org/{lang}</link>
        <description>Scientific news from Mars ({lang}).</description>
    """
    for post in posts:
        rss += f"""
        <item>
          <title>{post.title}</title>
          <link>https://the-planet-mars.org/{lang}/post/{post.slug}</link>
          <pubDate>{post.published_at.strftime('%a, %d %b %Y %H:%M:%S GMT') if post.published_at else ''}</pubDate>
        </item>
        """
    rss += "</channel></rss>"
    return Response(content=rss, media_type="application/xml")
