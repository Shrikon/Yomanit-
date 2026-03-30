@echo off
cd C:\yomanit\backend
call venv\Scripts\activate
set PYTHONUTF8=1
uvicorn main:app --port 8000
