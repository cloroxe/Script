@echo off
rem UEFN Vibe Starter - installation SANS exe (Python requis). Double-clic pour lancer.
setlocal
chcp 65001 >nul
cd /d "%~dp0.."

call :findpython || goto :nopython

echo [1/3] Creation de l'environnement Python (.venv)...
%PY% -m venv .venv || goto :fail
echo [2/3] Installation de UEFN Vibe Starter...
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
".venv\Scripts\python.exe" -m pip install . || goto :fail
echo [3/3] Configuration de ton projet UEFN...
".venv\Scripts\python.exe" -m uefn_vibe.setup_project
goto :end

:findpython
set "PY=py -3"
%PY% --version >nul 2>nul && exit /b 0
set "PY=python"
%PY% --version >nul 2>nul && exit /b 0
exit /b 1

:nopython
echo.
echo Python 3.10 ou plus recent est introuvable.
echo Installe-le depuis https://www.python.org/downloads/ en COCHANT "Add python.exe to PATH", puis relance.
goto :end

:fail
echo.
echo Une etape a echoue. Lis le message juste au-dessus.

:end
if not defined CI pause
endlocal
