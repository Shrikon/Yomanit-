@echo off
cd /d C:\yomanit
:loop
python auto_runner.py
timeout /t 5
goto loop
```

**שלב 2 — התקיני NSSM:**
הורידי מ: `https://nssm.cc/download` → חלצי → שמי `nssm.exe` ב-`C:\Windows\System32`

**שלב 3 — הריצי CMD כ-Administrator:**
```
nssm install YomanitWatcher C:\yomanit\run_watcher.bat
nssm set YomanitWatcher AppDirectory C:\yomanit
nssm start YomanitWatcher