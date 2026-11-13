# Dropship Video Agent - instructions for Claude Code

You turn short-form product videos into new, ready-to-post videos for an organic dropshipping
business (Instagram Reels / TikTok / Facebook). The user is usually not a developer: keep replies
short, make decisions yourself when they say "auto" or "don't ask", and never stop silently.

All scripts are in `agent/` and are run from THIS folder (the one containing this file).
On a Mac use `python3` wherever this file says `python`.

---------------------------------------------------------------------------------------------------
## HARD RULES (always)
1. **Product** - `notes/product.md` describes the product. Read it at the start of every job. The
   product must look exactly like `notes/product.md` + `references/product/` in every clip. Only
   people, clothes colours and backgrounds change. If `notes/product.md` still contains
   "FILL THIS IN", stop and help the user fill it in first (look at `references/product/`).
2. **Higgsfield model** - use ONLY **Wan 3.0** (video-to-video). Never pick another model, even if
   a tool suggests one. Default quality 720p, 9:16.
3. **Prompt method** - follow `notes/higgsfield_prompt_style.md` exactly (recreate @video1 frame by
   frame, change only what is listed).
4. **Content** - do NOT remove or cover logos or any items in clips, and never retry a clip because
   of them. Retry only when the product, a face or hands are broken (max 2 retries per clip).
5. **Files** - never move, rename or delete existing files in `clips/` (CapCut projects point to
   their exact paths - moving them causes "Media lost"). Only copy or create new files. Never touch
   `input/`.
6. **CapCut** - must be fully closed while you write a CapCut project. Never use `capcut_raw_patch`.
   A CapCut project is only "done" when `agent/check_capcut_text.py` prints TEXT CHECK OK.
7. **Money** - unless the user said "auto", tell them the number of clips and the credit cost and
   wait for OK before generating. Never buy credits or change plans.
8. **Waiting** - you cannot wake yourself up. When renders are still running, say so in one line and
   tell the user to type "continue" in a few minutes.

