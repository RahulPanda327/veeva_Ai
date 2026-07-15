"""Applies WARM_CACHE_TIME (from .env) to the Windows scheduled task that
runs scripts/warm_cache.py.

Windows Task Scheduler has no idea .env exists — it only runs whatever time
was baked into the task when it was created. This script is the bridge:
change WARM_CACHE_TIME in .env, then run this once, and the actual
OS-level schedule gets updated to match.

Safe to run repeatedly — re-registering an existing task just overwrites its
trigger time, it does not create duplicates.

Usage:
    python scripts/schedule_warm_cache.py
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings

TASK_NAME = "RepStream Cache Warm-Up"


def main():
    time_str = settings.WARM_CACHE_TIME  # "HH:MM", 24-hour
    python_exe = sys.executable
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    ps_script = f"""
$action = New-ScheduledTaskAction -Execute "{python_exe}" -Argument "scripts\\warm_cache.py" -WorkingDirectory "{backend_dir}"
$trigger = New-ScheduledTaskTrigger -Daily -At "{time_str}"
# Default task settings silently skip the run if the machine is on battery
# power, or if the exact trigger instant is missed (system busy, etc). Both
# would make the task look "scheduled" but never actually fire — disable both.
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName "{TASK_NAME}" -Action $action -Trigger $trigger -Settings $settings -Description "Pre-warms RepStream AI caches before business hours" -Force
"""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_script],
        capture_output=True, text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit(1)

    print(f"'{TASK_NAME}' scheduled to run daily at {time_str} (from WARM_CACHE_TIME in .env).")


if __name__ == "__main__":
    main()
