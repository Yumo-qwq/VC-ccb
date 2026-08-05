#!/usr/bin/env python3
"""Download scraped song covers into public/covers.

The script reuses cover URLs already stored in the song JSON. It downloads
each unique URL once, keeps a local static path in the JSON, and preserves the
original URL as coverUrl for future refreshes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
import time
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from PIL import Image, ImageOps
except ImportError:  # pragma: no cover - optional script dependency
    Image = None
    ImageOps = None


DEFAULT_INPUT = Path("src/data/vcpedia_legendary_songs.json")
DEFAULT_COVER_DIR = Path("public/covers")
USER_AGENT = "VOCALOID-ccb cover downloader/0.1"


def normalize_url(value: str | None) -> str | None:
    if not value:
        return None
    if value.startswith("//"):
        return f"https:{value}"
    if value.lower().startswith("http://"):
        return f"https://{value[7:]}"
    return value


def extension_for(content_type: str, url: str) -> str:
    content_type = content_type.lower().split(";", 1)[0].strip()
    extensions = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/avif": ".avif",
    }
    if content_type in extensions:
        return extensions[content_type]

    path = url.split("?", 1)[0].lower()
    for extension in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"):
        if path.endswith(extension):
            return ".jpg" if extension == ".jpeg" else extension
    return ".jpg"


def optimize_cover(body: bytes) -> tuple[bytes, str]:
    if Image is None or ImageOps is None:
        return body, ""

    with Image.open(BytesIO(body)) as image:
        image = ImageOps.exif_transpose(image)
        image.thumbnail((640, 360), Image.Resampling.LANCZOS)
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
        output = BytesIO()
        image.save(output, "WEBP", quality=78, method=6)
    return output.getvalue(), ".webp"


def public_url(path: Path) -> str:
    try:
        return "/" + path.relative_to(Path("public")).as_posix()
    except ValueError:
        return "/" + path.as_posix()


def candidate_urls(url: str) -> list[str]:
    candidates = [url]
    alternate = re.sub(r"^https://i[0-9]+\.hdslb\.com/", "https://archive.biliimg.com/", url)
    if alternate != url:
        candidates.append(alternate)
    return candidates


def download(url: str, timeout: float) -> tuple[bytes, str]:
    last_error: Exception | None = None
    for candidate in candidate_urls(url):
        try:
            referer = "https://www.bilibili.com/" if "biliimg.com" in candidate or "hdslb.com" in candidate else "https://vcpedia.cn/"
            request = Request(
                candidate,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                    "Referer": referer,
                },
            )
            with urlopen(request, timeout=timeout) as response:
                content_type = response.headers.get("Content-Type", "")
                body = response.read()
            if not body:
                raise RuntimeError("empty image response")
            if content_type and not content_type.lower().startswith("image/"):
                raise RuntimeError(f"unexpected content type: {content_type}")
            optimized, optimized_extension = optimize_cover(body)
            return optimized, optimized_extension or extension_for(content_type, url)
        except (HTTPError, URLError, TimeoutError, RuntimeError) as exc:
            last_error = exc
    raise last_error or RuntimeError("cover download failed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--cover-dir", type=Path, default=DEFAULT_COVER_DIR)
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--jitter", type=float, default=0.5)
    parser.add_argument("--max-covers", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=12.0)
    parser.add_argument("--refresh", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    songs = json.loads(args.input.read_text(encoding="utf-8"))
    args.cover_dir.mkdir(parents=True, exist_ok=True)

    by_url: dict[str, Path] = {}
    errors = []
    downloaded = 0
    skipped = 0
    last_request_at = 0.0

    for index, song in enumerate(songs, start=1):
        source_url = normalize_url(song.get("coverUrl") or song.get("cover"))
        if not source_url or not source_url.startswith("http"):
            errors.append({"id": song.get("id"), "title": song.get("title"), "error": "missing cover URL"})
            continue

        if args.max_covers and downloaded >= args.max_covers:
            break

        if source_url in by_url:
            local_path = by_url[source_url]
            song["coverUrl"] = source_url
            song["cover"] = public_url(local_path)
            skipped += 1
            continue

        digest = hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:20]
        existing = next(args.cover_dir.glob(f"{digest}.*"), None)
        if existing and not args.refresh:
            local_path = existing
            by_url[source_url] = local_path
            song["coverUrl"] = source_url
            song["cover"] = public_url(local_path)
            skipped += 1
            continue

        wait = max(0.0, args.delay - (time.monotonic() - last_request_at))
        wait += random.uniform(0.0, args.jitter)
        if wait:
            time.sleep(wait)

        try:
            print(f"Downloading cover {index}/{len(songs)}: {song['title']}", file=sys.stderr)
            body, extension = download(source_url, args.timeout)
            local_path = args.cover_dir / f"{digest}{extension}"
            local_path.write_bytes(body)
            by_url[source_url] = local_path
            song["coverUrl"] = source_url
            song["cover"] = public_url(local_path)
            downloaded += 1
            last_request_at = time.monotonic()
            if downloaded % 10 == 0:
                args.input.write_text(json.dumps(songs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except (HTTPError, URLError, TimeoutError, RuntimeError, OSError) as exc:
            errors.append({"id": song.get("id"), "title": song.get("title"), "url": source_url, "error": str(exc)})

    args.input.write_text(json.dumps(songs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"songs": len(songs), "downloaded": downloaded, "deduped": skipped, "errors": len(errors)}, ensure_ascii=False, indent=2))
    if errors:
        error_path = args.input.with_suffix(".cover-errors.json")
        error_path.write_text(json.dumps(errors, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote error metadata: {error_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
