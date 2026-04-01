@echo off
cd /d C:\yomanit
:loop
python auto_runner.py
timeout /t 5
goto loop
