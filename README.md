# Agentic AI Editor

Claude as Paras's video editor: raw take in, cut + motion graphics + captions + score out, preview for review.
The working rules are in [`CLAUDE.md`](CLAUDE.md). The build plan for the agentic version (14 agents, style
library, review player, NLE bridges) is the **Agentic Editing Tool** artifact:
https://claude.ai/artifact/Ct4Tz6T4pCBCEaXaid5JAR

Renders run on the PC only. This repo holds code and docs; footage, renders, music and model weights stay off git
(see `.gitignore`).

## What is in this repo

| Path | What it is |
|------|------------|
| `CLAUDE.md` | The editor's operating rules, stack, workflow and lessons from shipped reels |
| `buildloop/` | The older BuildLoop bundle docs (`video-cut-aligned` + `video-edit` skills, DaVinci Resolve guide). CLAUDE.md prefers video-use over these. |
| `.claude/` | Safety hook from the AI OS: blocks destructive commands, secret printing and un-approved sends; denies reads of `.env` and keys |
| `.gitignore` | Keeps footage, renders, music, model weights and `.env` out of git |

## Add the code from the PC

The code lives in `C:\Users\PARAS ARORA\AI_Editor` (`tools\`, `templates\`, `fonts\`, …). Run these in PowerShell.

**1. Clone this repo (once)**

```powershell
cd "C:\Users\PARAS ARORA\Developer"
git clone https://github.com/Parascoder3008/agentic_ai_editor.git
cd agentic_ai_editor
```

**2. Copy the code in, without footage or caches**

```powershell
robocopy "C:\Users\PARAS ARORA\AI_Editor" . /E `
  /XD inbox node_modules .venv __pycache__ .cache .git models frames `
  /XF *.mp4 *.mov *.mkv *.webm *.wav *.mp3 *.npz .env
```

Use `/E`, never `/MIR`: `/MIR` deletes files in this folder that are not in the source, including `.git`.

**3. Save the video-use patches** (the local fixes listed in CLAUDE.md)

```powershell
mkdir patches
git -C "C:\Users\PARAS ARORA\Developer\video-use" diff --output="$PWD\patches\video-use.patch"
```

**4. Check before committing**

```powershell
git status
Get-ChildItem -Recurse -File | Where-Object { $_.Length -gt 50MB -and $_.FullName -notmatch '\\\.git\\' } |
  Select-Object FullName, Length
```

The second command should print nothing. GitHub rejects files over 100 MB. If `git status` shows `README.md` or
`.gitignore` as modified, the copy overwrote them; restore them with `git checkout -- README.md .gitignore`.

**5. Commit and push**

```powershell
git add .
git commit -m "Add AI Editor tools"
git push origin main
```

The first push opens a GitHub sign-in window. If git asks who you are, set it once:
`git config --global user.name "Paras Arora"` and `git config --global user.email "<your GitHub email>"`.

After this, keep editing in this folder (or keep copying from `AI_Editor` with step 2) and push with step 5.
