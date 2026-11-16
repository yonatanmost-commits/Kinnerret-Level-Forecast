# Moving this project to a new machine

Keep the same folder path as on the old machine: Claude's memory for this project is keyed to it.

## 1. Code: clone the clean history

The public history was rewritten on 2026-11-16. Clone from GitHub; do **not** restore
from a backup or bundle made before that date. If the morning refresh rebased onto an
old clone, it would push the removed files back.

```powershell
git clone https://github.com/yonatanmost-commits/Kinnerret-Level-Forecast.git "<same path as before>"
```

## 2. Working files: copy everything git does not hold

Raw Data/, the ignored parts of Silver Data/, Gold Data/ and Models/, Reports/, `.env`,
and the local-only material (docs/talk/, docs/paper/, docs/experiments/,
intent/kinneret-talk-deck/, the talk tests). Copy the old folder over the clone, leaving out `.git`:

```powershell
robocopy "<old folder>" "<new folder>" /E /XD .git /XF "~$*" /R:1 /W:1
git status   # expect at most docs/olympics_results.json modified
```

## 3. Software

- Python on PATH (3.14 on the old machine). Both scheduled scripts call bare `python`.
- `pip install -r requirements.txt -r Automation/requirements-pipeline.txt pytest`
- Git for Windows (the `.sh` helpers run under its bash), GitHub CLI.

## 4. Secrets (names only; copy the values from the old machine or your password manager)

| Where | What |
|---|---|
| `.env` (repo root, git-ignored) | `GEMINI_API_KEY`, used by the talk image tools |
| `~/.cdsapirc` (home folder, outside the repo) | Copernicus CDS key, used by `Automation/seas5_fetch.py` and `c3s_fetch.py` |
| Git Credential Manager | GitHub push access; the morning refresh pushes master |

## 5. Scheduled task: on ONE machine only

The refresh pushes master to GitHub, so two machines would race.

```powershell
# old machine
schtasks /change /tn "Kinneret daily refresh" /disable
# new machine, from the repo root
powershell -NoProfile -ExecutionPolicy Bypass -File tasks\register_tasks.ps1
```

`DailyAgent-Kinneret` is retired; do not recreate it. See docs/DEPLOYMENT.md.

## 6. Smoke test (about 20 s)

```powershell
python -m pytest tests/test_daily_agent.py tests/test_kinneret_level.py tests/test_jordan_flow.py tests/test_local_refresh_sync.py tests/test_07b_keeps_cache.py tests/test_task_declaration.py tests/test_refresh_commits_olympics.py -q
```

After the first morning run, check:
- `Reports/local_refresh_<date>.log` ends with `=== local refresh finished cleanly ===`
- origin/master has a new `data: local refresh <date>` commit
- the last date in `Silver Data/Kinneret Level/kinneret_level.csv` is about yesterday
