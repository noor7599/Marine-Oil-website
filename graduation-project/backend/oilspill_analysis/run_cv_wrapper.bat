@echo off
REM Batch script to run quick_inference.py in conda mados environment

setlocal enabledelayedexpansion

REM Activate conda environment
call conda activate mados

REM Run the Python command that was passed in
python -c %1

endlocal
