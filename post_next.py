"""
@wealth.wave.fm posting agent (NeuroFusion + MeAffirmation).
The BRAND setting picks which one to post: neurofusion or meaffirmation.

Runs in the cloud on a timer (GitHub Actions). Each run it:
  1. Tops up the content bank if it's running low (writes new slideshows with Claude)
  2. Picks the next slideshow that hasn't been posted
  3. Renders the slides
  4. Posts them to TikTok as a photo slideshow via Upload-Post
  5. Records it as posted so it never repeats

Settings come from GitHub secrets, never from this file:
  UPLOAD_POST_API_KEY   your Upload-Post API key
  UPLOAD_POST_USER      the profile name you created in Upload-Post
  ANTHROPIC_API_KEY     optional - lets the agent write new slideshows itself
"""
import json, os, sys, glob, re
import requests
import engine

HERE = os.path.dirname(os.path.abspath(__file__))
BRAND = os.environ.get("BRAND", "neurofusion")
BANK = os.path.join(HERE, f"bank_{BRAND}.json")
STATE = os.path.join(HERE, f"state_{BRAND}.json")
BRIEF = os.path.join(HERE, f"brief_{BRAND}.txt")
REFILL_WHEN_LEFT = 5      # write more when this many or fewer are left
REFILL_COUNT = 10         # how many new slideshows to write each time
TEST_MODE = os.environ.get("TEST_MODE", "false").lower() == "true"


def load(path, default):
    return json.load(open(path)) if os.path.exists(path) else default


def save(path, data):
    json.dump(data, open(path, "w"), indent=1, ensure_ascii=False)


# ---------- 1. Refill the bank ----------
REFILL_PROMPT = """You write TikTok photo slideshows for the account @wealth.wave.fm.
Read the brand brief below carefully and follow every hard rule in it.

Write {n} NEW slideshows for this brand.

Style rules:
- Sell through information and curiosity. Each post gives one genuinely useful insight.
- No dashes of any kind in slide text or captions. Use commas and full stops only.
- Tone: direct, warm, confident.
- Each slideshow: 1 hook slide (max 12 words, curiosity driven), exactly 4 body slides
  (title max 4 words, text max 20 words), then a cta slide.
- Caption: 1 to 2 short sentences, may include 1 or 2 emojis. No hashtags (added automatically).
- Do not repeat these hooks already used: {used}

Return ONLY a JSON array, no other text, in this exact shape:
[{{"id": "short-kebab-id", "slides": [
  {{"type": "hook", "text": "..."}},
  {{"type": "body", "title": "...", "text": "..."}},
  {{"type": "body", "title": "...", "text": "..."}},
  {{"type": "body", "title": "...", "text": "..."}},
  {{"type": "body", "title": "...", "text": "..."}},
  {{"type": "cta"}}],
  "caption": "..."}}]

BRAND BRIEF:
{guide}
"""


def valid_show(s):
    try:
        sl = s["slides"]
        return (isinstance(s["id"], str) and isinstance(s["caption"], str)
                and len(sl) == 6 and sl[0]["type"] == "hook" and sl[-1]["type"] == "cta"
                and all(x["type"] == "body" and x["title"] and x["text"] for x in sl[1:5]))
    except Exception:
        return False


def refill(bank, posted):
    left = [s for s in bank["slideshows"] if s["id"] not in posted]
    if len(left) > REFILL_WHEN_LEFT:
        return False
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        print(f"Only {len(left)} slideshows left. Add ANTHROPIC_API_KEY to let the agent write more.")
        return False
    guide = open(BRIEF).read()
    used = ", ".join(s["slides"][0]["text"] for s in bank["slideshows"])
    prompt = REFILL_PROMPT.format(n=REFILL_COUNT, used=used, guide=guide)
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": "claude-sonnet-5", "max_tokens": 8000,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=300,
    )
    r.raise_for_status()
    text = "".join(b.get("text", "") for b in r.json()["content"])
    text = re.sub(r"```(json)?", "", text).strip()
    new = json.loads(text)
    existing = {s["id"] for s in bank["slideshows"]}
    added = 0
    for s in new:
        if not valid_show(s):
            continue
        base = re.sub(r"[^a-z0-9-]", "", s["id"].lower())[:40] or "post"
        num = len(bank["slideshows"]) + 1
        s["id"] = f"{BRAND[:2]}-{num:03d}-{base}"
        if s["id"] in existing:
            continue
        bank["slideshows"].append(s)
        existing.add(s["id"])
        added += 1
    print(f"Refill: wrote {added} new slideshows.")
    return added > 0


