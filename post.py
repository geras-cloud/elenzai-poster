"""Elenzai daily poster: posts the due reels from schedule.json to the Facebook page and Instagram.

Runs on a GitHub timer (see .github/workflows/post.yml). No packages needed.
  python post.py            posts anything due and not yet posted
  python post.py --dry-run  Facebook: saves a private draft only. Instagram: builds the post and checks it, but does not publish.
Secrets come from the environment (FB_PAGE_TOKEN); they are never printed.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

GRAPH = "https://graph.facebook.com/v21.0"
PAGE_ID = "1364743160046540"        # Elenzai Facebook page
IG_ID = "17841435850166550"         # elenzai.co.uk on Instagram
BASE_URL = "https://geras-cloud.github.io/elenzai-poster/"
UK = ZoneInfo("Europe/London")
HERE = os.path.dirname(os.path.abspath(__file__))
MAX_LATE = timedelta(hours=12)      # later than this we do not post, we flag it instead


def tok():
    t = os.environ.get("FB_PAGE_TOKEN", "").strip()
    if not t:
        sys.exit("FB_PAGE_TOKEN is not set")
    return t


def call(url, data=None, headers=None, method=None):
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers or {}, method=method or ("POST" if body is not None else "GET"))
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        msg = e.read().decode(errors="replace")
        msg = msg.replace(tok(), "***")
        raise RuntimeError(f"HTTP {e.code} from {url.split('?')[0]}: {msg[:600]}")


def post_facebook(item, dry):
    video_url = BASE_URL + item["video"]
    start = call(f"{GRAPH}/{PAGE_ID}/video_reels", {"upload_phase": "start", "access_token": tok()})
    video_id, upload_url = start["video_id"], start["upload_url"]
    up = call(upload_url, data={}, headers={"Authorization": "OAuth " + tok(), "file_url": video_url})
    if not up.get("success"):
        raise RuntimeError(f"Facebook upload did not succeed: {up}")
    fin = call(f"{GRAPH}/{PAGE_ID}/video_reels", {
        "upload_phase": "finish", "video_id": video_id,
        "video_state": "DRAFT" if dry else "PUBLISHED",
        "description": item["caption"], "access_token": tok()})
    print(f"  facebook: {'draft saved' if dry else 'published'} video_id={video_id} {fin.get('success')}")
    return video_id


def post_instagram(item, dry):
    video_url = BASE_URL + item["video"]
    c = call(f"{GRAPH}/{IG_ID}/media", {
        "media_type": "REELS", "video_url": video_url, "caption": item["caption"],
        "share_to_feed": "true", "access_token": tok()})
    cid = c["id"]
    for _ in range(40):                       # up to about 7 minutes
        s = call(f"{GRAPH}/{cid}?" + urllib.parse.urlencode({"fields": "status_code,status", "access_token": tok()}))
        code = s.get("status_code")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram processing failed: {s}")
        time.sleep(10)
    else:
        raise RuntimeError("Instagram took too long to process the video")
    if dry:
        print(f"  instagram: checked OK, not published (container {cid})")
        return "dry-" + cid
    p = call(f"{GRAPH}/{IG_ID}/media_publish", {"creation_id": cid, "access_token": tok()})
    print(f"  instagram: published media_id={p.get('id')}")
    return p.get("id")


def main():
    dry = "--dry-run" in sys.argv
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1]
    sched = json.load(open(os.path.join(HERE, "schedule.json"), encoding="utf-8"))
    state_path = os.path.join(HERE, "state.json")
    state = json.load(open(state_path, encoding="utf-8")) if os.path.exists(state_path) else {}
    now = datetime.now(UK)
    failures = 0
    for item in sched:
        if only and item["id"] != only:
            continue
        due = datetime.strptime(item["date"] + " " + item["time"], "%Y-%m-%d %H:%M").replace(tzinfo=UK)
        done = state.setdefault(item["id"], {}) if not dry else {}
        if not dry and now < due:
            continue
        if not dry and now - due > MAX_LATE and not (done.get("fb") and done.get("ig")):
            if not done.get("missed"):
                print(f"{item['id']}: more than 12 hours late, not posting. Check it by hand.")
                done["missed"] = True
                failures += 1
            continue
        print(f"{item['id']} ({item['date']} {item['time']} UK){' [dry run]' if dry else ''}")
        for name, fn in (("fb", post_facebook), ("ig", post_instagram)):
            if done.get(name):
                continue
            try:
                res = fn(item, dry)
                if not dry:
                    done[name] = res
            except Exception as e:  # keep going so one platform failing does not block the other
                print(f"  {name} FAILED: {e}")
                failures += 1
        if dry:
            break                                # a dry run tests one item only
    if not dry:
        json.dump(state, open(state_path, "w", encoding="utf-8"), indent=2)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
