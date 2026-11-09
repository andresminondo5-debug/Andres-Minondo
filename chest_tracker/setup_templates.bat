@echo off
rem Step 1: take a screenshot of the scan region. Step 2: drag boxes over the chest notifications.
cd /d "%~dp0"
python chest_tracker.py snapshot templates\region.png
python chest_tracker.py select templates\region.png templates\chest_open.png
python chest_tracker.py select templates\region.png templates\chest_break.png
echo.
echo Templates saved. Test them with: python chest_tracker.py check templates\region.png
pause
