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
     "brief": "brief_neurofusion.txt", "hour": 21, "minute": 0, "platforms": ["tiktok"],
     # what kind of post goes out each day (Mon=0 ... Sun=6)
     "mix": {0: "product", 1: "story", 2: "product", 3: "diagram", 4: "story", 5: "product", 6: "general"}},
]

# NeuroFusion post kinds
#   story   : Robert Monroe, the Gateway research, the declassified 1983 report
#   diagram : how it works, left ear + right ear = the third beat (drawn as a diagram)
#   product : NeuroFusion itself, why it is rare, how to use a session, the void
#   general : entry level binaural beats (old posts without a kind count as this)
NF_BATCH = {"story": 2, "diagram": 1, "product": 3, "general": 1}   # 7 at a time so the writer never runs out of room
NF_BANNED = ["hemi-sync", "hemi sync", "hemisync", "cure", "cures", "treat", "treats", "treatment",
             "guarantee", "guaranteed", "driving", "free trial", "suppressed", "suppress"]

DELIVEROO_DAYS = set()         # only used by Hyde's; empty means never
ORDER_LINE = ""                # extra line added to captions; empty means none
REFILL_WHEN_LEFT = 8           # write more slideshows when this many are left
REFILL_COUNT = 7               # fewer at a time so the writer never runs out of room
REFILL_ROUNDS = 3              # full batches it may write in one run
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


# ---------- checking a slideshow is the right shape ----------
def kind_of(s):
    return s.get("kind") or "general"


def valid_show(s, bank, stream=None):
    try:
        sl = s["slides"]
        nf = bool(stream and stream.get("mix"))
        middle_ok = all((x["type"] == "body" and x["title"] and x["text"]) or
                        (nf and x["type"] == "diagram") for x in sl[1:5])
        ok = (isinstance(s["id"], str) and isinstance(s["caption"], str) and len(sl) == 6
              and sl[0]["type"] == "hook" and sl[-1]["type"] == "cta" and middle_ok)
        if ok and nf:
            text = json.dumps(s, ensure_ascii=False).lower()
            if (any(re.search(r"\b" + re.escape(b) + r"\b", text) for b in NF_BANNED)
                    or any(c in text for c in ["—", "–", " - "])):
                return False
            diagrams = [x for x in sl if x["type"] == "diagram"]
            if kind_of(s) == "diagram":
                if len(diagrams) != 1:
                    return False
                lft, rgt = int(diagrams[0]["left"]), int(diagrams[0]["right"])
                ok = 60 <= lft <= 600 and 1 <= rgt - lft <= 40
            else:
                ok = not diagrams
        if ok and bank.get("photos"):                 # photo brands: every photo must exist
            pics = [s.get("photo")] + [x.get("photo") for x in sl if x.get("photo")]
            ok = bool(pics[0]) and all(p in bank["photos"] for p in pics)
        return ok
    except Exception:
        return False


