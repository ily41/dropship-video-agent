"""Pad short clips to a minimum length by freezing the last frame (Higgsfield Wan 3.0 needs >= 2 s).

Usage:
    python agent/pad.py <job>              # pads every labelled clip shorter than 2 s
    python agent/pad.py <job> --min 2.0
Writes jobs/<job>/padded/segNN.mp4 (clips that are long enough are copied unchanged).
The real movement stays at the start, so assemble.py / the CapCut merge cut it back to the
original length and the audio stays in sync.
"""
from __future__ import annotations

import argparse
import shutil

from common import absp, ffmpeg, job_dir, probe, read_manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("job")
    ap.add_argument("--min", type=float, default=2.0)
    a = ap.parse_args()
    m = read_manifest(a.job)
    out = job_dir(a.job) / "padded"
    out.mkdir(exist_ok=True)
    for s in m["segments"]:
        if s.get("category") == "skip":
            continue
        src = absp(s["segment_file"])
        dest = out / f"{s['id']}.mp4"
        have = probe(src)["duration"]
        if have >= a.min:
            shutil.copy2(src, dest)
            print(f"  {s['id']}: {have:.2f}s - ok, copied")
            continue
        extra = a.min - have + 0.05
        ffmpeg("-i", src, "-vf", f"tpad=stop_mode=clone:stop_duration={extra:.3f}", "-an",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p", dest)
        print(f"  {s['id']}: {have:.2f}s -> {probe(dest)['duration']:.2f}s (last frame frozen)")


if __name__ == "__main__":
    main()
