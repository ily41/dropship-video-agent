"""Step 1 - cut a source video into clips at every scene change.

Usage:
    python agent/split.py input/my_video.mp4
    python agent/split.py input/my_video.mp4 --threshold 0.25      # more sensitive (more cuts)
    python agent/split.py input/my_video.mp4 --cuts 2.4,5.1,9.8     # use these exact cut times (seconds)
    python agent/split.py input/my_video.mp4 --job my-name --force  # redo an existing job

Creates jobs/<job>/ with:
    manifest.json          list of segments (start, end, files) - the single source of truth
    segments/segNN.mp4     each cut clip (still unlabelled)
    frames/segNN_sheet.jpg 4-frame contact sheet per clip (for the agent to look at)
    frames/segNN_first.jpg full-res first frame (reference image for Higgsfield)
    original_audio.m4a     audio of the whole source video (used in the final edit)
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

from PIL import Image

from common import CFG, ffmpeg, folder, need, probe, rel, run, slug, write_manifest


def detect_cuts(src: Path, threshold: float) -> list[float]:
    res = run([
        need("ffmpeg"), "-hide_banner", "-i", str(src),
        "-filter:v", f"select='gt(scene,{threshold})',showinfo",
        "-an", "-f", "null", "-",
    ])
    return sorted({round(float(t), 3) for t in re.findall(r"pts_time:([0-9.]+)", res.stderr)})


def build_segments(cuts: list[float], duration: float, min_len: float) -> list[tuple[float, float]]:
    points = [0.0] + [c for c in cuts if 0 < c < duration] + [duration]
    segs: list[list[float]] = []
    for a, b in zip(points, points[1:]):
        if segs and (b - a) < min_len:
            segs[-1][1] = b          # too short -> glue onto the previous clip
        else:
            segs.append([a, b])
    if len(segs) > 1 and (segs[0][1] - segs[0][0]) < min_len:
        segs[1][0] = segs[0][0]      # very short first clip -> glue onto the next one
        segs.pop(0)
    return [(round(a, 3), round(b, 3)) for a, b in segs]


def contact_sheet(clip: Path, dur: float, out: Path, n: int = 4) -> None:
    tmp = out.parent / f"_{out.stem}"
    tmp.mkdir(exist_ok=True)
    frames = []
    for i in range(n):
        t = max(0.0, min(dur - 0.05, dur * (i + 0.5) / n))
        f = tmp / f"{i}.jpg"
        ffmpeg("-ss", f"{t:.3f}", "-i", clip, "-frames:v", "1", "-vf", "scale=360:-2", "-q:v", "3", f)
        if f.exists():
            frames.append(Image.open(f).convert("RGB"))
    if frames:
        w, h = frames[0].size
        sheet = Image.new("RGB", (w * len(frames) + 8 * (len(frames) - 1), h), "white")
        for i, im in enumerate(frames):
            sheet.paste(im.resize((w, h)), (i * (w + 8), 0))
        sheet.save(out, quality=88)
    shutil.rmtree(tmp, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--job", help="job name (default: from file name)")
    ap.add_argument("--threshold", type=float, default=CFG["split"]["scene_threshold"])
    ap.add_argument("--min", type=float, default=CFG["split"]["min_clip_seconds"], help="min clip seconds")
    ap.add_argument("--cuts", help="comma separated cut times in seconds (skips auto detection)")
    ap.add_argument("--force", action="store_true", help="overwrite an existing job")
    a = ap.parse_args()

    src = Path(a.video).resolve()
    if not src.exists():
        sys.exit(f"File not found: {src}")
    job = slug(a.job or src.stem)
    jdir = folder("jobs") / job
    if jdir.exists():
        if not a.force:
            sys.exit(f"Job '{job}' already exists ({jdir}). Use --force to redo it, or --job to pick another name.")
        shutil.rmtree(jdir)
    (jdir / "segments").mkdir(parents=True)
    (jdir / "frames").mkdir()
    (jdir / "prompts").mkdir()

    info = probe(src)
    cuts = [float(x) for x in a.cuts.split(",")] if a.cuts else detect_cuts(src, a.threshold)
    segs = build_segments(cuts, info["duration"], a.min)

    audio = None
    if info["has_audio"]:
        audio = jdir / "original_audio.m4a"
        ffmpeg("-i", src, "-vn", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2", audio)

    segments = []
    for i, (s, e) in enumerate(segs, 1):
        sid = f"seg{i:02d}"
        clip = jdir / "segments" / f"{sid}.mp4"
        dur = e - s
        # Re-encode so every cut is frame-accurate (stream copy would snap to keyframes).
        ffmpeg("-ss", f"{s:.3f}", "-i", src, "-t", f"{dur:.3f}",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", clip)
        first = jdir / "frames" / f"{sid}_first.jpg"
        ffmpeg("-ss", f"{min(0.08, dur / 4):.3f}", "-i", clip, "-frames:v", "1", "-q:v", "2", first)
        sheet = jdir / "frames" / f"{sid}_sheet.jpg"
        contact_sheet(clip, dur, sheet)
        segments.append({
            "id": sid, "start": s, "end": e, "duration": round(dur, 3),
            "segment_file": rel(clip), "sheet": rel(sheet), "first_frame": rel(first),
            "category": None, "clip_file": None, "prompt_file": None,
            "higgsfield": {}, "generated_file": None,
        })

    manifest = {
        "job": job, "source": str(src), "source_info": info,
        "original_audio": rel(audio) if audio else None,
        "cut_method": "manual" if a.cuts else f"scene>{a.threshold}",
        "hook_text": None, "segments": segments,
    }
    jdir.mkdir(exist_ok=True)
    write_manifest(job, manifest)

    print(f"JOB: {job}")
    print(f"source: {info['width']}x{info['height']} {info['fps']}fps {info['duration']:.2f}s audio={info['has_audio']}")
    for sg in segments:
        print(f"  {sg['id']}  {sg['start']:7.2f}s -> {sg['end']:7.2f}s  ({sg['duration']:.2f}s)  sheet: {sg['sheet']}")
    print("Next: look at each contact sheet, then label clips with organize.py")


if __name__ == "__main__":
    main()
