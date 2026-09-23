"""
Weekly scheduler.

Runs ONCE a week. It builds the next 7 days of slideshows and hands them to
Upload-Post with an exact date and time for each one. Upload-Post then holds
them and publishes them on the dot, so nothing depends on GitHub being on time,
and every upcoming post shows in your Upload-Post calendar.

Settings come from GitHub secrets:
  UPLOAD_POST_API_KEY   your Upload-Post API key
  UPLOAD_POST_USER      the profile name in Upload-Post
  ANTHROPIC_API_KEY     optional - lets the agent write new slideshows itself

=== SETTINGS =================================================================
"""
DAYS_AHEAD = 7                 # how many days to queue each run
TIMEZONE = "Europe/London"     # your local time, handles the clocks changing

# One entry per daily posting slot.
#   bank    : which content bank to take from
#   hour/min: local time the post goes live
STREAMS = [
    {"name": "meaffirmation", "bank": "bank_meaffirmation.json", "state": "state_meaffirmation.json",
     "brief": "brief_meaffirmation.txt", "hour": 18, "minute": 0, "platforms": ["tiktok"]},
    {"name": "neurofusion", "bank": "bank_neurofusion.json", "state": "state_neurofusion.json",
     "brief": "brief_neurofusion.txt", "hour": 21, "minute": 0, "platforms": ["tiktok"]},
]

DELIVEROO_DAYS = set()         # only used by Hyde's; empty means never
ORDER_LINE = ""                # extra line added to captions; empty means none
REFILL_WHEN_LEFT = 8           # write more slideshows when this many are left
REFILL_COUNT = 14
# =============================================================================

import json, os, re, glob, sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests
import engine

HERE = os.path.dirname(os.path.abspath(__file__))
TEST_MODE = os.environ.get("TEST_MODE", "false").lower() == "true"
API = "https://api.upload-post.com/api"
HEAD = lambda: {"Authorization": "Apikey " + os.environ["UPLOAD_POST_API_KEY"]}


def load(path, default=None):
    p = os.path.join(HERE, path)
    return json.load(open(p)) if os.path.exists(p) else default


def save(path, data):
    json.dump(data, open(os.path.join(HERE, path), "w"), indent=1, ensure_ascii=False)


# ---------- topping the bank up ----------
def valid_show(s, bank):
    try:
        sl = s["slides"]
        ok = (isinstance(s["id"], str) and isinstance(s["caption"], str) and len(sl) == 6
              and sl[0]["type"] == "hook" and sl[-1]["type"] == "cta"
              and all(x["type"] == "body" and x["title"] and x["text"] for x in sl[1:5]))
        if ok and bank.get("photos"):                 # photo brands: every photo must exist
            pics = [s.get("photo")] + [x.get("photo") for x in sl if x.get("photo")]
            ok = bool(pics[0]) and all(p in bank["photos"] for p in pics)
        return ok
    except Exception:
        return False


def refill(stream, bank, posted):
    left = [s for s in bank["slideshows"] if s["id"] not in posted]
    if len(left) >= REFILL_WHEN_LEFT:
        return False
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        print(f"  only {len(left)} slideshows left and no ANTHROPIC_API_KEY set")
        return False
    brief = open(os.path.join(HERE, stream["brief"])).read()
    used = " | ".join(s["slides"][0]["text"] for s in bank["slideshows"])
    photos = ""
    if bank.get("photos"):
        photos = ("\nEvery slideshow needs a main \"photo\", and each slide may set its own.\n"
                  "Use ONLY these exact filenames, matching what the slide talks about:\n"
                  + "\n".join(f"  {k}: {v}" for k, v in bank["photos"].items()))
    prompt = f"""You write TikTok photo slideshows for this brand. Follow every rule in the brief.

Write {REFILL_COUNT} NEW slideshows.

Rules:
- Each one gives one genuinely useful or appetising insight. Tease, never give everything away.
- No dashes of any kind. Commas and full stops only.
- Each slideshow: 1 hook slide (max 12 words), exactly 4 body slides (title max 4 words,
  text max 18 words), then a cta slide.
- Caption: 1 to 2 short sentences, may include 1 or 2 emojis. No hashtags, no links.
- Do not repeat these hooks already used: {used}
{photos}

Return ONLY a JSON array, no other text:
[{{"id": "short-kebab-id", {'"photo": "IMG_XXXX.jpeg", ' if photos else ''}"slides": [
  {{"type": "hook", "text": "..."}},
  {{"type": "body", "title": "...", "text": "..."}},
  {{"type": "body", "title": "...", "text": "..."}},
  {{"type": "body", "title": "...", "text": "..."}},
  {{"type": "body", "title": "...", "text": "..."}},
  {{"type": "cta"}}],
  "caption": "..."}}]

BRAND BRIEF:
{brief}
"""
    r = requests.post("https://api.anthropic.com/v1/messages",
                      headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                               "content-type": "application/json"},
                      json={"model": "claude-sonnet-5", "max_tokens": 8000,
                            "messages": [{"role": "user", "content": prompt}]}, timeout=600)
    r.raise_for_status()
    text = re.sub(r"```(json)?", "", "".join(b.get("text", "") for b in r.json()["content"])).strip()
    existing = {s["id"] for s in bank["slideshows"]}
    added = 0
    for s in json.loads(text):
        if not valid_show(s, bank):
            continue
        base = re.sub(r"[^a-z0-9-]", "", str(s["id"]).lower())[:40] or "post"
        s["id"] = f"{stream['name'][:2]}-{len(bank['slideshows']) + 1:03d}-{base}"
        if s["id"] in existing:
            continue
        bank["slideshows"].append(s); existing.add(s["id"]); added += 1
    print(f"  wrote {added} new slideshows")
    return added > 0