# ---------- 2-4. Pick, render, post ----------
def post(show, bank):
    folder = engine.render_show(show, bank["brand"])
    slides = sorted(glob.glob(os.path.join(folder, "slide_*.jpg")),
                    key=lambda p: int(re.findall(r"\d+", os.path.basename(p))[0]))
    hook = show["slides"][0]["text"]
    caption = show["caption"] + "\n\n" + " ".join(bank["brand"]["hashtags"])
    data = [
        ("user", os.environ["UPLOAD_POST_USER"]),
        ("platform[]", "tiktok"),
        ("title", hook[:90]),            # TikTok photo-post titles max out at 90 characters
        ("description", caption),
        ("auto_add_music", "true"),
        ("privacy_level", "SELF_ONLY" if TEST_MODE else "PUBLIC_TO_EVERYONE"),
    ]
    files = [("photos[]", (os.path.basename(p), open(p, "rb"), "image/jpeg")) for p in slides]
    r = requests.post(
        "https://api.upload-post.com/api/upload_photos",
        headers={"Authorization": "Apikey " + os.environ["UPLOAD_POST_API_KEY"],
                 "Idempotency-Key": show["id"] + ("-test" if TEST_MODE else "")},
        data=data, files=files, timeout=300,
    )
    print("Upload-Post replied:", r.status_code, r.text[:800])
    if r.status_code >= 300:
        raise SystemExit(f"Posting failed ({r.status_code}). Nothing marked as posted.")
    body = r.json()
    if body.get("success") is False:
        raise SystemExit("Upload-Post reported a failure. Nothing marked as posted.")
    if body.get("request_id"):
        wait_for_tiktok(body["request_id"])


def wait_for_tiktok(request_id):
    """Upload-Post finishes the TikTok hand-off in the background.
    Check back until it's done, so a rejected post shows as a failed run."""
    import time
    headers = {"Authorization": "Apikey " + os.environ["UPLOAD_POST_API_KEY"]}
    for attempt in range(24):                      # up to ~6 minutes
        time.sleep(15)
        try:
            s = requests.get("https://api.upload-post.com/api/uploadposts/status",
                             params={"request_id": request_id}, headers=headers, timeout=60)
        except requests.RequestException as e:
            print("Status check hiccup, retrying:", e)
            continue
        text = s.text
        low = text.lower().replace(" ", "")
        print(f"Status check {attempt + 1}:", s.status_code, text[:600])
        if any(k in low for k in ['"status":"failed"', '"status":"error"', '"success":false']):
            raise SystemExit("TikTok did not accept the post (details above). Nothing marked as posted.")
        if any(k in low for k in ['"status":"completed"', '"status":"success"', '"status":"published"',
                                  '"status":"done"', '"status":"finished"']):
            print("Confirmed: TikTok accepted the post.")
            return
    print("Still processing after 6 minutes. Check Upload-Post for the final result.")


def main():
    bank = load(BANK, None)
    state = load(STATE, {"posted": []})
    posted = set(state["posted"])

    if refill(bank, posted):
        save(BANK, bank)

    todo = [s for s in bank["slideshows"] if s["id"] not in posted]
    if not todo:
        print("Nothing left to post. Add ANTHROPIC_API_KEY so the agent can write more.")
        return
    show = todo[0]
    print(f"[{BRAND}] " + ("TEST RUN (only you will see it): " if TEST_MODE else "Posting: ") + show["id"])
    post(show, bank)

    if not TEST_MODE:
        state["posted"].append(show["id"])
        save(STATE, state)
    print(f"Done. {len(todo) - (0 if TEST_MODE else 1)} slideshows left in the bank.")


if __name__ == "__main__":
    main()
