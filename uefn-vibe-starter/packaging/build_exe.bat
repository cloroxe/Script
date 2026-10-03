@echo off
rem UEFN Vibe Starter - construit uefn-vibe-setup.exe et uefn-vibe-mcp.exe (dossier dist\).
rem Necessite Python 3.10+ sur cette machine Windows. Les EXE produits n'en ont plus besoin.
setlocal
chcp 65001 >nul
cd /d "%~dp0.."

call :findpython || goto :nopython

echo [1/4] Environnement de build...
%PY% -m venv .buildenv || goto :fail
call ".buildenv\Scripts\activate.bat" || goto :fail
rem Priorite aux paquets embarques (dossier wheels) : aucun telechargement necessaire.
python -m pip install --no-index --find-links "%CD%\wheels" uefn-vibe-starter pyinstaller --quiet
if not errorlevel 1 goto :installed
echo.
echo     Paquets locaux inutilisables avec cette version de Python : telechargement depuis Internet...
python -m pip install --upgrade pip --quiet
python -m pip install . pyinstaller --retries 10 --timeout 60 || goto :fail
:installed

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
echo Si c'est une erreur reseau ^(IncompleteRead, timeout^) : coupe VPN/antivirus un instant, change de reseau
echo ^(partage de connexion du telephone^), ou installe Python 3.13 et relance. Le dossier wheels evite Internet.

:end
if not defined CI pause
endlocal
