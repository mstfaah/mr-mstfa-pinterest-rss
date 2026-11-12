#!/usr/bin/env python3
"""Build a Pinterest-compatible RSS 2.0 feed from the Blogger RSS.

Blogger's native /rss.xml only emits media:thumbnail (often s72-c) and puts
full-size photos inside the HTML <description>. Pinterest auto-publish looks
for high-quality images in <media:content>, <enclosure>, or <image> under
each <item> — so the native feed fails.

This script does not change the Blogger blog. It reads the public RSS and
writes a new feed with one full-size image per item.
"""
from __future__ import annotations

import argparse
import html
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime, parsedate_to_datetime
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape

BLOGGER_RSS = "https://mr-mstfa.blogspot.com/feeds/posts/default?alt=rss"
BLOG_HOME = "https://mr-mstfa.blogspot.com/"
BLOG_TITLE = "MR.MSTFA | وظائف قطر والسعودية والإمارات"
BLOG_DESC = (
    "وظائف موثوقة وأدوات ونصائح عملية للباحثين عن عمل "
    "في قطر والسعودية والإمارات ودول الخليج."
)
CLAIMED_HOST = "mr-mstfa.blogspot.com"
UA = "MRMSTFA-PinterestFeed/1.0 (https://mr-mstfa.blogspot.com/; rss rebuild)"
IMG_RE = re.compile(r"<img[^>]+src=['\"]([^'\"]+)['\"]", re.I)
BLOGGER_SIZE_RE = re.compile(r"(/s\d+(?:-c)?/)|(=s\d+(?:-c)?\b)")
MEDIA_NS = "http://search.yahoo.com/mrss/"
ATOM_NS = "http://www.w3.org/2005/Atom"

# Default public URL after Mostafa approves a new GitHub Pages repo.
# Update FEED_SELF if the repo or path changes.
FEED_SELF_DEFAULT = "https://mstfaah.github.io/mr-mstfa-pinterest-rss/rss.xml"


def upscale_image_url(url: str) -> str:
    """Rewrite Blogger thumbnail/resized URLs to a large uncropped size.

    /s72-c/ or /s320/ or =s400-c  ->  /s1600/ or =s1600
    Wikimedia and other absolute image URLs are left unchanged.
    """
    if not url:
        return url
    url = re.sub(r"/s\d+-c/", "/s1600/", url)
    url = re.sub(r"/s\d+/", "/s1600/", url)
    url = re.sub(r"=s\d+-c\b", "=s1600", url)
    url = re.sub(r"=s\d+\b", "=s1600", url)
    return url


def guess_type(url: str) -> str:
    u = url.lower().split("?", 1)[0]
    if u.endswith(".png"):
        return "image/png"
    if u.endswith(".webp"):
        return "image/webp"
    if u.endswith(".gif"):
        return "image/gif"
    return "image/jpeg"


def first_image(description: str) -> Optional[str]:
    for src in IMG_RE.findall(description or ""):
        src = html.unescape(src).strip()
        if not src or src.startswith("data:"):
            continue
        if src.startswith("//"):
            src = "https:" + src
        if src.startswith("http://") or src.startswith("https://"):
            return src
    return None


