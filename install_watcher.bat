@echo off
:: התקנת YomanitWatcher כ-Scheduled Task (ללא NSSM)
:: הרץ כ-Administrator

echo מתקין YomanitWatcher...

:: מחק task קיים אם יש
schtasks /delete /tn "YomanitWatcher" /f 2>nul

:: צור task חדש שמתחיל עם Windows ורץ תמיד
schtasks /create /tn "YomanitWatcher" /tr "C:\yomanit\run_watcher.bat" /sc onlogon /ru "%USERNAME%" /rl highest /f

echo.
echo ✓ YomanitWatcher הותקן בהצלחה
echo הוא יתחיל אוטומטית בכל כניסה ל-Windows
echo.
echo להפעלה מיידית עכשיו:
start "" "C:\yomanit\run_watcher.bat"
echo ✓ הופעל
pause
