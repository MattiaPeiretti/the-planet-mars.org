Project name: the-planet-mars.org

Goal: create a simple platform where a researcher can publish news articles and posts about the planet mars. Posts often have an image or a video.

Requirements:
- There are two portals, the public portal and the admin portal.
- The admin portal is used to publish new posts.
- The public portal is used to read posts.
- The admin portal is protected by a password.
- No comments system.

PUBLIC PORTAL:
- Homepage: Hero section with a search bar. Statistics on post counts and views.
- Post Page: Content, views, likes, and date.
- Archive Page: A simple chronological list of all published posts.
- RSS Feed: A standard XML feed available at `/rss`.
- Footer: Email subscription field for new post notifications.
- SEO: Automatic meta tags for titles, descriptions, and OpenGraph/Social sharing image (Mars-themed).

ADMIN PORTAL:
- Post Management: Create, edit, delete posts.
- Rich Text Editor: A professional WYSIWYG editor for post content (no Markdown knowledge required).
- Post Content: Title, image/video, tags, and rich text (HTML).
- Draft/Published States: Posts must have title, media, and tags to be published.
- Subscriber Management: View the list of subscribed emails.
- Notifications: Option to send a batch email to all subscribers when a new post is published.

Tech:
- Server-side rendered using Jinja and FastAPI.
- Database: Postgres (Relational data and HTML-formatted posts).
- Storage: S3 bucket on Digital Ocean for media.
- Deployment: Containerized with Docker, hosted on Digital Ocean.
- Email: Simple SMTP configuration for notifications.
