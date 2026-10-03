@echo off
rem UEFN Vibe Starter - construit uefn-vibe-setup.exe et uefn-vibe-mcp.exe (dossier dist\).
rem Necessite Python 3.10+ sur cette machine Windows. Les EXE produits n'en ont plus besoin.
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

echo [1/4] Environnement de build...
%PY% -m venv .buildenv || goto :fail
call ".buildenv\Scripts\activate.bat" || goto :fail

rem Priorite aux paquets embarques (dossier wheels) : aucun telechargement necessaire.
python -m pip install --no-index --find-links "%WHEELS%" uefn-vibe-starter pyinstaller
if not errorlevel 1 goto :installed
echo.
echo     Installation hors-ligne impossible ^(voir l'erreur ci-dessus^) : tentative via Internet...
python -m pip install --upgrade pip --quiet
python -m pip install . pyinstaller --retries 10 --timeout 60 || goto :fail
:installed
echo     Paquets installes.

set "OPTS=--noconfirm --onefile --clean --collect-data uefn_vibe --add-data src\uefn_vibe\bridge\vibe_bridge.py;uefn_vibe\bridge"

echo [2/4] Construction de uefn-vibe-setup.exe...
pyinstaller %OPTS% --name uefn-vibe-setup packaging\launcher_setup.py || goto :fail
echo [3/4] Construction de uefn-vibe-mcp.exe...
pyinstaller %OPTS% --name uefn-vibe-mcp packaging\launcher_server.py || goto :fail

echo [4/4] Termine. Fichiers dans : %CD%\dist
dir /b dist\*.exe
echo.
echo Garde les DEUX exe dans le meme dossier, puis double-clique uefn-vibe-setup.exe.
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
