@echo off
echo ============================================================
echo Quiz Competition - Development Environment Startup
echo ============================================================
echo.

REM Check if PostgreSQL is running
echo [1/3] Checking PostgreSQL...
pg_isready >nul 2>&1
if errorlevel 1 (
    echo ERROR: PostgreSQL is not running!
    echo Please start PostgreSQL service and try again.
    pause
    exit /b 1
)
echo PostgreSQL is running.
echo.

REM Start backend in new window
echo [2/3] Starting backend server...
start "Quiz Competition Backend" cmd /k "cd backend && python run.py"
timeout /t 3 >nul
echo Backend starting at https://localhost:5000
echo.

REM Start add-in dev server in new window
echo [3/3] Starting add-in dev server...
start "Quiz Competition Add-in" cmd /k "cd addin\quiz competition && npm run dev-server"
timeout /t 3 >nul
echo Add-in starting at https://localhost:3000
echo.

echo ============================================================
echo Development environment started!
echo ============================================================
echo.
echo Backend:  https://localhost:5000
echo Add-in:   https://localhost:3000
echo.
echo To sideload the add-in:
echo   1. Open PowerPoint
echo   2. Insert ^> Get Add-ins ^> My Add-ins ^> Upload My Add-in
echo   3. Select: addin\quiz competition\manifest.xml
echo.
echo Or run: cd addin\quiz competition ^&^& npm start
echo.
echo Press any key to open PowerPoint...
pause >nul

REM Open PowerPoint
start powerpnt

echo.
echo Tip: Keep this window open to see status messages.
echo Close the backend and add-in windows to stop the servers.
echo.
pause
