@echo off
rem UEFN Vibe Starter - installation SANS exe (Python requis). Double-clic pour lancer.
setlocal
chcp 65001 >nul
cd /d "%~dp0.."

call :findpython || goto :nopython

echo [1/3] Creation de l'environnement Python (.venv)...
%PY% -m venv .venv || goto :fail
echo [2/3] Installation de UEFN Vibe Starter...
rem Priorite aux paquets embarques (dossier wheels) : aucun telechargement necessaire.
".venv\Scripts\python.exe" -m pip install --no-index --find-links "%CD%\wheels" uefn-vibe-starter --quiet
if not errorlevel 1 goto :installed
echo.
echo     Paquets locaux inutilisables avec cette version de Python : telechargement depuis Internet...
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
".venv\Scripts\python.exe" -m pip install . --retries 10 --timeout 60 || goto :fail
:installed
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
echo Si c'est une erreur reseau ^(IncompleteRead, timeout^) : coupe VPN/antivirus un instant, change de reseau
echo ^(partage de connexion du telephone^), ou installe Python 3.13 et relance. Le dossier wheels evite Internet.

:end
if not defined CI pause
endlocal
