@echo off
:: ============================================================
:: install_plugin.bat
:: Installe le plugin LIZPACK Publisher dans QGIS et installe
:: la dépendance paramiko si nécessaire.
:: ============================================================

setlocal

set PLUGIN_SRC=%~dp0lizpack_publisher
set QGIS_PLUGINS=%APPDATA%\QGIS\QGIS3\profiles\Formations\python\plugins
set DEST=%QGIS_PLUGINS%\lizpack_publisher

echo.
echo === LIZPACK Publisher — Installation ===
echo.

:: 1. Copier le plugin
echo [1/2] Copie du plugin vers %DEST%...
if not exist "%QGIS_PLUGINS%" mkdir "%QGIS_PLUGINS%"
if exist "%DEST%" rmdir /s /q "%DEST%"
xcopy /e /i /q "%PLUGIN_SRC%" "%DEST%"
if errorlevel 1 (
    echo ERREUR lors de la copie.
    pause
    exit /b 1
)
echo     OK

:: 2. Installer paramiko via pip QGIS
echo [2/2] Installation de paramiko...
set QGIS_PYTHON=""

:: Chercher python3 de QGIS dans les emplacements courants
for %%P in (
    "C:\Program Files\QGIS 3.38\apps\Python312\python3.exe"
    "C:\Program Files\QGIS 3.36\apps\Python312\python3.exe"
    "C:\Program Files\QGIS 3.34\apps\Python312\python3.exe"
    "C:\OSGeo4W\apps\Python312\python3.exe"
    "C:\OSGeo4W\apps\Python311\python3.exe"
    "C:\OSGeo4W\bin\python3.exe"
) do (
    if exist %%P (
        set QGIS_PYTHON=%%P
        goto :found_python
    )
)

:found_python
if %QGIS_PYTHON%=="" (
    echo     ATTENTION : Python QGIS non trouvé automatiquement.
    echo     Installez paramiko manuellement depuis la console Python QGIS :
    echo.
    echo         import subprocess, sys
    echo         subprocess.run([sys.executable, '-m', 'pip', 'install', 'paramiko'])
    echo.
) else (
    echo     Python QGIS trouvé : %QGIS_PYTHON%
    %QGIS_PYTHON% -m pip install --quiet paramiko
    if errorlevel 1 (
        echo     ATTENTION : échec installation paramiko. Faites-le manuellement.
    ) else (
        echo     paramiko installé avec succès.
    )
)

echo.
echo === Installation terminée ===
echo Redémarrez QGIS et activez le plugin via Extensions ^> Gérer les extensions.
echo.
pause