# ---------- topping the bank up ----------
def refill(stream, bank, posted):
    left = [s for s in bank["slideshows"] if s["id"] not in posted and valid_show(s, bank, stream)]
    if stream.get("mix"):                          # NeuroFusion: top up whichever kind runs low
        have = {k: sum(1 for s in left if kind_of(s) == k) for k in NF_BATCH}
        if all(have[k] >= max(2, n // 2) for k, n in NF_BATCH.items() if k != "general"):
            return False
    elif len(left) >= REFILL_WHEN_LEFT:
        return False
    # strip any stray spaces or line breaks that came in when the secret was pasted
    key = "".join((os.environ.get("ANTHROPIC_API_KEY") or "").split())
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
    mix = ""
    if stream.get("mix"):
        mix = f"""
KINDS: every slideshow has a "kind". Write exactly: {NF_BATCH["story"]} "story", {NF_BATCH["diagram"]} "diagram",
{NF_BATCH["product"]} "product", {NF_BATCH["general"]} "general" (see the WEEKLY MIX in the brief).
A "diagram" slideshow replaces its FIRST body slide with a diagram slide:
  {{"type": "diagram", "title": "How it works", "left": 200, "right": 210, "text": "max 14 words"}}
  left and right are whole numbers in Hz, right minus left between 4 and 14. The picture is drawn for you.
  The other 3 body slides then explain what that beat does and why NeuroFusion layers it.
Only "diagram" slideshows may contain a diagram slide.
"""
    prompt = f"""You write TikTok photo slideshows for this brand. Follow every rule in the brief.

Write {REFILL_COUNT} NEW slideshows.
{mix}
Rules:
- Each one gives one genuinely useful or appetising insight. Tease, never give everything away.
- No dashes of any kind. Commas and full stops only.
- Each slideshow: 1 hook slide (max 12 words), exactly 4 body slides (title max 4 words,
  text max 18 words), then a cta slide.
- Caption: 1 to 2 short sentences, may include 1 or 2 emojis. No hashtags, no links.
- Do not repeat these hooks already used: {used}
{photos}

Return ONLY a JSON array, no other text:
[{{"id": "short-kebab-id", {'"kind": "story", ' if stream.get("mix") else ''}{'"photo": "IMG_XXXX.jpeg", ' if photos else ''}"slides": [
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
    try:
        r = requests.post("https://api.anthropic.com/v1/messages",
                          headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                   "content-type": "application/json"},
                          json={"model": "claude-sonnet-5", "max_tokens": 16000,
                                "messages": [{"role": "user", "content": prompt}]}, timeout=600)
        r.raise_for_status()
        reply = r.json()
        text = re.sub(r"```(json)?", "", "".join(b.get("text", "") for b in reply.get("content", []))).strip()
        if "[" not in text:
            raise ValueError(f"no list in the reply (stop: {reply.get('stop_reason')}): {text[:200]!r}")
        new = json.loads(text[text.index("["): text.rindex("]") + 1])
    except Exception as e:
        # never let the writer stop the posts: carry on with what's already in the bank
        print(f"  couldn't write new slideshows ({str(e)[:200]}), carrying on with the {len(left)} left")
        return False
    existing = {s["id"] for s in bank["slideshows"]}
    added = 0
    for s in new:
        if not valid_show(s, bank, stream):
            continue
        base = re.sub(r"[^a-z0-9-]", "", str(s["id"]).lower())[:40] or "post"
        s["id"] = f"{stream['name'][:2]}-{len(bank['slideshows']) + 1:03d}-{base}"
        if s["id"] in existing:
            continue
        bank["slideshows"].append(s); existing.add(s["id"]); added += 1
    print(f"  wrote {added} new slideshows")
    return added > 0



# ---------- never run dry: bring back older posts ----------
RECYCLE_GAP = 21               # an old post can come back once 21 newer ones have gone out


def recycle(bank, posted_list, todo, need):
    """If the bank can't fill the week, reuse the longest-ago posts (with a fresh date), oldest first."""
    if len(todo) >= need:
        return todo
    history = list(dict.fromkeys(posted_list))
    gap = max(0, min(RECYCLE_GAP, len(history) - need))   # shrink the gap if history is short
    recent = set(history[-gap:]) if gap else set()
    by_id = {s["id"]: s for s in bank["slideshows"]}
    old = [by_id[i] for i in history if i in by_id and i not in recent]
    extra = [s for s in old if s not in todo][:need - len(todo)]
    if extra:
        print(f"  bank is low, bringing back {len(extra)} older post(s) so no day is missed")
    return todo + extra

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
    r = requests.post(f"{API}/upload_photos", headers={**HEAD(), "Idempotency-Key": show["id"] + "-" + when_local.strftime("%Y%m%d%H%M")},
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


# ---------- never double: clear anything already sitting in this slot ----------
def clear_slot(when_local):
    """Cancel any photo post already queued for this profile at this exact time,
    so a re-run replaces the week instead of doubling it."""
    try:
        r = requests.get(f"{API}/uploadposts/schedule", headers=HEAD(), timeout=60)
        jobs = r.json()
        if isinstance(jobs, dict):
            jobs = jobs.get("scheduled_posts") or jobs.get("jobs") or jobs.get("data") or []
    except Exception as e:
        print("  couldn't read the queue, carrying on:", e)
        return
    user = os.environ["UPLOAD_POST_USER"].lower()
    stamp = when_local.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M")
    for j in jobs:
        try:
            dt = datetime.fromisoformat(str(j.get("scheduled_date") or "").replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ZoneInfo("UTC"))
            same = dt.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M") == stamp
        except Exception:
            same = False
        if same and str(j.get("profile_username", "")).lower() == user and j.get("post_type") == "photo":
            requests.delete(f"{API}/uploadposts/schedule/{j['job_id']}", headers=HEAD(), timeout=60)
            print(f"  replaced old post at {when_local:%a %d %b %H:%M}: {str(j.get('title'))[:50]}")


def pick(todo, stream, when_local):
    """NeuroFusion picks the kind planned for that weekday; everything else goes in order."""
    if not stream.get("mix"):
        return todo.pop(0)
    want = stream["mix"][when_local.weekday()]
    for pool in ([s for s in todo if kind_of(s) == want],
                 [s for s in todo if kind_of(s) != "general"],
                 todo):
        if pool:
            chosen = pool[0]             # take it before removing (the last pool IS todo)
            todo.remove(chosen)
            return chosen


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
        for _ in range(REFILL_ROUNDS):
            if not refill(stream, bank, posted):
                break
            save(stream["bank"], bank)

        todo = [s for s in bank["slideshows"] if s["id"] not in posted and valid_show(s, bank, stream)]
        if not TEST_MODE:
            slots_left = sum(1 for day in range(DAYS_AHEAD)
                             if (now + timedelta(days=day)).replace(hour=stream["hour"], minute=stream["minute"],
                                                                    second=0, microsecond=0) > now + timedelta(minutes=10))
            todo = recycle(bank, state["posted"], todo, slots_left)
            todo = [s for s in todo if valid_show(s, bank, stream)]
        if not todo:
            print("  nothing left to post; add ANTHROPIC_API_KEY so it can write more")
            continue

        if TEST_MODE:
            when = now + timedelta(minutes=15)
            schedule_one(pick(todo, stream, when), bank, stream, when)
            continue

        for day in range(DAYS_AHEAD):
            when = (now + timedelta(days=day)).replace(hour=stream["hour"], minute=stream["minute"],
                                                       second=0, microsecond=0)
            if when <= now + timedelta(minutes=10):
                continue                                   # that slot has already gone today
            if not todo:
                print("  bank ran dry before the week was filled")
                break
            show = pick(todo, stream, when)
            clear_slot(when)
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
