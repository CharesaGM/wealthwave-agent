# wealthwave-agent

**An autonomous Python agent that writes, designs, renders and publishes short-form social content every day, with no human in the loop.**

It runs two daily content streams for the [@wealth.wave.fm](https://www.tiktok.com/@wealth.wave.fm) TikTok account (*NeuroFusion™* and *MeAffirmation*). Once a week it plans, generates and schedules the next seven days of posts, and it has been running in production since 2026.

---

## What it does

Every Sunday morning a GitHub Actions workflow wakes up and:

1. **Checks the content bank.** If fewer unused slideshows are left than the week needs, it asks the **Claude API** to write a new batch. Each batch follows a brand brief and a weekly content mix (story / diagram / product / general), and the prompt lists every hook already used so nothing is repeated.
2. **Validates everything Claude writes.** Each slideshow must have exactly 6 slides (a hook, the body slides, then a CTA), and any containing banned or non-compliant terms (medical claims, trademarked names, etc.) are rejected, so only clean content ever reaches the bank.
3. **Picks the right post for each day.** NeuroFusion follows a planned weekday mix (e.g. Thursday = diagram) and falls back gracefully if a category runs dry. If the bank is still short, it brings back the posts used longest ago so no day is ever missed.
4. **Renders the slides** with a custom **Pillow** graphics engine: procedurally generated backgrounds (waveforms, orbs, interference patterns, spectrums, constellations, botanical and paper textures), glow effects, word-wrapped typography and labelled left-ear / right-ear frequency diagrams. There are 12 visual themes, and each post's look is chosen deterministically from its ID.
5. **Builds a video** for NeuroFusion posts. **ffmpeg** turns the slides into a 1080×1920 MP4 with a slow zoom and crossfades. Underneath it synthesises a **real stereo binaural beat** (e.g. 200 Hz left ear, 210 Hz right ear = a 10 Hz beat) over a low-passed brown-noise pad, matched to the frequencies shown on screen.
6. **Schedules every post** for its exact local time (Europe/London, so the clocks changing is handled automatically) through the Upload-Post REST API. Each request carries an **idempotency key**, and the agent first **clears anything already queued in the same slot**, so a re-run replaces the week instead of doubling it.
7. **Commits its own state** (the content bank plus a record of what has been posted) back to the repo, so the next run knows exactly where it left off.

## Architecture

```
            ┌──────────────────────── GitHub Actions (weekly cron) ────────────────────────┐
            │                                                                              │
 brief_*.txt ──► Claude API ──► validate ──► bank_*.json ──► pick for each day ──► engine.py │
 (brand rules)   (new posts)   (6 slides,    (content bank)  (weekday mix,        (Pillow    │
                               banned words)                  recycle if short)    slides +  │
                                                                                    ffmpeg   │
                                                                                    video)   │
            │                                                                        │     │
            │                state_*.json ◄── commit back to repo ◄── Upload-Post API ◄┘     │
            │               (what's posted)                          (scheduled, idempotent) │
            └──────────────────────────────────────────────────────────────────────────────┘
```

## Files

| File | Purpose |
|---|---|
| `schedule_week.py` | The weekly scheduler: refill → validate → pick → render → schedule → record |
| `engine.py` | Rendering engine: procedural backgrounds, typography, frequency diagrams, slide-to-video with a synthesised binaural audio track |
| `post_next.py` | The original single-post runner (post the next unused slideshow immediately), kept for one-off posts |
| `bank_*.json` | Content banks: brand settings plus every slideshow (hook, body slides, CTA, caption, hashtags) |
| `brief_*.txt` | Brand briefs given to Claude: tone, facts, what to say and what never to say |
| `state_*.json` | IDs of everything already posted, so nothing repeats |
| `.github/workflows/post.yml` | The weekly cron job, plus a manual "test run" that queues one private post 15 minutes out |

## Tech

**Python 3.12** · **Pillow** · **ffmpeg** (via `imageio-ffmpeg`) · **requests** · **Anthropic Claude API** · **Upload-Post REST API** · **GitHub Actions** (cron, secrets, manual dispatch with inputs, concurrency control)

## Running it

All credentials live in **GitHub Actions secrets**. None of them are in the code.

| Secret | What it is |
|---|---|
| `UPLOAD_POST_API_KEY` | Upload-Post API key |
| `UPLOAD_POST_USER` | The Upload-Post profile to post as |
| `ANTHROPIC_API_KEY` | Optional. Lets the agent write new content itself when the bank runs low |

- **Automatic:** runs every Sunday at 09:17 UTC and queues the next 7 days.
- **Test run:** Actions → *WealthWave FM weekly scheduler* → *Run workflow* with `test = true`. This queues **one private post** 15 minutes from now so you can check the output without anything going public.
- **Redo one stream:** set `only` to `neurofusion` or `meaffirmation`.

Locally:

```bash
pip install pillow requests imageio-ffmpeg
export UPLOAD_POST_API_KEY=... UPLOAD_POST_USER=... ANTHROPIC_API_KEY=...
TEST_MODE=true python schedule_week.py
```

(The workflow downloads the Poppins and Lora fonts into `fonts/` before running. Do the same locally for identical output.)

## Design decisions worth noting

- **Weekly batch over daily cron.** Scheduling a week ahead with exact timestamps means posts go out on time even if GitHub's cron runs late, and the whole upcoming week is visible in one calendar.
- **Safe to re-run.** Idempotency keys plus clearing each slot before posting to it mean a failed or repeated run never double-posts.
- **LLM output is never trusted blindly.** Structural checks and a banned-terms filter sit between Claude and the content bank.
- **Same architecture, many brands.** This repo is one of five agents built on the same pattern, each with its own brand, schedule and content bank.

---

Built by [Charesa Gayle-Mulhall](https://github.com/CharesaGM).
