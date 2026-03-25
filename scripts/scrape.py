#!/usr/bin/env python3
"""
Scraper for deshabhimani.com and manoramaonline.com - fetches news articles
from various categories and outputs a JSON file for the static frontend.
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from typing import List, Optional

import cloudscraper
from bs4 import BeautifulSoup

# --- Source configurations ---

DESHABHIMANI_BASE = "https://www.deshabhimani.com"
MANORAMA_BASE = "https://www.manoramaonline.com"

CATEGORIES = {
    "kerala": {"label": "Kerala", "label_ml": "കേരളം"},
    "national": {"label": "National", "label_ml": "ദേശീയം"},
    "world": {"label": "International", "label_ml": "അന്താരാഷ്ട്രം"},
    "sports": {"label": "Sports", "label_ml": "കായികം"},
    "entertainment": {"label": "Entertainment", "label_ml": "വിനോദം"},
    "money-business": {"label": "Business", "label_ml": "ബിസിനസ്"},
    "editorial": {"label": "Editorial", "label_ml": "മുഖപ്രസംഗം"},
    "technology": {"label": "Technology", "label_ml": "ടെക്നോളജി"},
}

DESHABHIMANI_CATEGORIES = {
    "kerala": f"{DESHABHIMANI_BASE}/News/kerala",
    "national": f"{DESHABHIMANI_BASE}/News/national",
    "world": f"{DESHABHIMANI_BASE}/News/world",
    "sports": f"{DESHABHIMANI_BASE}/sports",
    "entertainment": f"{DESHABHIMANI_BASE}/entertainment",
    "money-business": f"{DESHABHIMANI_BASE}/money-business",
    "editorial": f"{DESHABHIMANI_BASE}/editorial",
    "technology": f"{DESHABHIMANI_BASE}/technology",
}

MANORAMA_CATEGORIES = {
    "kerala": f"{MANORAMA_BASE}/news/kerala.html",
    "national": f"{MANORAMA_BASE}/news/india.html",
    "world": f"{MANORAMA_BASE}/news/world.html",
    "sports": f"{MANORAMA_BASE}/sports.html",
    "entertainment": f"{MANORAMA_BASE}/movies.html",
    "money-business": f"{MANORAMA_BASE}/business.html",
    "editorial": f"{MANORAMA_BASE}/news/editorial.html",
    "technology": f"{MANORAMA_BASE}/technology.html",
}

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "linux", "desktop": True}
)


def fetch_page(url: str) -> Optional[BeautifulSoup]:
    """Fetch a page and return parsed BeautifulSoup object."""
    try:
        resp = scraper.get(url, timeout=30)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        print(f"  [WARN] Failed to fetch {url}: {e}", file=sys.stderr)
        return None


# =====================
# Deshabhimani scraping
# =====================

def db_extract_articles(soup: BeautifulSoup, category_key: str) -> List[dict]:
    """Extract articles from a Deshabhimani category page."""
    url_data = {}

    for link in soup.find_all("a", href=True):
        href = link["href"]

        if href.startswith("/"):
            path = href.strip("/")
            full_url = DESHABHIMANI_BASE + "/" + path
        elif href.startswith(DESHABHIMANI_BASE):
            path = href.replace(DESHABHIMANI_BASE, "").strip("/")
            full_url = href
        else:
            continue

        segments = path.split("/")
        if len(segments) < 2:
            continue

        skip_prefixes = (
            "topics/", "author/", "epaper", "about", "terms",
            "privacy", "quiz", "latest-news", "aksharamuttam",
            "weekly", "video/", "from-the-net/",
        )
        if any(path.startswith(p) for p in skip_prefixes):
            continue

        if len(segments) < 3 and not re.search(r'\d{3,}', segments[-1]):
            continue

        if not re.search(r'\d{3,}', segments[-1]):
            continue

        if full_url not in url_data:
            url_data[full_url] = {"titles": [], "images": []}

        title = link.get_text(strip=True)
        if title and len(title) >= 5:
            title = re.sub(r'^View news:\s*', '', title)
            title = re.sub(r'^print edition\s*', '', title)
            title = title.strip()
            if title and len(title) >= 5:
                url_data[full_url]["titles"].append(title)

        img = link.find("img")
        if img:
            src = img.get("src") or img.get("data-src")
            if src and "placeholder" not in src and "logo" not in src and "avatar" not in src:
                url_data[full_url]["images"].append(src)

    articles = []
    for full_url, data in url_data.items():
        if not data["titles"]:
            continue
        titles_sorted = sorted(data["titles"], key=len)
        title = titles_sorted[0]
        image_url = data["images"][0] if data["images"] else None

        articles.append({
            "title": title,
            "url": full_url,
            "image": image_url,
            "category": category_key,
            "source": "deshabhimani",
        })

    return articles


def db_fetch_article_content(url: str) -> Optional[dict]:
    """Fetch article content from a Deshabhimani article page."""
    soup = fetch_page(url)
    if not soup:
        return None

    result = {}

    body_container = soup.find("div", class_=re.compile(r"max-w-\[610px\]"))
    if body_container:
        paragraphs = []
        for p in body_container.find_all("p"):
            text = p.get_text(strip=True)
            if text and len(text) > 10:
                paragraphs.append(text)
        if paragraphs:
            result["content"] = "\n\n".join(paragraphs)

    author_el = soup.find("h6")
    if author_el:
        author = author_el.get_text(strip=True)
        if author and len(author) < 100:
            result["author"] = author

    time_el = soup.find("time")
    if time_el:
        result["date"] = time_el.get_text(strip=True)
    else:
        for text_node in soup.find_all(string=re.compile(
            r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}"
        )):
            date_match = re.search(
                r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}(?:,\s+\d{1,2}:\d{2}\s*(?:AM|PM))?)",
                str(text_node)
            )
            if date_match:
                result["date"] = date_match.group(1)
                break

    main_img = body_container.find("img") if body_container else None
    if not main_img:
        main_img = soup.find("img", src=re.compile(r"images-prd\.deshabhimani\.com"))
    if main_img:
        src = main_img.get("src") or main_img.get("data-src")
        if src and "placeholder" not in src and "logo" not in src:
            result["image_hq"] = src

    return result if result else None


def db_categorize_by_url(article: dict) -> None:
    """Re-categorize a Deshabhimani homepage article by its URL."""
    url_path = article["url"].replace(DESHABHIMANI_BASE, "").lower()
    mapping = {
        "/news/kerala": "kerala",
        "/news/national": "national",
        "/news/world": "world",
        "/sports": "sports",
        "/entertainment": "entertainment",
        "/money-business": "money-business",
        "/editorial": "editorial",
        "/technology": "technology",
        "/pravasi": "world",
    }
    for prefix, cat in mapping.items():
        if prefix in url_path:
            article["category"] = cat
            return


def scrape_deshabhimani() -> List[dict]:
    """Scrape all articles from Deshabhimani."""
    print("\n=== Deshabhimani ===")
    all_articles = []

    for key, url in DESHABHIMANI_CATEGORIES.items():
        print(f"  Fetching: {CATEGORIES[key]['label']} ({url})")
        soup = fetch_page(url)
        if not soup:
            continue
        articles = db_extract_articles(soup, key)[:15]
        print(f"    Found {len(articles)} articles")
        all_articles.extend(articles)

    # Homepage
    print(f"  Fetching: Homepage ({DESHABHIMANI_BASE})")
    soup = fetch_page(DESHABHIMANI_BASE)
    if soup:
        homepage_articles = db_extract_articles(soup, "trending")
        for article in homepage_articles:
            db_categorize_by_url(article)
        print(f"    Found {len(homepage_articles)} articles")
        all_articles.extend(homepage_articles)

    return all_articles


# ====================
# Manorama scraping
# ====================

def mm_extract_articles(soup: BeautifulSoup, category_key: str) -> List[dict]:
    """Extract articles from a Manorama Online category page."""
    url_data = {}

    for link in soup.find_all("a", href=True):
        href = link["href"]

        # Only process relative URLs or manoramaonline.com URLs
        if href.startswith("/"):
            full_url = MANORAMA_BASE + href
            path = href
        elif href.startswith(MANORAMA_BASE):
            full_url = href
            path = href.replace(MANORAMA_BASE, "")
        else:
            continue

        # Must look like an article URL (contains date pattern and .html)
        if not re.search(r'/\d{4}/\d{2}/\d{2}/', path):
            continue
        if not path.endswith(".html"):
            continue

        # Skip non-article pages
        skip_patterns = (
            "/premium/", "/web-stories/", "/podcast/",
            "/photogallery/", "/videos/", "/shortz/",
        )
        if any(pat in path for pat in skip_patterns):
            continue

        if full_url not in url_data:
            url_data[full_url] = {"titles": [], "images": []}

        title = link.get_text(strip=True)
        if title and len(title) >= 5:
            # Strip common prefixes like "VOTE 2026" or "PETROL CRISIS"
            title = re.sub(r'^[A-Z\s]{4,}\s+', '', title).strip()
            if title and len(title) >= 5:
                url_data[full_url]["titles"].append(title)

        # Manorama uses data-websrc for lazy-loaded images
        img = link.find("img", class_="cmp-story-list__img")
        if img:
            src = img.get("data-websrc") or img.get("src", "")
            if src and "mo-default" not in src and "config-assets" not in src:
                url_data[full_url]["images"].append(src)

    articles = []
    for full_url, data in url_data.items():
        if not data["titles"]:
            continue
        titles_sorted = sorted(data["titles"], key=len)
        title = titles_sorted[0]
        image_url = data["images"][0] if data["images"] else None

        articles.append({
            "title": title,
            "url": full_url,
            "image": image_url,
            "category": category_key,
            "source": "manorama",
        })

    return articles


def mm_fetch_article_content(url: str) -> Optional[dict]:
    """Fetch article content from a Manorama article page."""
    soup = fetch_page(url)
    if not soup:
        return None

    result = {}

    # Article body
    body = soup.find(class_="article-body")
    if body:
        # Get text but skip ad blocks
        paragraphs = []
        for p in body.find_all("p"):
            # Skip paragraphs inside ad containers
            if p.find_parent(class_=re.compile(r"advt|slb|ad-")):
                continue
            text = p.get_text(strip=True)
            if text and len(text) > 10:
                paragraphs.append(text)

        # If few paragraphs, try getting all text from body
        if len(paragraphs) < 2:
            full_text = body.get_text(separator="\n\n", strip=True)
            # Remove ad lines
            lines = [l.strip() for l in full_text.split("\n\n")]
            lines = [l for l in lines if l and len(l) > 15
                     and "ADVERTISEMENT" not in l
                     and "Go AD-FREE" not in l
                     and "Follow Us" not in l
                     and "googletag" not in l
                     and "English Summary" not in l]
            if lines:
                result["content"] = "\n\n".join(lines)
        else:
            result["content"] = "\n\n".join(paragraphs)

    # Author
    author_el = soup.find(class_="article-header__author-name")
    if author_el:
        author = author_el.get_text(strip=True)
        if author and len(author) < 100:
            result["author"] = author

    # Date
    date_el = soup.find(class_="article-header__published-date")
    if date_el:
        date_text = date_el.get_text(strip=True)
        # "Published: March 24, 2026 09:12 AM IST" -> "March 24, 2026 09:12 AM"
        date_match = re.search(
            r"((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}(?:\s+\d{1,2}:\d{2}\s*(?:AM|PM))?)",
            date_text
        )
        if date_match:
            result["date"] = date_match.group(1)

    return result if result else None


def mm_categorize_by_url(article: dict) -> None:
    """Re-categorize a Manorama homepage article by its URL."""
    url_path = article["url"].replace(MANORAMA_BASE, "").lower()
    mapping = {
        "/news/kerala": "kerala",
        "/district-news/": "kerala",
        "/news/india": "national",
        "/news/world": "world",
        "/sports": "sports",
        "/movies": "entertainment",
        "/business": "money-business",
        "/news/editorial": "editorial",
        "/technology": "technology",
    }
    for prefix, cat in mapping.items():
        if prefix in url_path:
            article["category"] = cat
            return


def scrape_manorama() -> List[dict]:
    """Scrape all articles from Manorama Online."""
    print("\n=== Manorama Online ===")
    all_articles = []

    for key, url in MANORAMA_CATEGORIES.items():
        print(f"  Fetching: {CATEGORIES[key]['label']} ({url})")
        soup = fetch_page(url)
        if not soup:
            continue
        articles = mm_extract_articles(soup, key)[:15]
        print(f"    Found {len(articles)} articles")
        all_articles.extend(articles)

    # Homepage
    print(f"  Fetching: Homepage ({MANORAMA_BASE})")
    soup = fetch_page(MANORAMA_BASE)
    if soup:
        homepage_articles = mm_extract_articles(soup, "trending")
        for article in homepage_articles:
            mm_categorize_by_url(article)
        print(f"    Found {len(homepage_articles)} articles")
        all_articles.extend(homepage_articles)

    return all_articles


# ====================
# Common
# ====================

def deduplicate_articles(articles: List[dict]) -> List[dict]:
    """Remove duplicate articles based on URL."""
    seen = set()
    unique = []
    for article in articles:
        if article["url"] not in seen:
            seen.add(article["url"])
            unique.append(article)
    return unique


def main():
    print("=== News Scraper (Deshabhimani + Manorama) ===")
    print(f"Started at: {datetime.now(timezone.utc).isoformat()}")

    # Scrape both sources
    db_articles = scrape_deshabhimani()
    mm_articles = scrape_manorama()

    # Interleave articles from both sources for balanced content fetching
    all_articles = []
    di, mi = 0, 0
    while di < len(db_articles) or mi < len(mm_articles):
        if di < len(db_articles):
            all_articles.append(db_articles[di])
            di += 1
        if mi < len(mm_articles):
            all_articles.append(mm_articles[mi])
            mi += 1

    all_articles = deduplicate_articles(all_articles)
    print(f"\nTotal unique articles: {len(all_articles)}")

    # Fetch full article content
    max_articles_to_fetch = int(os.environ.get("MAX_ARTICLE_FETCH", "80"))
    articles_to_fetch = all_articles[:max_articles_to_fetch]
    print(f"\nFetching content for {len(articles_to_fetch)} articles...")

    for i, article in enumerate(articles_to_fetch):
        print(f"  [{i+1}/{len(articles_to_fetch)}] {article['source']}: {article['url'][-50:]}")

        if article["source"] == "deshabhimani":
            content_data = db_fetch_article_content(article["url"])
        else:
            content_data = mm_fetch_article_content(article["url"])

        if content_data:
            if "content" in content_data:
                article["content"] = content_data["content"]
            if "author" in content_data:
                article["author"] = content_data["author"]
            if "date" in content_data:
                article["date"] = content_data["date"]
            if "image_hq" in content_data and not article.get("image"):
                article["image"] = content_data["image_hq"]
        time.sleep(0.3)

    # Build output
    categories_meta = {}
    for key, cat in CATEGORIES.items():
        categories_meta[key] = {
            "label": cat["label"],
            "label_ml": cat["label_ml"],
        }
    categories_meta["trending"] = {
        "label": "Trending",
        "label_ml": "ട്രെൻഡിംഗ്",
    }

    sources_meta = {
        "deshabhimani": {
            "label": "Deshabhimani",
            "url": DESHABHIMANI_BASE,
        },
        "manorama": {
            "label": "Manorama",
            "url": MANORAMA_BASE,
        },
    }

    output = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "sources": sources_meta,
        "categories": categories_meta,
        "articles": all_articles,
    }

    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "news.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nOutput written to: {out_path}")
    print(f"Finished at: {datetime.now(timezone.utc).isoformat()}")


if __name__ == "__main__":
    main()
