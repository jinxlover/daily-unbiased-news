#!/usr/bin/env python3
"""
Script to fetch RSS feeds defined in feeds.json and generate a consolidated
JSON file for use by the static news site. It fetches each feed, parses
the XML, extracts basic fields and deduplicates entries based on the
headline. The resulting structure is written to ``data/news.json``.

The script is intentionally kept lightweight and uses only Python's
standard library to avoid external dependencies. It should be run as part
of a scheduled job (e.g. GitHub Action) to refresh the site contents
daily. If any feeds fail to load or parse, the script will skip them
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
from urllib.parse import urlparse


def parse_pub_date(value: str) -> datetime.datetime:
    """Parse an RSS/Atom pubDate into a timezone‑aware datetime.

    Falls back to the current UTC time if parsing fails.
    """
    if not value:
        return datetime.datetime.utcnow()
    try:
        # Some feeds include commas or other tokens in the date. The
        # email.utils parser handles a variety of formats and returns a
        # 9‑tuple with timezone offset in seconds.
        dt_tuple = email.utils.parsedate_tz(value)
        if dt_tuple is None:
            raise ValueError
        dt = datetime.datetime(*dt_tuple[:6])
        tz_offset = dt_tuple[9]
        if tz_offset is not None:
            dt = dt - datetime.timedelta(seconds=tz_offset)
        return dt
    except Exception:
        return datetime.datetime.utcnow()


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

        pub = elem.findtext('pubDate') or elem.findtext('{http://www.w3.org/2005/Atom}published') or ''
        pub_date = parse_pub_date(pub)
        netloc = urlparse(link).netloc
        source = netloc.replace('www.', '') if netloc else ''
        items.append({
            'title': html.unescape(title.strip()),
            'link': link.strip(),
            'description': html.unescape(description_text.strip()),
            'pubDate': pub_date.isoformat(),
            'source': source,
            'image': image_url
        })
    return items


def fetch_feed(url: str) -> list:
    """Fetch and parse a single RSS/Atom feed URL, returning items list."""
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            data = response.read()
            return extract_items(data)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
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

    for category, urls in feeds.items():
        aggregated[category] = []
        for url in urls:
            items = fetch_feed(url)
            for item in items:
                # Deduplicate by title across all categories
                title_key = item['title'].strip().lower()
                if title_key in global_titles:
                    continue
                global_titles.add(title_key)
                aggregated[category].append(item)
        # Sort items by publication date descending and keep top 50
        aggregated[category].sort(key=lambda x: x['pubDate'], reverse=True)
        aggregated[category] = aggregated[category][:50]

    result = {
        'lastUpdate': datetime.datetime.utcnow().isoformat() + 'Z',
        'news': aggregated
    }

    with open(output_path, 'w', encoding='utf-8') as out:
        json.dump(result, out, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
