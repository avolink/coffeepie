@echo off
REM Docker deployment helper script for CoffeePie (Windows)

setlocal enabledelayedexpansion

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"

REM Colors simulation for Windows (using labels instead)
set "GREEN=[OK]"
set "RED=[ERROR]"
set "YELLOW=[INFO]"
set "BLUE=[===]"

echo %BLUE% CoffeePie Docker Deployment %BLUE%
echo.

REM Check if Docker is installed
where docker >nul 2>nul
if %errorlevel% neq 0 (
    echo %RED% Docker is not installed or not in PATH
    echo %YELLOW% Please install Docker Desktop for Windows
    exit /b 1
)
echo %GREEN% Docker found

where docker-compose >nul 2>nul
if %errorlevel% neq 0 (
    echo %RED% Docker Compose is not installed or not in PATH
    exit /b 1
)
echo %GREEN% Docker Compose found

echo.

if "%1"=="" goto :show_menu
if "%1"=="build" goto :build_image
if "%1"=="run" goto :run_application
if "%1"=="headless" goto :run_headless
if "%1"=="stop" goto :stop_application
if "%1"=="logs" goto :show_logs
if "%1"=="help" goto :show_help
echo %RED% Unknown command: %1
goto :show_help

:show_menu
echo Select an option:
echo 1 - Build Docker image
echo 2 - Run application with docker-compose
echo 3 - Run application headless
echo 4 - Stop application
echo 5 - Show logs
echo 6 - Exit
echo.
set /p choice="Enter your choice [1-6]: "

if "%choice%"=="1" goto :build_image
if "%choice%"=="2" goto :run_application
if "%choice%"=="3" goto :run_headless
if "%choice%"=="4" goto :stop_application
if "%choice%"=="5" goto :show_logs
if "%choice%"=="6" goto :exit_script

echo %RED% Invalid choice
goto :show_menu

:build_image
echo %BLUE% Building Docker image...
cd /d "%SCRIPT_DIR%"
docker-compose build
if %errorlevel% neq 0 (
    echo %RED% Failed to build Docker image
    exit /b 1
)
echo %GREEN% Docker image built successfully
if "%1"=="" (
    goto :show_menu
) else (
    exit /b 0
)

:run_application
echo %BLUE% Starting CoffeePie application...
echo %YELLOW% Note: Display forwarding may not work well on Windows
echo %YELLOW% Consider using WSL2 with a display server or run headless
cd /d "%SCRIPT_DIR%"
docker-compose up
if "%1"=="" goto :show_menu

:run_headless
echo %BLUE% Starting CoffeePie in headless mode...
cd /d "%SCRIPT_DIR%"
docker run -it --rm ^
    --env QT_QPA_PLATFORM=offscreen ^
    coffeepie:latest
if "%1"=="" goto :show_menu

:stop_application
echo %BLUE% Stopping CoffeePie...
cd /d "%SCRIPT_DIR%"
docker-compose down
echo %GREEN% Application stopped
if "%1"=="" (
    goto :show_menu
) else (
    exit /b 0
)

:show_logs
echo %BLUE% Showing application logs...
cd /d "%SCRIPT_DIR%"
docker-compose logs -f coffeepie
if "%1"=="" goto :show_menu

:show_help
echo.
echo Usage: %0 [command]
echo.
echo Commands:
echo   build      Build Docker image
echo   run        Run application with docker-compose
echo   headless   Run application in headless mode
echo   stop       Stop running application
echo   logs       Show application logs
echo   help       Show this help message
echo.
echo If no command is specified, an interactive menu will be shown.
echo.
exit /b 0

:exit_script
echo %YELLOW% Exiting
exit /b 0
