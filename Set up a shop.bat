@echo off
title Sonos shop setup
cd /d "%~dp0"
color 0F

echo.
echo  ====================================================================
echo    SONOS SHOP SETUP
echo  ====================================================================
echo.
echo    Which one are you setting up?
echo.
echo      1   West Harlem, 3600 Broadway
echo      2   Central Harlem, 370 Malcolm X
echo      3   Central Harlem, the single speaker on its own system
echo      4   Hell's Kitchen, 354 W 44th
echo      5   Home, as a rehearsal
echo.

set "SHOP="
set /p PICK=   Type a number and press Enter:
if "%PICK%"=="1" set "SHOP=west-harlem"
if "%PICK%"=="2" set "SHOP=central-harlem"
if "%PICK%"=="3" set "SHOP=central-harlem-b"
if "%PICK%"=="4" set "SHOP=hells-kitchen"
if "%PICK%"=="5" set "SHOP=home"

if not defined SHOP (
  echo.
  echo    That was not one of the numbers. Close this window and start again.
  echo.
  pause
  exit /b 1
)

echo.
echo    Do the whole setup, or just look?
echo.
echo      1   Do the setup, step by step
echo      2   Just look and change nothing
echo.

set "FLAG="
set /p MODE=   Type a number and press Enter:
if "%MODE%"=="2" set "FLAG=--check"

rem Find Python, whichever way it is installed on this machine.
set "PY="
py -3 -V >nul 2>&1 && set "PY=py -3"
if defined PY goto gotpython
python -V >nul 2>&1 && set "PY=python"
:gotpython

if not defined PY (
  echo.
  echo    PYTHON IS NOT INSTALLED ON THIS COMPUTER, or Windows cannot find it.
  echo.
  echo    Get it from  https://www.python.org/downloads/
  echo    On the first screen of the installer, tick the box at the bottom that
  echo    says "Add python.exe to PATH" before clicking Install. Then close this
  echo    window and double click this file again.
  echo.
  pause
  exit /b 1
)

echo.
echo  ====================================================================
echo.
%PY% instore.py %SHOP% %FLAG%
set "RESULT=%ERRORLEVEL%"

echo.
echo  ====================================================================
if "%RESULT%"=="0" echo    FINISHED. Nothing here needs you any more.
if "%RESULT%"=="2" echo    NOT FINISHED. Read the list above before you leave.
if "%RESULT%"=="1" echo    IT COULD NOT START. The reason is printed above.
echo  ====================================================================
echo.
echo    This window stays open so you can read it. Close it when you are done.
echo.
pause
