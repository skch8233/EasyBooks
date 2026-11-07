@echo off
REM Builds the Easy Books offline API server into server\dist\easybooks-server\
cd /d %~dp0
python -m venv .venv
call .venv\Scripts\activate
pip install --upgrade pip
pip install -r ..\..\backend\requirements.txt
pip install pyinstaller
pyinstaller --noconfirm --onedir --name easybooks-server --paths ..\..\backend ^
  --collect-all uvicorn --collect-submodules motor --collect-submodules pymongo ^
  --collect-submodules cryptography --hidden-import bcrypt --hidden-import email_validator ^
  --hidden-import auth --hidden-import business --hidden-import licensing --hidden-import shop ^
  offline_server.py
echo.
echo Done. Output: %~dp0dist\easybooks-server\easybooks-server.exe
