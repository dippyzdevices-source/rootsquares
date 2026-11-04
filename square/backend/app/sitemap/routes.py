from xml.sax.saxutils import escape

from flask import Blueprint, Response

from app.common.urls import frontend_base_url
from app.modules import module_enabled
from app.events.models import Event
from app.news.routes import _published_filter as news_published_filter
from app.news.models import News

sitemap_bp = Blueprint("sitemap", __name__)

# (path, module): a page of a module the owner turned off is not listed (W8-R16). Core pages have no module.
STATIC_PATHS = [("/", None), ("/events", "events"), ("/about", None), ("/contact", None), ("/gallery", "gallery"), ("/news", "news")]


@sitemap_bp.get("/sitemap.xml")
def get_sitemap():
    base_url = frontend_base_url()

    urls = [f"{base_url}{path}" for path, module in STATIC_PATHS if module_enabled(module)]

    if module_enabled("events"):
        events = Event.query.filter_by(published=True).all()
        urls += [f"{base_url}/events/{event.slug}" for event in events]

    if module_enabled("news"):
        news_items = News.query.filter(news_published_filter()).all()
        urls += [f"{base_url}/news/{article.slug}" for article in news_items]

    body = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url in urls:
        body.append(f"<url><loc>{escape(url)}</loc></url>")
    body.append("</urlset>")

    return Response("".join(body), mimetype="application/xml")
