"""
MuAPI AI Clipping ComfyUI Nodes
=================================
Turn a long-form video into N viral-ready short clips inside ComfyUI.

Single managed API call — transcription, virality ranking, dedupe, and
face-tracked auto-crop all run server-side. No local Whisper, no local LLM.

  AiClipping            — POST /api/v1/ai-clipping
  AiClippingPickClip    — pick a specific rank from the returned list
  AiClippingApiKey      — store your muapi.ai key once and wire to all nodes

Auth:    x-api-key header
Polling: GET  /api/v1/predictions/{request_id}/result
Upload:  POST /api/v1/upload_file
"""

import io
import json
import os
import time

import numpy as np
import requests
import torch
from PIL import Image

BASE_URL = "https://api.muapi.ai/api/v1"
POLL_INTERVAL = 10
MAX_WAIT = 1800

ASPECT_RATIOS = ["9:16", "1:1", "4:5"]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _load_api_key(api_key_input):
    """Return api_key_input if set, otherwise fall back to ~/.muapi/config.json."""
    if api_key_input and api_key_input.strip():
        return api_key_input.strip()
    config_path = os.path.expanduser("~/.muapi/config.json")
    if os.path.isfile(config_path):
        try:
            with open(config_path) as f:
                key = json.load(f).get("api_key", "")
            if key:
                return key
        except Exception:
            pass
    raise RuntimeError(
        "No API key found. Either paste your key into the api_key field, "
        "or run `muapi auth configure --api-key YOUR_KEY` in a terminal."
    )


def _check(resp):
    if resp.status_code == 401:
        raise RuntimeError("Auth failed — check API key.")
    if resp.status_code == 402:
        raise RuntimeError("Insufficient credits — top up at muapi.ai")
    if resp.status_code == 429:
        raise RuntimeError("Rate limited — retry later.")
    if not resp.ok:
        print(f"[AI Clipping] API ERROR {resp.status_code}: {resp.text[:500]}")
        try:
            err = resp.json()
            raise RuntimeError(f"API {resp.status_code}: {err}")
        except Exception:
            raise RuntimeError(f"API {resp.status_code}: {resp.text[:300]}")


def _upload_video(api_key, file_path):
    if not os.path.isfile(file_path):
        raise RuntimeError(f"Video file not found: {file_path}")
    with open(file_path, "rb") as fh:
        resp = requests.post(
            f"{BASE_URL}/upload_file",
            headers={"x-api-key": api_key},
            files={"file": (os.path.basename(file_path), fh, "video/mp4")},
            timeout=600,
        )
    _check(resp)
    data = resp.json()
    url = data.get("url") or data.get("file_url") or data.get("output")
    if not url:
        raise RuntimeError(f"Upload missing URL: {data}")
    return str(url)


