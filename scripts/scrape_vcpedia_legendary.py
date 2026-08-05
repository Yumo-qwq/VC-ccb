#!/usr/bin/env python3
"""Scrape VCPedia legendary-song lists into JSON.

The default mode only requests the four list pages from VCPedia and uses
Bilibili's public video API for current play counts. Detail pages are optional
because fetching one page per song can become a large crawl.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import random
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlparse
from urllib.request import Request, urlopen


BASE_URL = "https://vcpedia.cn"
DEFAULT_OUTPUT = Path("src/data/vcpedia_legendary_songs.json")
DEFAULT_CACHE_DIR = Path(".cache/vcpedia_legendary")

LABEL_TITLE = "\u66f2\u76ee"
LABEL_UP = "UP\u4e3b"
LABEL_SUBMITTED = "\u6295\u7a3f\u65f6\u95f4"
LABEL_ACHIEVED = "\u8fbe\u6210\u65f6\u95f4"
LABEL_SINGER = "\u6f14\u5531"
LABEL_LINK = "\u94fe\u63a5"

SOURCE_PAGES = [
    {
        "engine": "VOCALOID",
        "url": "https://vcpedia.cn/VOCALOID%E4%B8%AD%E6%96%87%E4%BC%A0%E8%AF%B4%E6%9B%B2",
    },
    {
        "engine": "X Studio",
        "url": "https://vcpedia.cn/X_Studio%E4%BC%A0%E8%AF%B4%E6%9B%B2",
    },
    {
        "engine": "Synthesizer V",
        "url": "https://vcpedia.cn/Synthesizer_V%E4%BC%A0%E8%AF%B4%E6%9B%B2",
    },
    {
        "engine": "ACE",
        "url": "https://vcpedia.cn/ACE%E4%BC%A0%E8%AF%B4%E6%9B%B2",
    },
]

USER_AGENT = (
    "VOCALOID-ccb data script/0.1 "
    "(respectful low-rate crawler; https://github.com/local/VOCALOID-ccb)"
)


@dataclass
class Fetcher:
    cache_dir: Path
    delay: float
    jitter: float
    refresh: bool
    last_request_at: float = 0.0

    def get_text(self, url: str, *, delay: float | None = None) -> str:
        cache_path = self._cache_path(url)
        if cache_path.exists() and not self.refresh:
            return cache_path.read_text(encoding="utf-8")

        wait = self._wait_time(delay)
        if wait > 0:
            time.sleep(wait)

        request = Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
            },
        )
        with urlopen(request, timeout=30) as response:
            content_type = response.headers.get_content_charset() or "utf-8"
            text = response.read().decode(content_type, errors="replace")

        self.last_request_at = time.monotonic()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(text, encoding="utf-8")
        return text

    def _wait_time(self, delay: float | None) -> float:
        spacing = self.delay if delay is None else delay
        elapsed = time.monotonic() - self.last_request_at
        base_wait = max(0.0, spacing - elapsed)
        jitter_wait = random.uniform(0.0, self.jitter) if self.jitter > 0 else 0.0
        return base_wait + jitter_wait

    def _cache_path(self, url: str) -> Path:
        parsed = urlparse(url)
        suffix = ".json" if parsed.path.endswith(".php") or "api.bilibili.com" in parsed.netloc else ".html"
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
        return self.cache_dir / f"{digest}{suffix}"


def clean_text(fragment: str) -> str:
    fragment = re.sub(r"(?i)<br\s*/?>", " ", fragment)
    fragment = re.sub(r"(?s)<script.*?</script>", " ", fragment)
    fragment = re.sub(r"(?s)<style.*?</style>", " ", fragment)
    fragment = re.sub(r"(?s)<[^>]+>", " ", fragment)
    text = html.unescape(fragment)
    text = re.sub(r"[\u200b\xa0]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def attr_value(tag: str, attr: str) -> str | None:
    pattern = rf'{attr}\s*=\s*(["\'])(.*?)\1'
    match = re.search(pattern, tag, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return html.unescape(match.group(2)).strip()


def first_group(pattern: str, text: str, flags: int = re.DOTALL | re.IGNORECASE) -> str | None:
    match = re.search(pattern, text, flags=flags)
    return match.group(1) if match else None


def split_people(text: str) -> list[str]:
    text = text.replace("feat.", "\u3001").replace("Feat.", "\u3001")
    text = re.sub(r"\s*(?:/|\uff0f|\u3001|,|&|\+| x | X | feat | with )\s*", "\u3001", text)
    people = []
    for item in text.split("\u3001"):
        name = item.strip(" \t\r\n[]()（）")
        if name and name not in people:
            people.append(name)
    return people


def canonical_url(url_or_path: str | None) -> str | None:
    if not url_or_path:
        return None
    return urljoin(BASE_URL, html.unescape(url_or_path))


def extract_bilibili_id(url: str | None) -> tuple[str, str] | tuple[None, None]:
    if not url:
        return None, None
    bv = re.search(r"/video/(BV[0-9A-Za-z]+)", url)
    if bv:
        return "bvid", bv.group(1)
    av = re.search(r"/video/av(\d+)", url, flags=re.IGNORECASE)
    if av:
        return "aid", av.group(1)
    aid = re.search(r"[?&]aid=(\d+)", url, flags=re.IGNORECASE)
    if aid:
        return "aid", aid.group(1)
    bvid = re.search(r"[?&]bvid=(BV[0-9A-Za-z]+)", url)
    if bvid:
        return "bvid", bvid.group(1)
    return None, None


def slice_bilibili_section(page_html: str) -> str:
    start_match = re.search(
        r'(?i)<span\s+class="mw-headline"\s+id="bilibili\u6295\u7a3f">',
        page_html,
    )
    if not start_match:
        start_match = re.search(r"(?i)bilibili\u6295\u7a3f", page_html)
    if not start_match:
        return page_html
    start = start_match.start()

    stop_match = re.search(
        r'<span\s+class="mw-headline"\s+id="(?:YouTube\u6295\u7a3f|\u5176\u4ed6\u5e73\u53f0\u6295\u7a3f|\u63a5\u8fd1\u4f20\u8bf4\u66f2\u8981\u6c42\u7684\u66f2\u76ee)"',
        page_html[start + 1 :],
    )
    stop = start + 1 + stop_match.start() if stop_match else len(page_html)
    return page_html[start:stop]


def parse_list_page(page_html: str, source_url: str, engine: str) -> tuple[list[dict[str, Any]], int]:
    section = slice_bilibili_section(page_html)
    chunks = section.split('class="CLS"')
    songs: list[dict[str, Any]] = []
    skipped_covers = 0

    for chunk in chunks[1:]:
        block = chunk.split('class="CLS"', 1)[0]
        title_line = first_group(
            rf"<b>\s*{LABEL_TITLE}\s*</b>\s*[:\uff1a]\s*(.*?)</div>",
            block,
        )
        if not title_line:
            continue

        if is_cover_song(title_line):
            skipped_covers += 1
            continue

        title_match = re.search(r"<a\b([^>]*)>(.*?)</a>", title_line, flags=re.DOTALL | re.IGNORECASE)
        if not title_match:
            continue

        title = clean_text(title_match.group(2))
        detail_url = canonical_url(attr_value(title_match.group(1), "href"))

        img_tag = first_group(r"(<img\b[^>]*>)", block)
        cover = canonical_url(attr_value(img_tag, "src") if img_tag else None)

        singer_header = block.split("<img", 1)[0]
        singer_titles = re.findall(r'title\s*=\s*(["\'])(.*?)\1', singer_header, flags=re.DOTALL)
        singers: list[str] = []
        for _, raw_title in singer_titles:
            for singer in split_people(html.unescape(raw_title)):
                if singer and singer not in singers:
                    singers.append(singer)

        up_line = first_group(rf"<b>\s*{LABEL_UP}\s*</b>\s*[:\uff1a]\s*(.*?)</div>", block)
        producer = clean_text(up_line or "") or None

        submitted_at = clean_text(first_group(rf"<b>\s*{LABEL_SUBMITTED}\s*</b>\s*[:\uff1a]\s*(.*?)</div>", block) or "")
        achieved_at = clean_text(first_group(rf"<b>\s*{LABEL_ACHIEVED}\s*</b>\s*[:\uff1a]\s*(.*?)</div>", block) or "")
        year = int(submitted_at[:4]) if re.match(r"\d{4}", submitted_at) else None

        bilibili_match = re.search(
            r'href\s*=\s*(["\'])(https?://(?:www\.)?bilibili\.com/video/[^"\']+)\1',
            block,
            flags=re.IGNORECASE,
        )
        bilibili_url = html.unescape(bilibili_match.group(2)) if bilibili_match else None

        songs.append(
            {
                "id": make_song_id(title, engine, bilibili_url),
                "title": title,
                "producer": producer,
                "singers": singers,
                "year": year,
                "plays": None,
                "engine": engine,
                "cover": cover,
                "bilibiliUrl": bilibili_url,
                "detailUrl": detail_url,
                "sourcePage": source_url,
                "submittedAt": submitted_at or None,
                "achievedAt": achieved_at or None,
            }
        )

    return songs, skipped_covers


def is_cover_song(title_line: str) -> bool:
    text = clean_text(title_line)
    if re.search(r"[\(（]\s*\u7ffb\s*[\)）]", text):
        return True
    if re.search(r">\s*\u7ffb\s*</a>", title_line):
        return True
    return False


def make_song_id(title: str, engine: str, bilibili_url: str | None) -> str:
    key = f"{engine}:{title}:{bilibili_url or ''}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def parse_detail_page(page_html: str) -> dict[str, Any]:
    table_start = page_html.find("moe-infobox infobox")
    if table_start < 0:
        return {}
    table_open = page_html.rfind("<table", 0, table_start)
    table_close = page_html.find("</table>", table_start)
    if table_open < 0 or table_close < 0:
        return {}
    table = page_html[table_open : table_close + len("</table>")]
    rows = re.findall(r"(?is)<tr\b[^>]*>(.*?)</tr>", table)

    data: dict[str, Any] = {}
    last_header: str | None = None
    for row in rows:
        row_text = clean_text(row)
        if not row_text:
            continue
        if row_text in {LABEL_SINGER, LABEL_UP, LABEL_LINK}:
            last_header = row_text
            continue
        if last_header == LABEL_SINGER:
            data["singers"] = split_people(row_text)
        elif last_header == LABEL_UP:
            data["producer"] = row_text
        elif last_header == LABEL_LINK:
            match = re.search(
                r'href\s*=\s*(["\'])(https?://(?:www\.)?bilibili\.com/video/[^"\']+)\1',
                row,
                flags=re.IGNORECASE,
            )
            if match:
                data["bilibiliUrl"] = html.unescape(match.group(2))
        last_header = None
    return data


def fetch_bilibili_stats(fetcher: Fetcher, song: dict[str, Any], delay: float) -> dict[str, Any]:
    id_type, video_id = extract_bilibili_id(song.get("bilibiliUrl"))
    if not id_type or not video_id:
        return {"plays": None, "bilibiliAid": None, "bilibiliBvid": None, "bilibiliTitle": None}

    api_url = f"https://api.bilibili.com/x/web-interface/view?{id_type}={quote(video_id)}"
    raw = fetcher.get_text(api_url, delay=delay)
    payload = json.loads(raw)
    if payload.get("code") != 0:
        raise RuntimeError(f"Bilibili API returned code {payload.get('code')}: {payload.get('message')}")
    data = payload.get("data") or {}
    stat = data.get("stat") or {}
    return {
        "plays": stat.get("view"),
        "bilibiliAid": data.get("aid"),
        "bilibiliBvid": data.get("bvid"),
        "bilibiliTitle": data.get("title"),
    }


def scrape(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    fetcher = Fetcher(
        cache_dir=args.cache_dir,
        delay=args.delay,
        jitter=args.jitter,
        refresh=args.refresh,
    )

    all_songs: list[dict[str, Any]] = []
    meta = {
        "scrapedAt": datetime.now(timezone.utc).isoformat(),
        "sourcePages": [page["url"] for page in SOURCE_PAGES],
        "skippedCovers": 0,
        "statErrors": [],
        "detailErrors": [],
    }

    for source in SOURCE_PAGES:
        print(f"Fetching list: {source['engine']} {source['url']}", file=sys.stderr)
        page_html = fetcher.get_text(source["url"])
        songs, skipped = parse_list_page(page_html, source["url"], source["engine"])
        meta["skippedCovers"] += skipped
        all_songs.extend(songs)
        if args.max_songs and len(all_songs) >= args.max_songs:
            all_songs = all_songs[: args.max_songs]
            break

    all_songs = dedupe_songs(all_songs)

    if args.fetch_details:
        for index, song in enumerate(all_songs, start=1):
            if not song.get("detailUrl"):
                continue
            try:
                print(f"Fetching detail {index}/{len(all_songs)}: {song['title']}", file=sys.stderr)
                detail_html = fetcher.get_text(song["detailUrl"], delay=args.detail_delay)
                detail = parse_detail_page(detail_html)
                for key, value in detail.items():
                    if value:
                        song[key] = value
            except (HTTPError, URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
                meta["detailErrors"].append({"title": song["title"], "error": str(exc)})

    if not args.no_bilibili_stats:
        for index, song in enumerate(all_songs, start=1):
            try:
                print(f"Fetching stat {index}/{len(all_songs)}: {song['title']}", file=sys.stderr)
                stat = fetch_bilibili_stats(fetcher, song, args.bilibili_delay)
                song.update(stat)
            except (HTTPError, URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
                meta["statErrors"].append({"title": song["title"], "url": song.get("bilibiliUrl"), "error": str(exc)})

    return all_songs, meta


def dedupe_songs(songs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str | None, str | None]] = set()
    result = []
    for song in songs:
        key = (song["engine"], song.get("detailUrl"), song.get("bilibiliUrl"))
        if key in seen:
            continue
        seen.add(key)
        result.append(song)
    return result


def write_output(path: Path, songs: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(songs, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help=f"JSON output path (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR, help=f"HTTP cache directory (default: {DEFAULT_CACHE_DIR})")
    parser.add_argument("--refresh", action="store_true", help="Ignore cached responses and request fresh data.")
    parser.add_argument("--delay", type=float, default=8.0, help="Seconds between VCPedia list requests (default: 8).")
    parser.add_argument("--jitter", type=float, default=1.0, help="Random extra wait in seconds before network requests (default: 1).")
    parser.add_argument("--fetch-details", action="store_true", help="Also fetch each song detail page. This is slower and heavier.")
    parser.add_argument("--detail-delay", type=float, default=10.0, help="Seconds between detail-page requests (default: 10).")
    parser.add_argument("--no-bilibili-stats", action="store_true", help="Do not fetch current Bilibili play counts.")
    parser.add_argument("--bilibili-delay", type=float, default=1.5, help="Seconds between Bilibili API requests (default: 1.5).")
    parser.add_argument("--max-songs", type=int, default=0, help="Limit songs for testing.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    songs, meta = scrape(args)
    write_output(args.output, songs)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "songs": len(songs),
                "skippedCovers": meta["skippedCovers"],
                "statErrors": len(meta["statErrors"]),
                "detailErrors": len(meta["detailErrors"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if meta["statErrors"] or meta["detailErrors"]:
        error_path = args.output.with_suffix(".errors.json")
        error_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote error metadata: {error_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
