# התקנת NSSM + YomanitWatcher כ-Windows Service

## שלב 1 — הורדת NSSM

1. גשי לאתר: https://nssm.cc/download
2. הורידי את הגרסה העדכנית (nssm-2.24.zip או דומה)
3. חלצי את הקובץ
4. העתיקי את הקובץ `win64\nssm.exe` לתיקייה: `C:\Windows\System32\`

## שלב 2 — וודאי שהקובץ run_watcher.bat קיים

הקובץ `C:\yomanit\run_watcher.bat` אמור להכיל:

```bat
@echo off
cd /d C:\yomanit
:loop
python auto_runner.py
timeout /t 5
goto loop
```

אם לא קיים — צרי אותו עכשיו עם התוכן הנ"ל.

## שלב 3 — פתחי CMD כ-Administrator

1. לחצי על כפתור Start
2. הקלידי `cmd`
3. לחצי ימני על "Command Prompt"
4. בחרי "Run as administrator"

## שלב 4 — התקינו את השירות

הריצי את הפקודות הבאות בזו אחר זו:

```
nssm install YomanitWatcher C:\yomanit\run_watcher.bat
nssm set YomanitWatcher AppDirectory C:\yomanit
nssm set YomanitWatcher DisplayName "Yomanit Auto Runner"
nssm set YomanitWatcher Description "מאזין לשינויים ומבצע push ל-GitHub"
nssm set YomanitWatcher Start SERVICE_AUTO_START
nssm start YomanitWatcher
```

## שלב 5 — אימות

בדקי שהשירות רץ:
```
nssm status YomanitWatcher
```

אמור להופיע: `SERVICE_RUNNING`

אפשר גם לבדוק ב: `services.msc` — תחפשי `YomanitWatcher`

## פקודות שימושיות

| פקודה | תיאור |
|-------|-------|
| `nssm start YomanitWatcher` | הפעלה |
| `nssm stop YomanitWatcher` | עצירה |
| `nssm restart YomanitWatcher` | הפעלה מחדש |
| `nssm remove YomanitWatcher confirm` | הסרה |
| `nssm status YomanitWatcher` | בדיקת סטטוס |

## הערה

אחרי ההתקנה — השירות יתחיל אוטומטית עם כל הפעלת Windows.
אין צורך להריץ `python auto_runner.py` ידנית יותר.
