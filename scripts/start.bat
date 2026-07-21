@echo off
setlocal
cd /d %~dp0\..
if not exist .venv py -3.12 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -e .
ashare-f10 serve --host 127.0.0.1 --port 8000
