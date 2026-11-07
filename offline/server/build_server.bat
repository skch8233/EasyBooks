@echo off
REM Builds the Easy Books offline API server into server\dist\easybooks-server\
cd /d %~dp0
python -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements-offline.txt pyinstaller
pyinstaller --noconfirm --onedir --name easybooks-server --paths ..\..\backend --collect-all uvicorn --collect-submodules motor --collect-submodules pymongo --collect-submodules cryptography --copy-metadata razorpay --hidden-import bcrypt --hidden-import email_validator --hidden-import accounting --hidden-import auth --hidden-import billing --hidden-import business --hidden-import db --hidden-import emailer --hidden-import gst --hidden-import licensing --hidden-import public --hidden-import reminders --hidden-import routes_admin --hidden-import routes_ledgers --hidden-import routes_reports --hidden-import routes_vouchers --hidden-import shop --hidden-import stock --hidden-import server offline_server.py
echo.
echo Done. Output: %~dp0dist\easybooks-server\easybooks-server.exe
