@echo off
echo ========================================
echo FlowBridge GitHub Push Script
echo ========================================
echo.

REM Initialize git repository
echo [1/6] Initializing git repository...
git init
if %errorlevel% neq 0 (
    echo ERROR: Failed to initialize git repository
    pause
    exit /b 1
)

REM Add remote repository
echo [2/6] Adding remote repository...
git remote add origin https://github.com/afridpasha/Flow_Bridge_File_Transfer.git
if %errorlevel% neq 0 (
    echo Remote already exists, updating URL...
    git remote set-url origin https://github.com/afridpasha/Flow_Bridge_File_Transfer.git
)

REM Add all files
echo [3/6] Adding all files...
git add .
if %errorlevel% neq 0 (
    echo ERROR: Failed to add files
    pause
    exit /b 1
)

REM Commit changes
echo [4/6] Committing changes...
git commit -m "Initial commit: FlowBridge - Hybrid File Transfer System"
if %errorlevel% neq 0 (
    echo ERROR: Failed to commit changes
    pause
    exit /b 1
)

REM Rename branch to master
echo [5/6] Setting branch to master...
git branch -M master
if %errorlevel% neq 0 (
    echo ERROR: Failed to rename branch
    pause
    exit /b 1
)

REM Push to GitHub
echo [6/6] Pushing to GitHub master branch...
git push -u origin master --force
if %errorlevel% neq 0 (
    echo ERROR: Failed to push to GitHub
    echo.
    echo Please ensure:
    echo 1. You have configured git credentials (git config --global user.name "Your Name")
    echo 2. You have configured git email (git config --global user.email "your@email.com")
    echo 3. You have access to the repository
    echo 4. You may need to authenticate with GitHub
    pause
    exit /b 1
)

echo.
echo ========================================
echo SUCCESS! Code pushed to GitHub master branch
echo Repository: https://github.com/afridpasha/Flow_Bridge_File_Transfer
echo ========================================
pause
