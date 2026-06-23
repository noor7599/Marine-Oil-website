@echo off
REM Windows Batch Runner for Hybrid Oil Spill Pipeline
REM Usage: RUN_PIPELINE.bat <image_path> [--no-cv] [--no-trajectory] [--no-nlp]
REM Example: RUN_PIPELINE.bat data\raw\image.tiff

if "%1"=="" (
    echo Usage: RUN_PIPELINE.bat ^<image_path^> [OPTIONS]
    echo.
    echo Options:
    echo   --no-cv          Skip CV model, use threshold detector
    echo   --no-trajectory  Skip trajectory simulation
    echo   --no-nlp         Skip NLP validation
    echo.
    exit /b 1
)

setlocal enabledelayedexpansion

REM Get script directory
set SCRIPT_DIR=%~dp0

REM Setup conda
call conda activate oilspill3

if errorlevel 1 (
    echo ERROR: Failed to activate oilspill3 environment
    echo Make sure you created the environment: conda create -n oilspill3 python=3.9
    exit /b 1
)

REM Run pipeline
python "%SCRIPT_DIR%src\main\main_pipeline.py" --image "%1" %2 %3 %4

if errorlevel 1 (
    echo Pipeline FAILED
    exit /b 1
) else (
    echo Pipeline COMPLETED SUCCESSFULLY
    exit /b 0
)
