#!/usr/bin/env python3
"""
Script to fetch RSS feeds defined in feeds.json and generate a consolidated
JSON file for use by the static news site. It fetches each feed, parses
the XML, extracts basic fields and deduplicates entries based on the
headline. The resulting structure is written to ``data/news.json``.

The script is intentionally kept lightweight and uses only Python's
standard library to avoid external dependencies. It should be run as part
of a scheduled job (e.g. GitHub Action) to refresh the site contents every
10 minutes. If any feeds fail to load or parse, the script will skip them
gracefully and continue processing the remaining feeds.
"""

import json
import xml.etree.ElementTree as ET
import urllib.request
import urllib.error
import datetime
import email.utils
import html
import os
import concurrent.futures
import re
from urllib.parse import urlparse


# Simple bias mapping by news domain. Values range from -1 (left) to +1 (right)
# with 0 representing a centrist or unknown leaning.
BIAS_RATINGS = {
    'reuters.com': 0,
    'bbc.co.uk': -1,
    'apnews.com': 0,
    'aljazeera.com': -1,
    'npr.org': -1,
    'news.google.com': 0,
}

def parse_pub_date(value: str) -> datetime.datetime:
    """Parse an RSS/Atom pubDate into a timezone‑aware UTC datetime.

    Falls back to the current UTC time if parsing fails.
    """
    if not value:
        return datetime.datetime.now(datetime.timezone.utc)
    try:
        # ``email.utils.parsedate_to_datetime`` returns a :class:`datetime`
        # object and handles many RSS/Atom date formats. It may produce a
        # naive datetime when the input lacks timezone information, so in
        # that case we explicitly assume UTC.
        dt = email.utils.parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        else:
            dt = dt.astimezone(datetime.timezone.utc)
        return dt
    except Exception:
        return datetime.datetime.now(datetime.timezone.utc)


def _html_parser() -> ET.XMLParser:
    parser = ET.XMLParser()
    for name, value in html.entities.html5.items():
        parser.entity[name[:-1]] = value
    return parser


def extract_items(xml_data: bytes) -> list:
    """Extract a list of items from an RSS or Atom feed XML.

    Returns a list of dictionaries with keys: title, link, description,
    pubDate, source and image (if available). The source is inferred
    from the link's domain.
    """
    items = []
    try:
        root = ET.fromstring(xml_data, parser=_html_parser())
    except ET.ParseError:
        return items

    # RSS feeds typically have channel/item; Atom uses entry
    # Try both patterns
    rss_items = root.findall('.//item')
    atom_items = root.findall('.//{http://www.w3.org/2005/Atom}entry')
    for elem in rss_items + atom_items:
        title = elem.findtext('title') or elem.findtext('{http://www.w3.org/2005/Atom}title') or ''
        link = elem.findtext('link') or ''
        # Atom may put link under <link href="..."/>
        if not link:
            link_elem = elem.find('link')
            if link_elem is not None:
                link = link_elem.attrib.get('href', '')
        description = elem.findtext('description') or elem.findtext('summary') or ''
        # Remove HTML tags from description
        try:
            description_text = ET.fromstring(f'<div>{description}</div>', parser=_html_parser()).text or ''
        except ET.ParseError:
            description_text = ''

        # Attempt to extract an image URL from common RSS/Atom fields
        image_url = ''
        media = elem.find('{http://search.yahoo.com/mrss/}content')
        if media is not None:
            image_url = media.attrib.get('url', '')
        if not image_url:
            enclosure = elem.find('enclosure')
            if enclosure is not None and enclosure.attrib.get('type', '').startswith('image'):
                image_url = enclosure.attrib.get('url', '')
        if not image_url:
            thumb = elem.find('{http://search.yahoo.com/mrss/}thumbnail')
            if thumb is not None:
                image_url = thumb.attrib.get('url', '')
        if not image_url:
            img_tag = elem.find('imageurl')
            if img_tag is not None:
                image_url = img_tag.text or ''
        if not image_url and description:
            match = re.search(r'<img[^>]+src="([^"]+)"', description)
            if not match:
                match = re.search(r"<img[^>]+src='([^']+)'", description)
            if match:
                image_url = match.group(1)

        pub = elem.findtext('pubDate') or elem.findtext('{http://www.w3.org/2005/Atom}published') or ''
        pub_date = parse_pub_date(pub)
        netloc = urlparse(link).netloc
        source = netloc.replace('www.', '') if netloc else ''
        bias = BIAS_RATINGS.get(source, 0)
        items.append({
            'title': html.unescape(title.strip()),
            'link': link.strip(),
            'description': html.unescape(description_text.strip()),
            'pubDate': pub_date.isoformat().replace('+00:00', 'Z'),
            'source': source,
            'image': image_url,
            'bias': bias
        })
    return items


def fetch_feed(url: str) -> list:
    """Fetch and parse a single RSS/Atom feed URL, returning items list."""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; DailyUnbiasedNews/1.0)'})
        with urllib.request.urlopen(req, timeout=20) as response:
            data = response.read()
            return extract_items(data)
    except Exception:
        # Return an empty list if any error occurs so other feeds continue processing
        return []


def main():
    feeds_path = os.path.join(os.path.dirname(__file__), 'feeds.json')
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    os.makedirs(data_dir, exist_ok=True)
    output_path = os.path.join(data_dir, 'news.json')

    with open(feeds_path, 'r', encoding='utf-8') as f:
        feeds = json.load(f)

    aggregated = {}
    global_titles = set()
    today = datetime.datetime.utcnow().date()

    for category, urls in feeds.items():
        aggregated[category] = []
        # Fetch all feeds for this category in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(urls) or 1) as executor:
            futures = [executor.submit(fetch_feed, url) for url in urls]
            for future in concurrent.futures.as_completed(futures):
                try:
                    items = future.result()
                except Exception:
                    items = []
                for item in items:
                    # Deduplicate by title across all categories
                    title_key = item['title'].strip().lower()
                    pub_date = datetime.datetime.fromisoformat(
                        item['pubDate'].replace('Z', '+00:00')
                    ).date()
                    if pub_date != today or title_key in global_titles:
                        continue
                    global_titles.add(title_key)
                    aggregated[category].append(item)
        # For gaming news, enforce presence of title, link and image
        if category == 'Gaming':
            aggregated[category] = [
                it for it in aggregated[category]
                if it.get('title') and it.get('link') and it.get('image')
            ]
        # Sort items by publication date descending
        aggregated[category].sort(key=lambda x: x['pubDate'], reverse=True)
        if category == 'Gaming':
            # Stable sort to prioritize Steam entries
            aggregated[category].sort(key=lambda x: x['source'] != 'store.steampowered.com')
        # Keep top 50 items
        aggregated[category] = aggregated[category][:50]

    result = {
        'lastUpdate': datetime.datetime.utcnow().isoformat() + 'Z',
        'news': aggregated
    }

    with open(output_path, 'w', encoding='utf-8') as out:
        json.dump(result, out, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
