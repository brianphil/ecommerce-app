@echo off
title Complete Database Reset
color 0E

echo.
echo  ╔═══════════════════════════════════════════════╗
echo  ║    Complete Database Reset                    ║
echo  ║    Fixes Django migration inconsistency       ║
echo  ╚═══════════════════════════════════════════════╝
echo.

echo ⚠️  This will completely reset the database and all migrations
echo    This fixes the InconsistentMigrationHistory error
echo.
set /p confirm="Type YES to completely reset: "

if /i not "%confirm%"=="YES" (
    echo Cancelled.
    pause
    exit /b 0
)

echo.
echo 🐍 Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo 🗑️  Step 1: Removing ALL migration files and database...

:: Delete SQLite database
if exist db.sqlite3 (
    del db.sqlite3
    echo ✅ Deleted database file
)

:: Remove ALL migration files from all apps (but keep __init__.py)
echo.
echo 🧹 Cleaning migration directories...

for %%d in (authentication products orders core notifications) do (
    if exist "apps\%%d\migrations" (
        echo Cleaning apps\%%d\migrations...
        for %%f in ("apps\%%d\migrations\*.py") do (
            if not "%%~nf"=="__init__" (
                del "%%f" 2>nul
                echo   Deleted %%f
            )
        )
    ) else (
        mkdir "apps\%%d\migrations" 2>nul
        echo # Django migrations > "apps\%%d\migrations\__init__.py"
        echo   Created apps\%%d\migrations directory
    )
)

echo.
echo 🔧 Step 2: Creating fresh migrations in correct order...

:: Create authentication migrations first (custom user model)
echo Creating authentication migrations...
python manage.py makemigrations authentication
if %errorlevel% neq 0 (
    echo ❌ Failed to create authentication migrations
    pause
    exit /b 1
)

:: Create other app migrations
echo Creating products migrations...
python manage.py makemigrations products

echo Creating orders migrations...
python manage.py makemigrations orders

echo Creating core migrations...
python manage.py makemigrations core

echo Creating notifications migrations...
python manage.py makemigrations notifications

echo.
echo 🗃️  Step 3: Running migrations...
python manage.py migrate
if %errorlevel% neq 0 (
    echo ❌ Migration failed
    pause
    exit /b 1
)

echo.
echo ✅ Database reset complete!
echo.
echo 📋 Next steps:
echo    1. Create superuser: python manage.py createsuperuser
echo    2. Add sample data: python manage.py create_sample_data
echo    3. Start server: python manage.py runserver
echo.
echo 🌐 Then access:
echo    • API Docs: http://127.0.0.1:8000/swagger/
echo    • Admin: http://127.0.0.1:8000/admin/
echo.
pause