@echo off
title Music Bot
color 0A

echo ========================================
echo     MUSIC BOT FOR TELEGRAM
echo ========================================
echo.

:: Проверка Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found!
    pause
    exit
)

:: Установка зависимостей (один раз)
pip show aiogram >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
)

echo.
echo Starting bot...

python main.py

echo.
echo Bot stopped or crashed
pause