"""AI Clipping Video Saver — downloads a clip URL, saves to disk, returns frames."""

import os
import numpy as np
import requests
import torch

try:
    import folder_paths
except ImportError:
    class folder_paths:
        @staticmethod
        def get_output_directory():
            return os.path.join(os.path.expanduser("~"), "comfyui_output")


class AiClippingVideoSaver:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "video_url": ("STRING", {"multiline": False, "default": ""}),
            "save_subfolder": ("STRING", {"default": "ai_clipping"}),
            "filename_prefix": ("STRING", {"default": "clip"}),
        }, "optional": {
            "frame_load_cap": ("INT", {"default": 0, "min": 0, "max": 9999}),
            "skip_first_frames": ("INT", {"default": 0, "min": 0, "max": 500}),
            "select_every_nth": ("INT", {"default": 1, "min": 1, "max": 30}),
        }}
    RETURN_TYPES = ("IMAGE", "STRING", "INT")
    RETURN_NAMES = ("frames", "filepath", "frame_count")
    FUNCTION = "run"
    CATEGORY = "✂️ AI Clipping"
    OUTPUT_NODE = True

    def run(self, video_url, save_subfolder, filename_prefix,
            frame_load_cap=0, skip_first_frames=0, select_every_nth=1):
        if not video_url or not video_url.strip().startswith("http"):
            return self._err("Invalid URL")
        out_dir = os.path.join(folder_paths.get_output_directory(), save_subfolder)
        os.makedirs(out_dir, exist_ok=True)
        n = 1
        fp = os.path.join(out_dir, f"{filename_prefix}_{n:05d}.mp4")
        while os.path.exists(fp):
            n += 1
            fp = os.path.join(out_dir, f"{filename_prefix}_{n:05d}.mp4")
        try:
            print(f"[AI Clipping Saver] Downloading {video_url[:80]}...")
            r = requests.get(video_url, stream=True, timeout=300)
            r.raise_for_status()
            with open(fp, "wb") as fh:
                for chunk in r.iter_content(8192):
                    if chunk:
                        fh.write(chunk)
            frames, count = self._load(fp, frame_load_cap, skip_first_frames, select_every_nth)
            fname = os.path.basename(fp)
            preview = {"filename": fname, "subfolder": save_subfolder, "type": "output", "format": "video/mp4"}
            print(f"[AI Clipping Saver] Saved {fname} — {count} frames")
            return {"ui": {"gifs": [preview]}, "result": (frames, fp, count)}
        except Exception as e:
            return self._err(str(e))

    def _load(self, path, cap, skip, nth):
        try:
            import cv2
            frames, raw, loaded = [], 0, 0
            vc = cv2.VideoCapture(path)
            while True:
                ret, frame = vc.read()
                if not ret:
                    break
                if raw < skip:
                    raw += 1
                    continue
                if (raw - skip) % nth == 0:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
                    frames.append(rgb)
                    loaded += 1
                    if cap > 0 and loaded >= cap:
                        break
                raw += 1
            vc.release()
            if not frames:
                raise RuntimeError("No frames")
            return torch.from_numpy(np.stack(frames)), len(frames)
        except Exception as e:
            print(f"[AI Clipping Saver] frame load error: {e}")
            return torch.zeros(1, 64, 64, 3), 1

    def _err(self, msg):
        print(f"[AI Clipping Saver] ERROR: {msg}")
        return {"ui": {"text": [msg]}, "result": (torch.zeros(1, 64, 64, 3), "ERROR", 0)}


NODE_CLASS_MAPPINGS = {"AiClippingVideoSaver": AiClippingVideoSaver}
NODE_DISPLAY_NAME_MAPPINGS = {"AiClippingVideoSaver": "✂️ AI Clipping Save Video"}
