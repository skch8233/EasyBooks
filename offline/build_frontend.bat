@echo off
REM Builds the React UI for the offline app into frontend\build
cd /d %~dp0\..\..\frontend
set REACT_APP_BACKEND_URL=http://127.0.0.1:8765
set REACT_APP_OFFLINE=1
REM Website used for "Activate online" (your live Easy Books site)
if "%REACT_APP_LICENCE_SERVER%"=="" set REACT_APP_LICENCE_SERVER=https://YOUR-EASYBOOKS-SITE
call yarn install
call yarn build
echo.
echo Done. Output: %cd%\build
