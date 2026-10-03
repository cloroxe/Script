@echo off
rem UEFN Vibe Starter - installation SANS exe (Python requis). Double-clic pour lancer.
setlocal
chcp 65001 >nul
cd /d "%~dp0.."

set "PY="
py -3 --version >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if defined PY goto :pyfound
python --version >nul 2>nul
if not errorlevel 1 set "PY=python"
:pyfound
if not defined PY goto :nopython
echo Python utilise :
%PY% --version
%PY% -c "import struct,sys; print('  64 bits :', struct.calcsize('P')*8==64, '| version', sys.version_info[0:3])"
set "WHEELS=%CD%\wheels"
if exist "%WHEELS%\*.whl" goto :haswheels
echo.
echo ATTENTION : le dossier "wheels" est introuvable ou vide : %WHEELS%
echo Tu utilises probablement un ancien ZIP. Extrais le NOUVEAU zip dans un dossier propre.
:haswheels

echo [1/3] Creation de l'environnement Python (.venv)...
%PY% -m venv .venv || goto :fail

echo [2/3] Installation de UEFN Vibe Starter...
rem Priorite aux paquets embarques (dossier wheels) : aucun telechargement necessaire.
".venv\Scripts\python.exe" -m pip install --no-index --find-links "%WHEELS%" uefn-vibe-starter
if not errorlevel 1 goto :installed
echo.
echo     Installation hors-ligne impossible ^(voir l'erreur ci-dessus^) : tentative via Internet...
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
".venv\Scripts\python.exe" -m pip install . --retries 10 --timeout 60 || goto :fail
:installed
echo     Paquets installes.

echo [3/3] Configuration de ton projet UEFN...
".venv\Scripts\python.exe" -m uefn_vibe.setup_project
goto :end

:nopython
echo.
echo Python 3.10 ou plus recent est introuvable.
echo Installe-le depuis https://www.python.org/downloads/ en COCHANT "Add python.exe to PATH", puis relance.
goto :end

:fail
echo.
echo Une etape a echoue. Lis le message juste au-dessus et envoie-le tel quel.
echo Si c'est une erreur reseau ^(IncompleteRead, timeout^) : verifie que le dossier wheels est bien present
echo ^(voir plus haut^), coupe VPN/antivirus un instant, ou change de reseau.

:end
if not defined CI pause
endlocal
