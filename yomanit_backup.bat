@echo off
set PGPASSWORD=secret
set BACKUP_DIR=C:\yomanit\backups
set DB_NAME=yomanit
set DB_USER=yomanit
set PG_DUMP="C:\Program Files\PostgreSQL\18\bin\pg_dump.exe"
set YYYY=%DATE:~10,4%
set MM=%DATE:~7,2%
set DD=%DATE:~4,2%
set TODAY=%YYYY%-%MM%-%DD%
if not exist %BACKUP_DIR% mkdir %BACKUP_DIR%
set BACKUP_FILE=%BACKUP_DIR%\%DB_NAME%_%TODAY%.backup
echo Starting backup: %BACKUP_FILE%
%PG_DUMP% -U %DB_USER% -h localhost -p 5432 -F c -b -f "%BACKUP_FILE%" %DB_NAME%
if %ERRORLEVEL% == 0 (echo Backup OK: %BACKUP_FILE%) else (echo ERROR)
forfiles /p %BACKUP_DIR% /m *.backup /d -14 /c "cmd /c del @path" 2>nul
for %%A in ("%BACKUP_FILE%") do echo Size: %%~zA bytes