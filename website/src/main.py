import os
from contextlib import asynccontextmanager
import asyncpg
from fastapi import FastAPI, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from src.persistence.repositories import PostRepository, SubscriberRepository, AdminRepository
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse
import bcrypt
from typing import List, Optional
from src.domain.models import Post, Subscriber, PostStatus, Admin
from slugify import slugify


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

# Auth helper
def get_current_admin(request: Request):
    user = request.session.get("user")
    if not user:
        return None
    return user

# --- PUBLIC ROUTES ---

@app.get("/")
async def home(request: Request, repo: PostRepository = Depends(get_post_repo)):
    posts = await repo.list_published(limit=5)
    stats = await repo.get_stats()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "posts": posts,
        "stats": stats
    })

@app.get("/post/{slug}")
async def post_detail(slug: str, request: Request, repo: PostRepository = Depends(get_post_repo)):
    post = await repo.find_by_slug(slug)
    if not post:
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
    post.increment_views()
    await repo.save(post)
    return templates.TemplateResponse("post.html", {"request": request, "post": post})

@app.get("/archive")
async def archive(request: Request, repo: PostRepository = Depends(get_post_repo)):
    posts = await repo.list_published(limit=100)
    return templates.TemplateResponse("archive.html", {"request": request, "posts": posts})

@app.post("/subscribe")
async def subscribe(request: Request, repo: SubscriberRepository = Depends(get_subscriber_repo)):
    form = await request.form()
    email = form.get("email")
    if email:
        sub = Subscriber.create(email)
        await repo.save(sub)
    return RedirectResponse("/", status_code=303)

@app.post("/post/{slug}/like")
async def post_like(slug: str, repo: PostRepository = Depends(get_post_repo)):
    post = await repo.find_by_slug(slug)
    if post:
        post.increment_likes()
        await repo.save(post)
    return RedirectResponse(f"/post/{slug}", status_code=303)

@app.get("/search")
async def search(q: str, request: Request, repo: PostRepository = Depends(get_post_repo)):
    posts = await repo.search(q)
    return templates.TemplateResponse("search.html", {"request": request, "posts": posts, "query": q})

@app.get("/rss")
async def rss_feed(repo: PostRepository = Depends(get_post_repo)):
    posts = await repo.list_published()
    rss = """<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0">
      <channel>
        <title>the-planet-mars.org</title>
        <link>https://the-planet-mars.org</link>
        <description>Scientific news from Mars.</description>
    """
    for post in posts:
        rss += f"""
        <item>
          <title>{post.title}</title>
          <link>https://the-planet-mars.org/post/{post.slug}</link>
          <pubDate>{post.published_at.strftime('%a, %d %b %Y %H:%M:%S GMT') if post.published_at else ''}</pubDate>
        </item>
        """
    rss += "</channel></rss>"
    from fastapi.responses import Response
    return Response(content=rss, media_type="application/xml")

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
    author_tags = [t.strip() for t in form.get("tags", "").split(",") if t.strip()]
    slug = slugify(form.get("title"))
    
    post = Post.create(
        title=form.get("title"),
        slug=slug,
        content=form.get("content"),
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
    post.slug = slugify(post.title)
    post.content = form.get("content")
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

@app.get("/admin/subscribers")
async def admin_subscribers(request: Request, repo: SubscriberRepository = Depends(get_subscriber_repo)):
    if not get_current_admin(request):
        return RedirectResponse("/admin/login")
    subs = await repo.list_active()
    return templates.TemplateResponse("admin_subscribers.html", {"request": request, "subscribers": subs})