---------------------------------------------------------------------------------------------------
## TWO MODES (both end with the same CAPCUT MERGE)
- **REMAKE** (`/make-video "input/<file>.mp4"`) - one source video -> cut into clips -> remake every
  clip in Higgsfield (new people / clothes / background, same movements, user's product) -> CapCut
  project with the remade clips + the source video's ORIGINAL audio + a text hook.
- **MIX** (`/mix-videos <what to make>`) - clips already exist in `clips/` -> combine them into one or
  more CapCut projects (hook + showcases + payoff) with music or the clips' own audio.
Partial jobs are fine too (e.g. "remake only the first clip of S(1), then merge S(1)a-d") - use the
same building blocks below.

---------------------------------------------------------------------------------------------------
## REMAKE MODE

### Step 0 - Preflight
- `ffmpeg -version` must work. `claude mcp list` should show `higgsfield` and `capcut` connected.
  If one is missing, tell the user which and point to README.md.
- Read `notes/product.md` and `notes/higgsfield_prompt_style.md`.

### Step 1 - Cut
    python agent/split.py "input/<file>.mp4"
Prints a job name (e.g. `video-3`). Read every `jobs/<job>/frames/segNN_sheet.jpg` (4 frames per clip).
Fix bad cuts: two shots in one sheet -> `--threshold 0.2 --force`; one shot split in two ->
`--threshold 0.4 --force`; still wrong -> `--cuts 2.4,5.1 --force`.

### Step 2 - Label
hooks = opening attention grabber; showcases = product shown/used; payoffs = result/reaction/end;
skip = black frames, end cards.

    python agent/organize.py <job> seg01=hooks seg02=showcases ... seg08=payoffs

Copies clips to `clips/<category>/<job>__<category>NN.mp4`.

### Step 3 - Characters and prompts
- Characters come from `references/characters/` (file names describe them, e.g. `20-woman-2.jpg`,
  `30-woman.png`, `20-men.jpg`, `old-woman.jpg`). Read the photos, match each person in the clip by
  gender and age. The main character (person with the product) is the SAME photo in every clip of a
  video and different from the previous job's main character. Files with the same base name may be
  the same person - upload both. If no photo fits someone, invent nothing: ask (or, in auto mode,
  let the prompt describe a new unrelated person in the background).
- For each clip write `jobs/<job>/prompts/segNN.json`:
  `{"segment": "seg02", "category": "showcases", "character_files": {"woman with the product": "20-woman-4.png"},
    "analysis": {...}, "video_prompt": "<full prompt from the template>", "image_prompt": "-"}`

### Step 4 - Generate in Higgsfield (MCP)
1. Pad short clips (Wan 3.0 minimum is 2 s):
       python agent/pad.py <job>
   -> `jobs/<job>/padded/segNN.mp4` (last frame frozen). Add to each prompt:
   "The last part of @video1 is a frozen frame - keep it still."
2. Upload with the Higgsfield tools: `media_upload` -> PUT the file with curl exactly as the tool says
   -> `media_confirm`. Upload the padded clip (@video1), the character photos (@image1, @image2...)
   and the product photo (always the LAST @image). Save the product once with
   `manage_reference_elements` and reuse it.
3. Generate with Wan 3.0 (video-to-video), 720p, 9:16, 2 s (or the padded length). Submit all clips;
   if Higgsfield rate-limits, submit the rest as earlier ones finish.
4. `jobs_wait` / `show_result` -> download each result to `jobs/<job>/inbox/segNN.mp4`
   (`curl -L -o <file> "<url>"`).
5. `python agent/higgsfield.py collect <job>` -> files land as `clips/<category>/<job>__<category>NN__hf.mp4`.
6. Check one frame of every clip (`ffmpeg -v error -y -ss 1 -i <clip> -frames:v 1 jobs/<job>/check_segNN.jpg`,
   then Read it). Retry only per HARD RULE 4.
7. Note the balance before and after (`balance`) for the report.
(No MCP? `python agent/higgsfield.py manual <job>` builds upload packs for the website, then `collect`.)

### Step 5 - Hook text
Write 5 hooks from the "Who buys it / hook angle" in `notes/product.md`; pick the best.
Max ~10 words, readable in 2 s, curiosity / surprise / relatable, no fake claims. You may add 1-2
emojis at the end - they only go into the HOOK.txt (the PC can't draw Apple emojis).

### Step 6 - Export files + CAPCUT MERGE
    python agent/assemble.py <job> --hook "<hook with emojis>"
Makes in `videos/`: `<name>__CLEAN.mp4` (no text, backup), `<name>.mp4` (preview with text),
`<name>__HOOK.txt` (hook with emojis). Then build the CapCut project with CAPCUT MERGE below:
clips = the `__hf` clips in manifest order, each trimmed to its original duration; audio =
`jobs/<job>/original_audio.m4a` from 0 s.

### Step 7 - Report (short)
CapCut project name, hook, HOOK.txt path, clips remade vs. originals used, credits used.

---------------------------------------------------------------------------------------------------
## MIX MODE
The user says what to make, e.g. "5 videos, each hook + 3 showcases + 1 payoff, max 20 s, song drop at 00:38".
Without "auto", ask once for anything missing (how many, clips per video, max length, music).
1. List clips with lengths (`ffprobe`) by folder. Pick by file name; only look inside clips when the
   user asks for "the best" ones.
2. Plan a table first: project name (e.g. `B1_H01`) -> hook -> showcases -> payoff -> length. No clip
   twice in one project; spread clips evenly.
3. Music (mp3 in `music/`; if several, ask which): with a drop point T (where the beat/words start),
   start the song at 0 s, trimmed so it plays from (T - hook length) - the drop lands exactly when the
   hook ends. Without T, play from the start. The song ends with the video. Clip audio muted.
4. Build with CAPCUT MERGE. Several projects: build the FIRST, stop for the user's check, then the
   rest after "go" (in auto mode: build all).

---------------------------------------------------------------------------------------------------
## CAPCUT MERGE (shared)
Uses the `capcut` MCP (community server that writes CapCut desktop drafts).
- CapCut fully closed. Ask once, then go. Never `capcut_raw_patch`.
- Canvas 1080x1920, 30 fps. Clips on one video track in order, each trimmed as given.
- Audio on its own track, ending exactly with the video. When the audio is a separate track, mute
  every video clip (volume 0); if the tools can't, say so (user mutes the track in CapCut).
- Text: the hook WITHOUT emojis, using the template project `TEXT_STYLE` (white text, black outline),
  **font size 13, centred, 2 lines (max 3) with a real line break, no line longer than 20 characters,
  from 0 s to the END of the video.**
- After EVERY save:
      python agent/check_capcut_text.py "<project folder>"
  must print TEXT CHECK OK. If it fails on size or line breaks, run it again with `--fix` (allowed:
  only changes text sizes/line breaks, backs the file up first). Fix anything else with the CapCut
  tools, save, check again. Never say a project is done while the check fails.
- Report a table: project -> clips (lengths) -> audio start -> text start/end -> total length.
- Never edit or delete the user's other CapCut projects.

### Getting the project to the iPhone (tell the user when relevant)
- The PC and the iPhone must be signed in to the SAME CapCut account; upload to a Space that account
  can upload to. Switching accounts is the #1 reason projects "don't arrive" or won't open.
- If uploads fail: Space storage may be full - delete old test projects and empty the Space trash.
- If the project won't open on the iPhone: update CapCut on both devices; or send the
  `__CLEAN.mp4` to the phone instead and add the text there (always works).

---------------------------------------------------------------------------------------------------
## Useful commands
- `python agent/higgsfield.py status <job>` - where each clip is
- `python agent/assemble.py <job> --preview-hook "text"` - render only the text overlay to check it
- `python agent/organize.py <job> --show` - current labels
