"""Shared helpers for the dropshipping video agent scripts.

Folder layout (ROOT = the folder that contains this `agent` folder):
    ROOT/input/                      source videos you drop in
    ROOT/jobs/<job>/                 working files per source video (manifest, frames, audio, prompts)
    ROOT/clips/hooks|showcases|payoffs/   cut clips + Higgsfield versions
    ROOT/videos/                     finished videos
    ROOT/references/product/         photos of the product (sent to Higgsfield so it stays identical)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent
ROOT = AGENT_DIR.parent


def load_config() -> dict:
    with open(AGENT_DIR / "config.json", encoding="utf-8") as f:
        cfg = json.load(f)
    # Optional overrides for folders (absolute or relative to ROOT)
    return cfg


CFG = load_config()


def folder(key: str) -> Path:
    """Resolve a configured folder (relative paths are relative to ROOT) and create it."""
    p = Path(CFG["folders"][key])
    if not p.is_absolute():
        p = ROOT / p
    p.mkdir(parents=True, exist_ok=True)
    return p


def category_dir(category: str) -> Path:
    p = folder("clips") / category
    p.mkdir(parents=True, exist_ok=True)
    return p


def job_dir(job: str) -> Path:
    p = folder("jobs") / job
    if not p.exists():
        sys.exit(f"Job '{job}' not found in {folder('jobs')}. Run split.py first.")
    return p


def slug(text: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return s[:40] or "video"


def need(tool: str) -> str:
    path = shutil.which(tool)
    if not path:
        sys.exit(
            f"'{tool}' was not found on PATH. Install FFmpeg (Windows: `winget install Gyan.FFmpeg`), "
            "then open a NEW terminal and try again."
        )
    return path


def run(cmd: list, capture: bool = False) -> subprocess.CompletedProcess:
    cmd = [str(c) for c in cmd]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        tail = (res.stderr or "")[-1500:]
        sys.exit(f"Command failed: {' '.join(cmd[:6])} ...\n{tail}")
    return res


def ffmpeg(*args) -> subprocess.CompletedProcess:
    return run([need("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", *args])


def probe(path: Path) -> dict:
    res = run([need("ffprobe"), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)])
    data = json.loads(res.stdout)
    v = next((s for s in data["streams"] if s.get("codec_type") == "video"), None)
    a = next((s for s in data["streams"] if s.get("codec_type") == "audio"), None)
    if v is None:
        sys.exit(f"No video stream in {path}")
    num, den = (v.get("avg_frame_rate") or "30/1").split("/")
    fps = float(num) / float(den) if float(den) else 30.0
    duration = float(data["format"].get("duration") or v.get("duration") or 0)
    # Handle rotated phone videos
    w, h = int(v["width"]), int(v["height"])
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(sd["rotation"])
    if abs(rot) in (90, 270):
        w, h = h, w
    return {"duration": duration, "width": w, "height": h, "fps": round(fps, 3), "has_audio": a is not None}


def read_manifest(job: str) -> dict:
    with open(job_dir(job) / "manifest.json", encoding="utf-8") as f:
        return json.load(f)


def write_manifest(job: str, manifest: dict) -> None:
    path = job_dir(job) / "manifest.json"
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def rel(p: Path | str) -> str:
    """Path relative to ROOT, with forward slashes, for storing in the manifest."""
    p = Path(p)
    try:
        return p.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def absp(p: str) -> Path:
    q = Path(p)
    return q if q.is_absolute() else ROOT / q
