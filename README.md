# Dropship Video Agent

An AI agent for **Claude Code** that turns product videos into new, ready-to-post short videos for
organic dropshipping (Instagram Reels, TikTok, Facebook) - using **Higgsfield (Wan 3.0)** to remake
clips with new people, and **CapCut** for the final edit.

It works for **any product** and on **Windows and Mac**. You describe your product once in
`notes/product.md`, add photos of your product and of the people you want in your videos, and then
make videos with one command.

---

## Contents
1. [What it does](#1-what-it-does)
2. [What you need](#2-what-you-need)
3. [Install - Windows](#3-install---windows)
4. [Install - Mac](#4-install---mac)
5. [Set up your product, people and prompts](#5-set-up-your-product-people-and-prompts)
6. [Connect Higgsfield and CapCut](#6-connect-higgsfield-and-capcut)
7. [Making videos](#7-making-videos)
8. [Finishing on your iPhone](#8-finishing-on-your-iphone)
9. [Folder map](#9-folder-map)
10. [Costs and timing](#10-costs-and-timing)
11. [Rules the agent follows](#11-rules-the-agent-follows)
12. [Troubleshooting](#12-troubleshooting)
13. [FAQ](#13-faq)

---

## 1. What it does

### Mode A - REMAKE a video (`/make-video`)
You drop one video (e.g. a competitor's viral Reel) into `input/`. The agent:

1. **Cuts** it at every scene change and sorts the clips into `clips/hooks`, `clips/showcases`,
   `clips/payoffs`.
2. **Looks at each clip**, finds the people in it and picks replacements from your character photos.
3. **Writes a Higgsfield prompt per clip** (your proven method in `notes/higgsfield_prompt_style.md`):
   recreate the clip frame by frame - same movements, same camera - but with your characters, new
   clothes colours, a new background, and **your product**.
4. **Generates every clip with Wan 3.0** through the Higgsfield MCP and downloads them.
5. **Builds a CapCut project**: the new clips in the original order, the **original audio** of the
   source video, and a text hook (white text, black outline, size 13, whole video).
6. **Checks the text** in the CapCut project automatically (`TEXT CHECK OK`).
7. Also exports a `__CLEAN.mp4` (no text) and a `__HOOK.txt` (hook with emojis) as backup.

### Mode B - MIX ready clips (`/mix-videos`)
Your clips are already in `clips/hooks`, `clips/showcases`, `clips/payoffs`. The agent combines them
into many CapCut projects (e.g. every hook + 3 showcases), lines the music drop up with the end of the
hook, and adds the text.

### Partial jobs
You can also ask for anything in between, e.g. *"remake only the first clip of S(1) with a new
person, then merge S(1)a-d in CapCut"*. See the ready prompts in [section 7](#7-making-videos).

---

## 2. What you need

| Thing | Why | Cost |
|---|---|---|
| **Claude Pro or Max** plan | Claude Code runs the agent | Claude subscription |
| **Higgsfield** account with credits | Remakes the clips (Wan 3.0) | ~3.5 credits per 2-second clip at 720p |
| **CapCut** desktop (Windows or Mac) | Final project | Free (Pro optional) |
| **CapCut** on iPhone (optional) | Add Apple emojis to the text, export | Free |
| A computer: Windows 10/11 or macOS 13+ | | |

You don't need to know how to code. Every step below is copy-paste.

---

## 3. Install - Windows

Open **PowerShell** (Start menu -> type `PowerShell` -> Enter). Important: the prompt must start with
`PS`. If it shows `C:\Users\...>` without `PS`, you're in CMD - type `powershell` and press Enter.

Paste these one by one:

```powershell
winget install Python.Python.3.12
winget install Gyan.FFmpeg
winget install OpenJS.NodeJS.LTS
winget install Git.Git
irm https://claude.ai/install.ps1 | iex
```

**Close PowerShell and open a new one** (so it finds the new programs), then check:

```powershell
python --version
ffmpeg -version
node --version
git --version
claude --version
```

Each should print a version. Then get the agent:

```powershell
cd $HOME\Documents
git clone https://github.com/ily41/dropship-video-agent
cd dropship-video-agent
pip install -r agent\requirements.txt
```

(No git? On the GitHub page click **Code -> Download ZIP**, unzip it into `Documents`, and `cd` into it.)

---

## 4. Install - Mac

Open **Terminal** (Cmd+Space -> type `Terminal` -> Enter). If macOS asks to allow Terminal access to
a folder, click **Allow**.

1. **Homebrew** (installer for the tools below):
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```
   It asks for your Mac password (nothing shows while typing). At the end it prints **"Next steps"**
   with 2-3 commands - **copy and run them**.
2. **FFmpeg, Node.js and Git:**
   ```bash
   brew install ffmpeg node git
   ```
3. **Claude Code:**
   ```bash
   curl -fsSL https://claude.ai/install.sh | bash
   ```
   It shows no progress - wait for "Claude Code successfully installed!". Open a **new** Terminal
   window and check `claude --version`.
4. **The agent:**
   ```bash
   cd ~/Documents
   git clone https://github.com/ily41/dropship-video-agent
   cd dropship-video-agent
   python3 -m pip install --user -r agent/requirements.txt
   ```
   If pip says `externally-managed-environment`, add `--break-system-packages` at the end.

On a Mac, write `python3` wherever this guide says `python`, and `/` instead of `\` in paths.

---

## 5. Set up your product, people and prompts

### 5.1 Your product -> `notes/product.md`
1. Put **3-5 clear photos** of your product in `references/product/` (front, side, details, open/in use).
2. Start Claude Code in the folder (`claude`) and paste:
   ```
   Look at the photos in references/product/ and fill in notes/product.md for MY product.
   Keep the same sections. Ask me anything you can't see in the photos. The "Product block" must
   describe only visible things: shape, material, colours, details. Remove "FILL THIS IN" from the
   title when done.
   ```
3. Answer its questions and read the result. `notes/product.example.md` shows a finished example.

> The **Product block** matters most - it goes into every Higgsfield prompt. Concrete words
> ("matte black metal, rounded top, small silver logo on the front") work. Vague words
> ("premium", "beautiful") don't.

### 5.2 Your people -> `references/characters/`
Put photos of the people you want in your videos here (e.g. from Pinterest - AI-generated faces are
the safest choice for ads). **Name the files by gender and age**, the agent matches by name:

```
20-woman-1.jpg   20-woman-2.png   20-woman-b-2.jpg   20-woman-b-3.jpg   (b-2/b-3 = same woman, 2 photos)
30-woman-1.png   50-woman.png     old-woman.jpg
20-men-1.jpg     20-men-2.jpg
```

The person holding the product stays the same in every clip of a video, and changes from video to video.

### 5.3 Your Higgsfield prompts -> `notes/higgsfield_prompt_style.md`
This file already contains a proven method (recreate @video1 frame by frame, change only people,
clothes colours and background). If you have your own prompts that worked, paste them **at the
bottom** of the file - don't delete what's there.

---

## 6. Connect Higgsfield and CapCut

Run these **inside the agent folder**.

### 6.1 Higgsfield (official MCP - uses your higgsfield.ai plan credits)
```
claude mcp add --transport http higgsfield https://mcp.higgsfield.ai/mcp
claude
```
Inside Claude Code type `/mcp`, choose **higgsfield**, and log in in the browser window that opens.
Type `/exit` when done.

### 6.2 CapCut (community MCP - unofficial)
1. **Text template:** open CapCut desktop, create a project named exactly **`TEXT_STYLE`**, add one
   text in the **Classic** style (white text, black outline). Close CapCut completely.
2. **Install the CapCut MCP:**

   Windows (PowerShell):
   ```powershell
   cd $HOME\Documents
   git clone https://github.com/JmsLdrn/capcut-mcp
   cd capcut-mcp
   npm install
   claude mcp add capcut --scope user -e CAPCUT_TEMPLATE_DRAFT="TEXT_STYLE" -- node "$HOME\Documents\capcut-mcp\src\server.js"
   ```
   Mac (Terminal):
   ```bash
   cd ~
   git clone https://github.com/JmsLdrn/capcut-mcp
   cd capcut-mcp
   npm install
   claude mcp add capcut --scope user -e CAPCUT_TEMPLATE_DRAFT="TEXT_STYLE" -- node ~/capcut-mcp/src/server.js
   ```
3. **Check:** `claude mcp list` -> `higgsfield` and `capcut` must say **Connected**.

> The CapCut MCP is not made by CapCut. It writes CapCut's project files directly, so a CapCut update
> can break it, and some CapCut versions lock (encrypt) their project files. If the agent reports
> "encrypted" or can't find projects, use the `__CLEAN.mp4` it exports instead and add the text by hand.

---

## 7. Making videos

Always start from the agent folder:
```
cd <path to dropship-video-agent>
claude
```
**Close CapCut completely** (Windows: system tray icon -> Quit; Mac: Cmd+Q) before the agent builds
a project, and open it only after the agent says `TEXT CHECK OK`.

### Remake a video
Put the video in `input/`, then:
```
/make-video "input/my video.mp4"
```
First time: the agent shows the clip count and credit cost and waits for your OK. Ask it to
*"generate one test clip first"* and check it.

**No questions, just the video** (once you trust it):
```
/make-video "input/my video.mp4" auto
Don't ask me anything and don't stop for checks. Make every decision yourself:
- Wan 3.0 only, 720p. Pad clips under 2 s to 2 s by freezing the last frame.
- Pick characters from references/characters yourself, with a different main character than last time.
- Generate all clips at once. Redo a clip only if the product, a face or hands are broken (max 2 retries).
- Pick the hook yourself.
- CapCut is closed. Build the CapCut project, run check_capcut_text.py (with --fix if needed) until TEXT CHECK OK.
At the end, give me only: the CapCut project name, the HOOK.txt path, and the total credits used.
```

### Mix ready clips
Put a song in `music/` (optional), then e.g.:
```
/mix-videos 5 videos, each hook + 3 showcases, max 20s, song drop at 00:38
```
It shows a plan, builds the first project, waits for your check, then builds the rest after you type `go`.

### Give a winning video a new hook (repost)
A video did well and you want a fresh version: keep the proven clips, remake only the first one.
```
Folder: clips/showcase. Don't ask me anything, decide yourself.
1. Remake S(1)a in Higgsfield with Wan 3.0 only, using notes/higgsfield_prompt_style.md: same movements,
   timing and product, but a DIFFERENT person from references/characters (same gender, similar age),
   new clothes colours and a new natural background. Pad to 2 s if shorter. Save as S(1)a__hf.mp4.
   Don't touch S(1)b, S(1)c, S(1)d.
2. CapCut project "S1_newhook": S(1)a__hf (trimmed to the original S(1)a length) -> S(1)b -> S(1)c -> S(1)d,
   the clips' own original audio (original S(1)a audio for the first clip), and a NEW hook text
   (size 13, 2 lines, whole video). Run check_capcut_text.py until TEXT CHECK OK.
Give me only: project name, new hook, character used, credits used.
```
> Only changing clothes colours is usually not enough for the platform (or viewers) to see it as a
> new video - change the person, the background and the hook text.

### Continue later
```
claude --continue      # reopens the last chat in this folder
claude --resume        # pick an older chat
```
A new chat also works - everything is saved in files (`CLAUDE.md`, `jobs/<job>/`).

### While it's rendering
Claude can't wake itself up. If it says renders are still running and goes quiet, wait 3-5 minutes and type:
```
continue
```

---

## 8. Finishing on your iPhone
The PC can't draw Apple emojis, so emojis are added on the phone:

1. Open CapCut on the PC, check the project (text, audio, cuts).
2. Upload it to **Space**.
3. On the iPhone, open CapCut -> Space -> the project. Paste the text from `videos/<name>__HOOK.txt`
   (it has the emojis), export, post.

**The PC and the iPhone must be logged into the SAME CapCut account.** Switching accounts is the #1
reason a project doesn't show up or won't open. Plan B that always works: send
`videos/<name>__CLEAN.mp4` to the phone (AirDrop, Google Drive, Telegram) and add the text in a new
CapCut project there.

---

## 9. Folder map

| Folder / file | What it is | You touch it? |
|---|---|---|
| `input/` | Source videos for `/make-video` | **Yes** |
| `references/product/` | 3-5 photos of your product | **Yes**, once |
| `references/characters/` | Photos of people, named by gender/age | **Yes** |
| `music/` | Songs for `/mix-videos` | **Yes** |
| `notes/product.md` | Your product description | **Yes**, once |
| `notes/higgsfield_prompt_style.md` | The prompt method | Optional |
| `clips/hooks`, `clips/showcases`, `clips/payoffs` | Cut clips + remakes (`__hf.mp4`) | Look |
| `videos/` | `__CLEAN.mp4`, preview `.mp4`, `__HOOK.txt` | Look |
| `jobs/` | The agent's working files per video | No |
| `agent/` | Scripts + `config.json` | No |
| `CLAUDE.md` | The agent's instructions | No |
| `.claude/commands/` | `/make-video` and `/mix-videos` | No |

Your media, photos and keys are in `.gitignore` - they never get uploaded to GitHub.

### The scripts (the agent runs these, you don't have to)
| Script | Does |
|---|---|
| `agent/split.py` | Cuts a video at scene changes, makes contact sheets, extracts the original audio (AAC 44.1 kHz stereo) |
| `agent/organize.py` | Labels clips and copies them into hooks / showcases / payoffs |
| `agent/pad.py` | Pads clips under 2 s (freezes the last frame) for Wan 3.0 |
| `agent/higgsfield.py` | `collect` puts downloaded remakes in place; `status`; `manual` (website route); API route optional |
| `agent/assemble.py` | Exports `__CLEAN.mp4`, a preview with text, and `__HOOK.txt` |
| `agent/check_capcut_text.py` | Verifies (and with `--fix` repairs) the text in a CapCut project |

---

## 10. Costs and timing
Measured on real jobs:

| | |
|---|---|
| One Wan 3.0 clip, 2 s, 720p | ~3.5 credits |
| A 9-clip video incl. 2 retries | 38.5 credits |
| Render time | ~3-5 min; clips render in parallel (Higgsfield rate-limits big batches - the agent resubmits) |
| Whole video, start to CapCut project | ~20-25 min, mostly waiting for renders |

Higgsfield prices change - the agent reads your balance before and after and reports the real cost.
The website's generate button shows prices for its own settings (e.g. 4 s at 1080p costs far more) -
don't compare those with the agent's 2 s / 720p clips.

---

## 11. Rules the agent follows
Learned the hard way - they're all in `CLAUDE.md`:

- **Wan 3.0 only** in Higgsfield.
- **Only people, clothes colours and backgrounds change** - the product, movements, camera and timing stay identical.
- **Never moves or renames files in `clips/`** - CapCut projects point to exact paths (moving = "Media lost").
- **CapCut closed while it writes** - an open CapCut overwrites the agent's changes.
- **Never uses `capcut_raw_patch`.**
- **Text:** size 13, real line break, max 20 characters per line, whole video - verified by `check_capcut_text.py`.
- **Doesn't remove logos/items or retry because of them** - retries only for a broken product, face or hands, max 2.
- **Asks before spending credits** unless you say `auto`.

---

## 12. Troubleshooting

| Problem | Fix |
|---|---|
| `'$c' is not recognized` / `'Get-ChildItem' is not recognized` | You're in CMD, not PowerShell. Type `powershell`, then paste only the command (not the old prompt/errors). |
| `'ffmpeg' is not recognized` | Install FFmpeg (section 3/4) and open a **new** terminal. |
| `claude mcp list` doesn't show higgsfield/capcut | Redo section 6 from inside the agent folder. |
| Project doesn't appear in CapCut | Quit CapCut **completely** (tray icon / Cmd+Q) and reopen. Use the search icon above Projects. |
| CapCut shows **"Media lost"** | Clip files were moved. Click **Link media** and select the folder where they are now, or copy them back to where they were. |
| Text too big / one line / only on the first clip | Ask the agent to run `python agent/check_capcut_text.py "<project folder>" --fix`, or fix it in CapCut (size 13, Enter after a few words, drag the text bar to the end). |
| Agent's changes "disappeared" | CapCut was open and overwrote them. Close CapCut, ask the agent to redo, reopen after `TEXT CHECK OK`. |
| Hear double audio | Mute the video track in CapCut (speaker icon on the track). |
| Project won't open / doesn't show on iPhone | Same CapCut account on PC and iPhone; update both apps; Space full -> delete old projects and empty the Space trash; or use `__CLEAN.mp4` (section 8). |
| Higgsfield "rate limit" | Normal for big batches - type `continue` in a few minutes. |
| Higgsfield "Protected content" | A known character/brand is in the clip - ask the agent to cover that area and describe a plain version. |
| Agent stopped and is quiet | It's waiting for renders or for you - type `continue`. |
| Agent asks too many questions | Add `auto` and "don't ask me anything" to your request (section 7). |
| `externally-managed-environment` (Mac pip) | Add `--break-system-packages` to the pip command. |

---

## 13. FAQ

**Can it download viral videos from Instagram for me?**
It can find the top Reels on a page (via Claude in Chrome) and list them by views, but downloading
other people's Reels breaks Instagram's terms and can get your account flagged. Save the videos
yourself and drop them into `input/`.

**Is remaking competitors' videos allowed?**
Common in dropshipping, but the original creator can still report a near-copy. The more you change
(people, background, clip order, hook text, music), the lower the risk.

**Why are emojis added on the iPhone?**
Windows/Mac can't render Apple emojis into the video. The agent saves the hook with emojis in
`__HOOK.txt` so you can paste it in CapCut on the iPhone.

**Can I use the Higgsfield API instead of the MCP?**
Yes - see `agent/config.json` and `python agent/higgsfield.py check`. The API is billed separately
from the website plan; the MCP uses your plan credits and is the default.

**How does my friend use it with a different product?**
Same repo, different `notes/product.md`, `references/product/` and `references/characters/` - nothing else changes.
