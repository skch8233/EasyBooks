@echo off
REM Builds the React UI for the offline app into frontend\build
REM Website address comes from offline\settings.env (WEBSITE_URL)
for /f "usebackq eol=# tokens=1,* delims==" %%a in ("%~dp0settings.env") do set "%%a=%%b"
cd /d %~dp0\..\frontend
set REACT_APP_BACKEND_URL=http://127.0.0.1:8765
set REACT_APP_OFFLINE=1
set REACT_APP_LICENCE_SERVER=%WEBSITE_URL%
set GENERATE_SOURCEMAP=false
call yarn install
call yarn build
echo.
echo Done. Output: %cd%\build
