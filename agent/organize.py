"""Step 2 - label each cut clip and copy it into its folder (hooks / showcases / payoffs).

Usage:
    python agent/organize.py <job> seg01=hooks seg02=showcases seg03=showcases seg04=payoffs
    python agent/organize.py <job> seg05=skip          # leave a clip out of everything
    python agent/organize.py <job> --show               # print current labels

Short labels also work: h / s / p / skip.
Clips are copied to clips/<category>/<job>__<category>NN.mp4
"""
from __future__ import annotations

import argparse
import shutil
import sys

from common import CFG, absp, category_dir, read_manifest, rel, write_manifest

SHORT = {"h": "hooks", "hook": "hooks", "s": "showcases", "showcase": "showcases",
         "p": "payoffs", "payoff": "payoffs", "x": "skip"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("job")
    ap.add_argument("labels", nargs="*", help="segNN=category")
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()

    m = read_manifest(a.job)
    by_id = {s["id"]: s for s in m["segments"]}
    allowed = set(CFG["categories"]) | {"skip"}

    for item in a.labels:
        if "=" not in item:
            sys.exit(f"Bad label '{item}'. Use segNN=category")
        sid, cat = item.split("=", 1)
        cat = SHORT.get(cat.lower(), cat.lower())
        if sid not in by_id:
            sys.exit(f"Unknown segment {sid}. Known: {', '.join(by_id)}")
        if cat not in allowed:
            sys.exit(f"Unknown category '{cat}'. Allowed: {', '.join(sorted(allowed))}")
        by_id[sid]["category"] = cat

    if a.labels:
        # (Re)copy every labelled clip; numbering is per category in video order.
        counters: dict[str, int] = {}
        for s in m["segments"]:
            old = s.get("clip_file")
            if s["category"] in (None, "skip"):
                if old and absp(old).exists():
                    absp(old).unlink()
                s["clip_file"] = None
                continue
            counters[s["category"]] = counters.get(s["category"], 0) + 1
            dest = category_dir(s["category"]) / f"{m['job']}__{s['category']}{counters[s['category']]:02d}.mp4"
            if old and absp(old) != dest and absp(old).exists():
                absp(old).unlink()
            shutil.copy2(absp(s["segment_file"]), dest)
            s["clip_file"] = rel(dest)
        write_manifest(a.job, m)

    for s in m["segments"]:
        print(f"  {s['id']}  {s['duration']:5.2f}s  {str(s['category']):10s}  {s['clip_file'] or ''}")
    missing = [s["id"] for s in m["segments"] if s["category"] is None]
    if missing:
        print(f"Still unlabelled: {', '.join(missing)}")


if __name__ == "__main__":
    main()
