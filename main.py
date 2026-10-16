"""Download the Instagram data visible for one profile using local cookies.

Paste your own Cookie header into instagram_cookies.py, then run
`python main.py`. The script writes JSON exports and available media files to
`output/`; it does not start a local HTTP API.
"""
import json
import mimetypes
import os
import re
import time
from pathlib import Path
from urllib.parse import urlsplit

from curl_cffi import requests as curl_requests

import config
from instagram import discovery, refs
from instagram.posts import get_comments
from instagram.users import (
    get_followers,
    get_following,
    get_highlights,
    get_posts,
    get_profile,
    get_reels,
)

TARGET_USERNAME = "jhonatan.coronel"
PAGE_DELAY_SECONDS = 0.7
DOWNLOAD_MEDIA = True
DOWNLOAD_COMMENTS = True

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def save(name, data):
    path = OUTPUT_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    print(f"saved {path}")
    return path


def collect_all_pages(fetch_page, *, item_key, count_key, label, defaults=None):
    """Follow next_cursor until Instagram ends the list or blocks a page."""
    items = []
    seen_items = set()
    seen_cursors = set()
    first_page = None
    pending_cursor = None
    cursor = None
    pages_fetched = 0
    complete = False
    error = None

    while True:
        try:
            page = fetch_page(cursor)
            if not isinstance(page, dict):
                raise TypeError("Instagram returned an invalid page")
        except Exception as exc:
            error = f"{type(exc).__name__}: {str(exc)[:400]}"
            break

        if first_page is None:
            first_page = page
        pages_fetched += 1
        rows = page.get(item_key) or []
        added = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            key = row.get("id") or row.get("username") or json.dumps(row, sort_keys=True, ensure_ascii=False)
            if key in seen_items:
                continue
            seen_items.add(key)
            items.append(row)
            added += 1

        if not page.get("has_more"):
            complete = True
            pending_cursor = None
            break

        pending_cursor = page.get("next_cursor")
        if not pending_cursor:
            error = "Instagram indicó que había más páginas, pero no entregó un cursor."
            break
        if pending_cursor in seen_cursors:
            error = "Instagram repitió el cursor; se detuvo para evitar un bucle."
            break
        if not rows or not added:
            error = "Instagram indicó que había más páginas, pero la página llegó vacía o repetida."
            break

        seen_cursors.add(pending_cursor)
        cursor = pending_cursor
        time.sleep(PAGE_DELAY_SECONDS)

    result = dict(first_page or {})
    result.update(defaults or {})
    result[item_key] = items
    result[count_key] = len(items)
    result["pages_fetched"] = pages_fetched
    result["complete"] = complete
    result["has_more"] = not complete
    result["next_cursor"] = pending_cursor if not complete else None
    result["status"] = "complete" if complete else ("partial" if items else "failed")
    if error:
        result["error"] = error
    print(f"{label}: {len(items)} items, {pages_fetched} páginas, {result['status']}")
    if error:
        print(f"{label}: {error}")
    return result


def _safe_filename(value):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "item"))[:100]


def _item_asset_candidates(item, prefix):
    candidates = []
    image = item.get("image")
    if isinstance(image, str) and image.startswith("https://"):
        candidates.append((f"{prefix}_image", image))
    video = item.get("video")
    if isinstance(video, dict) and isinstance(video.get("link"), str):
        candidates.append((f"{prefix}_video", video["link"]))
    for index, slide in enumerate(item.get("carousel") or [], 1):
        if not isinstance(slide, dict):
            continue
        slide_prefix = f"{prefix}_slide_{index:02d}"
        slide_image = slide.get("image")
        if isinstance(slide_image, str) and slide_image.startswith("https://"):
            candidates.append((f"{slide_prefix}_image", slide_image))
        slide_video = slide.get("video")
        if isinstance(slide_video, dict) and isinstance(slide_video.get("link"), str):
            candidates.append((f"{slide_prefix}_video", slide_video["link"]))
    for index, story in enumerate(item.get("items") or [], 1):
        if not isinstance(story, dict):
            continue
        story_prefix = f"{prefix}_story_{index:02d}"
        story_image = story.get("image")
        if isinstance(story_image, str) and story_image.startswith("https://"):
            candidates.append((f"{story_prefix}_image", story_image))
        story_video = story.get("video")
        if isinstance(story_video, dict) and isinstance(story_video.get("link"), str):
            candidates.append((f"{story_prefix}_video", story_video["link"]))
    return candidates


def download_media(rows, folder_name):
    """Save available photos and videos from signed CDN links, without cookies."""
    media_dir = OUTPUT_DIR / "media" / _safe_filename(TARGET_USERNAME) / folder_name
    media_dir.mkdir(parents=True, exist_ok=True)
    downloaded = 0
    failed = []
    seen_urls = set()

    for index, item in enumerate(rows or [], 1):
        prefix = _safe_filename(item.get("id") or item.get("code") or f"item_{index:04d}")
        local_files = []
        for asset_name, url in _item_asset_candidates(item, prefix):
            if url in seen_urls:
                continue
            seen_urls.add(url)
            try:
                response = curl_requests.get(url, impersonate="chrome", timeout=90)
                if response.status_code >= 400:
                    raise RuntimeError(f"HTTP {response.status_code}")
                suffix = Path(urlsplit(url).path).suffix.lower()
                if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov"}:
                    content_type = response.headers.get("content-type", "").split(";", 1)[0]
                    suffix = mimetypes.guess_extension(content_type) or ".bin"
                path = media_dir / f"{asset_name}{suffix}"
                path.write_bytes(response.content)
                local_files.append(str(path))
                downloaded += 1
            except Exception as exc:
                failed.append({"item_id": item.get("id"), "asset": asset_name, "error": f"{type(exc).__name__}: {str(exc)[:180]}"})
            time.sleep(0.2)
        item["local_media_files"] = local_files

    report = {"downloaded": downloaded, "failed_count": len(failed), "failed": failed}
    print(f"media {folder_name}: {downloaded} archivos guardados, {len(failed)} fallos")
    return report


