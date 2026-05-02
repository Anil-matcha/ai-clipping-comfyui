# AI Clipping ComfyUI Nodes — Open-Source Opus Clip Alternative

> **A free, open-source [Opus Clip](https://www.opus.pro) alternative for [ComfyUI](https://github.com/comfyanonymous/ComfyUI).**
> Turn long-form videos, podcasts, interviews, lectures, and livestreams into ranked viral-ready short clips for **YouTube Shorts**, **TikTok**, and **Instagram Reels** — directly inside your ComfyUI workflow.
> Single managed API call: transcription, virality ranking, dedupe, and face-tracked auto-crop all run server-side via [muapi.ai](https://muapi.ai). No local Whisper, no local LLM, no GPU.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![ComfyUI](https://img.shields.io/badge/ComfyUI-Custom%20Node-blue)](https://github.com/comfyanonymous/ComfyUI)
[![Opus Clip Alternative](https://img.shields.io/badge/Opus%20Clip-Alternative-orange)](#why-this-vs-opus-clip-klap-vizard)

> Searching for an Opus Clip alternative, a Klap.app alternative, or a Vizard / 2short.ai alternative that you can run inside ComfyUI? You're in the right place. This pack ships AI clipping, AI highlight extraction, automatic vertical reframing, face tracking, and viral-clip ranking — all as native ComfyUI nodes.

---

## Why This vs. Opus Clip / Klap / Vizard?

| | This (AI Clipping nodes) | Opus Clip / Klap / Vizard |
|---|---|---|
| Native ComfyUI integration | ✅ — clip, then chain into upscale / lipsync / VHS / etc. | ❌ — closed web app |
| Pricing | Pay-as-you-go via muapi.ai (no subscription) | Monthly subscription tiers |
| Self-hostable / scriptable | ✅ — open-source nodes + open API | ❌ |
| Aspect ratios | 9:16 / 1:1 / 4:5 | 9:16 / 1:1 / 4:5 |
| Face-tracked vertical crop | ✅ | ✅ |
| Viral-score per clip | ✅ (0–100 + hook line + reason) | ✅ |
| Coordinates-only mode | ✅ — render with your own ffmpeg / VHS pipeline | ❌ |

If you're shipping shorts at scale and want clipping to be one node in a bigger ComfyUI graph (intro/outro overlays, watermark removal, AI b-roll, captions, lipsync, etc.), this is the cleanest path.

---

## What is AI Clipping?

AI Clipping converts a long-form video (podcast, interview, lecture, vlog, livestream, …) into ranked short-form clips suitable for TikTok / Reels / YouTube Shorts. The server handles the entire pipeline:

- **Whisper transcription** — audio → timestamped segments
- **Highlight ranking** through a virality framework — hook moments, emotional peaks, opinion bombs, revelation moments, conflict, quotable lines, story peaks, practical value
- **Overlap dedupe** — collapses near-duplicate candidates by score
- **Top-N selection** — keeps the highest-scoring N
- **Face-tracked vertical auto-crop** — renders each clip at the requested aspect ratio

Each clip ships with a **viral score (0–100)**, an **opening hook line**, and a one-sentence **"why it works"** reason — all surfaced as a JSON output you can pass to downstream nodes.

Reference implementation (open source): [SamurAIGPT/AI-Youtube-Shorts-Generator](https://github.com/SamurAIGPT/AI-Youtube-Shorts-Generator)
Underlying API: https://muapi.ai/playground/ai-clipping

---

## Nodes

| Node | Description |
|------|-------------|
| 🔑 AI Clipping API Key | Set your key once — wire to all nodes |
| ✂️ AI Clipping | Long video → ranked vertical short clips (full pipeline) |
| ✂️ AI Clipping Pick Clip | Pick the Nth clip from the highlights JSON for fan-out |
| ✂️ AI Clipping Save Video | Download a clip URL → disk + ComfyUI IMAGE frames |

---

## Installation

### Via ComfyUI Manager (recommended)
1. Open **ComfyUI Manager** → **Install via Git URL**
2. Paste: `https://github.com/Anil-matcha/ai-clipping-comfyui`
3. Restart ComfyUI

### Manual
```bash
cd ComfyUI/custom_nodes
git clone https://github.com/Anil-matcha/ai-clipping-comfyui
pip install -r ai-clipping-comfyui/requirements.txt
```

---

## Quick Start

1. Sign up at [muapi.ai](https://muapi.ai) and grab a key from **Dashboard → API Keys → Create Key**.
2. Right-click the ComfyUI canvas → **Add Node** → **✂️ AI Clipping**.
3. Add a **🔑 AI Clipping API Key** node, paste your key, and wire its output into the AI Clipping node.
4. Paste a hosted video URL (or a local file path), set `num_clips`, hit **Queue Prompt**.

> **Tip:** If you use the [MuAPI CLI](https://github.com/SamurAIGPT/muapi-cli), run `muapi auth configure --api-key YOUR_KEY` once and every node will pick the key up automatically — no need to paste it anywhere.

---

## Node Reference

### 🔑 AI Clipping API Key

Set your muapi.ai API key once and wire the output to all AI Clipping nodes. Alternatively, leave every `api_key` field blank — nodes auto-read from `~/.muapi/config.json` if you've authenticated via the CLI.

---

### ✂️ AI Clipping

Run the full clipping pipeline server-side and return a ranked list of vertical short clips.

| Field | Values | Default | Notes |
|-------|--------|---------|-------|
| `video_url` | URL string | — | Hosted MP4 / MOV URL of the source video |
| `video_path` | Local path | — | Alternative to `video_url` — file is auto-uploaded to muapi |
| `num_clips` | 1 – 20 | `3` | How many highlights to extract |
| `aspect_ratio` | `9:16` / `1:1` / `4:5` | `9:16` | `9:16` for Shorts/TikTok/Reels, `1:1` for IG Feed, `4:5` portrait |
| `return_coordinates_only` | bool | `false` | Return only highlight time ranges, skip cropping |
| `api_key` | Optional — leave blank if using the API Key node or CLI config | — | |

Provide **either** `video_url` **or** `video_path` (not both). When `return_coordinates_only=true`, the response carries `start_time`/`end_time` per highlight but no `clip_url` — render the clips yourself with ffmpeg or any downstream node.

**Outputs**
- `first_clip_url` (STRING) — URL of the top-ranked clip (most useful to pipe directly into Save Video)
- `first_frame` (IMAGE) — first frame of the top clip, ready for previews / further processing
- `highlights_json` (STRING) — full JSON array of every clip, with metadata (`title`, `score`, `hook_sentence`, `virality_reason`, `start_time`, `end_time`, `clip_url`). Pass this to **Pick Clip** to fan out.
- `request_id` (STRING) — for re-fetching the result later
- `clip_count` (INT) — how many clips actually came back

**Endpoint:** `POST /api/v1/ai-clipping`

---

### ✂️ AI Clipping Pick Clip

Pick the Nth clip from the `highlights_json` returned by the main node. Use this to fan out — e.g. send clip #1 to one Save Video, clip #2 to another, etc.

| Field | Values | Default | Notes |
|-------|--------|---------|-------|
| `highlights_json` | JSON array | — | Wire from `AI Clipping` → `highlights_json` |
| `index` | 1 – 50 | `1` | 1-based rank (#1 = top-scoring clip) |
| `load_first_frame` | bool | `true` | Download the clip and return its first frame |

**Outputs:** `clip_url` · `first_frame` (IMAGE) · `title` · `hook_sentence` · `start_time` · `end_time` · `score`

Out-of-range indices clamp to the available range. If the input list is empty, returns blanks.

---

### ✂️ AI Clipping Save Video

Downloads a clip URL to ComfyUI's output folder and returns all frames as an IMAGE tensor for use with other nodes (preview, VHS, upscale, etc.).

| Field | Description |
|-------|-------------|
| `video_url` | URL returned by AI Clipping or Pick Clip |
| `save_subfolder` | Subfolder under `ComfyUI/output/` (default: `ai_clipping`) |
| `filename_prefix` | Filename prefix (default: `clip`) |
| `frame_load_cap` | Optional max frames returned (`0` = all) |
| `skip_first_frames` | Skip N frames from the start |
| `select_every_nth` | Stride for frame selection |

**Outputs:** `frames` (IMAGE) · `filepath` (STRING) · `frame_count` (INT)

---

## Example Workflows

Load `AiClipping_Example.json` via **File → Load** in ComfyUI.

| File | Description |
|------|-------------|
| `AiClipping_Example.json` | Long video URL → top clip → save to disk + preview frame |
| `AiClipping_FanOut_Example.json` | Same pipeline plus Pick Clip nodes for #2 and #3 saved separately |

**Single best clip:**
```
[🔑 API Key] ───────────────────────────────────────────────────────┐
                                                                     ↓
(video URL) → [✂️ AI Clipping] → first_clip_url → [✂️ Save Video] → frames → [Preview Image]
```

**Fan-out — pick clips #1, #2, #3 separately:**
```
                                            ┌→ [✂️ Pick Clip #1] → [✂️ Save Video]
[✂️ AI Clipping] → highlights_json ─────────┼→ [✂️ Pick Clip #2] → [✂️ Save Video]
                                            └→ [✂️ Pick Clip #3] → [✂️ Save Video]
```

---

## Aspect Ratio Picker

| Platform | Ratio | Sweet-spot duration |
|:---|:---|:---|
| TikTok / Reels / YouTube Shorts | `9:16` | 30–75s |
| Instagram Feed | `1:1` | 15–45s |
| Pinterest / portrait | `4:5` | 30–60s |

Default to `9:16` unless the platform is specified.

---

## Output Schema (`highlights_json`)

```json
[
  {
    "title": "The one mistake that cost me $50K",
    "start_time": 124.3,
    "end_time": 187.6,
    "score": 92,
    "hook_sentence": "Nobody talks about this, but it killed my first startup...",
    "virality_reason": "Opens with a number + regret, peaks on a contrarian lesson",
    "clip_url": "https://.../short_1.mp4"
  }
]
```

When `return_coordinates_only=true`, each entry has `start_time`/`end_time` but no `clip_url` — render locally.

---

## API

This node pack uses the **muapi.ai** API under the hood:

- **AI Clipping:**  `POST https://api.muapi.ai/api/v1/ai-clipping`
- **Poll:**        `GET  https://api.muapi.ai/api/v1/predictions/{request_id}/result`
- **Upload:**      `POST https://api.muapi.ai/api/v1/upload_file`

Authentication is a single `x-api-key` header — no session tokens required.

The submit-then-poll flow:

```
POST /api/v1/ai-clipping   →  { "request_id": "abc123" }
GET  /api/v1/predictions/abc123/result
                           →  { "status": "processing" }       (keep polling)
                           →  { "status": "completed",
                                "shorts": [ {...}, {...}, ... ] }
```

Status values: `queued`, `pending`, `processing`, `completed`, `failed`.

---

## Requirements

- Python ≥ 3.8
- `requests` ≥ 2.28 · `Pillow` ≥ 9.0 · `numpy` ≥ 1.23 · `torch` ≥ 2.0 · `opencv-python` ≥ 4.7

---

## Want More Models?

This repo is focused on AI Clipping only. If you need access to **100+ models** — Kling, Veo3, Flux, HiDream, GPT-image-1.5, Imagen4, Wan, lipsync, audio, image enhancement and more — check out the full MuAPI ComfyUI node pack:

**[SamurAIGPT/muapi-comfyui](https://github.com/SamurAIGPT/muapi-comfyui)** — ComfyUI nodes for every muapi.ai model in one place.

---

## License

MIT © 2026

---

<sub>**Keywords:** Opus Clip alternative, Opus Clip ComfyUI, Opus.pro alternative, Klap alternative, Klap.app alternative, Vizard alternative, 2short.ai alternative, free Opus Clip, open-source Opus Clip, AI video clipper, AI clipping, AI clipper for ComfyUI, ComfyUI shorts generator, ComfyUI TikTok generator, ComfyUI Reels generator, viral clip generator, podcast clipper, podcast to shorts, long video to shorts, video highlight extraction, AI highlight extractor, automatic vertical reframing, face-tracked vertical crop, autocrop video, viral score, hook detection, ComfyUI video editing, muapi.ai, YouTube Shorts maker, TikTok clip maker, Instagram Reels maker.</sub>

