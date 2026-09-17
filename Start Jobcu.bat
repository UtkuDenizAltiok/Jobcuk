@echo off
rem Double-click this file to start Jobcu on Windows.
rem Keep the window that opens while you use Jobcu. Close it to stop Jobcu.
setlocal
title Jobcu
cd /d "%~dp0"
set "PATH=%USERPROFILE%\.local\bin;%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"

where uv >nul 2>nul
if errorlevel 1 goto no_uv

echo Preparing Jobcu. The first start can take a minute...
uv run --frozen --no-dev --quiet jobcu
if errorlevel 1 goto problem
endlocal
exit /b 0

:no_uv
echo Jobcu can't start yet: a free helper tool called uv is missing.
echo Please follow the installation guide in Jobcu's docs folder.
goto fail

:problem
echo.
echo Jobcu stopped because of a problem. See the messages above.

:fail
if not "%JOBCU_SELFTEST%"=="1" pause
endlocal
exit /b 1
