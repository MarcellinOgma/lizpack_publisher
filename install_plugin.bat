@echo off
:: ============================================================
:: install_plugin.bat
::
:: Fabrique les deux paquets — production et accept — et les
:: installe cote a cote dans un profil QGIS.
::
::   install_plugin.bat              profil Formations
::   install_plugin.bat default      autre profil
::
:: Tout le travail est fait par generer_paquets.py : ce fichier
:: ne sert qu'a le lancer d'un double-clic, avec un Python valide.
:: ============================================================

setlocal enabledelayedexpansion

set PROFIL=%~1
if "%PROFIL%"=="" set PROFIL=Formations

set SCRIPT=%~dp0generer_paquets.py

echo.
echo === LIZPACK Publisher — Installation (profil %PROFIL%) ===
echo.

if not exist "%SCRIPT%" (
    echo ERREUR : generer_paquets.py est introuvable a cote de ce fichier.
    pause
    exit /b 1
)

:: Chercher un Python. Celui de QGIS d'abord — c'est le seul dont on
:: soit sur qu'il existe sur un poste ou QGIS est installe.
set PY=
for %%P in (
    "C:\OSGeo4W\apps\Python312\python3.exe"
    "C:\OSGeo4W\apps\Python311\python3.exe"
    "C:\OSGeo4W\bin\python3.exe"
    "C:\Program Files\QGIS 3.44.8\apps\Python312\python3.exe"
    "C:\Program Files\QGIS 3.38\apps\Python312\python3.exe"
    "C:\Program Files\QGIS 3.36\apps\Python312\python3.exe"
    "C:\Program Files\QGIS 3.34\apps\Python312\python3.exe"
) do (
    if not defined PY if exist %%P set PY=%%P
)

:: A defaut, le Python du PATH.
if not defined PY (
    where python >nul 2>&1 && set PY=python
)

if not defined PY (
    echo ERREUR : aucun Python trouve.
    echo Ouvrez l'invite OSGeo4W livree avec QGIS, puis lancez :
    echo     python "%SCRIPT%" --installer --profil %PROFIL%
    pause
    exit /b 1
)

echo Python : %PY%
echo.

%PY% "%SCRIPT%" --installer --profil "%PROFIL%"
if errorlevel 1 (
    echo.
    echo === Installation INTERROMPUE ===
    echo Rien n'a ete installe. Le message ci-dessus dit pourquoi.
    pause
    exit /b 1
)

echo.
echo === Installation terminee ===
echo Dans QGIS : Extensions ^> Gerer les extensions, cochez
echo   - LizPack Publisher            (production)
echo   - LizPack Publisher (accept)   (recette)
echo Les deux cohabitent : menus, reglages et connexions sont separes.
echo.
pause
