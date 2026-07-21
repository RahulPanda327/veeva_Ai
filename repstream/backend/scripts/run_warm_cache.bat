@echo off
REM Double-click (or run) this file to manually trigger the cache warm-up
REM right now, instead of waiting for the scheduled 6 AM run.
REM Runs the exact same script the Windows scheduled task uses.

cd /d "%~dp0.."
echo Running warm_cache.py from %CD% ...
echo.

python scripts\warm_cache.py %*

echo.
echo Done. Full log also saved to .warm_cache.log
