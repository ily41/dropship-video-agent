"""Check the hook text inside a saved CapCut draft. Run it after EVERY CapCut merge.

Usage:
    python agent/check_capcut_text.py "<path to the draft folder>"
    python agent/check_capcut_text.py "<draft folder>" --size 13 --max-line 20

    python agent/check_capcut_text.py "<draft folder>" --fix   # repair sizes / line breaks, then check

Fails (exit code 1) if any text:
  - has a font size other than --size (checks the material "font_size" AND every style "size")
  - has a line longer than --max-line characters, or contains a literal backslash-n instead of a real line break
  - does not run from the start to the end of the video
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

US = 1_000_000  # CapCut stores times in microseconds


def load(folder: Path) -> list[tuple[Path, dict]]:
    out = []
    for name in ("draft_content.json", "draft_info.json"):
        p = folder / name
        if p.exists():
            try:
                out.append((p, json.loads(p.read_text(encoding="utf-8"))))
            except json.JSONDecodeError:
                sys.exit(f"{p} is not readable JSON (encrypted?) - cannot check it.")
    if not out:
        sys.exit(f"No draft_content.json / draft_info.json in {folder}")
    return out


def check(path: Path, d: dict, size: float, max_line: int) -> list[str]:
    errs = []
    total = d.get("duration") or 0
    texts = {m.get("id"): m for m in d.get("materials", {}).get("texts", [])}
    used = set()
    for track in d.get("tracks", []):
        if track.get("type") != "text":
            continue
        for seg in track.get("segments", []):
            mid = seg.get("material_id")
            used.add(mid)
            m = texts.get(mid)
            if not m:
                errs.append(f"text segment points to missing material {mid}")
                continue
            tr = seg.get("target_timerange", {})
            start, dur = tr.get("start", 0), tr.get("duration", 0)
            # content is a JSON string with "text" and "styles"
            raw = m.get("content") or ""
            try:
                content = json.loads(raw) if raw.strip().startswith("{") else {"text": raw, "styles": []}
            except json.JSONDecodeError:
                content = {"text": raw, "styles": []}
            text = content.get("text", "")
            label = repr(text[:40])
            if "\\n" in text:
                errs.append(f"{label}: contains a literal backslash-n, not a real line break")
            lines = text.split("\n")
            if len(lines) < 2 and len(text) > max_line:
                errs.append(f"{label}: one line of {len(text)} chars - needs line breaks")
            for ln in lines:
                if len(ln) > max_line:
                    errs.append(f"{label}: line '{ln}' is {len(ln)} chars (max {max_line})")
            fs = m.get("font_size")
            if fs is not None and abs(float(fs) - size) > 0.01:
                errs.append(f"{label}: material font_size = {fs}, expected {size}")
            for st in content.get("styles", []):
                if "size" in st and abs(float(st["size"]) - size) > 0.01:
                    errs.append(f"{label}: style size = {st['size']}, expected {size}")
            if start > US // 30:
                errs.append(f"{label}: starts at {start / US:.2f}s, should start at 0s")
            if total and start + dur < total - US // 30:
                errs.append(f"{label}: ends at {(start + dur) / US:.2f}s, video ends at {total / US:.2f}s - "
                            "text must last the whole video")
            print(f"  {path.name}: {label} size={fs} lines={len(lines)} "
                  f"{start / US:.2f}s-{(start + dur) / US:.2f}s (video {total / US:.2f}s)")
    if not used:
        errs.append("no text track found")
    # render_index clashes between tracks
    seen = {}
    for track in d.get("tracks", []):
        if track.get("type") == "audio":  # audio has no layer order on screen
            continue
        for seg in track.get("segments", []):
            ri = seg.get("render_index")
            if ri is None:
                continue
            if ri in seen and seen[ri] != track.get("id"):
                errs.append(f"render_index {ri} is shared by two tracks - layer order may break")
                break
            seen[ri] = track.get("id")
    return errs


def fix(path: Path, d: dict, size: float) -> int:
    """Make the material font_size and every style size equal to `size`; turn literal \\n into real breaks."""
    changed = 0
    for m in d.get("materials", {}).get("texts", []):
        if m.get("font_size") is not None and abs(float(m["font_size"]) - size) > 0.01:
            m["font_size"] = size
            changed += 1
        raw = m.get("content") or ""
        if raw.strip().startswith("{"):
            c = json.loads(raw)
            if "\\n" in c.get("text", ""):
                c["text"] = c["text"].replace("\\n", "\n")
                changed += 1
            for st in c.get("styles", []):
                if "size" in st and abs(float(st["size"]) - size) > 0.01:
                    st["size"] = size
                    changed += 1
            m["content"] = json.dumps(c, ensure_ascii=False, separators=(",", ":"))
    if changed:
        bak = path.with_suffix(path.suffix + ".before-textfix")
        if not bak.exists():
            bak.write_bytes(path.read_bytes())
        path.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return changed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("draft_folder")
    ap.add_argument("--size", type=float, default=13)
    ap.add_argument("--max-line", type=int, default=20)
    ap.add_argument("--fix", action="store_true",
                    help="set text sizes to --size and fix literal \\n (backs up the file first). CapCut must be closed.")
    a = ap.parse_args()
    if a.fix:
        for path, d in load(Path(a.draft_folder)):
            print(f"  {path.name}: {fix(path, d, a.size)} value(s) fixed")
    errors = []
    for path, d in load(Path(a.draft_folder)):
        errors += [f"{path.name}: {e}" for e in check(path, d, a.size, a.max_line)]
    if errors:
        print("TEXT CHECK FAILED:")
        for e in dict.fromkeys(errors):
            print("  -", e)
        sys.exit(1)
    print("TEXT CHECK OK")


if __name__ == "__main__":
    main()