# ---------- scheduling one post ----------
def schedule_one(show, bank, stream, when_local):
    brand = dict(bank["brand"])
    if brand.get("deliveroo_line") and when_local.weekday() in DELIVEROO_DAYS:
        brand["cta_extra"] = brand["deliveroo_line"]
    folder = engine.render_show(show, brand)
    slides = sorted(glob.glob(os.path.join(folder, "slide_*.jpg")),
                    key=lambda p: int(re.findall(r"\d+", os.path.basename(p))[0]))

    caption = show["caption"]
    if ORDER_LINE:
        caption += "\n\n" + ORDER_LINE
        if brand.get("deliveroo_line") and when_local.weekday() in DELIVEROO_DAYS:
            caption += "\n" + brand["deliveroo_line"]
    caption += "\n\n" + " ".join(brand["hashtags"])

    data = [("user", os.environ["UPLOAD_POST_USER"]),
            ("title", show["slides"][0]["text"][:90]),
            ("description", caption),
            ("caption", caption),
            ("auto_add_music", "true"),
            ("privacy_level", "SELF_ONLY" if TEST_MODE else "PUBLIC_TO_EVERYONE"),  # always public on real runs
            ("scheduled_date", when_local.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")),
            ("timezone", "UTC"),
            ("async_upload", "true")]
    for p in stream["platforms"]:
        if p == "instagram" and TEST_MODE:
            continue                      # Instagram has no private option, so tests skip it
        data.append(("platform[]", p))

    files = [("photos[]", (os.path.basename(p), open(p, "rb"), "image/jpeg")) for p in slides]
    r = requests.post(f"{API}/upload_photos", headers={**HEAD(), "Idempotency-Key": show["id"]},
                      data=data, files=files, timeout=300)
    body = {}
    try:
        body = r.json()
    except Exception:
        pass
    when = when_local.strftime("%a %d %b, %H:%M")
    if r.status_code >= 300 or body.get("success") is False:
        print(f"  FAILED  {when}  {show['id']}  ->  {r.status_code} {r.text[:400]}")
        return False
    print(f"  queued  {when}  {show['id']}")
    return True


def main():
    now = datetime.now(ZoneInfo(TIMEZONE))
    print(f"Scheduling from {now:%a %d %b %H:%M} ({TIMEZONE})"
          + ("   [TEST: one private post in 15 minutes]" if TEST_MODE else ""))
    failures = 0

    for stream in STREAMS:
        print(f"\n{stream['name']}:")
        bank = load(stream["bank"])
        state = load(stream["state"], {"posted": []})
        posted = set(state["posted"])
        if refill(stream, bank, posted):
            save(stream["bank"], bank)

        todo = [s for s in bank["slideshows"] if s["id"] not in posted]
        if not todo:
            print("  nothing left to post; add ANTHROPIC_API_KEY so it can write more")
            continue

        if TEST_MODE:
            when = now + timedelta(minutes=15)
            schedule_one(todo[0], bank, stream, when)
            continue

        for day in range(DAYS_AHEAD):
            when = (now + timedelta(days=day)).replace(hour=stream["hour"], minute=stream["minute"],
                                                       second=0, microsecond=0)
            if when <= now + timedelta(minutes=10):
                continue                                   # that slot has already gone today
            if not todo:
                print("  bank ran dry before the week was filled")
                break
            show = todo.pop(0)
            if schedule_one(show, bank, stream, when):
                state["posted"].append(show["id"])
                save(stream["state"], state)
            else:
                failures += 1

    if failures:
        raise SystemExit(f"{failures} post(s) could not be scheduled. See the lines above.")
    print("\nAll queued. Check your Upload-Post calendar to see the week.")


if __name__ == "__main__":
    main()
