"""Step 4 - build the final video: new clips in the original order + the ORIGINAL audio + a text hook.

Usage:
    python agent/assemble.py <job> --hook "Wait, this is actually a BAG?!"
    python agent/assemble.py <job> --hook "..." --use original      # preview with the original clips
    python agent/assemble.py <job> --hook "..." --show-for all      # keep the text for the whole video
    python agent/assemble.py <job> --hook "..." --style outline     # white text, black outline (no box)
    python agent/assemble.py <job> --preview-hook "..."             # only render the text overlay PNG to check it

Each clip is fitted to the exact length of the original clip it replaces, so the original
audio (voice-over / music / beat) stays in sync. Output: videos/<job>__<date-time>.mp4
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import textwrap
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from common import CFG, absp, ffmpeg, folder, job_dir, probe, read_manifest, rel, write_manifest

OUT = CFG["output"]
HT = CFG["hook_text"]


def pick_font(size: int) -> ImageFont.FreeTypeFont:
    own = sorted((Path(__file__).parent / "fonts").glob("*.[ot]tf"))  # drop your own font here
    for f in [*map(str, own), *HT["font_files"]]:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    print("  warning: none of the configured fonts exist - using Pillow's default font")
    return ImageFont.load_default(size=size)


def strip_emoji(text: str) -> str:
    out = "".join(ch for ch in text if ord(ch) < 0x2190 or 0x3000 <= ord(ch) < 0xFE00)
    return " ".join(out.split())


def render_hook(text: str, dest: Path, style: str) -> None:
    text = strip_emoji(text)
    W, H = OUT["width"], OUT["height"]
    size = int(HT["font_size"] * W / 1080)
    font = pick_font(size)
    lines = textwrap.wrap(text.strip(), width=HT["max_chars_per_line"]) or [""]
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    line_h = int(size * 1.28)
    pad_x, pad_y = int(size * 0.45), int(size * 0.16)
    y = int(H * HT["y_ratio"])
    for line in lines:
        l, t, r, b = d.textbbox((0, 0), line, font=font)
        tw = r - l
        x = (W - tw) // 2
        if style == "box":
            d.rounded_rectangle([x - pad_x, y - pad_y, x + tw + pad_x, y + line_h - pad_y],
                                radius=int(size * 0.28), fill=(255, 255, 255, 255))
            d.text((x - l, y + (line_h - (b - t)) // 2 - t - pad_y // 2), line, font=font, fill=(0, 0, 0, 255))
        else:
            d.text((x - l, y), line, font=font, fill=(255, 255, 255, 255),
                   stroke_width=max(4, int(size * HT.get("stroke_ratio", 0.11))), stroke_fill=(0, 0, 0, 255))
        y += line_h
    img.save(dest)


def fit_clip(src: Path, dur: float, dest: Path) -> None:
    """Scale/crop to the output frame, fix fps, and make the clip exactly `dur` seconds long."""
    W, H, FPS = OUT["width"], OUT["height"], OUT["fps"]
    have = probe(src)["duration"]
    speed = 1.0
    if OUT.get("fit") == "speed" and have > dur:
        speed = min(have / dur, OUT.get("max_speed", 1.6))
    vf = [f"setpts=PTS/{speed:.4f}" if speed != 1.0 else None,
          f"scale={W}:{H}:force_original_aspect_ratio=increase", f"crop={W}:{H}", "setsar=1",
          f"fps={FPS}", f"tpad=stop_mode=clone:stop_duration={dur:.3f}"]
    ffmpeg("-i", src, "-t", f"{dur:.3f}", "-vf", ",".join(v for v in vf if v), "-an",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", "-r", str(FPS), dest)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("job")
    ap.add_argument("--hook", help="text hook shown on screen")
    ap.add_argument("--use", choices=["auto", "generated", "original"], default="auto",
                    help="auto = Higgsfield clip when it exists, else the original clip")
    ap.add_argument("--show-for", default=str(HT["show_for"]), help='"hook", "all", or seconds')
    ap.add_argument("--style", choices=["box", "outline"], default=HT["style"])
    ap.add_argument("--out", help="output file name (without folder)")
    ap.add_argument("--preview-hook", metavar="TEXT", help="only render the hook overlay to jobs/<job>/hook_preview.png")
    a = ap.parse_args()

    jdir = job_dir(a.job)
    m = read_manifest(a.job)

    if a.preview_hook:
        render_hook(a.preview_hook, jdir / "hook_preview.png", a.style)
        print(f"Hook preview: {rel(jdir / 'hook_preview.png')}")
        return

    hook = a.hook or m.get("hook_text")
    segs = [s for s in m["segments"] if s.get("category") != "skip"]
    if not segs:
        sys.exit("No segments to assemble.")

    tmp = jdir / "_assemble"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()

    parts, used = [], []
    for i, s in enumerate(segs):
        gen = absp(s["generated_file"]) if s.get("generated_file") else None
        orig = absp(s.get("clip_file") or s["segment_file"])
        if a.use == "original":
            src = orig
        elif gen and gen.exists():
            src = gen
        elif a.use == "generated":
            sys.exit(f"{s['id']} has no Higgsfield clip yet (use --use auto to fall back to the original).")
        else:
            src = orig
            print(f"  {s['id']}: no Higgsfield clip - using the original")
        part = tmp / f"p{i:02d}.mp4"
        fit_clip(src, s["duration"], part)
        parts.append(part)
        used.append({"id": s["id"], "category": s["category"], "file": rel(src), "duration": s["duration"]})
    total = round(sum(s["duration"] for s in segs), 3)

    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    video_only = tmp / "video_only.mp4"
    ffmpeg("-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", video_only)

    # Audio: the original soundtrack, cut to the same clips that were kept.
    audio_args, audio_filter = [], None
    if m.get("original_audio"):
        audio_args = ["-i", absp(m["original_audio"])]
        kept_all = len(segs) == len(m["segments"])
        if not kept_all:
            chains = [f"[2:a]atrim={s['start']}:{s['end']},asetpts=PTS-STARTPTS[a{i}]" for i, s in enumerate(segs)]
            audio_filter = ";".join(chains) + ";" + "".join(f"[a{i}]" for i in range(len(segs))) + \
                f"concat=n={len(segs)}:v=0:a=1[aout]"
    else:
        print("  note: source video had no audio")

    # Text hook overlay
    if hook:
        overlay = tmp / "hook.png"
        render_hook(hook, overlay, a.style)
        if a.show_for == "all":
            until = total
        elif a.show_for == "hook":
            t, until = 0.0, 0.0
            for s in segs:
                if s["category"] != "hooks":
                    break
                t += s["duration"]
                until = t
            until = max(until, 2.5)
        else:
            until = float(a.show_for)
        until = min(until, total)
    else:
        overlay, until = tmp / "none.png", 0
        Image.new("RGBA", (OUT["width"], OUT["height"]), (0, 0, 0, 0)).save(overlay)

    out_dir = folder("videos")
    name = a.out or f"{a.job}__{datetime.now().strftime('%Y%m%d-%H%M')}.mp4"
    if not name.lower().endswith(".mp4"):
        name += ".mp4"
    out = out_dir / name
    clean = out.with_name(out.stem + "__CLEAN.mp4")

    def encode(ov: Path, show_until: float, dest: Path) -> None:
        fc = f"[0:v][1:v]overlay=0:0:enable='between(t,0,{show_until:.3f})'[v]"
        if audio_filter:
            fc += ";" + audio_filter
        args = ["-i", video_only, "-loop", "1", "-t", f"{total:.3f}", "-i", ov, *audio_args,
                "-filter_complex", fc, "-map", "[v]"]
        if audio_args:
            args += ["-map", "[aout]" if audio_filter else "2:a", "-c:a", "aac", "-b:a", "192k"]
        args += ["-t", f"{total:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", str(OUT["crf"]),
                 "-pix_fmt", "yuv420p", "-r", str(OUT["fps"]), "-movflags", "+faststart", dest]
        ffmpeg(*args)

    # 1) CLEAN version (no text) - this is the one to edit in CapCut on the iPhone
    blank = tmp / "blank.png"
    Image.new("RGBA", (OUT["width"], OUT["height"]), (0, 0, 0, 0)).save(blank)
    encode(blank, 0, clean)
    # 2) Preview version with the hook burned in (emojis can't be drawn on Windows, so they are left out)
    if hook:
        encode(overlay, until, out)
    # 3) Hook text WITH emojis, to copy-paste into CapCut on the iPhone
    if hook:
        out.with_name(out.stem + "__HOOK.txt").write_text(hook + "\n", encoding="utf-8")

    info = {"video": rel(out) if hook else None, "clean_video": rel(clean), "hook_text": hook,
            "hook_seconds": until, "duration": total,
            "made": datetime.now().isoformat(timespec="seconds"), "clips": used}
    out.with_suffix(".json").write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    m["hook_text"] = hook
    m.setdefault("exports", []).append(info)
    write_manifest(a.job, m)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"CLEAN (no text, for CapCut): {rel(clean)}")
    if hook:
        print(f"PREVIEW (text burned in, no emojis): {rel(out)}")
        print(f"HOOK TEXT (with emojis): {rel(out.with_name(out.stem + '__HOOK.txt'))}")
    print(f"DONE ({total:.2f}s, hook shown 0-{until:.1f}s)")


if __name__ == "__main__":
    main()