def _submit(api_key, endpoint, payload):
    resp = requests.post(
        f"{BASE_URL}/{endpoint}",
        headers={"x-api-key": api_key, "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    _check(resp)
    rid = resp.json().get("request_id")
    if not rid:
        raise RuntimeError(f"No request_id: {resp.json()}")
    return rid


def _poll(api_key, request_id):
    deadline = time.time() + MAX_WAIT
    while time.time() < deadline:
        resp = requests.get(
            f"{BASE_URL}/predictions/{request_id}/result",
            headers={"x-api-key": api_key},
            timeout=30,
        )
        _check(resp)
        data = resp.json()
        status = data.get("status")
        print(f"[AI Clipping] {status}  {request_id}")
        if status == "completed":
            return data
        if status == "failed":
            raise RuntimeError(f"Failed: {data.get('error', 'unknown')}")
        time.sleep(POLL_INTERVAL)
    raise RuntimeError(f"Timeout: {request_id}")


def _extract_clips(result):
    """Normalize the /ai-clipping response into a list of dicts.

    Tries to handle several shapes the backend has used:
      • {"shorts": [...]}                    — preferred (matches schema docs)
      • {"highlights": [...]}                — alternate naming
      • {"outputs": ["url1", "url2", ...]}   — bare URL list
      • {"output": [...]} / {"output": "u"}  — single field
    Each returned dict is guaranteed to have a `clip_url` key when one is
    available; metadata fields (title, score, hook_sentence, ...) pass through
    unmodified.
    """
    for k in ("shorts", "highlights", "clips"):
        if isinstance(result.get(k), list) and result[k]:
            clips = []
            for item in result[k]:
                if isinstance(item, dict):
                    if "clip_url" not in item:
                        item = {**item, "clip_url": item.get("url") or item.get("output") or ""}
                    clips.append(item)
                elif isinstance(item, str):
                    clips.append({"clip_url": item})
            if clips:
                return clips

    out = result.get("outputs") or result.get("output")
    if isinstance(out, list) and out:
        return [{"clip_url": str(u)} if not isinstance(u, dict) else u for u in out]
    if isinstance(out, str) and out:
        return [{"clip_url": out}]

    raise RuntimeError(f"No clips in response: {result}")


def _first_frame(video_url):
    try:
        import tempfile, cv2
        r = requests.get(video_url, timeout=180, stream=True)
        r.raise_for_status()
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            for chunk in r.iter_content(8192):
                if chunk:
                    tmp.write(chunk)
            path = tmp.name
        cap = cv2.VideoCapture(path)
        ret, frame = cap.read()
        cap.release()
        os.remove(path)
        if not ret:
            raise RuntimeError("no frame")
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        return torch.from_numpy(rgb).unsqueeze(0)
    except Exception as e:
        print(f"[AI Clipping] first frame failed: {e}")
        return torch.zeros(1, 64, 64, 3)


def _format_clip_summary(clips):
    lines = []
    for i, c in enumerate(clips):
        score = c.get("score", "?")
        start = c.get("start_time", "?")
        end = c.get("end_time", "?")
        title = c.get("title", "—")
        hook = c.get("hook_sentence", "")
        url = c.get("clip_url", "(coords-only)")
        lines.append(
            f"#{i+1}  score={score}  {start}s → {end}s\n"
            f"  title: {title}\n"
            f"  hook:  \"{hook}\"\n"
            f"  url:   {url}"
        )
    return "\n\n".join(lines)


# ── Nodes ──────────────────────────────────────────────────────────────────────

class AiClippingApiKey:
    """
    Store your MuAPI API key once and wire it to any AI Clipping node.
    Leave all node api_key fields empty — they auto-read from this node
    or from ~/.muapi/config.json (set via `muapi auth configure`).
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "api_key": ("STRING", {"multiline": False, "default": "",
                "tooltip": "Your muapi.ai API key. Get one at muapi.ai → Dashboard → API Keys"}),
        }}
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("api_key",)
    FUNCTION = "run"
    CATEGORY = "✂️ AI Clipping"

    def run(self, api_key):
        return (_load_api_key(api_key),)


class AiClipping:
    """
    AI Clipping — long-form video → N ranked viral-ready short clips
    -----------------------------------------------------------------
    Wraps muapi.ai's `/ai-clipping` endpoint. The server runs the full
    pipeline so ComfyUI doesn't have to:

      • Whisper transcription
      • Highlight ranking through a virality framework
        (hook / emotional peak / opinion bomb / revelation /
         conflict / quotable / story peak / practical value)
      • Overlap dedupe
      • Top-N selection
      • Face-tracked vertical auto-crop

    Each returned clip carries a viral score (0–100), an opening hook line,
    a one-sentence "why it works" reason, and a hosted MP4 URL.

    Endpoint: POST /api/v1/ai-clipping
    Aspect ratios: 9:16 | 1:1 | 4:5
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "video_url": ("STRING", {"multiline": False, "default": "",
                "tooltip": "URL of the source video (MP4 / MOV). Use `video_path` instead to upload a local file."}),
        }, "optional": {
            "video_path": ("STRING", {"multiline": False, "default": "",
                "tooltip": "Local file path — auto-uploaded to muapi if `video_url` is empty."}),
            "num_clips": ("INT", {"default": 3, "min": 1, "max": 20, "step": 1,
                "tooltip": "How many highlights to extract (server enforces a cap)."}),
            "aspect_ratio": (ASPECT_RATIOS, {"default": "9:16",
                "tooltip": "9:16 for Shorts / TikTok / Reels, 1:1 for IG feed, 4:5 portrait."}),
            "return_coordinates_only": ("BOOLEAN", {"default": False,
                "tooltip": "Return only the highlight time ranges, skip cropping (no clip_url)."}),
            "api_key": ("STRING", {"multiline": False, "default": ""}),
        }}
    RETURN_TYPES = ("STRING", "IMAGE", "STRING", "STRING", "INT")
    RETURN_NAMES = ("first_clip_url", "first_frame", "highlights_json", "request_id", "clip_count")
    FUNCTION = "run"
    CATEGORY = "✂️ AI Clipping"

    def run(self, video_url, video_path="", num_clips=3, aspect_ratio="9:16",
            return_coordinates_only=False, api_key=""):
        api_key = _load_api_key(api_key)

        url = (video_url or "").strip()
        if not url and video_path and video_path.strip():
            print(f"[AI Clipping] Uploading local file: {video_path.strip()}")
            url = _upload_video(api_key, video_path.strip())
        if not url:
            raise ValueError("Provide either `video_url` or `video_path`.")

        payload = {
            "video_url": url,
            "num_highlights": int(num_clips),
            "aspect_ratio": aspect_ratio,
            "return_coordinates_only": bool(return_coordinates_only),
        }
        print(f"[AI Clipping] Submitting (n={num_clips}, ratio={aspect_ratio}, coords_only={return_coordinates_only})...")
        rid = _submit(api_key, "ai-clipping", payload)
        result = _poll(api_key, rid)
        clips = _extract_clips(result)

        first_url = clips[0].get("clip_url", "") if clips else ""
        frame = _first_frame(first_url) if first_url and not return_coordinates_only else torch.zeros(1, 64, 64, 3)

        print(f"[AI Clipping] Done — {len(clips)} clip(s)")
        print(_format_clip_summary(clips))

        return (first_url, frame, json.dumps(clips, indent=2), rid, len(clips))


