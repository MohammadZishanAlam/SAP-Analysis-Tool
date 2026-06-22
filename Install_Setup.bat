@echo off
REM Force the script to run in the folder where it is located
cd /d "%~dp0"

color 0A
echo ===================================================
echo    SAP Analysis Tool - Initial Setup Installer
echo ===================================================
echo.
echo Welcome! This will install the necessary background
echo components required to run the application.
echo.
echo Step 1: Checking for Python...
python --version
if %errorlevel% neq 0 (
    echo.
    color 0C
    echo ERROR: Python is not installed on this computer!
    echo Please install Python from the Software Center or python.org
    echo and ensure "Add Python to PATH" is checked.
    pause
    exit
)

echo.
echo Step 2: Preparing and installing libraries...
echo Please wait, this may take a minute or two.
echo.
python -m pip install --upgrade pip

REM Auto-generate the requirements file on the fly!
echo streamlit > install_list.txt
echo pandas >> install_list.txt
echo openpyxl >> install_list.txt
echo plotly >> install_list.txt
echo fpdf2 >> install_list.txt

REM Install the libraries
pip install -r install_list.txt

if %errorlevel% neq 0 (
    color 0C
    echo.
    echo ERROR: Something went wrong while installing the libraries.
    pause
    exit
)

del install_list.txt

echo.
echo Step 3: Creating Desktop Application Shortcut...
REM This block dynamically creates a shortcut with your custom logo on the user's desktop!
set SCRIPT="%TEMP%\CreateShortcut.vbs"
echo Set oWS = WScript.CreateObject("WScript.Shell") > %SCRIPT%
echo sLinkFile = "%USERPROFILE%\Desktop\SAP Analysis Tool.lnk" >> %SCRIPT%
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> %SCRIPT%
echo oLink.TargetPath = "%~dp02_Run_Application.bat" >> %SCRIPT%
echo oLink.WorkingDirectory = "%~dp0" >> %SCRIPT%
echo oLink.IconLocation = "%~dp0app_logo.ico" >> %SCRIPT%
echo oLink.Save >> %SCRIPT%
cscript /nologo %SCRIPT%
del %SCRIPT%

echo.
color 0A
echo ===================================================
echo SUCCESS! The software is installed and ready to use.
echo A shortcut has been placed on your desktop.
echo You can now close this window.
echo ===================================================
pause