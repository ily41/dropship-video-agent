"""Step 3 - remake each clip in Higgsfield with new characters and a new background.

Two stages per clip (so you only pay for video once the still looks right):
  1. FRAME  - the original first frame + your product photos + image_prompt
              -> a new start frame (new people, new natural background, same product, same pose)
  2. VIDEO  - the new start frame + video_prompt -> new clip (image-to-video),
              or, with mode "frame_then_motion", the original clip's motion is copied onto the new frame.

Usage:
    python agent/higgsfield.py check                 # are keys + config ok? (--ping also tests the upload)
    python agent/higgsfield.py frames <job>          # stage 1 for every clip that has a prompt file
    python agent/higgsfield.py videos <job>          # stage 2 for every clip whose new frame exists
    python agent/higgsfield.py run <job>             # both stages
    python agent/higgsfield.py status <job>
    python agent/higgsfield.py manual <job>          # no API? build upload packs for the Higgsfield website
    python agent/higgsfield.py collect <job>         # pick up files you downloaded into jobs/<job>/inbox/
Options: --only seg01,seg03   --redo   --mode frame_then_video|frame_then_motion

Credentials: put them in agent/.env (see .env.example) or in environment variables:
    HF_KEY=<key id>:<key secret>      (or HF_API_KEY_ID and HF_API_KEY_SECRET)
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
import time
import uuid
from pathlib import Path

from common import AGENT_DIR, CFG, absp, category_dir, folder, job_dir, read_manifest, rel, write_manifest

try:
    import requests
except ImportError:  # pragma: no cover
    sys.exit("Missing package: run  pip install -r agent/requirements.txt")

HF = CFG["higgsfield"]
TERMINAL = {"completed", "failed", "nsfw", "canceled", "cancelled", "error"}
MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".mp4": "video/mp4"}


# ---------------------------------------------------------------- auth / http
def load_env() -> None:
    env = AGENT_DIR / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def auth_header() -> dict:
    load_env()
    key = os.environ.get("HF_KEY")
    if not key and os.environ.get("HF_API_KEY_ID") and os.environ.get("HF_API_KEY_SECRET"):
        key = f"{os.environ['HF_API_KEY_ID']}:{os.environ['HF_API_KEY_SECRET']}"
    if not key or ":" not in key:
        sys.exit("No Higgsfield API key. Create one at cloud.higgsfield.ai (API keys), then put\n"
                 "HF_KEY=<key id>:<key secret>\ninto agent/.env  -- or use `higgsfield.py manual` for the website flow.")
    return {"Authorization": f"Key {key}"}


def explain(resp: requests.Response, what: str) -> None:
    body = resp.text[:800]
    hint = {
        401: "API key rejected - check HF_KEY in agent/.env.",
        402: "Not enough API balance - top up at cloud.higgsfield.ai (API billing is separate from the website plan).",
        403: "This key cannot use that model or endpoint.",
        404: "Model id not found - open the model page on cloud.higgsfield.ai, copy its id into agent/config.json.",
        422: "The model rejected the arguments - compare argument names in agent/config.json with the model page.",
        429: "Rate limited - wait a minute and re-run (finished clips are kept).",
    }.get(resp.status_code, "")
    sys.exit(f"Higgsfield {what} failed: HTTP {resp.status_code}. {hint}\n{body}")


def upload(path: Path, cache: dict) -> str:
    """Upload a local file to Higgsfield storage, return its public URL (cached for 24h per file)."""
    key = rel(path)
    hit = cache.get(key)
    if hit and time.time() - hit["t"] < 24 * 3600 and hit.get("mtime") == path.stat().st_mtime:
        return hit["url"]
    ctype = MIME.get(path.suffix.lower())
    if not ctype:
        sys.exit(f"Unsupported file type for upload: {path}")
    r = requests.post(HF["upload_url_endpoint"], headers={**auth_header(), "Content-Type": "application/json"},
                      json={"content_type": ctype}, timeout=60)
    if r.status_code >= 300:
        explain(r, "upload-url")
    info = r.json()
    with open(path, "rb") as f:
        put = requests.put(info["upload_url"], data=f, headers=info.get("upload_headers") or {"Content-Type": ctype},
                           timeout=600)
    if put.status_code >= 300:
        sys.exit(f"Upload of {path.name} failed: HTTP {put.status_code} {put.text[:300]}")
    cache[key] = {"url": info["public_url"], "t": time.time(), "mtime": path.stat().st_mtime}
    return info["public_url"]


def fill(template, vars: dict):
    """Fill "{name}" placeholders in the config argument template."""
    if isinstance(template, dict):
        out = {}
        for k, v in template.items():
            val = fill(v, vars)
            if val not in (None, "", []):
                out[k] = val
        return out
    if isinstance(template, list):
        return [fill(v, vars) for v in template]
    if isinstance(template, str):
        if template.startswith("{") and template.endswith("}") and template[1:-1] in vars:
            return vars[template[1:-1]]
        class Safe(dict):
            def __missing__(self, k):
                return "{" + k + "}"
        return template.format_map(Safe({k: v for k, v in vars.items() if isinstance(v, (str, int, float))}))
    return template


def submit(model: dict, vars: dict) -> dict:
    args = fill(model["args"], vars)
    url = f"{HF['api_base'].rstrip('/')}/{model['id'].strip('/')}"
    r = requests.post(url, headers={**auth_header(), "Content-Type": "application/json",
                                    "Idempotency-Key": str(uuid.uuid4())}, json=args, timeout=120)
    if r.status_code >= 300:
        explain(r, f"submit to {model['id']}")
    data = r.json()
    rid = data.get("request_id") or data.get("id")
    return {"id": rid, "status_url": data.get("status_url") or f"{HF['api_base'].rstrip('/')}/requests/{rid}/status",
            "status": data.get("status", "queued"), "model": model["id"], "args": args}


def find_url(data, kind: str) -> str | None:
    if kind == "video" and isinstance(data.get("video"), dict) and data["video"].get("url"):
        return data["video"]["url"]
    if kind == "image" and data.get("images"):
        return data["images"][0].get("url")
    exts = (".mp4", ".mov", ".webm") if kind == "video" else (".png", ".jpg", ".jpeg", ".webp")
    stack = [data]
    while stack:  # fallback: any url that looks like the right media type
        cur = stack.pop()
        if isinstance(cur, dict):
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
        elif isinstance(cur, str) and cur.startswith("http") and cur.split("?")[0].lower().endswith(exts):
            return cur
    return None


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with requests.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    os.replace(tmp, dest)


# ---------------------------------------------------------------- per-clip helpers
def segments_to_do(m: dict, only: str | None) -> list[dict]:
    wanted = set(only.split(",")) if only else None
    out = []
    for s in m["segments"]:
        if wanted and s["id"] not in wanted:
            continue
        if s["category"] in (None, "skip"):
            if wanted:
                print(f"  {s['id']}: not labelled (run organize.py first) - skipped")
            continue
        out.append(s)
    return out


def load_prompt(job: str, s: dict) -> dict | None:
    p = job_dir(job) / "prompts" / f"{s['id']}.json"
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    for k in ("image_prompt", "video_prompt"):
        if not data.get(k):
            sys.exit(f"{p} is missing '{k}'")
    s["prompt_file"] = rel(p)
    return data


def product_refs() -> list[Path]:
    d = folder("product_refs")
    files = sorted(p for p in d.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))
    return files[: HF.get("max_product_refs", 3)]


def frame_path(job: str, s: dict) -> Path:
    return job_dir(job) / "generated" / f"{s['id']}_frame.png"


def video_path(s: dict) -> Path:
    clip = absp(s["clip_file"])
    return clip.with_name(clip.stem + "__hf.mp4")


def wait_all(pending: list[tuple[dict, str, str, Path]], m: dict, job: str) -> None:
    """pending: (segment, stage, kind, destination). Polls until every request finishes."""
    deadline = time.time() + HF["timeout_minutes"] * 60
    headers = auth_header()
    while pending and time.time() < deadline:
        time.sleep(HF["poll_seconds"])
        still = []
        for s, stage, kind, dest in pending:
            req = s["higgsfield"][stage]
            r = requests.get(req["status_url"], headers=headers, timeout=60)
            if r.status_code >= 300:
                print(f"  {s['id']} {stage}: status check HTTP {r.status_code}, retrying")
                still.append((s, stage, kind, dest))
                continue
            data = r.json()
            st = str(data.get("status", "")).lower()
            req["status"] = st
            if st == "completed":
                url = find_url(data, kind)
                if not url:
                    print(f"  {s['id']} {stage}: completed but no {kind} url in response: {json.dumps(data)[:400]}")
                    continue
                download(url, dest)
                req["output_url"] = url
                print(f"  {s['id']} {stage}: done -> {rel(dest)}")
                if stage == "video":
                    s["generated_file"] = rel(dest)
            elif st in TERMINAL:
                print(f"  {s['id']} {stage}: {st.upper()} {data.get('error', '')} - edit the prompt and re-run with --redo --only {s['id']}")
            else:
                still.append((s, stage, kind, dest))
        write_manifest(job, m)
        if still:
            print(f"  ...waiting on {len(still)} request(s)")
        pending = still
    if pending:
        print(f"Timed out with {len(pending)} still running. Re-run the same command later; it resumes them.")


# ---------------------------------------------------------------- stages
def stage_frames(job: str, m: dict, only: str | None, redo: bool) -> None:
    cache = m.setdefault("upload_cache", {})
    refs = product_refs()
    if not refs:
        print("  note: references/product/ is empty - add 1-3 clean product photos so the backpack stays identical")
    pending = []
    for s in segments_to_do(m, only):
        prompt = load_prompt(job, s)
        if not prompt:
            print(f"  {s['id']}: no prompts/{s['id']}.json yet - skipped")
            continue
        dest = frame_path(job, s)
        req = s["higgsfield"].get("frame")
        if dest.exists() and not redo:
            print(f"  {s['id']}: frame exists ({rel(dest)})")
            continue
        if req and req.get("status") not in TERMINAL and not redo:
            print(f"  {s['id']}: resuming frame request {req['id']}")
            pending.append((s, "frame", "image", dest))
            continue
        extra = [absp(p) for p in prompt.get("extra_reference_images", [])]
        files = [absp(s["first_frame"])] + refs + extra
        urls = [upload(p, cache) for p in files]
        write_manifest(job, m)
        vars = {**prompt, "reference_urls": urls, "first_frame_url": urls[0],
                "product_urls": urls[1:1 + len(refs)], "aspect_ratio": "9:16"}
        s["higgsfield"]["frame"] = submit(HF["frame_model"], vars)
        s["higgsfield"].pop("video", None)
        s["generated_file"] = None
        old_video = video_path(s)
        if old_video.exists():  # new frame -> old video is outdated; keep it as __hf_prev
            os.replace(old_video, old_video.with_name(old_video.stem + "_prev.mp4"))
        print(f"  {s['id']}: frame submitted ({s['higgsfield']['frame']['id']})")
        pending.append((s, "frame", "image", dest))
    write_manifest(job, m)
    wait_all(pending, m, job)


def stage_videos(job: str, m: dict, only: str | None, redo: bool, mode: str) -> None:
    cache = m.setdefault("upload_cache", {})
    pending = []
    for s in segments_to_do(m, only):
        prompt = load_prompt(job, s)
        frame = frame_path(job, s)
        if not prompt or not frame.exists():
            print(f"  {s['id']}: no new frame yet - run `frames` first")
            continue
        dest = video_path(s)
        req = s["higgsfield"].get("video")
        if dest.exists() and not redo:
            print(f"  {s['id']}: video exists ({rel(dest)})")
            s["generated_file"] = rel(dest)
            continue
        if req and req.get("status") not in TERMINAL and not redo:
            print(f"  {s['id']}: resuming video request {req['id']}")
            pending.append((s, "video", "video", dest))
            continue
        frame_url = upload(frame, cache)
        vars = {**prompt, "start_frame_url": frame_url, "start_frame_url_list": [frame_url],
                "duration": 10 if s["duration"] > 5.2 else 5, "aspect_ratio": "9:16"}
        model = HF["video_model"]
        if mode == "frame_then_motion":
            if s["duration"] >= HF["motion_model"].get("min_source_seconds", 0):
                vars["source_clip_url"] = upload(absp(s["segment_file"]), cache)
                model = HF["motion_model"]
            else:
                print(f"  {s['id']}: clip shorter than {HF['motion_model']['min_source_seconds']}s - using image-to-video instead of motion transfer")
        write_manifest(job, m)
        s["higgsfield"]["video"] = submit(model, vars)
        print(f"  {s['id']}: video submitted to {model['id']} ({s['higgsfield']['video']['id']})")
        pending.append((s, "video", "video", dest))
    write_manifest(job, m)
    wait_all(pending, m, job)


def cmd_status(job: str, m: dict) -> None:
    for s in m["segments"]:
        hf = s.get("higgsfield", {})
        fr = "frame:ok" if frame_path(job, s).exists() else f"frame:{hf.get('frame', {}).get('status', '-')}"
        vd = "video:ok" if s.get("generated_file") and absp(s["generated_file"]).exists() else f"video:{hf.get('video', {}).get('status', '-')}"
        pr = "prompt:ok" if (job_dir(job) / "prompts" / f"{s['id']}.json").exists() else "prompt:-"
        print(f"  {s['id']}  {str(s['category']):10s} {pr:10s} {fr:16s} {vd}")


def cmd_manual(job: str, m: dict, only: str | None) -> None:
    """Build per-clip packs for the Higgsfield website (or for the agent driving Chrome)."""
    base = job_dir(job) / "higgsfield_manual"
    inbox = job_dir(job) / "inbox"
    inbox.mkdir(exist_ok=True)
    refs = product_refs()
    for s in segments_to_do(m, only):
        prompt = load_prompt(job, s)
        if not prompt:
            print(f"  {s['id']}: no prompt file - skipped")
            continue
        d = base / s["id"]
        d.mkdir(parents=True, exist_ok=True)
        shutil.copy2(absp(s["first_frame"]), d / "1_reference_original_frame.jpg")
        for i, r in enumerate(refs, 2):
            shutil.copy2(r, d / f"{i}_reference_product{r.suffix.lower()}")
        (d / "prompt.txt").write_text(
            f"CLIP {s['id']} ({s['category']}, {s['duration']:.1f}s)\n\n"
            f"STEP 1 - IMAGE (upload the reference images in this folder):\n{prompt['image_prompt']}\n\n"
            f"STEP 2 - VIDEO (upload the image from step 1, 9:16, {5 if s['duration'] <= 5.2 else 10}s):\n{prompt['video_prompt']}\n\n"
            f"NEGATIVE: {prompt.get('negative_prompt', '')}\n\n"
            f"When done, save the video as  jobs/{job}/inbox/{s['id']}.mp4  "
            f"(and optionally the still as  jobs/{job}/inbox/{s['id']}_frame.png), then run:\n"
            f"python agent/higgsfield.py collect {job}\n", encoding="utf-8")
        print(f"  {s['id']}: pack ready -> {rel(d)}")
    write_manifest(job, m)
    print(f"Drop finished downloads into {rel(inbox)} named segNN.mp4, then run collect.")


def cmd_collect(job: str, m: dict) -> None:
    inbox = job_dir(job) / "inbox"
    if not inbox.exists():
        sys.exit(f"No inbox folder: {inbox}")
    by_id = {s["id"]: s for s in m["segments"]}
    for f in sorted(inbox.iterdir()):
        sid = f.stem.split("_")[0].lower()
        s = by_id.get(sid)
        if not s or s["category"] in (None, "skip"):
            print(f"  {f.name}: no labelled segment '{sid}' - left in inbox")
            continue
        if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp") and "frame" in f.stem.lower():
            dest = frame_path(job, s)
            dest.parent.mkdir(parents=True, exist_ok=True)
            from PIL import Image
            Image.open(f).convert("RGB").save(dest)
            f.unlink()
            print(f"  {f.name} -> {rel(dest)}")
        elif f.suffix.lower() in (".mp4", ".mov", ".webm"):
            dest = video_path(s).with_suffix(f.suffix.lower())
            shutil.move(str(f), dest)
            s["generated_file"] = rel(dest)
            print(f"  {f.name} -> {rel(dest)}")
    write_manifest(job, m)


def cmd_check(ping: bool) -> None:
    hdr = auth_header()
    print("API key: found")
    for k in ("frame_model", "video_model", "motion_model"):
        print(f"{k}: {HF[k]['id']}  args={list(HF[k]['args'])}")
    print(f"mode: {HF['mode']}")
    print(f"product refs: {[p.name for p in product_refs()] or 'NONE - add photos to references/product/'}")
    if ping:
        r = requests.post(HF["upload_url_endpoint"], headers={**hdr, "Content-Type": "application/json"},
                          json={"content_type": "image/png"}, timeout=60)
        print("upload endpoint:", "OK" if r.status_code < 300 else f"HTTP {r.status_code} {r.text[:300]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["check", "frames", "videos", "run", "status", "manual", "collect"])
    ap.add_argument("job", nargs="?")
    ap.add_argument("--only")
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--mode", default=HF["mode"], choices=["frame_then_video", "frame_then_motion"])
    ap.add_argument("--ping", action="store_true")
    a = ap.parse_args()

    if a.command == "check":
        return cmd_check(a.ping)
    if not a.job:
        sys.exit("Give the job name, e.g.  python agent/higgsfield.py frames my-video")
    m = read_manifest(a.job)
    if a.command == "status":
        return cmd_status(a.job, m)
    if a.command == "manual":
        return cmd_manual(a.job, m, a.only)
    if a.command == "collect":
        return cmd_collect(a.job, m)
    if a.command in ("frames", "run"):
        print("Stage 1: new start frames")
        stage_frames(a.job, m, a.only, a.redo)
    if a.command in ("videos", "run"):
        print("Stage 2: videos")
        stage_videos(a.job, m, a.only, a.redo, a.mode)
    cmd_status(a.job, m)


if __name__ == "__main__":
    main()
