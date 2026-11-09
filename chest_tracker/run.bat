@echo off
rem Start the chest tracker. It keeps watching the screen until you close this window.
cd /d "%~dp0"
python chest_tracker.py run
pause