def collect_highlight_data(user):
    try:
        tray = get_highlights(user)
    except Exception as exc:
        return {"highlights": [], "highlight_count": 0, "complete": False,
                "error": f"{type(exc).__name__}: {str(exc)[:400]}"}

    details = []
    errors = []
    highlights = tray.get("highlights") or []
    for highlight in highlights:
        try:
            details.append(discovery.highlight_items(highlight["id"]))
        except Exception as exc:
            errors.append({"highlight_id": highlight.get("id"), "error": f"{type(exc).__name__}: {str(exc)[:250]}"})
        time.sleep(PAGE_DELAY_SECONDS)

    tray["highlight_items"] = details
    tray["highlight_count"] = len(highlights)
    tray["complete"] = not tray.get("has_more") and not errors
    if errors:
        tray["errors"] = errors
    tray["story_media_download"] = download_media(details, "highlights") if DOWNLOAD_MEDIA else None
    return tray


def collect_post_comments(posts):
    collections = []
    for index, post in enumerate(posts or [], 1):
        if not post.get("id") or not post.get("code"):
            continue
        post_ref = {"id": post["id"], "code": post["code"]}
        comments = collect_all_pages(
            lambda cursor, ref=post_ref: get_comments(ref, cursor=cursor),
            item_key="comments",
            count_key="comment_count",
            label=f"comments {post.get('code')}",
            defaults={"post_id": post["id"], "code": post["code"]},
        )
        collections.append(comments)
        if index < len(posts):
            time.sleep(PAGE_DELAY_SECONDS)
    return {
        "post_count": len(collections),
        "comment_count": sum(row.get("comment_count", 0) for row in collections),
        "posts": collections,
        "complete": all(row.get("complete") for row in collections),
    }


def main():
    if not config.instagram_cookies():
        raise SystemExit(
            "Pega tu Cookie header de Instagram en instagram_cookies.py y vuelve a ejecutar."
        )

    user = refs.resolve_user(TARGET_USERNAME)
    profile = get_profile(user)
    save(f"profile_{TARGET_USERNAME}.json", profile)

    posts = collect_all_pages(
        lambda cursor: get_posts(user, cursor=cursor),
        item_key="posts", count_key="post_count", label="posts",
        defaults={"user": user, "is_private": profile.get("is_private")},
    )
    reels = collect_all_pages(
        lambda cursor: get_reels(user, cursor=cursor),
        item_key="reels", count_key="reel_count", label="reels",
        defaults={"user": user, "is_private": profile.get("is_private")},
    )
    followers = collect_all_pages(
        lambda cursor: get_followers(user, cursor=cursor),
        item_key="users", count_key="count", label="followers",
        defaults={"user": user, "relationship": "followers"},
    )
    following = collect_all_pages(
        lambda cursor: get_following(user, cursor=cursor),
        item_key="users", count_key="count", label="following",
        defaults={"user": user, "relationship": "following"},
    )

    post_media_report = download_media(posts["posts"], "posts") if DOWNLOAD_MEDIA else None
    reel_media_report = download_media(reels["reels"], "reels") if DOWNLOAD_MEDIA else None
    posts["media_download"] = post_media_report
    reels["media_download"] = reel_media_report

    save(f"posts_{TARGET_USERNAME}.json", posts)
    save(f"reels_{TARGET_USERNAME}.json", reels)
    save(f"followers_{TARGET_USERNAME}.json", followers)
    save(f"following_{TARGET_USERNAME}.json", following)

    highlights = collect_highlight_data(user)
    save(f"highlights_{TARGET_USERNAME}.json", highlights)

    comments = collect_post_comments(posts["posts"]) if DOWNLOAD_COMMENTS else {
        "post_count": 0, "comment_count": 0, "posts": [], "complete": False,
        "status": "disabled",
    }
    save(f"comments_{TARGET_USERNAME}.json", comments)

    datasets = {
        "posts": posts,
        "reels": reels,
        "followers": followers,
        "following": following,
        "highlights": highlights,
        "comments": comments,
    }
    count_keys = {
        "posts": "post_count",
        "reels": "reel_count",
        "followers": "count",
        "following": "count",
        "highlights": "highlight_count",
        "comments": "comment_count",
    }
    summary = {
        "target": TARGET_USERNAME,
        "profile_post_count_reported": profile.get("post_count"),
        "profile_follower_count_reported": profile.get("follower_count"),
        "profile_following_count_reported": profile.get("following_count"),
        "datasets": {
            name: {
                "count": data.get(count_keys[name], 0),
                "complete": data.get("complete", False),
                "status": data.get("status", "complete" if data.get("complete") else "partial"),
                "error": data.get("error"),
            }
            for name, data in datasets.items()
        },
        "media_download": {"posts": post_media_report, "reels": reel_media_report,
                           "highlights": highlights.get("story_media_download")},
    }
    save(f"summary_{TARGET_USERNAME}.json", summary)


if __name__ == "__main__":
    main()
