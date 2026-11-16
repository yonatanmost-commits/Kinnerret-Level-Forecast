"""Bug (2026-11-16): the daily retrain rewrites docs/olympics_results.json
(winner_retrained_at), but neither the morning refresh nor CI committed it, so the
deployed app (pages 7 and 8 read it) showed the retrain date as 2026-10-17 for a month.

Acceptance:
  * local_refresh.ps1 and the GitHub workflow both stage docs/olympics_results.json
    with the data they commit
  * the file counts as derived data: when CI and a local run both rewrite it, the
    refresh's rebase takes CI's copy and finishes, as it does for Gold Data/
"""
from pathlib import Path

from tests.test_local_refresh_sync import git, mid_rebase, repos, run_sync, write  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
OLYMPICS = "docs/olympics_results.json"


def _git_add_block(text: str) -> str:
    """The `git add` that stages the data commit: the one that names Gold Data."""
    for marker in ("'add', '--', 'Gold Data'", "git add -- \\"):
        i = text.find(marker)
        if i >= 0:
            return text[i:i + 300]
    raise AssertionError("no data-staging git add found")


def test_local_refresh_stages_olympics():
    text = (ROOT / "Automation" / "local_refresh.ps1").read_text(encoding="utf-8")
    assert OLYMPICS in _git_add_block(text)


def test_ci_workflow_stages_olympics():
    text = (ROOT / ".github" / "workflows" / "daily-data-refresh.yml").read_text(encoding="utf-8")
    assert OLYMPICS in _git_add_block(text)


def test_olympics_conflict_takes_ci_copy_and_finishes(repos):
    origin, ci, local = repos
    for r in (ci, local):
        git(r, "pull", "-q", "origin", "master")
    write(ci / OLYMPICS, '{"winner_retrained_at": "seed"}')
    git(ci, "add", "-A"); git(ci, "commit", "-m", "seed olympics"); git(ci, "push", "origin", "master")
    git(local, "pull", "-q", "origin", "master")

    write(ci / OLYMPICS, '{"winner_retrained_at": "CI"}')
    git(ci, "commit", "-am", "data: daily refresh"); git(ci, "push", "origin", "master")
    write(local / OLYMPICS, '{"winner_retrained_at": "LOCAL"}')
    git(local, "commit", "-am", "data: local refresh")

    r = run_sync(local)
    assert r.returncode == 0, r.stdout + r.stderr
    assert not mid_rebase(local)
    assert (local / OLYMPICS).read_text(encoding="utf-8") == '{"winner_retrained_at": "CI"}'
