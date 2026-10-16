"""Bug (2026-10-16 07:30): local_refresh.ps1 stopped mid-rebase when a local commit and
CI's daily data commit both changed Gold Data/, leaving the working tree stripped.

Derived data (Gold Data/, Models/) is rebuilt by the daily agent on every run, so a
conflict there must resolve to CI's copy and the sync must finish. A conflict anywhere
else must abort the rebase cleanly: exit 1, tree and HEAD exactly as before.

Runs the real script with -SyncOnly (sync step only, no agent, no push) in throwaway
repos.
"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "Automation" / "local_refresh.ps1"

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="PowerShell refresh script")


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def repos(tmp_path):
    """origin (bare) <- ci clone pushes a data commit; local clone has its own commits."""
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "--bare", "-b", "master", str(origin))
    seed = tmp_path / "seed"
    git(tmp_path, "clone", str(origin), str(seed))
    for r in (seed,):
        git(r, "config", "user.email", "t@example.com"); git(r, "config", "user.name", "t")
    write(seed / "Gold Data" / "gold.csv", "date,v\n1,1\n")
    write(seed / "Automation" / "code.py", "x = 1\n")
    write(seed / "Automation" / "local_refresh.ps1", SCRIPT.read_text(encoding="utf-8"))
    git(seed, "add", "-A"); git(seed, "commit", "-m", "seed"); git(seed, "push", "origin", "master")

    ci = tmp_path / "ci"; local = tmp_path / "local"
    for r in (ci, local):
        git(tmp_path, "clone", str(origin), str(r))
        git(r, "config", "user.email", "t@example.com"); git(r, "config", "user.name", "t")
    return origin, ci, local


def run_sync(local: Path):
    return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                           str(local / "Automation" / "local_refresh.ps1"), "-SyncOnly"],
                          cwd=local, capture_output=True, text=True, timeout=120)


def mid_rebase(repo: Path) -> bool:
    g = repo / ".git"
    return (g / "rebase-merge").exists() or (g / "rebase-apply").exists()


def test_gold_conflict_takes_ci_copy_and_finishes(repos):
    origin, ci, local = repos
    write(ci / "Gold Data" / "gold.csv", "date,v\n1,CI\n")
    git(ci, "commit", "-am", "data: daily refresh"); git(ci, "push", "origin", "master")
    write(local / "Gold Data" / "gold.csv", "date,v\n1,LOCAL\n")
    write(local / "Automation" / "code.py", "x = 2\n")
    git(local, "commit", "-am", "feature: code and rebuilt gold")

    r = run_sync(local)
    assert r.returncode == 0, r.stdout + r.stderr
    assert not mid_rebase(local)
    assert (local / "Gold Data" / "gold.csv").read_text(encoding="utf-8") == "date,v\n1,CI\n"
    assert (local / "Automation" / "code.py").read_text(encoding="utf-8") == "x = 2\n"   # local work kept
    assert git(local, "merge-base", "--is-ancestor", "origin/master", "HEAD") == ""      # on top of CI


def test_other_conflict_aborts_cleanly(repos):
    origin, ci, local = repos
    write(ci / "Automation" / "code.py", "x = 'ci'\n")
    git(ci, "commit", "-am", "ci edits code"); git(ci, "push", "origin", "master")
    write(local / "Automation" / "code.py", "x = 'local'\n")
    git(local, "commit", "-am", "local edits code")
    head = git(local, "rev-parse", "HEAD")

    r = run_sync(local)
    assert r.returncode == 1
    assert not mid_rebase(local)
    assert git(local, "rev-parse", "HEAD") == head
    assert (local / "Automation" / "code.py").read_text(encoding="utf-8") == "x = 'local'\n"
