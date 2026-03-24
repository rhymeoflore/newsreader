#!/usr/bin/env python3
"""
Scraper for deshabhimani.com - fetches news articles from various categories
and outputs a JSON file for the static frontend.
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

BASE_URL = "https://www.deshabhimani.com"

CATEGORIES = {
    "kerala": {
        "url": f"{BASE_URL}/News/kerala",
        "label": "Kerala",
        "label_ml": "കേരളം",
    },
    "national": {
        "url": f"{BASE_URL}/News/national",
        "label": "National",
        "label_ml": "ദേശീയം",
    },
    "world": {
        "url": f"{BASE_URL}/News/world",
        "label": "International",
        "label_ml": "അന്താരാഷ്ട്രം",
    },
    "sports": {
        "url": f"{BASE_URL}/sports",
        "label": "Sports",
        "label_ml": "കായികം",
    },
    "entertainment": {
        "url": f"{BASE_URL}/entertainment",
        "label": "Entertainment",
        "label_ml": "വിനോദം",
    },
    "money-business": {
        "url": f"{BASE_URL}/money-business",
        "label": "Business",
        "label_ml": "ബിസിനസ്",
    },
    "editorial": {
        "url": f"{BASE_URL}/editorial",
        "label": "Editorial",
        "label_ml": "മുഖപ്രസംഗം",
    },
    "technology": {
        "url": f"{BASE_URL}/technology",
        "label": "Technology",
        "label_ml": "ടെക്നോളജി",
    },
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


def extract_articles_from_page(soup: BeautifulSoup, category_key: str) -> List[dict]:
    """Extract article data from a category page."""
    # Two-pass approach: collect all URL data first, then pick best title/image
    url_data = {}  # full_url -> {titles: [], images: []}

    for link in soup.find_all("a", href=True):
        href = link["href"]

        # Normalize: handle both relative and absolute URLs
        if href.startswith("/"):
            path = href.strip("/")
            full_url = BASE_URL + "/" + path
        elif href.startswith(BASE_URL):
            path = href.replace(BASE_URL, "").strip("/")
            full_url = href
        else:
            continue

        segments = path.split("/")
        if len(segments) < 2:
            continue

        # Skip non-article pages
        skip_prefixes = (
            "topics/", "author/", "epaper", "about", "terms",
            "privacy", "quiz", "latest-news", "aksharamuttam",
            "weekly", "video/", "from-the-net/",
        )
        if any(path.startswith(p) for p in skip_prefixes):
            continue

        # Skip pure category pages (e.g. /News, /News/kerala, /sports)
        if len(segments) < 3 and not re.search(r'\d{3,}', segments[-1]):
            continue

        # Article slugs typically contain digits
        if not re.search(r'\d{3,}', segments[-1]):
            continue

        if full_url not in url_data:
            url_data[full_url] = {"titles": [], "images": []}

        # Collect title
        title = link.get_text(strip=True)
        if title and len(title) >= 5:
            title = re.sub(r'^View news:\s*', '', title)
            title = re.sub(r'^print edition\s*', '', title)
            title = title.strip()
            if title and len(title) >= 5:
                url_data[full_url]["titles"].append(title)

        # Collect image
        img = link.find("img")
        if img:
            src = img.get("src") or img.get("data-src")
            if src and "placeholder" not in src and "logo" not in src and "avatar" not in src:
                url_data[full_url]["images"].append(src)

    # Build articles from collected data
    articles = []
    for full_url, data in url_data.items():
        if not data["titles"]:
            continue

        # Pick shortest title (usually the headline, not the description)
        titles_sorted = sorted(data["titles"], key=len)
        title = titles_sorted[0]

        # Pick first valid image
        image_url = data["images"][0] if data["images"] else None

        articles.append({
            "title": title,
            "url": full_url,
            "image": image_url,
            "category": category_key,
        })

    return articles


def deduplicate_articles(articles: List[dict]) -> List[dict]:
    """Remove duplicate articles based on URL."""
    seen = set()
    unique = []
    for article in articles:
        if article["url"] not in seen:
            seen.add(article["url"])
            unique.append(article)
    return unique


def fetch_article_content(url: str) -> Optional[dict]:
    """Fetch an individual article page and extract the body text and metadata."""
    soup = fetch_page(url)
    if not soup:
        return None

    result = {}

    # Extract article body paragraphs
    # Article body lives inside a div with class "max-w-[610px]"
    body_container = soup.find("div", class_=re.compile(r"max-w-\[610px\]"))
    if body_container:
        paragraphs = []
        for p in body_container.find_all("p"):
            text = p.get_text(strip=True)
            if text and len(text) > 10:
                paragraphs.append(text)
        if paragraphs:
            result["content"] = "\n\n".join(paragraphs)

    # Extract author
    author_el = soup.find("h6")
    if author_el:
        author = author_el.get_text(strip=True)
        if author and len(author) < 100:
            result["author"] = author

    # Extract published date
    time_el = soup.find("time")
    if time_el:
        result["date"] = time_el.get_text(strip=True)
    else:
        # Look for date text like "Mar 24, 2026, 08:22 AM"
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

    # Extract main image (higher quality than thumbnail)
    main_img = body_container.find("img") if body_container else None
    if not main_img:
        # Look for the featured image before the body
        main_img = soup.find("img", src=re.compile(r"images-prd\.deshabhimani\.com"))
    if main_img:
        src = main_img.get("src") or main_img.get("data-src")
        if src and "placeholder" not in src and "logo" not in src:
            result["image_hq"] = src

    return result if result else None


def main():
    print("=== Deshabhimani News Scraper ===")
    print(f"Started at: {datetime.now(timezone.utc).isoformat()}")

    all_articles = []

    for key, cat in CATEGORIES.items():
        print(f"\nFetching: {cat['label']} ({cat['url']})")
        soup = fetch_page(cat["url"])
        if not soup:
            continue

        articles = extract_articles_from_page(soup, key)
        # Limit per category to keep the JSON reasonable
        articles = articles[:15]
        print(f"  Found {len(articles)} articles")
        all_articles.extend(articles)

    # Also scrape the homepage for top/trending stories
    print(f"\nFetching: Homepage ({BASE_URL})")
    soup = fetch_page(BASE_URL)
    if soup:
        homepage_articles = extract_articles_from_page(soup, "trending")
        # Try to re-categorize homepage articles based on their URL
        for article in homepage_articles:
            url_path = article["url"].replace(BASE_URL, "").lower()
            if "/news/kerala" in url_path:
                article["category"] = "kerala"
            elif "/news/national" in url_path:
                article["category"] = "national"
            elif "/news/world" in url_path:
                article["category"] = "world"
            elif "/sports" in url_path:
                article["category"] = "sports"
            elif "/entertainment" in url_path:
                article["category"] = "entertainment"
            elif "/money-business" in url_path:
                article["category"] = "money-business"
            elif "/editorial" in url_path:
                article["category"] = "editorial"
            elif "/technology" in url_path:
                article["category"] = "technology"
            elif "/pravasi" in url_path:
                article["category"] = "world"
            # else stays "trending"

        print(f"  Found {len(homepage_articles)} articles")
        all_articles.extend(homepage_articles)

    # Deduplicate
    all_articles = deduplicate_articles(all_articles)
    print(f"\nTotal unique articles: {len(all_articles)}")

    # Fetch full article content for each article
    # Limit to avoid overloading the server
    max_articles_to_fetch = int(os.environ.get("MAX_ARTICLE_FETCH", "60"))
    articles_to_fetch = all_articles[:max_articles_to_fetch]
    print(f"\nFetching content for {len(articles_to_fetch)} articles...")

    for i, article in enumerate(articles_to_fetch):
        print(f"  [{i+1}/{len(articles_to_fetch)}] {article['url'][-50:]}")
        content_data = fetch_article_content(article["url"])
        if content_data:
            if "content" in content_data:
                article["content"] = content_data["content"]
            if "author" in content_data:
                article["author"] = content_data["author"]
            if "date" in content_data:
                article["date"] = content_data["date"]
            if "image_hq" in content_data and not article.get("image"):
                article["image"] = content_data["image_hq"]
        # Small delay to be respectful
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

    output = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "source": "https://www.deshabhimani.com",
        "categories": categories_meta,
        "articles": all_articles,
    }

    # Write output
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "news.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nOutput written to: {out_path}")
    print(f"Finished at: {datetime.now(timezone.utc).isoformat()}")


if __name__ == "__main__":
    main()
