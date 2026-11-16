"""The morning refresh is declared in the repo (2026-11-16, machine migration).

Acceptance:
  * tasks/kinneret_daily_refresh.xml carries no user SID or user name (the repo is public)
  * tasks/register_tasks.ps1 -DryRun renders it for the repo it sits in: the action runs
    this repo's Automation/local_refresh.ps1 from the repo root, daily, and catches up
    when the laptop was off at the start time
"""
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "tasks"
NS = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}


def test_declared_xml_has_no_machine_identity():
    text = (TASKS / "kinneret_daily_refresh.xml").read_text(encoding="utf-8")
    assert "S-1-5-21" not in text
    assert "<UserId>" not in text
    assert "yonatanm" not in text.lower()


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell register script")
def test_dry_run_renders_task_for_this_repo():
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(TASKS / "register_tasks.ps1"), "-DryRun"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    task = ET.fromstring(r.stdout.strip())
    exe = task.find("t:Actions/t:Exec", NS)
    assert exe.find("t:Command", NS).text == "powershell.exe"
    assert str(ROOT / "Automation" / "local_refresh.ps1") in exe.find("t:Arguments", NS).text
    assert Path(exe.find("t:WorkingDirectory", NS).text) == ROOT
    assert task.find("t:Triggers/t:CalendarTrigger/t:ScheduleByDay/t:DaysInterval", NS).text == "1"
    assert task.find("t:Settings/t:StartWhenAvailable", NS).text == "true"