class AiClippingPickClip:
    """
    Pick the Nth clip from an `AiClipping` result.

    The main node returns the first clip's URL directly; use this node when
    you want to fan out and process clip #2, #3, … with their own Save Video
    nodes (or any downstream pipeline).

    `index` is 1-based to match the printed ranking (#1 = top-scoring clip).
    Out-of-range indices clamp to the available range; if no clip exists,
    the node returns empty strings and a 64×64 black image.
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "highlights_json": ("STRING", {"multiline": True, "default": "",
                "tooltip": "Pass `highlights_json` from the AI Clipping node here."}),
            "index": ("INT", {"default": 1, "min": 1, "max": 50, "step": 1,
                "tooltip": "1-based rank — #1 = top-scoring clip."}),
        }, "optional": {
            "load_first_frame": ("BOOLEAN", {"default": True,
                "tooltip": "If true, downloads the clip and returns its first frame as IMAGE."}),
        }}
    RETURN_TYPES = ("STRING", "IMAGE", "STRING", "STRING", "FLOAT", "FLOAT", "INT")
    RETURN_NAMES = ("clip_url", "first_frame", "title", "hook_sentence", "start_time", "end_time", "score")
    FUNCTION = "run"
    CATEGORY = "✂️ AI Clipping"

    def run(self, highlights_json, index, load_first_frame=True):
        try:
            clips = json.loads(highlights_json) if highlights_json.strip() else []
        except json.JSONDecodeError as e:
            raise ValueError(f"highlights_json is not valid JSON: {e}")
        if not isinstance(clips, list):
            raise ValueError("highlights_json must be a JSON array")
        if not clips:
            print("[AI Clipping Pick] no clips in input")
            return ("", torch.zeros(1, 64, 64, 3), "", "", 0.0, 0.0, 0)

        idx = max(1, min(int(index), len(clips))) - 1
        clip = clips[idx] if isinstance(clips[idx], dict) else {"clip_url": str(clips[idx])}

        url = clip.get("clip_url", "")
        frame = _first_frame(url) if (load_first_frame and url) else torch.zeros(1, 64, 64, 3)

        return (
            url,
            frame,
            clip.get("title", ""),
            clip.get("hook_sentence", ""),
            float(clip.get("start_time", 0.0) or 0.0),
            float(clip.get("end_time", 0.0) or 0.0),
            int(clip.get("score", 0) or 0),
        )


NODE_CLASS_MAPPINGS = {
    "AiClippingApiKey":   AiClippingApiKey,
    "AiClipping":         AiClipping,
    "AiClippingPickClip": AiClippingPickClip,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AiClippingApiKey":   "🔑 AI Clipping API Key",
    "AiClipping":         "✂️ AI Clipping",
    "AiClippingPickClip": "✂️ AI Clipping Pick Clip",
}