def plain_text(description: str, limit: int = 420) -> str:
    text = description or ""
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?is)<br\s*/?>", "\n", text)
    text = re.sub(r"(?is)</p>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, */*"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read()


def build(source_xml: bytes, self_link: str, max_items: int) -> tuple[str, list[dict]]:
    root = ET.fromstring(source_xml)
    channel = root.find("channel")
    if channel is None:
        raise SystemExit("source is not RSS 2.0 (no channel)")
    items_out: list[dict] = []
    skipped: list[dict] = []
    now = format_datetime(datetime.now(timezone.utc))

    parts: list[str] = []
    parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    parts.append(
        '<rss version="2.0" '
        f'xmlns:media="{MEDIA_NS}" '
        f'xmlns:atom="{ATOM_NS}">'
    )
    parts.append("<channel>")
    parts.append(f"<title>{escape(BLOG_TITLE)}</title>")
    parts.append(f"<link>{escape(BLOG_HOME)}</link>")
    parts.append(f"<description>{escape(BLOG_DESC)}</description>")
    parts.append("<language>ar</language>")
    parts.append(f"<lastBuildDate>{escape(now)}</lastBuildDate>")
    parts.append(
        f'<atom:link href="{escape(self_link)}" rel="self" type="application/rss+xml"/>'
    )

    for it in channel.findall("item"):
        if len(items_out) >= max_items:
            break
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        guid = (it.findtext("guid") or link).strip()
        pub = (it.findtext("pubDate") or now).strip()
        desc = it.findtext("description") or ""
        img = first_image(desc)
        if not img:
            skipped.append({"title": title, "link": link, "reason": "no image in item"})
            continue
        # Keep item links on the claimed Blogger domain only.
        if CLAIMED_HOST not in link:
            skipped.append({"title": title, "link": link, "reason": "link not on claimed domain"})
            continue
        hi = upscale_image_url(img)
        mime = guess_type(hi)
        pin_desc = plain_text(desc)
        rec = {
            "title": title,
            "link": link,
            "pubDate": pub,
            "image": hi,
            "original_image": img,
            "upscaled": hi != img,
            "type": mime,
            "description": pin_desc,
        }
        items_out.append(rec)
        parts.append("<item>")
        parts.append(f"<title>{escape(title)}</title>")
        parts.append(f"<link>{escape(link)}</link>")
        parts.append(f'<guid isPermaLink="true">{escape(link)}</guid>')
        parts.append(f"<pubDate>{escape(pub)}</pubDate>")
        parts.append(f"<description>{escape(pin_desc)}</description>")
        parts.append(
            f'<media:content url="{escape(hi)}" medium="image" type="{escape(mime)}"/>'
        )
        parts.append(
            f'<enclosure url="{escape(hi)}" type="{escape(mime)}" length="0"/>'
        )
        parts.append("</item>")

    parts.append("</channel></rss>")
    return "\n".join(parts) + "\n", items_out, skipped


def validate_xml(text: str) -> list[dict]:
    """Structural validation (no network). Returns per-item findings."""
    # namespace map so ElementTree finds media:*
    ET.register_namespace("media", MEDIA_NS)
    ET.register_namespace("atom", ATOM_NS)
    root = ET.fromstring(text.encode("utf-8"))
    if root.tag != "rss":
        raise SystemExit(f"root is {root.tag}, not rss")
    ver = root.attrib.get("version", "")
    if not ver.startswith("2"):
        raise SystemExit(f"rss version {ver} is not 2.x")
    findings = []
    for it in root.findall("channel/item"):
        title = it.findtext("title") or ""
        link = it.findtext("link") or ""
        mc = it.find(f"{{{MEDIA_NS}}}content")
        enc = it.find("enclosure")
        img_tag = it.find("image")
        mc_url = mc.get("url") if mc is not None else ""
        enc_url = enc.get("url") if enc is not None else ""
        ok = bool(mc_url or enc_url or (img_tag is not None))
        findings.append(
            {
                "title": title,
                "link": link,
                "has_media_content": mc is not None and bool(mc_url),
                "media_medium": mc.get("medium") if mc is not None else None,
                "media_type": mc.get("type") if mc is not None else None,
                "has_enclosure": enc is not None and bool(enc_url),
                "enclosure_type": enc.get("type") if enc is not None else None,
                "image_url": mc_url or enc_url,
                "link_on_claimed_domain": CLAIMED_HOST in link,
                "pinterest_image_tag_ok": ok,
            }
        )
    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", help="Local Blogger RSS file (default: fetch live)")
    ap.add_argument("-o", "--output", default="rss.xml")
    ap.add_argument("--self-link", default=FEED_SELF_DEFAULT)
    ap.add_argument("--max-items", type=int, default=25)
    args = ap.parse_args()

    if args.source:
        source = Path(args.source).read_bytes()
    else:
        source = fetch(f"{BLOGGER_RSS}&max-results={args.max_items}")

    xml_text, items, skipped = build(source, args.self_link, args.max_items)
    findings = validate_xml(xml_text)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(xml_text, encoding="utf-8")

    ok = sum(1 for f in findings if f["pinterest_image_tag_ok"] and f["link_on_claimed_domain"])
    print(f"wrote {out}  items={len(items)}  skipped={len(skipped)}  pinterest_ok={ok}/{len(findings)}")
    for s in skipped:
        print(f"  SKIP {s['reason']}: {s['title']}  {s['link']}")
    bad = [f for f in findings if not (f["pinterest_image_tag_ok"] and f["link_on_claimed_domain"])]
    if bad:
        print("VALIDATION FAILURES:")
        for f in bad:
            print(" ", f)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
