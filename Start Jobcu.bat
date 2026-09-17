@echo off
rem Double-click this file to start Jobcu on Windows.
rem Keep the window that opens while you use Jobcu. Close it to stop Jobcu.
setlocal
title Jobcu
cd /d "%~dp0"
set "PATH=%USERPROFILE%\.local\bin;%LOCALAPPDATA%\Microsoft\WinGet\Links;%PATH%"

if "%JOBCU_TEST_PRETEND_NO_UV%"=="1" goto no_uv
where uv >nul 2>nul
if errorlevel 1 goto no_uv
goto start

:no_uv
echo Jobcu needs a free helper program called "uv" to run. It downloads Python and the
echo other parts Jobcu needs. This happens only once and takes a few minutes.
echo.
if not "%JOBCU_SELFTEST%"=="1" (
  echo Press any key to install it now, or close this window to cancel.
  pause >nul
)
if "%JOBCU_TEST_SKIP_INSTALL%"=="1" goto install_skipped
rem The official installer from uv's makers (astral.sh). It installs into your user folder.
powershell -NoProfile -ExecutionPolicy ByPass -Command "$env:UV_NO_MODIFY_PATH=1; irm https://astral.sh/uv/install.ps1 | iex"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
where uv >nul 2>nul
if errorlevel 1 goto install_failed
goto start

:install_skipped
echo (Test: installation skipped.)
endlocal
exit /b 0

:install_failed
echo.
echo The helper couldn't be installed. Please check your internet connection and try again.
echo More help: docs\guides\troubleshooting.md in the Jobcu folder.
goto fail

:start
echo Preparing Jobcu. The first start can take a few minutes...
uv run --frozen --no-dev --quiet jobcu
if errorlevel 1 goto problem
endlocal
exit /b 0

:problem
echo.
echo Jobcu stopped because of a problem. See the messages above.
echo More help: docs\guides\troubleshooting.md in the Jobcu folder.

:fail
if not "%JOBCU_SELFTEST%"=="1" pause
endlocal
exit /b 1
